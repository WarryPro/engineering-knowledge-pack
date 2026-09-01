"""Transactional lifecycle file operations."""

from __future__ import annotations

import os
import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

from ekp.install.cursor_deploy import sha256_file
from ekp.install.errors import InstallAssemblyError, InstallConflictError, InstallFilesystemError
from ekp.install.manifest import InstallManifest, ManifestStore
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
class UpdateApplyResult:
    warnings: List[str]


@dataclass
class _CreatedFile:
    relative_path: str
    expected_sha256: str


@dataclass
class _WrittenFile:
    relative_path: str
    backup_path: Path
    previous_sha256: str
    expected_sha256: str


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

    def apply_update(self, plan: LifecyclePlan) -> UpdateApplyResult:
        if plan.has_conflicts:
            raise LifecycleConflictError("Cannot apply update plan with conflicts.")
        if plan.dry_run:
            raise InstallFilesystemError("Dry-run plans cannot be applied.")
        if not plan.manifest_sha256:
            raise InstallFilesystemError("Update plan is missing manifest fingerprint.")

        backup_root = Path(tempfile.mkdtemp(prefix="ekp-lifecycle-"))
        created: List[_CreatedFile] = []
        written: List[_WrittenFile] = []
        deleted: List[_DeletedFile] = []
        created_directories: List[str] = []

        try:
            self._create_directories(plan, created_directories)
            for operation in plan.operations:
                if operation.kind == LifecycleOpKind.NOOP:
                    continue
                if operation.kind == LifecycleOpKind.CREATE:
                    self._apply_create(plan, operation, created)
                elif operation.kind == LifecycleOpKind.WRITE:
                    self._apply_write(plan, operation, backup_root, written)
                elif operation.kind == LifecycleOpKind.DELETE:
                    self._apply_delete(plan.project_root, operation, backup_root, deleted)

            if plan.commit_manifest and plan.new_manifest is not None:
                manifest = self._finalize_new_manifest(plan, created_directories)
                ManifestStore(plan.project_root).replace(
                    manifest, expected_sha256=plan.manifest_sha256
                )

            shutil.rmtree(backup_root, ignore_errors=True)
            return UpdateApplyResult(warnings=[])
        except InstallConflictError:
            if self._rollback_update(plan.project_root, created, written, deleted):
                shutil.rmtree(backup_root, ignore_errors=True)
            else:
                raise LifecycleRollbackError(
                    self._rollback_incomplete_message(backup_root)
                )
            raise
        except OSError as exc:
            if not self._rollback_update(plan.project_root, created, written, deleted):
                raise LifecycleRollbackError(
                    self._rollback_incomplete_message(backup_root, exc)
                ) from exc
            shutil.rmtree(backup_root, ignore_errors=True)
            raise InstallFilesystemError("Update failed: {}".format(exc)) from exc
        except InstallAssemblyError:
            if not self._rollback_update(plan.project_root, created, written, deleted):
                raise LifecycleRollbackError(self._rollback_incomplete_message(backup_root))
            shutil.rmtree(backup_root, ignore_errors=True)
            raise
        except Exception:
            if not self._rollback_update(plan.project_root, created, written, deleted):
                raise LifecycleRollbackError(self._rollback_incomplete_message(backup_root))
            shutil.rmtree(backup_root, ignore_errors=True)
            raise

    def _create_directories(self, plan: LifecyclePlan, created_directories: List[str]) -> None:
        for relative in sorted(plan.directories_to_create, key=lambda path: path.count("/")):
            boundary = check_symlink_boundary(plan.project_root, relative)
            if boundary:
                raise LifecycleConflictError(boundary)
            target = resolve_under_root(plan.project_root, relative)
            if target.exists():
                if target.is_symlink():
                    raise LifecycleConflictError(
                        "Refusing to create under symlinked directory: {}".format(relative)
                    )
                continue
            target.mkdir()
            created_directories.append(relative)

    def _verify_source(self, plan: LifecyclePlan, operation: LifecycleFileOperation) -> Path:
        if operation.source_path is None:
            raise InstallAssemblyError(
                "Update source is missing for {}".format(operation.relative_path)
            )
        source = operation.source_path.resolve()
        if plan.bundle_path is not None:
            bundle_root = plan.bundle_path.resolve()
            try:
                source.relative_to(bundle_root)
            except ValueError as exc:
                raise InstallAssemblyError(
                    "Update source escapes bundle for {}".format(operation.relative_path)
                ) from exc
        if not source.is_file():
            raise InstallAssemblyError(
                "Update source is missing for {}".format(operation.relative_path)
            )
        if sha256_file(source) != operation.expected_sha256:
            raise InstallAssemblyError(
                "Update source changed for {}".format(operation.relative_path)
            )
        return source

    def _apply_create(
        self,
        plan: LifecyclePlan,
        operation: LifecycleFileOperation,
        created: List[_CreatedFile],
    ) -> None:
        relative = operation.relative_path
        boundary = check_symlink_boundary(plan.project_root, relative)
        if boundary:
            raise LifecycleConflictError(boundary)

        target = resolve_under_root(plan.project_root, relative)
        if target.exists() or target.is_symlink():
            raise LifecycleConflictError(
                "Managed file appeared before update could complete: {}".format(relative)
            )

        source = self._verify_source(plan, operation)
        if not target.parent.exists():
            raise InstallFilesystemError(
                "Parent directory missing for {}".format(relative)
            )
        shutil.copy2(source, target)
        if sha256_file(target) != operation.expected_sha256:
            raise InstallFilesystemError("Created file verification failed for {}".format(relative))

        created.append(
            _CreatedFile(
                relative_path=relative,
                expected_sha256=operation.expected_sha256,
            )
        )

    def _apply_write(
        self,
        plan: LifecyclePlan,
        operation: LifecycleFileOperation,
        backup_root: Path,
        written: List[_WrittenFile],
    ) -> None:
        relative = operation.relative_path
        target = self._validate_write_target(
            plan.project_root, relative, operation.previous_sha256
        )

        backup_path = backup_root / relative.replace("/", os.sep)
        backup_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(target, backup_path)
        if sha256_file(backup_path) != operation.previous_sha256:
            raise InstallFilesystemError(
                "Backup verification failed for {}".format(relative)
            )

        source = self._verify_source(plan, operation)

        target = self._validate_write_target(
            plan.project_root, relative, operation.previous_sha256
        )
        if target is None:
            raise LifecycleConflictError(
                "Managed file changed before update could complete: {}".format(relative)
            )

        temp_path = target.with_suffix(target.suffix + ".ekp.tmp")
        try:
            shutil.copy2(source, temp_path)
            if sha256_file(temp_path) != operation.expected_sha256:
                raise InstallFilesystemError(
                    "Temp file verification failed for {}".format(relative)
                )

            target = self._validate_write_target(
                plan.project_root, relative, operation.previous_sha256
            )
            if target is None:
                raise LifecycleConflictError(
                    "Managed file changed before update could complete: {}".format(relative)
                )

            os.replace(str(temp_path), str(target))
        finally:
            if temp_path.exists():
                temp_path.unlink(missing_ok=True)

        written.append(
            _WrittenFile(
                relative_path=relative,
                backup_path=backup_path,
                previous_sha256=operation.previous_sha256,
                expected_sha256=operation.expected_sha256,
            )
        )

    def _validate_write_target(
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
            raise LifecycleConflictError(
                "Managed file changed before update could complete: {}".format(relative)
            )
        if target.is_symlink():
            raise LifecycleConflictError(
                "Refusing to write symlink target: {}".format(relative)
            )

        current_sha = sha256_file(target)
        if current_sha != expected_sha256:
            raise LifecycleConflictError(
                "Managed file changed before update could complete: {}".format(relative)
            )
        return target

    def _finalize_new_manifest(
        self, plan: LifecyclePlan, created_directories: List[str]
    ) -> InstallManifest:
        manifest = plan.new_manifest
        if manifest is None:
            raise InstallFilesystemError("Update plan is missing new manifest.")
        merged = sorted(set(manifest.created_directories) | set(created_directories))
        return InstallManifest(
            schema_version=manifest.schema_version,
            ekp_version=manifest.ekp_version,
            profile=manifest.profile,
            adapters=list(manifest.adapters),
            installed_at=manifest.installed_at,
            install_root=manifest.install_root,
            managed_files=list(manifest.managed_files),
            created_directories=merged,
        )

    def _rollback_update(
        self,
        project_root: Path,
        created: List[_CreatedFile],
        written: List[_WrittenFile],
        deleted: List[_DeletedFile],
    ) -> bool:
        restored_all = self._rollback_deleted(project_root, deleted)
        restored_all = self._rollback_written(project_root, written) and restored_all
        restored_all = self._rollback_created(project_root, created) and restored_all
        return restored_all

    def _rollback_written(self, project_root: Path, written: List[_WrittenFile]) -> bool:
        restored_all = True
        for item in reversed(written):
            boundary = check_symlink_boundary(project_root, item.relative_path)
            if boundary:
                restored_all = False
                continue
            try:
                target = resolve_under_root(project_root, item.relative_path)
            except ValueError:
                restored_all = False
                continue
            if not target.exists() or target.is_symlink():
                restored_all = False
                continue
            if sha256_file(target) != item.expected_sha256:
                restored_all = False
                continue
            try:
                shutil.copy2(item.backup_path, target)
                if sha256_file(target) != item.previous_sha256:
                    restored_all = False
            except OSError:
                restored_all = False
        return restored_all

    def _rollback_created(self, project_root: Path, created: List[_CreatedFile]) -> bool:
        restored_all = True
        for item in reversed(created):
            boundary = check_symlink_boundary(project_root, item.relative_path)
            if boundary:
                restored_all = False
                continue
            try:
                target = resolve_under_root(project_root, item.relative_path)
            except ValueError:
                restored_all = False
                continue
            if not target.exists() or target.is_symlink():
                restored_all = False
                continue
            if sha256_file(target) != item.expected_sha256:
                restored_all = False
                continue
            try:
                target.unlink()
            except OSError:
                restored_all = False
        return restored_all

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
