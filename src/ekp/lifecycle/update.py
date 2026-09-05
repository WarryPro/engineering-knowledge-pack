"""Cross-version update orchestration service."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Dict, List, Optional, Set, Tuple

from ekp.assembly import AssemblyRequest, AssemblyService, CompositionAssemblyRequest
from ekp.composition import ComponentRegistry
from ekp.config.models import ProjectConfigError
from ekp.config.project import ProjectConfigStore
from ekp.install.cursor_deploy import CURSOR_ADAPTER, CursorDeployService, sha256_file
from ekp.install.errors import (
    InstallAssemblyError,
    InstallConflictError,
    InstallError,
    InstallFilesystemError,
    InstallSelectionError,
)
from ekp.install.manifest import (
    INSTALL_MODE_COMPOSITION,
    InstallManifest,
    ManagedFile,
    ManifestSnapshot,
    ManifestStore,
)
from ekp.install.paths import check_symlink_boundary, relative_posix_path, resolve_under_root
from ekp.lifecycle.apply import (
    LifecycleConflictError,
    LifecycleRollbackError,
    TransactionApplier,
)
from ekp.lifecycle.plan import LifecycleFileOperation, LifecycleOpKind, LifecyclePlan
from ekp.lifecycle.render import (
    render_update_confirmation,
    render_update_conflict_message,
    render_update_dry_run,
    render_update_success,
)
from ekp.lifecycle.uninstall import validate_lifecycle_manifest
from ekp.paths import get_ekp_root
from ekp.resolution.catalog import validate_profile_name
from ekp.version import get_version

BundleInventory = Dict[str, Tuple[Path, str]]

_COMPOSITION_DRIFT_MESSAGE = (
    "Project configuration has changed since EKP was installed.\n\n"
    "Automatic reconfiguration is not supported in v0.18.\n"
    "Restore the installed configuration or use the future reconfiguration workflow."
)


class UpdateCancelled(Exception):
    """User declined confirmation."""

    exit_code = 0


@dataclass
class UpdateRequest:
    path: str = "."
    assume_yes: bool = False
    dry_run: bool = False


@dataclass
class UpdateResult:
    exit_code: int
    message: str = ""


class UpdateService:
    """Consumer update workflow."""

    def __init__(
        self,
        applier: Optional[TransactionApplier] = None,
        assembly: Optional[AssemblyService] = None,
        deploy: Optional[CursorDeployService] = None,
        input_fn: Callable[[str], str] = input,
        output_fn: Callable[[str], None] = print,
    ):
        self.applier = applier or TransactionApplier()
        self.assembly = assembly or AssemblyService()
        self.deploy = deploy or CursorDeployService()
        self.input_fn = input_fn
        self.output_fn = output_fn

    def update(self, request: UpdateRequest) -> UpdateResult:
        try:
            return self._update(request)
        except UpdateCancelled:
            return UpdateResult(exit_code=0, message="Update cancelled.")
        except InstallError as exc:
            return UpdateResult(exit_code=exc.exit_code, message=exc.message)

    def _update(self, request: UpdateRequest) -> UpdateResult:
        from ekp.install.paths import resolve_project_root

        project_root = resolve_project_root(request.path)
        manifest_store = ManifestStore(project_root)

        if not manifest_store.exists():
            return UpdateResult(
                exit_code=InstallSelectionError.exit_code,
                message=(
                    "EKP is not installed in this project.\n"
                    "Run `ekp install` first."
                ),
            )

        snapshot = manifest_store.load_with_fingerprint()
        if snapshot is None:
            return UpdateResult(
                exit_code=InstallSelectionError.exit_code,
                message=(
                    "EKP is not installed in this project.\n"
                    "Run `ekp install` first."
                ),
            )

        try:
            validate_lifecycle_manifest(snapshot.manifest)
        except InstallConflictError as exc:
            return UpdateResult(exit_code=exc.exit_code, message=exc.message)

        mode = snapshot.manifest.effective_mode
        if mode == INSTALL_MODE_COMPOSITION:
            return self._update_composition(project_root, snapshot, request)
        return self._update_legacy(project_root, snapshot, request)

    def _update_legacy(
        self,
        project_root: Path,
        snapshot: ManifestSnapshot,
        request: UpdateRequest,
    ) -> UpdateResult:
        running_version = get_version()
        profile = snapshot.manifest.profile

        if not validate_profile_name(profile):
            return UpdateResult(
                exit_code=InstallSelectionError.exit_code,
                message=(
                    "Installed profile {} is not available in the running EKP package.".format(
                        profile
                    )
                ),
            )

        assembly_result = None
        try:
            assembly_result = self.assembly.assemble(
                AssemblyRequest(profile=profile, verify=True, clean=True)
            )
            inventory = self._inventory_to_map(
                self.deploy.inventory_bundle(assembly_result.bundle_path)
            )
            plan = build_update_plan(
                project_root=project_root,
                snapshot=snapshot,
                running_version=running_version,
                inventory=inventory,
                bundle_path=assembly_result.bundle_path,
                dry_run=request.dry_run,
            )
            return self._finish_update(plan, request)
        except InstallAssemblyError as exc:
            return UpdateResult(exit_code=exc.exit_code, message=exc.message)
        finally:
            if assembly_result is not None and assembly_result._temp_ctx is not None:
                assembly_result._temp_ctx.cleanup()

    def _update_composition(
        self,
        project_root: Path,
        snapshot: ManifestSnapshot,
        request: UpdateRequest,
    ) -> UpdateResult:
        running_version = get_version()
        registry = ComponentRegistry.load(get_ekp_root())
        expected_hash = snapshot.manifest.configuration_sha256

        try:
            store = ProjectConfigStore(project_root, registry=registry)
            if not store.exists():
                return UpdateResult(
                    exit_code=InstallSelectionError.exit_code,
                    message=(
                        "Composition update requires .ekp/project.yaml.\n"
                        "The project configuration file is missing."
                    ),
                )
            config_snapshot = store.load_snapshot()
            if config_snapshot is None:
                return UpdateResult(
                    exit_code=InstallSelectionError.exit_code,
                    message=(
                        "Composition update requires .ekp/project.yaml.\n"
                        "The project configuration file is missing."
                    ),
                )
        except ProjectConfigError as exc:
            return UpdateResult(
                exit_code=InstallSelectionError.exit_code,
                message="Invalid project configuration: {}".format(exc),
            )

        if config_snapshot.configuration_sha256 != expected_hash:
            return UpdateResult(
                exit_code=InstallConflictError.exit_code,
                message=_COMPOSITION_DRIFT_MESSAGE,
            )

        try:
            reloaded = store.load_snapshot()
            if reloaded is None or reloaded.configuration_sha256 != expected_hash:
                return UpdateResult(
                    exit_code=InstallConflictError.exit_code,
                    message=_COMPOSITION_DRIFT_MESSAGE,
                )
            config = reloaded.config
        except ProjectConfigError as exc:
            return UpdateResult(
                exit_code=InstallSelectionError.exit_code,
                message="Invalid project configuration: {}".format(exc),
            )

        assistants = list(config.assistants) or ["cursor"]
        if assistants != ["cursor"]:
            return UpdateResult(
                exit_code=InstallSelectionError.exit_code,
                message="Composition update supports only assistants=['cursor'] in v0.18.",
            )

        assembly_result = None
        try:
            assembly_result = self.assembly.assemble_composition(
                CompositionAssemblyRequest(
                    components=list(config.components),
                    outputs=assistants,
                    verify=True,
                    clean=True,
                )
            )
            inventory = self._inventory_to_map(
                self.deploy.inventory_bundle(assembly_result.bundle_path)
            )
            plan = build_update_plan(
                project_root=project_root,
                snapshot=snapshot,
                running_version=running_version,
                inventory=inventory,
                bundle_path=assembly_result.bundle_path,
                dry_run=request.dry_run,
                expected_configuration_sha256=expected_hash,
            )
            return self._finish_update(plan, request)
        except InstallAssemblyError as exc:
            return UpdateResult(exit_code=exc.exit_code, message=exc.message)
        finally:
            if assembly_result is not None and assembly_result._temp_ctx is not None:
                assembly_result._temp_ctx.cleanup()

    def _finish_update(self, plan: LifecyclePlan, request: UpdateRequest) -> UpdateResult:
        if plan.has_conflicts:
            return UpdateResult(
                exit_code=InstallConflictError.exit_code,
                message=render_update_conflict_message(plan),
            )

        if request.dry_run:
            return UpdateResult(exit_code=0, message=render_update_dry_run(plan))

        if not request.assume_yes and not _is_complete_noop(plan):
            self.output_fn(render_update_confirmation(plan))
            answer = self.input_fn("").strip().lower()
            if answer not in ("", "y", "yes"):
                raise UpdateCancelled()

        try:
            self.applier.apply_update(plan)
        except LifecycleConflictError as exc:
            return UpdateResult(exit_code=exc.exit_code, message=exc.message)
        except LifecycleRollbackError as exc:
            return UpdateResult(exit_code=exc.exit_code, message=exc.message)
        except InstallFilesystemError as exc:
            return UpdateResult(exit_code=exc.exit_code, message=exc.message)
        except InstallConflictError as exc:
            return UpdateResult(exit_code=exc.exit_code, message=exc.message)

        return UpdateResult(exit_code=0, message=render_update_success(plan))

    @staticmethod
    def _inventory_to_map(
        inventory: List[Tuple[str, Path, str]],
    ) -> BundleInventory:
        return {relative: (source, digest) for relative, source, digest in inventory}


def _is_complete_noop(plan: LifecyclePlan) -> bool:
    return (
        plan.create_count == 0
        and plan.write_count == 0
        and plan.delete_count == 0
        and not plan.commit_manifest
    )


def build_update_plan(
    project_root: Path,
    snapshot: ManifestSnapshot,
    running_version: str,
    inventory: BundleInventory,
    bundle_path: Path,
    *,
    dry_run: bool = False,
    expected_configuration_sha256: Optional[str] = None,
) -> LifecyclePlan:
    project_root = project_root.resolve()
    manifest = snapshot.manifest
    old_by_path = manifest.managed_by_path()
    old_inventory = {path: item.sha256 for path, item in old_by_path.items()}
    new_by_path = {relative: digest for relative, (_, digest) in inventory.items()}
    same_version = manifest.ekp_version == running_version

    if same_version:
        if old_inventory != new_by_path:
            raise InstallAssemblyError(
                "Installed bundle content does not match ownership manifest for this version."
            )

    conflicts: List[str] = []
    operations: List[LifecycleFileOperation] = []

    for relative in (".cursor", ".cursor/rules", ".ekp"):
        message = check_symlink_boundary(project_root, relative)
        if message:
            conflicts.append(message)

    all_paths = sorted(set(old_by_path) | set(new_by_path))
    for relative in all_paths:
        old_sha = old_by_path[relative].sha256 if relative in old_by_path else None
        new_entry = inventory.get(relative)
        new_sha = new_entry[1] if new_entry else None
        source_path = new_entry[0] if new_entry else None

        boundary = check_symlink_boundary(project_root, relative)
        if boundary:
            conflicts.append(boundary)
            operations.append(_noop_operation(relative, old_sha))
            continue

        try:
            target = resolve_under_root(project_root, relative)
        except ValueError as exc:
            conflicts.append(str(exc))
            operations.append(_noop_operation(relative, old_sha))
            continue

        disk_exists = target.exists()
        disk_symlink = target.is_symlink() if disk_exists else False
        disk_sha = sha256_file(target) if disk_exists and not disk_symlink else None

        if disk_symlink:
            conflicts.append("Symlink target not managed safely: {}".format(relative))
            operations.append(_noop_operation(relative, old_sha))
            continue

        op = _classify_update_operation(
            relative=relative,
            old_sha=old_sha,
            new_sha=new_sha,
            source_path=source_path,
            disk_exists=disk_exists,
            disk_sha=disk_sha,
        )
        if op is None:
            if old_sha is None and new_sha is not None:
                conflicts.append("Unmanaged file blocks update: {}".format(relative))
            else:
                conflicts.append("Managed file modified by user: {}".format(relative))
            operations.append(_noop_operation(relative, old_sha))
        else:
            operations.append(op)

    directories_to_create = _directories_to_create(project_root, operations)
    cross_version = manifest.ekp_version != running_version
    commit_manifest = cross_version

    new_manifest = None
    if commit_manifest:
        new_manifest = _build_new_manifest(
            manifest=manifest,
            running_version=running_version,
            inventory=inventory,
            directories_to_create=directories_to_create,
            existing_directories=set(manifest.created_directories),
            project_root=project_root,
        )

    return LifecyclePlan(
        project_root=project_root,
        profile=manifest.profile,
        old_version=manifest.ekp_version,
        new_version=running_version,
        adapter=CURSOR_ADAPTER,
        mode="update",
        operations=operations,
        conflicts=conflicts,
        directories_to_create=directories_to_create,
        manifest_sha256=snapshot.sha256,
        commit_manifest=commit_manifest,
        new_manifest=new_manifest,
        bundle_path=bundle_path,
        dry_run=dry_run,
        expected_configuration_sha256=expected_configuration_sha256,
    )


def _noop_operation(relative: str, old_sha: Optional[str]) -> LifecycleFileOperation:
    return LifecycleFileOperation(
        relative_path=relative,
        kind=LifecycleOpKind.NOOP,
        previous_sha256=old_sha,
        adapter=CURSOR_ADAPTER,
    )


def _classify_update_operation(
    *,
    relative: str,
    old_sha: Optional[str],
    new_sha: Optional[str],
    source_path: Optional[Path],
    disk_exists: bool,
    disk_sha: Optional[str],
) -> Optional[LifecycleFileOperation]:
    if old_sha is not None and new_sha is not None:
        if old_sha == new_sha:
            if not disk_exists:
                return LifecycleFileOperation(
                    relative_path=relative,
                    kind=LifecycleOpKind.CREATE,
                    previous_sha256=None,
                    expected_sha256=new_sha,
                    source_path=source_path,
                    adapter=CURSOR_ADAPTER,
                )
            if disk_sha == old_sha:
                return _noop_operation(relative, old_sha)
            return None

        if not disk_exists:
            return LifecycleFileOperation(
                relative_path=relative,
                kind=LifecycleOpKind.CREATE,
                previous_sha256=None,
                expected_sha256=new_sha,
                source_path=source_path,
                adapter=CURSOR_ADAPTER,
            )
        if disk_sha == old_sha:
            return LifecycleFileOperation(
                relative_path=relative,
                kind=LifecycleOpKind.WRITE,
                previous_sha256=old_sha,
                expected_sha256=new_sha,
                source_path=source_path,
                adapter=CURSOR_ADAPTER,
            )
        return None

    if old_sha is None and new_sha is not None:
        if not disk_exists:
            return LifecycleFileOperation(
                relative_path=relative,
                kind=LifecycleOpKind.CREATE,
                previous_sha256=None,
                expected_sha256=new_sha,
                source_path=source_path,
                adapter=CURSOR_ADAPTER,
            )
        return None

    if old_sha is not None and new_sha is None:
        if not disk_exists:
            return _noop_operation(relative, old_sha)
        if disk_sha == old_sha:
            return LifecycleFileOperation(
                relative_path=relative,
                kind=LifecycleOpKind.DELETE,
                previous_sha256=old_sha,
                expected_sha256=None,
                source_path=None,
                adapter=CURSOR_ADAPTER,
            )
        return None

    return _noop_operation(relative, old_sha)


def _directories_to_create(
    project_root: Path, operations: List[LifecycleFileOperation]
) -> List[str]:
    needed: Set[str] = set()
    for operation in operations:
        if operation.kind != LifecycleOpKind.CREATE:
            continue
        parent = Path(operation.relative_path).parent
        current = parent
        while current.as_posix() not in (".", ""):
            needed.add(current.as_posix())
            current = current.parent

    created: List[str] = []
    for relative in sorted(needed, key=lambda path: path.count("/")):
        boundary = check_symlink_boundary(project_root, relative)
        if boundary:
            continue
        try:
            target = resolve_under_root(project_root, relative)
        except ValueError:
            continue
        if not target.exists():
            created.append(relative)
    return created


def _build_new_manifest(
    *,
    manifest: InstallManifest,
    running_version: str,
    inventory: BundleInventory,
    directories_to_create: List[str],
    existing_directories: Set[str],
    project_root: Path,
) -> InstallManifest:
    managed_files = [
        ManagedFile(relative_path=relative, adapter=CURSOR_ADAPTER, sha256=digest)
        for relative, (_, digest) in sorted(inventory.items())
    ]

    newly_created = []
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

    created_directories = sorted(existing_directories | set(newly_created))

    return InstallManifest(
        schema_version=manifest.schema_version,
        ekp_version=running_version,
        profile=manifest.profile,
        adapters=list(manifest.adapters),
        installed_at=manifest.installed_at,
        install_root=manifest.install_root,
        managed_files=managed_files,
        created_directories=created_directories,
        mode=manifest.mode,
        configuration_sha256=manifest.configuration_sha256,
    )
