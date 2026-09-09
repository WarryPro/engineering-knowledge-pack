"""Desired-state ConfigureService (internal / programmatic; no public CLI)."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, List, Optional, Sequence, Set

from ekp.assembly import AssemblyService, CompositionAssemblyRequest
from ekp.composition import PROJECT_COMPOSITION_PROFILE, ComponentRegistry
from ekp.config.models import (
    ProjectConfig,
    ProjectConfigError,
    ProjectConfigFileSnapshot,
)
from ekp.config.normalization import configuration_sha256
from ekp.config.project import (
    ProjectConfigStore,
    project_config_content_sha256,
    render_project_config_yaml,
)
from ekp.install.deploy.engine import SharedDeploymentEngine
from ekp.install.deploy.hashing import sha256_file
from ekp.install.deploy.models import DesiredManagedFile
from ekp.install.deploy.registry import DeployRegistry, build_default_deploy_registry
from ekp.install.errors import (
    EXIT_SUCCESS,
    InstallConflictError,
    InstallError,
    InstallFilesystemError,
    InstallSelectionError,
)
from ekp.install.intent import (
    build_composition_intent,
    intent_to_project_config,
)
from ekp.install.manifest import (
    INSTALL_MODE_COMPOSITION,
    InstallManifest,
    ManagedFile,
    ManifestSnapshot,
    ManifestStore,
)
from ekp.install.paths import (
    check_symlink_boundary,
    relative_posix_path,
    resolve_project_root,
    resolve_under_root,
)
from ekp.lifecycle.apply import (
    LifecycleConflictError,
    LifecycleRollbackError,
    TransactionApplier,
)
from ekp.lifecycle.boundaries import adapters_from_desired, lifecycle_symlink_check_paths
from ekp.lifecycle.file_ops import (
    classify_lifecycle_operation,
    directories_to_create_for_operations,
    noop_operation,
)
from ekp.lifecycle.plan import LifecycleFileOperation, LifecyclePlan
from ekp.lifecycle.uninstall import validate_lifecycle_manifest
from ekp.paths import get_ekp_root
from ekp.status.models import StatusState
from ekp.status.service import StatusRequest, StatusService
from ekp.version import get_version


@dataclass
class ConfigureRequest:
    """Exact desired-state configure request (both dimensions required)."""

    path: str
    components: Sequence[str]
    assistants: Sequence[str]
    dry_run: bool = False


@dataclass
class ConfigurePreparedOperation:
    """Prepared configure transition: same LifecyclePlan for confirm → apply.

    Holds assembly temp resources until ``close()`` (apply, dry-run, or refuse).
    """

    plan: LifecyclePlan
    desired_config: ProjectConfig
    old_file_snapshot: ProjectConfigFileSnapshot
    desired_semantic_hash: str
    noop: bool = False
    _assembly_result: Any = None
    _closed: bool = False

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        result = self._assembly_result
        self._assembly_result = None
        if result is not None:
            temp_ctx = getattr(result, "_temp_ctx", None)
            if temp_ctx is not None:
                temp_ctx.cleanup()
                try:
                    result._temp_ctx = None
                except Exception:
                    pass


@dataclass
class ConfigureResult:
    """Programmatic configure outcome."""

    exit_code: int
    message: str = ""
    plan: Optional[LifecyclePlan] = None
    prepared: Optional[ConfigurePreparedOperation] = None
    noop: bool = False
    desired_configuration_sha256: Optional[str] = None
    old_configuration_sha256: Optional[str] = None


class ConfigureService:
    """Transform a HEALTHY composition install to an exact desired intent."""

    def __init__(
        self,
        *,
        assembly_service: Optional[AssemblyService] = None,
        status_service: Optional[StatusService] = None,
        applier: Optional[TransactionApplier] = None,
        registry: Optional[ComponentRegistry] = None,
        deploy_registry: Optional[DeployRegistry] = None,
        deployment_engine: Optional[SharedDeploymentEngine] = None,
        resource_root: Optional[Path] = None,
    ):
        self.assembly = assembly_service or AssemblyService()
        self.status = status_service or StatusService()
        self.applier = applier or TransactionApplier()
        self._registry = registry
        self._deploy_registry = deploy_registry
        self._engine = deployment_engine or SharedDeploymentEngine()
        self._resource_root = Path(resource_root) if resource_root is not None else None

    def _registry_or_load(self) -> ComponentRegistry:
        if self._registry is not None:
            return self._registry
        return ComponentRegistry.load(self._resource_root or get_ekp_root())

    def _deploy_registry_or_default(self) -> DeployRegistry:
        return self._deploy_registry or build_default_deploy_registry()

    def configure(self, request: ConfigureRequest) -> ConfigureResult:
        """Prepare and apply (or dry-run / NOOP) in one call."""
        prepared_result = self.prepare(request)
        if prepared_result.exit_code != EXIT_SUCCESS:
            if prepared_result.prepared is not None:
                prepared_result.prepared.close()
            return prepared_result

        prepared = prepared_result.prepared
        assert prepared is not None

        if request.dry_run or prepared.noop:
            prepared.close()
            return ConfigureResult(
                exit_code=EXIT_SUCCESS,
                message=prepared_result.message,
                plan=prepared.plan,
                noop=prepared.noop,
                desired_configuration_sha256=prepared.desired_semantic_hash,
                old_configuration_sha256=prepared.old_file_snapshot.configuration_sha256,
            )

        return self.apply(prepared)

    def prepare(self, request: ConfigureRequest) -> ConfigureResult:
        """Build an exact LifecyclePlan without mutating the project.

        Callers that confirm interactively (AY-C) must ``apply`` this same
        prepared operation — never re-plan after confirmation.
        """
        try:
            return self._prepare(request)
        except InstallError as exc:
            return ConfigureResult(exit_code=exc.exit_code, message=exc.message)

    def apply(self, prepared: ConfigurePreparedOperation) -> ConfigureResult:
        """Apply a previously prepared plan (same object; no re-planning)."""
        try:
            return self._apply(prepared)
        except InstallError as exc:
            prepared.close()
            return ConfigureResult(exit_code=exc.exit_code, message=exc.message)
        except Exception:
            prepared.close()
            raise

    def _prepare(self, request: ConfigureRequest) -> ConfigureResult:
        project_root = resolve_project_root(request.path)
        running_version = get_version()
        registry = self._registry_or_load()
        deploy_registry = self._deploy_registry_or_default()

        # Desired IDs first — refuse empty/unknown before any mutation path.
        desired_components = list(request.components)
        desired_assistants = list(request.assistants)
        if not desired_components:
            raise InstallSelectionError(
                "configure requires at least one component.\n"
                "Use components=['core'] for Core-only; uninstall to remove EKP."
            )
        if not desired_assistants:
            raise InstallSelectionError(
                "configure requires at least one assistant.\n"
                "Use uninstall to remove EKP entirely."
            )

        try:
            intent = build_composition_intent(
                desired_components,
                registry,
                assistants=desired_assistants,
                deploy_registry=deploy_registry,
            )
        except InstallSelectionError:
            raise

        desired_config = intent_to_project_config(intent)
        desired_semantic = configuration_sha256(desired_config, registry)

        eligibility = self._check_eligibility(project_root, running_version)
        if eligibility is not None:
            return eligibility

        snapshot = ManifestStore(project_root).load_with_fingerprint()
        if snapshot is None:
            raise InstallSelectionError(
                "EKP is not installed in this project.\nRun `ekp install` first."
            )

        try:
            validate_lifecycle_manifest(
                snapshot.manifest, deploy_registry=deploy_registry
            )
        except InstallConflictError as exc:
            raise InstallSelectionError(exc.message) from exc

        manifest = snapshot.manifest
        if manifest.effective_mode != INSTALL_MODE_COMPOSITION:
            raise InstallSelectionError(
                "configure requires a composition installation.\n"
                "Legacy profile installs cannot be reconfigured; reinstall with components."
            )
        if manifest.ekp_version != running_version:
            raise InstallSelectionError(
                "Installed EKP version {} does not match running version {}.\n"
                "Run `ekp update` before configure.".format(
                    manifest.ekp_version, running_version
                )
            )

        store = ProjectConfigStore(project_root, registry=registry)
        try:
            file_snap = store.load_file_snapshot()
        except ProjectConfigError as exc:
            raise InstallSelectionError(
                "Project configuration is invalid: {}".format(exc)
            ) from exc
        if file_snap is None:
            raise InstallSelectionError(
                "Composition configure requires .ekp/project.yaml."
            )

        if file_snap.configuration_sha256 != manifest.configuration_sha256:
            raise InstallSelectionError(
                "Project configuration drifted from the ownership manifest.\n"
                "configure refuses to adopt or rewrite drifted intent."
            )
        current_assistants = set(file_snap.config.assistants)
        manifest_adapters = set(manifest.adapters)
        if current_assistants != manifest_adapters:
            raise InstallSelectionError(
                "Project assistants do not match manifest adapters.\n"
                "configure refuses inconsistent ownership state."
            )

        # Semantic NOOP — preserve exact project.yaml bytes; no assembly.
        if file_snap.configuration_sha256 == desired_semantic:
            noop_plan = LifecyclePlan(
                project_root=project_root,
                profile=manifest.profile,
                old_version=manifest.ekp_version,
                new_version=running_version,
                adapters=list(manifest.adapters),
                mode="composition",
                operations=[],
                conflicts=[],
                manifest_sha256=snapshot.sha256,
                commit_manifest=False,
                new_manifest=None,
                dry_run=request.dry_run,
                transition_kind="configure",
                expected_old_configuration_sha256=file_snap.configuration_sha256,
                new_configuration_sha256=desired_semantic,
                expected_project_config_content_sha256=file_snap.content_sha256,
                new_project_config_bytes=None,
                new_project_config_content_sha256=None,
            )
            prepared = ConfigurePreparedOperation(
                plan=noop_plan,
                desired_config=desired_config,
                old_file_snapshot=file_snap,
                desired_semantic_hash=desired_semantic,
                noop=True,
            )
            return ConfigureResult(
                exit_code=EXIT_SUCCESS,
                message="Configure NOOP: desired intent matches current configuration.",
                plan=noop_plan,
                prepared=prepared,
                noop=True,
                desired_configuration_sha256=desired_semantic,
                old_configuration_sha256=file_snap.configuration_sha256,
            )

        new_bytes = render_project_config_yaml(desired_config).encode("utf-8")
        new_content_sha = project_config_content_sha256(new_bytes)

        assembly_result = self.assembly.assemble_composition(
            CompositionAssemblyRequest(
                components=list(desired_config.components),
                outputs=list(desired_config.assistants),
                verify=True,
                clean=True,
                resource_root=self._resource_root or registry.resource_root,
            )
        )
        try:
            desired_files = self._collect_desired_files(
                assembly_result.bundle_path, desired_config.assistants
            )
            plan = build_configure_plan(
                project_root=project_root,
                snapshot=snapshot,
                running_version=running_version,
                desired=desired_files,
                bundle_path=assembly_result.bundle_path,
                dry_run=request.dry_run,
                old_file_snapshot=file_snap,
                desired_config=desired_config,
                desired_semantic_hash=desired_semantic,
                new_project_config_bytes=new_bytes,
                new_project_config_content_sha256=new_content_sha,
            )
            prepared = ConfigurePreparedOperation(
                plan=plan,
                desired_config=desired_config,
                old_file_snapshot=file_snap,
                desired_semantic_hash=desired_semantic,
                noop=False,
                _assembly_result=assembly_result,
            )
            # Transfer ownership of temp lifetime to prepared.
            assembly_result = None
            if plan.has_conflicts:
                prepared.close()
                return ConfigureResult(
                    exit_code=InstallConflictError.exit_code,
                    message=_render_configure_conflicts(plan),
                    plan=plan,
                    desired_configuration_sha256=desired_semantic,
                    old_configuration_sha256=file_snap.configuration_sha256,
                )
            return ConfigureResult(
                exit_code=EXIT_SUCCESS,
                message="Configure plan ready.",
                plan=plan,
                prepared=prepared,
                noop=False,
                desired_configuration_sha256=desired_semantic,
                old_configuration_sha256=file_snap.configuration_sha256,
            )
        except Exception:
            if assembly_result is not None:
                temp_ctx = getattr(assembly_result, "_temp_ctx", None)
                if temp_ctx is not None:
                    temp_ctx.cleanup()
            raise

    def _apply(self, prepared: ConfigurePreparedOperation) -> ConfigureResult:
        if prepared._closed:
            raise InstallFilesystemError(
                "Configure prepared operation already closed; cannot apply."
            )
        if prepared.noop:
            prepared.close()
            return ConfigureResult(
                exit_code=EXIT_SUCCESS,
                message="Configure NOOP: desired intent matches current configuration.",
                plan=prepared.plan,
                noop=True,
                desired_configuration_sha256=prepared.desired_semantic_hash,
                old_configuration_sha256=prepared.old_file_snapshot.configuration_sha256,
            )
        if prepared.plan.dry_run:
            prepared.close()
            return ConfigureResult(
                exit_code=EXIT_SUCCESS,
                message="Configure dry-run complete (0 writes).",
                plan=prepared.plan,
                noop=False,
                desired_configuration_sha256=prepared.desired_semantic_hash,
                old_configuration_sha256=prepared.old_file_snapshot.configuration_sha256,
            )
        if prepared.plan.has_conflicts:
            prepared.close()
            return ConfigureResult(
                exit_code=InstallConflictError.exit_code,
                message=_render_configure_conflicts(prepared.plan),
                plan=prepared.plan,
            )

        try:
            self.applier.apply_configure_transition(prepared.plan)
        except LifecycleConflictError as exc:
            prepared.close()
            return ConfigureResult(exit_code=exc.exit_code, message=exc.message)
        except LifecycleRollbackError as exc:
            prepared.close()
            return ConfigureResult(exit_code=exc.exit_code, message=exc.message)
        except InstallFilesystemError as exc:
            prepared.close()
            return ConfigureResult(exit_code=exc.exit_code, message=exc.message)
        except InstallConflictError as exc:
            prepared.close()
            return ConfigureResult(exit_code=exc.exit_code, message=exc.message)
        finally:
            # Always release assembly temps after apply attempt.
            if not prepared._closed:
                prepared.close()

        post = self._post_apply_verify(
            prepared.plan.project_root,
            prepared.desired_semantic_hash,
            prepared.desired_config,
        )
        if post is not None:
            return post

        return ConfigureResult(
            exit_code=EXIT_SUCCESS,
            message="Configure applied successfully.",
            plan=prepared.plan,
            noop=False,
            desired_configuration_sha256=prepared.desired_semantic_hash,
            old_configuration_sha256=prepared.old_file_snapshot.configuration_sha256,
        )

    def _post_apply_verify(
        self,
        project_root: Path,
        desired_semantic: str,
        desired_config: ProjectConfig,
    ) -> Optional[ConfigureResult]:
        registry = self._registry_or_load()
        try:
            store = ProjectConfigStore(project_root, registry=registry)
            snap = store.load_snapshot()
            manifest = ManifestStore(project_root).load()
        except (ProjectConfigError, InstallConflictError) as exc:
            return ConfigureResult(
                exit_code=InstallFilesystemError.exit_code,
                message="Configure post-apply verification failed: {}".format(exc),
            )
        if snap is None or manifest is None:
            return ConfigureResult(
                exit_code=InstallFilesystemError.exit_code,
                message="Configure post-apply verification failed: missing config/manifest.",
            )
        if snap.configuration_sha256 != desired_semantic:
            return ConfigureResult(
                exit_code=InstallFilesystemError.exit_code,
                message="Configure post-apply: project.yaml semantic hash mismatch.",
            )
        if manifest.configuration_sha256 != desired_semantic:
            return ConfigureResult(
                exit_code=InstallFilesystemError.exit_code,
                message="Configure post-apply: manifest configuration_sha256 mismatch.",
            )
        if set(manifest.adapters) != set(desired_config.assistants):
            return ConfigureResult(
                exit_code=InstallFilesystemError.exit_code,
                message="Configure post-apply: manifest adapters mismatch.",
            )
        status = self.status.inspect(StatusRequest(path=str(project_root)))
        if status.state != StatusState.HEALTHY:
            return ConfigureResult(
                exit_code=InstallFilesystemError.exit_code,
                message="Configure post-apply: project is not HEALTHY ({}).".format(
                    status.state.value
                ),
            )
        return None

    def _check_eligibility(
        self, project_root: Path, running_version: str
    ) -> Optional[ConfigureResult]:
        status = self.status.inspect(StatusRequest(path=str(project_root)))
        if status.state == StatusState.NOT_INSTALLED:
            return ConfigureResult(
                exit_code=InstallSelectionError.exit_code,
                message=(
                    "EKP is not installed in this project.\nRun `ekp install` first."
                ),
            )
        if status.state == StatusState.INVALID:
            return ConfigureResult(
                exit_code=InstallSelectionError.exit_code,
                message=(
                    "Installed ownership/config is invalid; configure refused.\n{}".format(
                        status.error_message or ""
                    ).rstrip()
                ),
            )
        if status.state == StatusState.CONFIGURATION_DRIFT:
            return ConfigureResult(
                exit_code=InstallSelectionError.exit_code,
                message=(
                    "Project configuration drifted from the ownership manifest.\n"
                    "configure refuses drifted installations."
                ),
            )
        if status.state == StatusState.VERSION_MISMATCH:
            return ConfigureResult(
                exit_code=InstallSelectionError.exit_code,
                message=(
                    "Installed EKP version {} does not match running version {}.\n"
                    "Run `ekp update` before configure.".format(
                        status.installed_version, running_version
                    )
                ),
            )
        if status.state == StatusState.INCOMPLETE:
            return ConfigureResult(
                exit_code=InstallSelectionError.exit_code,
                message=(
                    "Installation is incomplete; configure refused.\n"
                    "Do not use configure to repair missing managed files."
                ),
            )
        if status.state == StatusState.MODIFIED:
            return ConfigureResult(
                exit_code=InstallSelectionError.exit_code,
                message=(
                    "Managed files were modified; configure refused.\n"
                    "Do not use configure to delete or overwrite modified ownership."
                ),
            )
        if status.state != StatusState.HEALTHY:
            return ConfigureResult(
                exit_code=InstallSelectionError.exit_code,
                message="configure requires a HEALTHY composition installation.",
            )
        return None

    def _collect_desired_files(
        self, bundle_path: Path, assistants: Sequence[str]
    ) -> List[DesiredManagedFile]:
        deploy_registry = self._deploy_registry_or_default()
        desired: List[DesiredManagedFile] = []
        for assistant_id in assistants:
            deployer = deploy_registry.get(assistant_id)
            desired.extend(deployer.collect_desired_files(bundle_path))
        return self._engine.normalize_desired_files(desired)


def build_configure_plan(
    *,
    project_root: Path,
    snapshot: ManifestSnapshot,
    running_version: str,
    desired: List[DesiredManagedFile],
    bundle_path: Path,
    dry_run: bool,
    old_file_snapshot: ProjectConfigFileSnapshot,
    desired_config: ProjectConfig,
    desired_semantic_hash: str,
    new_project_config_bytes: bytes,
    new_project_config_content_sha256: str,
) -> LifecyclePlan:
    """Build a configure LifecyclePlan allowing same-version ownership change."""
    project_root = project_root.resolve()
    manifest = snapshot.manifest
    old_by_path = manifest.managed_by_path()
    new_by_path = {item.relative_path: item for item in desired}

    desired_adapters = adapters_from_desired(desired)
    # Safety probes cover old + new assistant roots; final adapters stay desired-only.
    safety_adapters = sorted(set(manifest.adapters) | set(desired_adapters))

    conflicts: List[str] = []
    operations: List[LifecycleFileOperation] = []

    for relative in lifecycle_symlink_check_paths(safety_adapters):
        message = check_symlink_boundary(project_root, relative)
        if message:
            conflicts.append(message)

    all_paths = sorted(set(old_by_path) | set(new_by_path))
    for relative in all_paths:
        old_item = old_by_path.get(relative)
        new_item = new_by_path.get(relative)
        old_sha = old_item.sha256 if old_item else None
        new_sha = new_item.sha256 if new_item else None
        source_path = new_item.source_path if new_item else None
        if new_item is not None:
            adapter = new_item.adapter
        elif old_item is not None:
            adapter = old_item.adapter
        else:
            from ekp.install.cursor_deploy import CURSOR_ADAPTER

            adapter = CURSOR_ADAPTER

        boundary = check_symlink_boundary(project_root, relative)
        if boundary:
            conflicts.append(boundary)
            operations.append(noop_operation(relative, old_sha, adapter))
            continue

        try:
            target = resolve_under_root(project_root, relative)
        except ValueError as exc:
            conflicts.append(str(exc))
            operations.append(noop_operation(relative, old_sha, adapter))
            continue

        disk_exists = target.exists()
        disk_symlink = target.is_symlink() if disk_exists else False
        disk_sha = sha256_file(target) if disk_exists and not disk_symlink else None

        if disk_symlink:
            conflicts.append("Symlink target not managed safely: {}".format(relative))
            operations.append(noop_operation(relative, old_sha, adapter))
            continue

        op = classify_lifecycle_operation(
            relative=relative,
            adapter=adapter,
            old_sha=old_sha,
            new_sha=new_sha,
            source_path=source_path,
            disk_exists=disk_exists,
            disk_sha=disk_sha,
        )
        if op is None:
            if old_sha is None and new_sha is not None:
                conflicts.append(
                    "Unmanaged file blocks configure: {}".format(relative)
                )
            else:
                conflicts.append(
                    "Managed file modified by user: {}".format(relative)
                )
            operations.append(noop_operation(relative, old_sha, adapter))
        else:
            operations.append(op)

    directories_to_create = directories_to_create_for_operations(project_root, operations)
    directories_to_remove = _directories_to_remove(
        manifest.created_directories,
        remaining_paths=set(new_by_path),
        directories_to_create=directories_to_create,
    )

    new_manifest = _build_configure_manifest(
        manifest=manifest,
        running_version=running_version,
        desired=desired,
        desired_semantic_hash=desired_semantic_hash,
        directories_to_create=directories_to_create,
        directories_to_remove=directories_to_remove,
        project_root=project_root,
    )

    return LifecyclePlan(
        project_root=project_root,
        profile=PROJECT_COMPOSITION_PROFILE,
        old_version=manifest.ekp_version,
        new_version=running_version,
        adapters=desired_adapters,
        mode="composition",
        operations=operations,
        conflicts=conflicts,
        directories_to_create=directories_to_create,
        directories_to_remove=directories_to_remove,
        manifest_sha256=snapshot.sha256,
        commit_manifest=True,
        new_manifest=new_manifest,
        bundle_path=bundle_path,
        dry_run=dry_run,
        expected_configuration_sha256=None,
        transition_kind="configure",
        expected_old_configuration_sha256=old_file_snapshot.configuration_sha256,
        new_configuration_sha256=desired_semantic_hash,
        expected_project_config_content_sha256=old_file_snapshot.content_sha256,
        new_project_config_bytes=new_project_config_bytes,
        new_project_config_content_sha256=new_project_config_content_sha256,
    )


def _directories_to_remove(
    created_directories: Sequence[str],
    *,
    remaining_paths: Set[str],
    directories_to_create: Sequence[str],
) -> List[str]:
    keep = set(directories_to_create)
    for path in remaining_paths:
        parent = Path(path).parent
        current = parent
        while current.as_posix() not in (".", ""):
            keep.add(current.as_posix())
            current = current.parent

    removable: List[str] = []
    for relative in created_directories:
        try:
            normalized = relative_posix_path(relative)
        except ValueError:
            continue
        if normalized in keep:
            continue
        prefix = normalized.rstrip("/") + "/"
        if any(
            path == normalized or path.startswith(prefix) for path in remaining_paths
        ):
            continue
        removable.append(normalized)
    return sorted(set(removable), key=lambda path: path.count("/"), reverse=True)


def _build_configure_manifest(
    *,
    manifest: InstallManifest,
    running_version: str,
    desired: List[DesiredManagedFile],
    desired_semantic_hash: str,
    directories_to_create: List[str],
    directories_to_remove: List[str],
    project_root: Path,
) -> InstallManifest:
    managed_files = [
        ManagedFile(
            relative_path=item.relative_path,
            adapter=item.adapter,
            sha256=item.sha256,
        )
        for item in sorted(
            desired, key=lambda entry: (entry.relative_path, entry.adapter)
        )
    ]
    adapters = adapters_from_desired(desired)

    newly_created: List[str] = []
    for relative in directories_to_create:
        try:
            normalized = relative_posix_path(relative)
        except ValueError:
            continue
        boundary = check_symlink_boundary(project_root, normalized)
        if boundary:
            continue
        try:
            target = resolve_under_root(project_root, normalized)
        except ValueError:
            continue
        if not target.exists():
            newly_created.append(normalized)

    remove_set = set(directories_to_remove)
    created_directories = sorted(
        (set(manifest.created_directories) | set(newly_created)) - remove_set
    )

    return InstallManifest(
        schema_version=1,
        ekp_version=running_version,
        profile=PROJECT_COMPOSITION_PROFILE,
        adapters=adapters,
        installed_at=manifest.installed_at,
        install_root=".",
        managed_files=managed_files,
        created_directories=created_directories,
        mode=INSTALL_MODE_COMPOSITION,
        configuration_sha256=desired_semantic_hash,
    )


def _render_configure_conflicts(plan: LifecyclePlan) -> str:
    lines = ["Configure conflicts detected:"]
    for item in plan.conflicts:
        lines.append("  - {}".format(item))
    return "\n".join(lines)
