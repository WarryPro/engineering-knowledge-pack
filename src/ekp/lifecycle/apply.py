"""Transactional lifecycle file operations."""

from __future__ import annotations

import os
import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

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
        if not plan.manifest_sha256:
            raise InstallFilesystemError("Uninstall plan is missing manifest fingerprint.")

        backup_root = Path(tempfile.mkdtemp(prefix="ekp-lifecycle-"))
        deleted: List[_DeletedFile] = []

        try:
            for operation in plan.operations:
                if operation.kind == LifecycleOpKind.NOOP:
                    continue
                if operation.kind == LifecycleOpKind.DELETE:
                    self._apply_delete(plan.project_root, operation, backup_root, deleted)

            self._remove_manifest(plan)
            shutil.rmtree(backup_root, ignore_errors=True)
            warnings = self._cleanup_directories(plan)
            return UninstallApplyResult(warnings=warnings)
        except InstallConflictError:
            if self._rollback_deleted(plan.project_root, deleted):
                shutil.rmtree(backup_root, ignore_errors=True)
            else:
                raise LifecycleRollbackError(
                    self._rollback_incomplete_message(backup_root)
                )
            raise
        except OSError as exc:
            if not self._rollback_deleted(plan.project_root, deleted):
                raise LifecycleRollbackError(
                    self._rollback_incomplete_message(backup_root, exc)
                ) from exc
            shutil.rmtree(backup_root, ignore_errors=True)
            raise InstallFilesystemError("Uninstall failed: {}".format(exc)) from exc
        except Exception:
            if not self._rollback_deleted(plan.project_root, deleted):
                raise LifecycleRollbackError(self._rollback_incomplete_message(backup_root))
            shutil.rmtree(backup_root, ignore_errors=True)
            raise

    def _apply_delete(
        self,
        project_root: Path,
        operation: LifecycleFileOperation,
        backup_root: Path,
        deleted: List[_DeletedFile],
    ) -> None:
        relative = operation.relative_path
        target = self._validate_delete_target(
            project_root, relative, operation.previous_sha256
        )
        if target is None:
            return

        backup_path = backup_root / relative.replace("/", os.sep)
        backup_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(target, backup_path)
        if sha256_file(backup_path) != operation.previous_sha256:
            raise InstallFilesystemError(
                "Backup verification failed for {}".format(relative)
            )

        target = self._validate_delete_target(
            project_root, relative, operation.previous_sha256
        )
        if target is None:
            raise LifecycleConflictError(
                "Managed file changed before uninstall could complete: {}".format(relative)
            )

        target.unlink()
        deleted.append(
            _DeletedFile(
                relative_path=relative,
                backup_path=backup_path,
                expected_sha256=operation.previous_sha256,
            )
        )

    def _validate_delete_target(
        self,
        project_root: Path,
        relative: str,
        expected_sha256: Optional[str],
    ) -> Optional[Path]:
        boundary = check_symlink_boundary(project_root, relative)
        if boundary:
            raise LifecycleConflictError(boundary)

        target = resolve_under_root(project_root, relative)

        if not target.exists():
            return None

        if target.is_symlink():
            raise LifecycleConflictError(
                "Refusing to delete symlink target: {}".format(relative)
            )

        current_sha = sha256_file(target)
        if current_sha != expected_sha256:
            raise LifecycleConflictError(
                "Managed file changed before uninstall could complete: {}".format(relative)
            )

        return target

    def _remove_manifest(self, plan: LifecyclePlan) -> None:
        ManifestStore(plan.project_root).delete(expected_sha256=plan.manifest_sha256)

    def _rollback_deleted(self, project_root: Path, deleted: List[_DeletedFile]) -> bool:
        restored_all = True
        for item in reversed(deleted):
            boundary = check_symlink_boundary(project_root, item.relative_path)
            if boundary:
                restored_all = False
                continue

            try:
                target = resolve_under_root(project_root, item.relative_path)
            except ValueError:
                restored_all = False
                continue

            if target.exists() or target.is_symlink():
                restored_all = False
                continue

            try:
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(item.backup_path, target)
                if sha256_file(target) != item.expected_sha256:
                    restored_all = False
            except OSError:
                restored_all = False
        return restored_all

    def _rollback_incomplete_message(
        self, backup_root: Path, exc: Optional[OSError] = None
    ) -> str:
        message = (
            "Uninstall failed and rollback incomplete. "
            "Recovery data preserved at: {}".format(backup_root)
        )
        if exc is not None:
            return "{} ({})".format(message, exc)
        return message

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
