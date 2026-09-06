"""Shared managed-file deployment planner and applier."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

from ekp.install.atomic import ExclusiveTempFile, exclusive_create_from_temp
from ekp.install.deploy.hashing import sha256_file
from ekp.install.deploy.models import DesiredManagedFile
from ekp.install.errors import InstallAssemblyError, InstallConflictError, InstallFilesystemError
from ekp.install.manifest import ManagedFile
from ekp.install.paths import check_symlink_boundary, relative_posix_path, resolve_under_root
from ekp.install.plan import FileOpKind, FileOperation, InstallPlan


@dataclass
class AppliedManagedFiles:
    """Result of writing managed adapter files without an ownership manifest."""

    created_files: List[Path] = field(default_factory=list)
    created_dirs: List[Path] = field(default_factory=list)
    preexisting_dirs: set = field(default_factory=set)
    managed_files: List[ManagedFile] = field(default_factory=list)
    created_directory_names: List[str] = field(default_factory=list)


class SharedDeploymentEngine:
    """Generic DesiredManagedFile[] planner / applier (assistant-agnostic)."""

    def normalize_desired_files(
        self, desired: Sequence[DesiredManagedFile]
    ) -> List[DesiredManagedFile]:
        """Validate paths, reject duplicates, return deterministic inventory."""
        validated: List[DesiredManagedFile] = []
        seen_paths: Dict[str, DesiredManagedFile] = {}

        for item in desired:
            try:
                relative = relative_posix_path(item.relative_path)
            except ValueError as exc:
                raise InstallAssemblyError(
                    "Unsafe desired managed path: {}".format(item.relative_path)
                ) from exc
            if Path(item.relative_path).is_absolute():
                raise InstallAssemblyError(
                    "Absolute desired managed path is not allowed: {}".format(
                        item.relative_path
                    )
                )
            if relative != item.relative_path:
                raise InstallAssemblyError(
                    "Desired managed path must be normalized POSIX: {}".format(
                        item.relative_path
                    )
                )
            if not item.adapter:
                raise InstallAssemblyError("DesiredManagedFile.adapter must be non-empty")
            if not item.sha256:
                raise InstallAssemblyError(
                    "DesiredManagedFile.sha256 must be non-empty for {}".format(relative)
                )

            prior = seen_paths.get(relative)
            if prior is not None:
                if prior.adapter == item.adapter:
                    raise InstallAssemblyError(
                        "Duplicate desired target for adapter {}: {}".format(
                            item.adapter, relative
                        )
                    )
                raise InstallConflictError(
                    "Cross-adapter desired target conflict: {} ({} vs {})".format(
                        relative, prior.adapter, item.adapter
                    )
                )
            seen_paths[relative] = item
            validated.append(item)

        return sorted(validated, key=lambda item: (item.relative_path, item.adapter))

    def plan_first_install(
        self,
        project_root: Path,
        desired: Sequence[DesiredManagedFile],
    ) -> Tuple[List[FileOperation], List[str]]:
        operations: List[FileOperation] = []
        conflicts: List[str] = []
        inventory = self.normalize_desired_files(desired)

        for item in inventory:
            boundary = check_symlink_boundary(project_root, item.relative_path)
            if boundary:
                conflicts.append(boundary)
                continue
            target = resolve_under_root(project_root, item.relative_path)
            if target.exists() or target.is_symlink():
                conflicts.append(item.relative_path)
                continue
            operations.append(
                FileOperation(
                    relative_path=item.relative_path,
                    kind=FileOpKind.CREATE,
                    source_path=item.source_path,
                    expected_sha256=item.sha256,
                    adapter=item.adapter,
                )
            )
        return operations, conflicts

    def plan_reinstall(
        self,
        project_root: Path,
        desired: Sequence[DesiredManagedFile],
        managed_by_path: Dict[str, ManagedFile],
    ) -> Tuple[List[FileOperation], List[str]]:
        operations: List[FileOperation] = []
        conflicts: List[str] = []
        inventory = self.normalize_desired_files(desired)

        expected_paths = {item.relative_path for item in inventory}
        manifest_paths = set(managed_by_path)
        if expected_paths != manifest_paths:
            raise InstallAssemblyError(
                "Installed bundle content does not match ownership manifest for this version."
            )

        for item in inventory:
            boundary = check_symlink_boundary(project_root, item.relative_path)
            if boundary:
                conflicts.append(boundary)
                continue
            target = resolve_under_root(project_root, item.relative_path)
            owned = managed_by_path[item.relative_path]
            if owned.sha256 != item.sha256:
                raise InstallAssemblyError(
                    "Internal consistency failure for {}: manifest hash differs from bundle.".format(
                        item.relative_path
                    )
                )

            if not target.exists():
                operations.append(
                    FileOperation(
                        relative_path=item.relative_path,
                        kind=FileOpKind.RESTORE,
                        source_path=item.source_path,
                        expected_sha256=item.sha256,
                        adapter=item.adapter,
                    )
                )
                continue

            if target.is_symlink():
                conflicts.append(
                    "Symlink target not managed safely: {}".format(item.relative_path)
                )
                continue

            disk_digest = sha256_file(target)
            if disk_digest == item.sha256:
                operations.append(
                    FileOperation(
                        relative_path=item.relative_path,
                        kind=FileOpKind.NOOP,
                        source_path=item.source_path,
                        expected_sha256=item.sha256,
                        adapter=item.adapter,
                    )
                )
            else:
                conflicts.append(
                    "Managed file modified by user: {}".format(item.relative_path)
                )

        return operations, conflicts

    def directories_to_create(
        self, project_root: Path, operations: Iterable[FileOperation]
    ) -> List[str]:
        needed = set()
        for operation in operations:
            if operation.kind == FileOpKind.NOOP:
                continue
            parent = Path(operation.relative_path).parent.as_posix()
            if parent and parent != ".":
                needed.add(parent)
        # Touch resolve for safety; do not filter on existence (parity with v0.18).
        for relative in sorted(needed):
            resolve_under_root(project_root, relative)
        return sorted(needed)

    def apply_managed_files(
        self,
        plan: InstallPlan,
        *,
        extra_directories: Optional[Iterable[str]] = None,
        rollback_on_error: bool = True,
    ) -> AppliedManagedFiles:
        """Create directories and write managed files (no ``install.json``)."""
        if plan.has_conflicts:
            raise InstallConflictError("Cannot apply install plan with conflicts.")
        if plan.dry_run:
            raise InstallFilesystemError("Dry-run plans cannot be applied.")

        directory_relatives = list(plan.directories_to_create)
        for item in extra_directories or ():
            if item not in directory_relatives:
                directory_relatives.append(item)

        created_files: List[Path] = []
        created_dirs: List[Path] = []
        preexisting_dirs = {
            resolve_under_root(plan.project_root, item)
            for item in directory_relatives
            if resolve_under_root(plan.project_root, item).exists()
        }

        try:
            for relative in directory_relatives:
                target_dir = resolve_under_root(plan.project_root, relative)
                existed = target_dir.exists()
                target_dir.mkdir(parents=True, exist_ok=True)
                if not existed:
                    created_dirs.append(target_dir)

            for operation in plan.files_to_write:
                target = resolve_under_root(plan.project_root, operation.relative_path)
                if target.is_symlink():
                    raise InstallConflictError(
                        "Refusing to write through symlink: {}".format(operation.relative_path)
                    )
                if operation.source_path is None:
                    raise InstallFilesystemError(
                        "Missing source for {}".format(operation.relative_path)
                    )

                existed = target.exists()
                if operation.kind == FileOpKind.CREATE:
                    if existed or target.is_symlink():
                        raise InstallConflictError(
                            "Refusing to overwrite unexpected target: {}".format(
                                operation.relative_path
                            )
                        )
                elif operation.kind == FileOpKind.RESTORE:
                    if existed or target.is_symlink():
                        raise InstallConflictError(
                            "Restore target appeared before apply: {}".format(
                                operation.relative_path
                            )
                        )

                temp = ExclusiveTempFile.create(target.parent)
                try:
                    temp.write_from_source(operation.source_path)
                    if sha256_file(temp.path) != operation.expected_sha256:
                        raise InstallFilesystemError(
                            "Temp file verification failed for {}".format(
                                operation.relative_path
                            )
                        )
                    if operation.kind == FileOpKind.CREATE:
                        temp.close_fd()
                        try:
                            exclusive_create_from_temp(temp.path, target)
                        except FileExistsError as exc:
                            raise InstallConflictError(
                                "Refusing to overwrite unexpected target: {}".format(
                                    operation.relative_path
                                )
                            ) from exc
                        temp.path = None
                    else:
                        temp.commit(target)
                except Exception:
                    temp.cleanup()
                    raise
                if not existed:
                    created_files.append(target)

            managed_files = [
                ManagedFile(
                    relative_path=op.relative_path,
                    adapter=op.adapter,
                    sha256=op.expected_sha256,
                )
                for op in plan.operations
            ]
            # Created dirs come from resolve_under_root (canonical). Relative conversion
            # must use the same resolved project-root spelling so Windows short/long
            # aliases and other equivalent path forms remain containable.
            canonical_project_root = plan.project_root.resolve()
            created_directory_names = [
                relative_posix_path(
                    str(path.relative_to(canonical_project_root)).replace("\\", "/")
                )
                for path in created_dirs
            ]
            return AppliedManagedFiles(
                created_files=created_files,
                created_dirs=created_dirs,
                preexisting_dirs=preexisting_dirs,
                managed_files=managed_files,
                created_directory_names=sorted(set(created_directory_names)),
            )
        except OSError as exc:
            if rollback_on_error:
                self.rollback(created_files, created_dirs, preexisting_dirs)
            raise InstallFilesystemError("Installation failed: {}".format(exc)) from exc
        except Exception:
            if rollback_on_error:
                self.rollback(created_files, created_dirs, preexisting_dirs)
            raise

    def rollback(
        self,
        created_files: List[Path],
        created_dirs: List[Path],
        preexisting_dirs: set,
    ) -> None:
        for path in reversed(created_files):
            try:
                if path.exists():
                    path.unlink()
            except OSError:
                pass
        for path in reversed(created_dirs):
            if path in preexisting_dirs:
                continue
            try:
                if path.exists() and path.is_dir() and not any(path.iterdir()):
                    path.rmdir()
            except OSError:
                pass
