"""Safe Cursor rule deployment."""

from __future__ import annotations

import hashlib
import os
import shutil
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

from ekp.install.errors import (
    InstallAssemblyError,
    InstallConflictError,
    InstallFilesystemError,
    InstallSelectionError,
)
from ekp.install.manifest import InstallManifest, ManagedFile, ManifestStore, utc_now_iso
from ekp.install.paths import check_symlink_boundary, relative_posix_path, resolve_under_root
from ekp.install.plan import FileOpKind, FileOperation, InstallPlan

CURSOR_RULES_DIR = ".cursor/rules"
CURSOR_ADAPTER = "cursor"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


class CursorDeployService:
    """Build and apply Cursor install plans from assembled bundles."""

    def inventory_bundle(self, bundle_path: Path) -> List[Tuple[str, Path, str]]:
        cursor_dir = bundle_path / "cursor"
        if not cursor_dir.is_dir():
            raise InstallAssemblyError(
                "Assembled bundle is missing cursor output: {}".format(cursor_dir)
            )

        items: List[Tuple[str, Path, str]] = []
        for source in sorted(cursor_dir.glob("*.mdc")):
            name = source.name
            if ".." in name or "/" in name or "\\" in name:
                raise InstallAssemblyError("Unsafe generated filename: {}".format(name))
            resolved = source.resolve()
            try:
                resolved.relative_to(cursor_dir.resolve())
            except ValueError as exc:
                raise InstallAssemblyError(
                    "Generated file escapes bundle cursor directory: {}".format(name)
                ) from exc
            relative_target = relative_posix_path("{}/{}".format(CURSOR_RULES_DIR, name))
            items.append((relative_target, source, sha256_file(source)))
        return items

    def build_plan(
        self,
        project_root: Path,
        bundle_path: Path,
        profile: str,
        ekp_version: str,
        existing_manifest: Optional[InstallManifest] = None,
        additional_concerns: Optional[Iterable[str]] = None,
        dry_run: bool = False,
    ) -> InstallPlan:
        project_root = project_root.resolve()
        inventory = self.inventory_bundle(bundle_path)
        conflicts: List[str] = []
        operations: List[FileOperation] = []

        self._validate_existing_manifest(existing_manifest, profile, ekp_version)

        for relative in (".cursor", CURSOR_RULES_DIR, ".ekp"):
            message = check_symlink_boundary(project_root, relative)
            if message:
                conflicts.append(message)

        expected_by_path = {relative: (source, digest) for relative, source, digest in inventory}

        if existing_manifest is None:
            operations, install_conflicts = self._plan_first_install(
                project_root, expected_by_path
            )
            conflicts.extend(install_conflicts)
        else:
            operations, install_conflicts = self._plan_reinstall(
                project_root, expected_by_path, existing_manifest
            )
            conflicts.extend(install_conflicts)

        directories_to_create = self._directories_to_create(project_root, operations)

        return InstallPlan(
            project_root=project_root,
            profile=profile,
            ekp_version=ekp_version,
            adapter=CURSOR_ADAPTER,
            bundle_path=bundle_path,
            rules_count=len(inventory),
            operations=operations,
            conflicts=conflicts,
            directories_to_create=directories_to_create,
            additional_concerns=list(additional_concerns or []),
            dry_run=dry_run,
        )

    def apply(self, plan: InstallPlan) -> InstallManifest:
        if plan.has_conflicts:
            raise InstallConflictError("Cannot apply install plan with conflicts.")
        if plan.dry_run:
            raise InstallFilesystemError("Dry-run plans cannot be applied.")

        created_files: List[Path] = []
        created_dirs: List[Path] = []
        preexisting_dirs = {
            resolve_under_root(plan.project_root, item)
            for item in plan.directories_to_create
            if resolve_under_root(plan.project_root, item).exists()
        }

        try:
            for relative in plan.directories_to_create:
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
                temp_path = target.with_suffix(target.suffix + ".ekp.tmp")
                shutil.copyfile(operation.source_path, temp_path)
                try:
                    with temp_path.open("rb") as handle:
                        try:
                            os.fsync(handle.fileno())
                        except OSError:
                            pass
                except OSError:
                    pass
                os.replace(str(temp_path), str(target))
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
            created_directory_names = [
                relative_posix_path(str(path.relative_to(plan.project_root)).replace("\\", "/"))
                for path in created_dirs
            ]
            manifest = InstallManifest(
                schema_version=1,
                ekp_version=plan.ekp_version,
                profile=plan.profile,
                adapters=[plan.adapter],
                installed_at=utc_now_iso(),
                install_root=".",
                managed_files=managed_files,
                created_directories=sorted(set(created_directory_names)),
            )
            ManifestStore(plan.project_root).save(manifest)
            return manifest
        except OSError as exc:
            self._rollback(created_files, created_dirs, preexisting_dirs)
            raise InstallFilesystemError("Installation failed: {}".format(exc)) from exc
        except Exception:
            self._rollback(created_files, created_dirs, preexisting_dirs)
            raise

    def _validate_existing_manifest(
        self,
        manifest: Optional[InstallManifest],
        profile: str,
        ekp_version: str,
    ) -> None:
        if manifest is None:
            return
        if manifest.profile != profile:
            raise InstallSelectionErrorProfileMismatch(manifest.profile)
        if manifest.ekp_version != ekp_version:
            raise InstallSelectionErrorVersionMismatch(manifest.ekp_version, ekp_version)
        if "cursor" not in manifest.adapters:
            raise InstallConflictError(
                "Existing install manifest does not include Cursor adapter ownership."
            )

    def _plan_first_install(
        self,
        project_root: Path,
        expected_by_path: Dict[str, Tuple[Path, str]],
    ) -> Tuple[List[FileOperation], List[str]]:
        operations: List[FileOperation] = []
        conflicts: List[str] = []

        for relative, (source, digest) in sorted(expected_by_path.items()):
            target = resolve_under_root(project_root, relative)
            boundary = check_symlink_boundary(project_root, relative)
            if boundary:
                conflicts.append(boundary)
                continue
            if target.exists() or target.is_symlink():
                conflicts.append(relative)
                continue
            operations.append(
                FileOperation(
                    relative_path=relative,
                    kind=FileOpKind.CREATE,
                    source_path=source,
                    expected_sha256=digest,
                )
            )
        return operations, conflicts

    def _plan_reinstall(
        self,
        project_root: Path,
        expected_by_path: Dict[str, Tuple[Path, str]],
        manifest: InstallManifest,
    ) -> Tuple[List[FileOperation], List[str]]:
        operations: List[FileOperation] = []
        conflicts: List[str] = []
        managed = manifest.managed_by_path()

        expected_paths = set(expected_by_path)
        manifest_paths = set(managed)
        if expected_paths != manifest_paths:
            raise InstallAssemblyError(
                "Installed bundle content does not match ownership manifest for this version."
            )

        for relative, (source, digest) in sorted(expected_by_path.items()):
            target = resolve_under_root(project_root, relative)
            boundary = check_symlink_boundary(project_root, relative)
            if boundary:
                conflicts.append(boundary)
                continue

            owned = managed[relative]
            if owned.sha256 != digest:
                raise InstallAssemblyError(
                    "Internal consistency failure for {}: manifest hash differs from bundle.".format(
                        relative
                    )
                )

            if not target.exists():
                operations.append(
                    FileOperation(
                        relative_path=relative,
                        kind=FileOpKind.RESTORE,
                        source_path=source,
                        expected_sha256=digest,
                    )
                )
                continue

            if target.is_symlink():
                conflicts.append("Symlink target not managed safely: {}".format(relative))
                continue

            disk_digest = sha256_file(target)
            if disk_digest == digest:
                operations.append(
                    FileOperation(
                        relative_path=relative,
                        kind=FileOpKind.NOOP,
                        source_path=source,
                        expected_sha256=digest,
                    )
                )
            else:
                conflicts.append(
                    "Managed file modified by user: {}".format(relative)
                )

        return operations, conflicts

    def _directories_to_create(
        self, project_root: Path, operations: Iterable[FileOperation]
    ) -> List[str]:
        needed = set()
        for operation in operations:
            if operation.kind == FileOpKind.NOOP:
                continue
            parent = Path(operation.relative_path).parent.as_posix()
            if parent and parent != ".":
                needed.add(parent)
        for relative in sorted(needed):
            target = resolve_under_root(project_root, relative)
            if not target.exists():
                pass
        return sorted(needed)

    def _rollback(
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


class InstallSelectionErrorProfileMismatch(InstallSelectionError):
    def __init__(self, installed_profile: str):
        super().__init__(
            "EKP is already installed with profile {}.\n\n"
            "Profile replacement is not supported by this v0.15.0 installer.".format(
                installed_profile
            )
        )


class InstallSelectionErrorVersionMismatch(InstallSelectionError):
    def __init__(self, installed_version: str, running_version: str):
        super().__init__(
            "Installed EKP version: {}\n"
            "Running EKP version: {}\n\n"
            "Cross-version update is not yet supported.".format(
                installed_version, running_version
            )
        )
