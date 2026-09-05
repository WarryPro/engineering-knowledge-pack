"""Uninstall orchestration service."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable, List, Optional, Set

from ekp.install.deploy.hashing import sha256_file
from ekp.install.deploy.registry import DeployRegistry, build_default_deploy_registry
from ekp.install.errors import InstallConflictError, InstallError, InstallFilesystemError
from ekp.install.manifest import InstallManifest, ManifestStore
from ekp.install.paths import (
    check_symlink_boundary,
    relative_posix_path,
    resolve_under_root,
)
from ekp.lifecycle.apply import (
    LifecycleConflictError,
    LifecycleRollbackError,
    TransactionApplier,
)
from ekp.lifecycle.boundaries import lifecycle_symlink_check_paths
from ekp.lifecycle.plan import LifecycleFileOperation, LifecycleOpKind, LifecyclePlan
from ekp.lifecycle.render import (
    render_uninstall_confirmation,
    render_uninstall_conflict_message,
    render_uninstall_dry_run,
    render_uninstall_success,
)

CURSOR_ADAPTER = "cursor"


class UninstallCancelled(Exception):
    """User declined confirmation."""

    exit_code = 0


@dataclass
class UninstallRequest:
    path: str = "."
    assume_yes: bool = False
    dry_run: bool = False


@dataclass
class UninstallResult:
    exit_code: int
    message: str = ""


class UninstallService:
    """Consumer uninstall workflow."""

    def __init__(
        self,
        applier: Optional[TransactionApplier] = None,
        input_fn: Callable[[str], str] = input,
        output_fn: Callable[[str], None] = print,
        deploy_registry: Optional[DeployRegistry] = None,
    ):
        self.applier = applier or TransactionApplier()
        self.input_fn = input_fn
        self.output_fn = output_fn
        self._deploy_registry = deploy_registry

    def _registry(self) -> DeployRegistry:
        if self._deploy_registry is None:
            self._deploy_registry = build_default_deploy_registry()
        return self._deploy_registry

    def uninstall(self, request: UninstallRequest) -> UninstallResult:
        try:
            return self._uninstall(request)
        except UninstallCancelled:
            return UninstallResult(exit_code=0, message="Uninstall cancelled.")
        except InstallError as exc:
            return UninstallResult(exit_code=exc.exit_code, message=exc.message)

    def _uninstall(self, request: UninstallRequest) -> UninstallResult:
        from ekp.install.paths import resolve_project_root

        project_root = resolve_project_root(request.path)
        manifest_store = ManifestStore(project_root)

        if not manifest_store.exists():
            return UninstallResult(
                exit_code=0,
                message="EKP is not installed in this project.",
            )

        snapshot = manifest_store.load_with_fingerprint()
        if snapshot is None:
            return UninstallResult(
                exit_code=0,
                message="EKP is not installed in this project.",
            )

        manifest = snapshot.manifest

        try:
            validate_lifecycle_manifest(manifest, deploy_registry=self._registry())
        except InstallConflictError as exc:
            return UninstallResult(exit_code=exc.exit_code, message=exc.message)

        plan = build_uninstall_plan(
            project_root,
            manifest,
            manifest_sha256=snapshot.sha256,
            dry_run=request.dry_run,
        )

        if plan.has_conflicts:
            return UninstallResult(
                exit_code=InstallConflictError.exit_code,
                message=render_uninstall_conflict_message(plan),
            )

        if request.dry_run:
            return UninstallResult(exit_code=0, message=render_uninstall_dry_run(plan))

        if not request.assume_yes:
            self.output_fn(render_uninstall_confirmation(plan))
            answer = self.input_fn("").strip().lower()
            if answer not in ("", "y", "yes"):
                raise UninstallCancelled()

        try:
            apply_result = self.applier.apply_uninstall(plan)
        except LifecycleConflictError as exc:
            return UninstallResult(exit_code=exc.exit_code, message=exc.message)
        except LifecycleRollbackError as exc:
            return UninstallResult(exit_code=exc.exit_code, message=exc.message)
        except InstallFilesystemError as exc:
            return UninstallResult(exit_code=exc.exit_code, message=exc.message)

        return UninstallResult(
            exit_code=0,
            message=render_uninstall_success(plan, warnings=apply_result.warnings),
        )


def validate_lifecycle_manifest(
    manifest: InstallManifest,
    *,
    deploy_registry: Optional[DeployRegistry] = None,
) -> None:
    """Validate ownership manifest for status/update/uninstall.

    Capability SoT for composition adapters is ``DeployRegistry``.
    Legacy profiles remain Cursor-only.
    """
    from ekp.composition import PROJECT_COMPOSITION_PROFILE
    from ekp.install.manifest import (
        INSTALL_MODE_COMPOSITION,
        INSTALL_MODE_LEGACY_PROFILE,
    )

    registry = deploy_registry or build_default_deploy_registry()

    if manifest.install_root != ".":
        raise InstallConflictError(
            "Unsupported install_root in ownership manifest: {}".format(
                manifest.install_root
            )
        )

    mode = manifest.effective_mode
    if mode == INSTALL_MODE_COMPOSITION:
        _validate_composition_lifecycle_manifest(manifest, registry)
    elif mode == INSTALL_MODE_LEGACY_PROFILE:
        _validate_legacy_lifecycle_manifest(manifest)
    else:
        raise InstallConflictError(
            "Unsupported EKP install mode for lifecycle: {!r}".format(manifest.mode)
        )

    seen_paths: Set[str] = set()
    for item in manifest.managed_files:
        try:
            relative_posix_path(item.relative_path)
        except ValueError as exc:
            raise InstallConflictError(
                "Unsafe managed file path in ownership manifest: {}".format(
                    item.relative_path
                )
            ) from exc
        if item.relative_path in seen_paths:
            raise InstallConflictError(
                "Duplicate managed file in ownership manifest: {}".format(
                    item.relative_path
                )
            )
        seen_paths.add(item.relative_path)

        if item.adapter not in manifest.adapters:
            raise InstallConflictError(
                "Managed file adapter is not listed in manifest.adapters: {}".format(
                    item.relative_path
                )
            )
        if not registry.is_supported(item.adapter):
            raise InstallConflictError(
                "Managed file adapter is not supported by DeployRegistry: {}".format(
                    item.adapter
                )
            )


def _validate_legacy_lifecycle_manifest(manifest: InstallManifest) -> None:
    adapter_set = set(manifest.adapters)
    if adapter_set != {CURSOR_ADAPTER}:
        raise InstallConflictError(
            "Legacy-profile lifecycle requires adapters=['cursor'] only."
        )
    for item in manifest.managed_files:
        if item.adapter != CURSOR_ADAPTER:
            raise InstallConflictError(
                "Managed file adapter does not match legacy Cursor contract: {}".format(
                    item.relative_path
                )
            )


def _validate_composition_lifecycle_manifest(
    manifest: InstallManifest,
    registry: DeployRegistry,
) -> None:
    from ekp.composition import PROJECT_COMPOSITION_PROFILE

    if manifest.profile != PROJECT_COMPOSITION_PROFILE:
        raise InstallConflictError(
            "Composition lifecycle requires profile {!r}, found {!r}".format(
                PROJECT_COMPOSITION_PROFILE, manifest.profile
            )
        )
    if not manifest.configuration_sha256:
        raise InstallConflictError(
            "Composition ownership manifest is missing configuration_sha256"
        )
    if not manifest.adapters:
        raise InstallConflictError(
            "Composition ownership manifest adapters must be non-empty"
        )
    if len(manifest.adapters) != len(set(manifest.adapters)):
        raise InstallConflictError(
            "Composition ownership manifest adapters must be unique"
        )
    for adapter in manifest.adapters:
        if not registry.is_supported(adapter):
            raise InstallConflictError(
                "Composition ownership manifest adapter is not supported by "
                "DeployRegistry: {}".format(adapter)
            )

    owned = {item.adapter for item in manifest.managed_files}
    declared = set(manifest.adapters)
    if owned != declared:
        raise InstallConflictError(
            "Composition ownership manifest adapters do not match managed file "
            "adapters (declared={}, owned={}).".format(
                sorted(declared), sorted(owned)
            )
        )


def build_uninstall_plan(
    project_root: Path,
    manifest: InstallManifest,
    *,
    manifest_sha256: Optional[str] = None,
    dry_run: bool = False,
) -> LifecyclePlan:
    project_root = project_root.resolve()
    conflicts: List[str] = []
    operations: List[LifecycleFileOperation] = []
    directories_to_remove: List[str] = []
    adapters = sorted(set(manifest.adapters))

    for relative in lifecycle_symlink_check_paths(adapters):
        message = check_symlink_boundary(project_root, relative)
        if message:
            conflicts.append(message)

    for managed in manifest.managed_files:
        relative = managed.relative_path
        adapter = managed.adapter
        boundary = check_symlink_boundary(project_root, relative)
        if boundary:
            conflicts.append(boundary)
            operations.append(
                LifecycleFileOperation(
                    relative_path=relative,
                    kind=LifecycleOpKind.NOOP,
                    adapter=adapter,
                    previous_sha256=managed.sha256,
                )
            )
            continue

        try:
            target = resolve_under_root(project_root, relative)
        except ValueError as exc:
            conflicts.append(str(exc))
            operations.append(
                LifecycleFileOperation(
                    relative_path=relative,
                    kind=LifecycleOpKind.NOOP,
                    adapter=adapter,
                    previous_sha256=managed.sha256,
                )
            )
            continue

        if not target.exists():
            operations.append(
                LifecycleFileOperation(
                    relative_path=relative,
                    kind=LifecycleOpKind.NOOP,
                    adapter=adapter,
                    previous_sha256=managed.sha256,
                )
            )
            continue

        if target.is_symlink():
            conflicts.append("Symlink target not managed safely: {}".format(relative))
            operations.append(
                LifecycleFileOperation(
                    relative_path=relative,
                    kind=LifecycleOpKind.NOOP,
                    adapter=adapter,
                    previous_sha256=managed.sha256,
                )
            )
            continue

        disk_sha = sha256_file(target)
        if disk_sha == managed.sha256:
            operations.append(
                LifecycleFileOperation(
                    relative_path=relative,
                    kind=LifecycleOpKind.DELETE,
                    adapter=adapter,
                    previous_sha256=managed.sha256,
                )
            )
        else:
            conflicts.append("Managed file modified by user: {}".format(relative))
            operations.append(
                LifecycleFileOperation(
                    relative_path=relative,
                    kind=LifecycleOpKind.NOOP,
                    adapter=adapter,
                    previous_sha256=managed.sha256,
                )
            )

    for relative in manifest.created_directories:
        try:
            normalized = relative_posix_path(relative)
        except ValueError:
            conflicts.append("Unsafe recorded directory in manifest: {}".format(relative))
            continue
        boundary = check_symlink_boundary(project_root, normalized)
        if boundary:
            conflicts.append("Unsafe recorded directory in manifest: {}".format(relative))
            continue
        directories_to_remove.append(normalized)

    return LifecyclePlan(
        project_root=project_root,
        profile=manifest.profile,
        old_version=manifest.ekp_version,
        new_version=None,
        adapters=adapters,
        mode="uninstall",
        operations=operations,
        conflicts=conflicts,
        directories_to_remove=sorted(set(directories_to_remove)),
        manifest_sha256=manifest_sha256,
        dry_run=dry_run,
    )
