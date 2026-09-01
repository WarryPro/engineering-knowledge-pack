"""Uninstall orchestration service."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable, List, Optional, Set

from ekp.install.cursor_deploy import sha256_file
from ekp.install.errors import InstallConflictError, InstallError, InstallFilesystemError
from ekp.install.manifest import InstallManifest, ManifestStore
from ekp.install.paths import check_symlink_boundary, relative_posix_path, resolve_under_root
from ekp.lifecycle.apply import (
    LifecycleConflictError,
    LifecycleRollbackError,
    TransactionApplier,
)
from ekp.lifecycle.plan import LifecycleFileOperation, LifecycleOpKind, LifecyclePlan
from ekp.lifecycle.render import (
    render_uninstall_confirmation,
    render_uninstall_conflict_message,
    render_uninstall_dry_run,
    render_uninstall_success,
)

CURSOR_ADAPTER = "cursor"
SUPPORTED_LIFECYCLE_ADAPTERS: Set[str] = {CURSOR_ADAPTER}


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
    ):
        self.applier = applier or TransactionApplier()
        self.input_fn = input_fn
        self.output_fn = output_fn

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

        manifest = manifest_store.load()
        if manifest is None:
            return UninstallResult(
                exit_code=0,
                message="EKP is not installed in this project.",
            )

        try:
            validate_lifecycle_manifest(manifest)
        except InstallConflictError as exc:
            return UninstallResult(exit_code=exc.exit_code, message=exc.message)

        plan = build_uninstall_plan(project_root, manifest, dry_run=request.dry_run)

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


def validate_lifecycle_manifest(manifest: InstallManifest) -> None:
    if manifest.install_root != ".":
        raise InstallConflictError(
            "Unsupported install_root in ownership manifest: {}".format(manifest.install_root)
        )

    adapter_set = set(manifest.adapters)
    if adapter_set != SUPPORTED_LIFECYCLE_ADAPTERS:
        raise InstallConflictError(
            "Lifecycle uninstall supports Cursor-only Consumer CLI installations."
        )


def build_uninstall_plan(
    project_root: Path,
    manifest: InstallManifest,
    *,
    dry_run: bool = False,
) -> LifecyclePlan:
    project_root = project_root.resolve()
    conflicts: List[str] = []
    operations: List[LifecycleFileOperation] = []
    directories_to_remove: List[str] = []

    for relative in (".cursor", ".cursor/rules", ".ekp"):
        message = check_symlink_boundary(project_root, relative)
        if message:
            conflicts.append(message)

    for managed in manifest.managed_files:
        relative = managed.relative_path
        boundary = check_symlink_boundary(project_root, relative)
        if boundary:
            conflicts.append(boundary)
            operations.append(
                LifecycleFileOperation(
                    relative_path=relative,
                    kind=LifecycleOpKind.NOOP,
                    previous_sha256=managed.sha256,
                    adapter=managed.adapter,
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
                    previous_sha256=managed.sha256,
                    adapter=managed.adapter,
                )
            )
            continue

        if not target.exists():
            operations.append(
                LifecycleFileOperation(
                    relative_path=relative,
                    kind=LifecycleOpKind.NOOP,
                    previous_sha256=managed.sha256,
                    adapter=managed.adapter,
                )
            )
            continue

        if target.is_symlink():
            conflicts.append("Symlink target not managed safely: {}".format(relative))
            operations.append(
                LifecycleFileOperation(
                    relative_path=relative,
                    kind=LifecycleOpKind.NOOP,
                    previous_sha256=managed.sha256,
                    adapter=managed.adapter,
                )
            )
            continue

        disk_sha = sha256_file(target)
        if disk_sha == managed.sha256:
            operations.append(
                LifecycleFileOperation(
                    relative_path=relative,
                    kind=LifecycleOpKind.DELETE,
                    previous_sha256=managed.sha256,
                    adapter=managed.adapter,
                )
            )
        else:
            conflicts.append("Managed file modified by user: {}".format(relative))
            operations.append(
                LifecycleFileOperation(
                    relative_path=relative,
                    kind=LifecycleOpKind.NOOP,
                    previous_sha256=managed.sha256,
                    adapter=managed.adapter,
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
        adapter=CURSOR_ADAPTER,
        mode="uninstall",
        operations=operations,
        conflicts=conflicts,
        directories_to_remove=sorted(set(directories_to_remove)),
        dry_run=dry_run,
    )
