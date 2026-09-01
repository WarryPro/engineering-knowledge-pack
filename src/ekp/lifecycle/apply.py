"""Transactional lifecycle file operations."""

from __future__ import annotations

import os
import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import List

from ekp.install.cursor_deploy import sha256_file
from ekp.install.errors import InstallConflictError, InstallFilesystemError
from ekp.install.manifest import ManifestStore
from ekp.install.paths import check_symlink_boundary, resolve_under_root
from ekp.lifecycle.plan import LifecycleFileOperation, LifecycleOpKind, LifecyclePlan


class LifecycleConflictError(InstallConflictError):
    """Lifecycle ownership or concurrent-state conflict."""


class LifecycleRollbackError(InstallFilesystemError):
    """Lifecycle rollback could not fully restore project state."""

    def __init__(self, message: str):
        super().__init__(message)
        self.message = message


@dataclass
class UninstallApplyResult:
    warnings: List[str]


@dataclass
class _DeletedFile:
    relative_path: str
    backup_path: Path
    expected_sha256: str


class TransactionApplier:
    """Apply lifecycle plans with backup, revalidation, and rollback."""

    def apply_uninstall(self, plan: LifecyclePlan) -> UninstallApplyResult:
        if plan.has_conflicts:
            raise LifecycleConflictError("Cannot apply uninstall plan with conflicts.")
        if plan.dry_run:
            raise InstallFilesystemError("Dry-run plans cannot be applied.")

        backup_ctx = tempfile.TemporaryDirectory(prefix="ekp-lifecycle-")
        backup_root = Path(backup_ctx.name)
        deleted: List[_DeletedFile] = []

        try:
            for operation in plan.operations:
                if operation.kind == LifecycleOpKind.NOOP:
                    continue
                if operation.kind == LifecycleOpKind.DELETE:
                    self._apply_delete(plan.project_root, operation, backup_root, deleted)

            self._remove_manifest(plan.project_root)
            backup_ctx.cleanup()
            warnings = self._cleanup_directories(plan)
            return UninstallApplyResult(warnings=warnings)
        except LifecycleConflictError:
            self._rollback_deleted(plan.project_root, deleted)
            backup_ctx.cleanup()
            raise
        except OSError as exc:
            if not self._rollback_deleted(plan.project_root, deleted):
                backup_ctx.cleanup()
                raise LifecycleRollbackError(
                    "Uninstall failed and rollback incomplete: {}".format(exc)
                ) from exc
            backup_ctx.cleanup()
            raise InstallFilesystemError("Uninstall failed: {}".format(exc)) from exc
        except Exception:
            if not self._rollback_deleted(plan.project_root, deleted):
                backup_ctx.cleanup()
                raise LifecycleRollbackError("Uninstall failed and rollback incomplete.")
            backup_ctx.cleanup()
            raise

    def _apply_delete(
        self,
        project_root: Path,
        operation: LifecycleFileOperation,
        backup_root: Path,
        deleted: List[_DeletedFile],
    ) -> None:
        relative = operation.relative_path
        boundary = check_symlink_boundary(project_root, relative)
        if boundary:
            raise LifecycleConflictError(boundary)

        target = resolve_under_root(project_root, relative)

        if not target.exists():
            return

        if target.is_symlink():
            raise LifecycleConflictError(
                "Refusing to delete symlink target: {}".format(relative)
            )

        current_sha = sha256_file(target)
        if current_sha != operation.previous_sha256:
            raise LifecycleConflictError(
                "Managed file changed before uninstall could complete: {}".format(relative)
            )

        backup_path = backup_root / relative.replace("/", os.sep)
        backup_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(target, backup_path)
        if sha256_file(backup_path) != operation.previous_sha256:
            raise InstallFilesystemError(
                "Backup verification failed for {}".format(relative)
            )

        target.unlink()
        deleted.append(
            _DeletedFile(
                relative_path=relative,
                backup_path=backup_path,
                expected_sha256=operation.previous_sha256,
            )
        )

    def _remove_manifest(self, project_root: Path) -> None:
        ManifestStore(project_root).delete()

    def _rollback_deleted(self, project_root: Path, deleted: List[_DeletedFile]) -> bool:
        restored_all = True
        for item in reversed(deleted):
            target = resolve_under_root(project_root, item.relative_path)
            try:
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(item.backup_path, target)
                if sha256_file(target) != item.expected_sha256:
                    restored_all = False
            except OSError:
                restored_all = False
        return restored_all

    def _cleanup_directories(self, plan: LifecyclePlan) -> List[str]:
        warnings: List[str] = []
        candidates = sorted(
            plan.directories_to_remove,
            key=lambda path: path.count("/"),
            reverse=True,
        )
        for relative in candidates:
            boundary = check_symlink_boundary(plan.project_root, relative)
            if boundary:
                warnings.append(
                    "Skipped unsafe recorded directory cleanup: {}".format(relative)
                )
                continue
            try:
                target = resolve_under_root(plan.project_root, relative)
            except ValueError:
                warnings.append(
                    "Skipped unsafe recorded directory cleanup: {}".format(relative)
                )
                continue

            if not target.exists() or not target.is_dir():
                continue
            if target.is_symlink():
                warnings.append(
                    "Skipped symlinked recorded directory cleanup: {}".format(relative)
                )
                continue
            try:
                if not any(target.iterdir()):
                    target.rmdir()
            except OSError as exc:
                warnings.append(
                    "Could not remove empty directory {}: {}".format(relative, exc)
                )
        return warnings
