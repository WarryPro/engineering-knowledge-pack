"""Composition install service (public multi-assistant Consumer path)."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Dict, List, Optional, Sequence, Tuple

from ekp.assembly import (
    AssemblyService,
    CompositionAssemblyRequest,
    ScopedProjectAssemblyRequest,
)
from ekp.composition import PROJECT_COMPOSITION_PROFILE, ComponentRegistry
from ekp.config.models import (
    PROJECT_CONFIG_RELATIVE,
    PROJECT_SCHEMA_VERSION_1,
    PROJECT_SCHEMA_VERSION_2,
    ProjectConfig,
    ProjectConfigError,
)
from ekp.config.normalization import configuration_sha256
from ekp.config.project import ProjectConfigStore, render_project_config_yaml
from ekp.install.cursor_deploy import AppliedManagedFiles, CursorDeployService
from ekp.install.deploy.engine import SharedDeploymentEngine
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
    MODE_COMPOSITION,
    InstallIntent,
    ProjectLifecycleIntent,
    build_project_lifecycle_intent,
    intent_to_project_config,
    project_lifecycle_intent_from_install_intent,
    validate_composition_assistants,
)
from ekp.install.manifest import (
    INSTALL_MODE_COMPOSITION,
    MANIFEST_RELATIVE,
    InstallManifest,
    ManifestStore,
    utc_now_iso,
)
from ekp.install.paths import check_symlink_boundary, resolve_under_root
from ekp.install.plan import InstallPlan
from ekp.paths import get_ekp_root
from ekp.version import get_version

CONFIG_ACTION_CREATE = "create"
CONFIG_ACTION_REUSE = "reuse"

_ASSISTANT_SYMLINK_ROOTS = {
    "cursor": (".cursor", ".cursor/rules"),
    "copilot": (".github", ".github/instructions"),
    "claude": (".claude", ".claude/skills", ".claude/rules", "CLAUDE.md"),
    "antigravity": (".agents", ".agents/rules"),
}


@dataclass
class CompositionInstallPlan:
    """Composition install plan over a generic shared deployment plan."""

    project_root: Path
    intent: Optional[InstallIntent]
    project_config: ProjectConfig
    configuration_sha256: str
    config_action: str
    deployment_plan: InstallPlan
    assistant_counts: Dict[str, int] = field(default_factory=dict)
    conflicts: List[str] = field(default_factory=list)
    dry_run: bool = False
    lifecycle_intent: Optional[ProjectLifecycleIntent] = None

    @property
    def cursor_plan(self) -> InstallPlan:
        """Compatibility alias — canonical field is ``deployment_plan``."""
        return self.deployment_plan

    @property
    def has_conflicts(self) -> bool:
        return bool(self.conflicts) or self.deployment_plan.has_conflicts

    @property
    def rules_count(self) -> int:
        """Cursor-managed file count (public Cursor messaging compatibility)."""
        return int(self.assistant_counts.get("cursor", 0))

    @property
    def managed_file_count(self) -> int:
        return sum(self.assistant_counts.values())

    @property
    def assistants(self) -> Tuple[str, ...]:
        if self.lifecycle_intent is not None:
            return tuple(self.lifecycle_intent.config.assistants)
        if self.intent is not None:
            return tuple(self.intent.assistants)
        return tuple(self.project_config.assistants)


@dataclass
class CompositionInstallResult:
    """Structured internal composition install outcome."""

    exit_code: int
    message: str = ""
    intent: Optional[InstallIntent] = None
    plan: Optional[CompositionInstallPlan] = None
    manifest: Optional[InstallManifest] = None


class CompositionInstallService:
    """Persist a composed EKP installation (Consumer + programmatic)."""

    def __init__(
        self,
        assembly_service: Optional[AssemblyService] = None,
        deploy_service: Optional[CursorDeployService] = None,
        registry: Optional[ComponentRegistry] = None,
        resource_root: Optional[Path] = None,
        deploy_registry: Optional[DeployRegistry] = None,
        deployment_engine: Optional[SharedDeploymentEngine] = None,
    ):
        self.assembly_service = assembly_service or AssemblyService()
        self.deploy_service = deploy_service or CursorDeployService()
        self._registry = registry
        self._resource_root = Path(resource_root) if resource_root is not None else None
        self._deploy_registry = deploy_registry
        self._engine = deployment_engine or SharedDeploymentEngine()
        # Test hooks (None in production): called during apply after named steps.
        self._after_config_hook: Optional[Callable[[CompositionInstallPlan], None]] = None
        self._after_managed_files_hook: Optional[
            Callable[[CompositionInstallPlan, AppliedManagedFiles], None]
        ] = None

    def _registry_or_load(self) -> ComponentRegistry:
        if self._registry is not None:
            return self._registry
        return ComponentRegistry.load(self._resource_root or get_ekp_root())

    def _deploy_registry_or_default(self) -> DeployRegistry:
        return self._deploy_registry or build_default_deploy_registry()

    def install(
        self,
        project_root: Path,
        intent: InstallIntent,
        *,
        dry_run: bool = False,
    ) -> CompositionInstallResult:
        try:
            root = Path(project_root).resolve()
            registry = self._registry_or_load()
            lifecycle = project_lifecycle_intent_from_install_intent(
                intent,
                registry,
                deploy_registry=self._deploy_registry_or_default(),
                project_root=root,
            )
            return self._install_lifecycle(
                root, lifecycle, legacy_intent=intent, dry_run=dry_run
            )
        except InstallError as exc:
            return CompositionInstallResult(
                exit_code=exc.exit_code,
                message=exc.message,
                intent=intent,
            )

    def install_project_config(
        self,
        project_root: Path,
        config: ProjectConfig,
        *,
        dry_run: bool = False,
        additional_concerns: Sequence[str] = (),
    ) -> CompositionInstallResult:
        """Programmatic composition install from an exact ProjectConfig (schema1/2)."""
        try:
            root = Path(project_root).resolve()
            registry = self._registry_or_load()
            lifecycle = build_project_lifecycle_intent(
                config,
                registry,
                additional_concerns=additional_concerns,
                deploy_registry=self._deploy_registry_or_default(),
                project_root=root,
            )
            return self._install_lifecycle(
                root, lifecycle, legacy_intent=None, dry_run=dry_run
            )
        except InstallError as exc:
            return CompositionInstallResult(
                exit_code=exc.exit_code,
                message=exc.message,
                intent=None,
            )

    def _install_lifecycle(
        self,
        project_root: Path,
        lifecycle: ProjectLifecycleIntent,
        *,
        legacy_intent: Optional[InstallIntent],
        dry_run: bool,
    ) -> CompositionInstallResult:
        registry = self._registry_or_load()
        resource_root = self._resource_root or registry.resource_root
        assembly_result = self._assemble_for_config(
            lifecycle.config, resource_root=resource_root
        )
        try:
            plan = self._build_plan_lifecycle(
                project_root,
                lifecycle,
                legacy_intent=legacy_intent,
                dry_run=dry_run,
                assembly_result=assembly_result,
                registry=registry,
            )
            if plan.has_conflicts:
                return CompositionInstallResult(
                    exit_code=InstallConflictError.exit_code,
                    message=self._render_conflicts(plan),
                    intent=legacy_intent,
                    plan=plan,
                )

            if dry_run:
                return CompositionInstallResult(
                    exit_code=EXIT_SUCCESS,
                    message=self._render_dry_run(plan),
                    intent=legacy_intent,
                    plan=plan,
                )

            manifest = self._apply(plan, registry=registry)
            return CompositionInstallResult(
                exit_code=EXIT_SUCCESS,
                message=self._render_success(plan),
                intent=legacy_intent,
                plan=plan,
                manifest=manifest,
            )
        finally:
            temp_ctx = getattr(assembly_result, "_temp_ctx", None)
            if temp_ctx is not None:
                temp_ctx.cleanup()

    def _assemble_for_config(self, config: ProjectConfig, *, resource_root: Path):
        if config.schema_version == PROJECT_SCHEMA_VERSION_2:
            return self.assembly_service.assemble_scoped_project(
                ScopedProjectAssemblyRequest(
                    config=config,
                    assistants=list(config.assistants),
                    verify=True,
                    clean=True,
                    resource_root=resource_root,
                )
            )
        return self.assembly_service.assemble_composition(
            CompositionAssemblyRequest(
                components=list(config.components),
                outputs=list(config.assistants),
                verify=True,
                clean=True,
                resource_root=resource_root,
            )
        )

    def _install(
        self,
        project_root: Path,
        intent: InstallIntent,
        *,
        dry_run: bool,
    ) -> CompositionInstallResult:
        # Compatibility shim retained for callers/tests that invoke _install.
        return self.install(project_root, intent, dry_run=dry_run)

    def _collect_desired_files(
        self, bundle_path: Path, assistants: Sequence[str]
    ) -> List[DesiredManagedFile]:
        deploy_registry = self._deploy_registry_or_default()
        desired: List[DesiredManagedFile] = []
        for assistant_id in assistants:
            deployer = deploy_registry.get(assistant_id)
            desired.extend(deployer.collect_desired_files(bundle_path))
        return self._engine.normalize_desired_files(desired)

    def _assistant_symlink_paths(self, assistants: Sequence[str]) -> List[str]:
        paths: List[str] = [".ekp", PROJECT_CONFIG_RELATIVE]
        for assistant_id in assistants:
            paths.extend(_ASSISTANT_SYMLINK_ROOTS.get(assistant_id, ()))
        # Deterministic unique order
        seen = set()
        ordered: List[str] = []
        for item in paths:
            if item not in seen:
                seen.add(item)
                ordered.append(item)
        return ordered

    def _validate_intent(self, intent: InstallIntent) -> None:
        if intent.mode != MODE_COMPOSITION:
            raise InstallSelectionError(
                "Composition install requires mode={!r}, found {!r}".format(
                    MODE_COMPOSITION, intent.mode
                )
            )
        if not intent.components:
            raise InstallSelectionError("composition intent has no requested components")
        if intent.composition is None:
            raise InstallSelectionError("composition intent is missing resolved composition")
        if not intent.configuration_sha256:
            raise InstallSelectionError(
                "composition intent is missing configuration_sha256"
            )
        assistants = validate_composition_assistants(
            intent.assistants,
            deploy_registry=self._deploy_registry_or_default(),
        )
        if tuple(intent.assistants) != assistants:
            raise InstallSelectionError(
                "composition intent assistants must be canonical: expected {}, found {}".format(
                    list(assistants), list(intent.assistants)
                )
            )

    def _build_plan(
        self,
        project_root: Path,
        intent: InstallIntent,
        *,
        dry_run: bool,
        assembly_result,
        registry: Optional[ComponentRegistry] = None,
    ) -> CompositionInstallPlan:
        registry = registry or self._registry_or_load()
        lifecycle = project_lifecycle_intent_from_install_intent(
            intent,
            registry,
            deploy_registry=self._deploy_registry_or_default(),
            project_root=project_root,
        )
        return self._build_plan_lifecycle(
            project_root,
            lifecycle,
            legacy_intent=intent,
            dry_run=dry_run,
            assembly_result=assembly_result,
            registry=registry,
        )

    def _build_plan_lifecycle(
        self,
        project_root: Path,
        lifecycle: ProjectLifecycleIntent,
        *,
        legacy_intent: Optional[InstallIntent],
        dry_run: bool,
        assembly_result,
        registry: Optional[ComponentRegistry] = None,
    ) -> CompositionInstallPlan:
        registry = registry or self._registry_or_load()
        conflicts: List[str] = []
        assistants = tuple(lifecycle.config.assistants)

        for relative in self._assistant_symlink_paths(assistants):
            message = check_symlink_boundary(project_root, relative)
            if message:
                conflicts.append(message)

        if ManifestStore(project_root).exists():
            conflicts.append(
                "Ownership manifest already exists: {}".format(MANIFEST_RELATIVE)
            )

        project_config, config_action, config_conflicts = self._resolve_project_config(
            project_root, lifecycle, registry
        )
        conflicts.extend(config_conflicts)

        digest = lifecycle.configuration_sha256
        if project_config is not None and not config_conflicts:
            computed = configuration_sha256(project_config, registry)
            if computed != digest:
                conflicts.append(
                    "project config semantic hash does not match install intent"
                )
            if set(project_config.assistants) != set(assistants):
                conflicts.append(
                    "Existing project config assistants differ from install intent "
                    "(automatic reconfiguration is not supported)."
                )

        if assembly_result is None or assembly_result.bundle_path is None:
            raise InstallFilesystemError("Composition assembly did not produce a bundle")

        try:
            desired = self._collect_desired_files(
                assembly_result.bundle_path, assistants
            )
        except InstallError:
            raise
        except Exception as exc:
            raise InstallFilesystemError(
                "Failed to collect managed files from assembled bundle: {}".format(exc)
            ) from exc

        assistant_counts: Dict[str, int] = {assistant: 0 for assistant in assistants}
        for item in desired:
            assistant_counts[item.adapter] = assistant_counts.get(item.adapter, 0) + 1

        operations, deploy_conflicts = self._engine.plan_first_install(
            project_root, desired
        )
        conflicts.extend(deploy_conflicts)
        directories = self._engine.directories_to_create(project_root, operations)

        concerns = list(lifecycle.additional_concerns)
        if legacy_intent is not None:
            concerns = list(legacy_intent.additional_concerns)

        deployment_plan = InstallPlan(
            project_root=project_root,
            profile=PROJECT_COMPOSITION_PROFILE,
            ekp_version=get_version(),
            adapter="+".join(assistants),
            bundle_path=assembly_result.bundle_path,
            rules_count=len(desired),
            operations=operations,
            conflicts=list(deploy_conflicts),
            directories_to_create=directories,
            additional_concerns=concerns,
            dry_run=dry_run,
        )

        for op in deployment_plan.operations:
            if op.relative_path == PROJECT_CONFIG_RELATIVE:
                conflicts.append(
                    "Deployment plan must not manage {}".format(PROJECT_CONFIG_RELATIVE)
                )

        return CompositionInstallPlan(
            project_root=project_root,
            intent=legacy_intent,
            project_config=project_config
            if project_config is not None
            else lifecycle.config,
            configuration_sha256=digest,
            config_action=config_action,
            deployment_plan=deployment_plan,
            assistant_counts=assistant_counts,
            conflicts=conflicts,
            dry_run=dry_run,
            lifecycle_intent=lifecycle,
        )

    def _resolve_project_config(
        self,
        project_root: Path,
        lifecycle: ProjectLifecycleIntent,
        registry: ComponentRegistry,
    ):
        store = ProjectConfigStore(
            project_root,
            registry=registry,
            resource_root=self._resource_root or registry.resource_root,
        )
        draft = lifecycle.config
        expected = lifecycle.configuration_sha256

        try:
            if not store.exists():
                return draft, CONFIG_ACTION_CREATE, []

            loaded = store.load()
            if loaded is None:
                return draft, CONFIG_ACTION_CREATE, []

            digest = configuration_sha256(loaded, registry)
            if digest != expected:
                return loaded, CONFIG_ACTION_REUSE, [
                    "Existing project config semantic hash differs from install intent "
                    "(automatic reconfiguration is not supported)."
                ]
            return loaded, CONFIG_ACTION_REUSE, []
        except ProjectConfigError as exc:
            raise InstallSelectionError(str(exc)) from exc

    def _apply(
        self,
        plan: CompositionInstallPlan,
        *,
        registry: ComponentRegistry,
    ) -> InstallManifest:
        if plan.has_conflicts:
            raise InstallConflictError("Cannot apply composition install with conflicts.")
        if plan.dry_run:
            raise InstallFilesystemError("Dry-run composition plans cannot be applied.")

        store = ProjectConfigStore(
            plan.project_root,
            registry=registry,
            resource_root=self._resource_root or registry.resource_root,
        )
        config_path = store.config_path
        created_config_bytes: Optional[bytes] = None
        applied: Optional[AppliedManagedFiles] = None
        created_ekp_dir = False
        ekp_dir = resolve_under_root(plan.project_root, ".ekp")
        ekp_preexisted = ekp_dir.exists()

        try:
            self._pre_apply_revalidate(plan, store, registry)

            if plan.config_action == CONFIG_ACTION_CREATE:
                if config_path.exists() or config_path.is_symlink():
                    raise InstallConflictError(
                        "project config appeared before create: {}".format(
                            PROJECT_CONFIG_RELATIVE
                        )
                    )
                if not ekp_preexisted:
                    ekp_dir.mkdir(parents=True, exist_ok=True)
                    created_ekp_dir = True
                store.create(plan.project_config)
                created_config_bytes = config_path.read_bytes()
                if self._after_config_hook is not None:
                    self._after_config_hook(plan)
            else:
                self._revalidate_reuse(store, registry, plan.configuration_sha256)

            applied = self.deploy_service.apply_managed_files(
                plan.deployment_plan,
                extra_directories=(
                    [".ekp"] if plan.config_action == CONFIG_ACTION_CREATE else None
                ),
                rollback_on_error=True,
            )
            if self._after_managed_files_hook is not None:
                self._after_managed_files_hook(plan, applied)

            snapshot = store.load_snapshot()
            if snapshot is None:
                raise InstallFilesystemError(
                    "project config missing before ownership manifest commit"
                )
            if snapshot.configuration_sha256 != plan.configuration_sha256:
                raise InstallConflictError(
                    "project config semantic hash drifted before ownership manifest commit"
                )
            if set(snapshot.config.assistants) != set(plan.assistants):
                raise InstallConflictError(
                    "project config assistants drifted before ownership manifest commit"
                )

            if ManifestStore(plan.project_root).exists():
                raise InstallConflictError(
                    "Ownership manifest already exists: {}".format(MANIFEST_RELATIVE)
                )

            created_dirs = list(applied.created_directory_names)
            if created_ekp_dir and ".ekp" not in created_dirs:
                created_dirs.append(".ekp")

            adapters = list(plan.assistants)
            if set(adapters) != set(item.adapter for item in applied.managed_files):
                # Allow managed_files to only include selected adapters; set must match.
                managed_adapters = sorted(
                    set(item.adapter for item in applied.managed_files)
                )
                if managed_adapters != sorted(adapters):
                    raise InstallConflictError(
                        "managed file adapters {} do not match intent assistants {}".format(
                            managed_adapters, adapters
                        )
                    )

            manifest = InstallManifest(
                schema_version=1,
                ekp_version=plan.deployment_plan.ekp_version,
                profile=PROJECT_COMPOSITION_PROFILE,
                adapters=adapters,
                installed_at=utc_now_iso(),
                install_root=".",
                managed_files=applied.managed_files,
                created_directories=sorted(set(created_dirs)),
                mode=INSTALL_MODE_COMPOSITION,
                configuration_sha256=plan.configuration_sha256,
            )
            if set(manifest.adapters) != set(plan.assistants):
                raise InstallConflictError(
                    "manifest adapters do not match install intent assistants"
                )
            ManifestStore(plan.project_root).create(manifest)
            return manifest
        except Exception as exc:
            notes = self._rollback_transaction(
                applied=applied,
                config_path=config_path,
                created_config_bytes=created_config_bytes,
                created_ekp_dir=created_ekp_dir,
                ekp_dir=ekp_dir,
            )
            if notes:
                suffix = " Rollback: {}.".format("; ".join(notes))
                if isinstance(exc, InstallError):
                    raise type(exc)(exc.message + suffix) from exc
                raise InstallFilesystemError(
                    "Composition install failed.{}".format(suffix)
                ) from exc
            raise

    def _pre_apply_revalidate(
        self,
        plan: CompositionInstallPlan,
        store: ProjectConfigStore,
        registry: ComponentRegistry,
    ) -> None:
        if ManifestStore(plan.project_root).exists():
            raise InstallConflictError(
                "Ownership manifest already exists: {}".format(MANIFEST_RELATIVE)
            )
        if plan.config_action == CONFIG_ACTION_CREATE:
            if store.exists():
                raise InstallConflictError(
                    "project config appeared before create: {}".format(
                        PROJECT_CONFIG_RELATIVE
                    )
                )
        else:
            self._revalidate_reuse(store, registry, plan.configuration_sha256)

        # Schema2: revalidate workspace directories immediately before apply.
        if plan.project_config.schema_version == PROJECT_SCHEMA_VERSION_2:
            try:
                build_project_lifecycle_intent(
                    plan.project_config,
                    registry,
                    deploy_registry=self._deploy_registry_or_default(),
                    project_root=plan.project_root,
                )
            except InstallSelectionError as exc:
                raise InstallConflictError(str(exc)) from exc

        for operation in plan.deployment_plan.files_to_write:
            target = resolve_under_root(plan.project_root, operation.relative_path)
            if target.exists() or target.is_symlink():
                raise InstallConflictError(
                    "Refusing to overwrite unexpected target: {}".format(
                        operation.relative_path
                    )
                )

    def _revalidate_reuse(
        self,
        store: ProjectConfigStore,
        registry: ComponentRegistry,
        expected_sha256: str,
    ) -> None:
        try:
            snapshot = store.load_snapshot()
        except ProjectConfigError as exc:
            raise InstallSelectionError(str(exc)) from exc
        if snapshot is None:
            raise InstallConflictError(
                "project config disappeared before reuse apply: {}".format(
                    PROJECT_CONFIG_RELATIVE
                )
            )
        if snapshot.configuration_sha256 != expected_sha256:
            raise InstallConflictError(
                "project config semantic hash changed before reuse apply"
            )

    def _rollback_transaction(
        self,
        *,
        applied: Optional[AppliedManagedFiles],
        config_path: Path,
        created_config_bytes: Optional[bytes],
        created_ekp_dir: bool,
        ekp_dir: Path,
    ) -> List[str]:
        notes: List[str] = []

        if applied is not None:
            self.deploy_service.rollback_managed_files(applied)

        if created_config_bytes is not None:
            try:
                if config_path.is_symlink():
                    notes.append("cannot rollback symlinked project config")
                elif config_path.is_file():
                    current = config_path.read_bytes()
                    if current == created_config_bytes:
                        config_path.unlink()
                    else:
                        notes.append(
                            "project config changed during failed install; left in place"
                        )
            except OSError as exc:
                notes.append("unable to rollback project config: {}".format(exc))

        if created_ekp_dir:
            try:
                if ekp_dir.is_dir() and not any(ekp_dir.iterdir()):
                    ekp_dir.rmdir()
            except OSError:
                pass

        return notes

    @staticmethod
    def _render_conflicts(plan: CompositionInstallPlan) -> str:
        lines = ["Composition install conflicts detected:"]
        for item in plan.conflicts:
            lines.append("  - {}".format(item))
        for item in plan.deployment_plan.conflicts:
            lines.append("  - {}".format(item))
        return "\n".join(lines)

    @staticmethod
    def _render_dry_run(plan: CompositionInstallPlan) -> str:
        config = plan.project_config
        composition = None
        if plan.lifecycle_intent is not None:
            composition = plan.lifecycle_intent.composition
        elif plan.intent is not None:
            composition = plan.intent.composition
        counts = ", ".join(
            "{}={}".format(name, plan.assistant_counts.get(name, 0))
            for name in plan.assistants
        )
        lines = [
            "Composition install dry-run",
            "  mode: {}".format(MODE_COMPOSITION),
            "  profile: {}".format(PROJECT_COMPOSITION_PROFILE),
            "  schema_version: {}".format(config.schema_version),
            "  config_action: {}".format(plan.config_action),
            "  configuration_sha256: {}".format(plan.configuration_sha256),
            "  requested_components: {}".format(",".join(config.components)),
            "  resolved_components: {}".format(
                ",".join(composition.resolved_components) if composition else ""
            ),
            "  assistants: {}".format(",".join(plan.assistants)),
            "  assistant_counts: {}".format(counts),
            "  managed_files: {}".format(plan.managed_file_count),
            "  cursor_rules: {}".format(plan.rules_count),
            "  file_operations: {}".format(len(plan.deployment_plan.files_to_write)),
        ]
        if config.workspaces:
            lines.append(
                "  workspaces: {}".format(
                    ",".join(ws.path for ws in config.workspaces)
                )
            )
        return "\n".join(lines)

    @staticmethod
    def _render_success(plan: CompositionInstallPlan) -> str:
        if plan.assistants == ("cursor",):
            return "Composition install completed ({} Cursor rules).".format(
                plan.rules_count
            )
        return "Composition install completed ({} managed files; assistants={}).".format(
            plan.managed_file_count,
            ",".join(plan.assistants),
        )


def preview_project_config_bytes(config: ProjectConfig) -> bytes:
    """Exact bytes CompositionInstallService would write for a new project.yaml."""
    return render_project_config_yaml(config).encode("utf-8")
