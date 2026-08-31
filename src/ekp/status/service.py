"""Read-only installation status inspection."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from ekp.install.cursor_deploy import sha256_file
from ekp.install.errors import InstallConflictError
from ekp.install.manifest import InstallManifest, ManifestStore
from ekp.install.paths import check_symlink_boundary, resolve_project_root, resolve_under_root
from ekp.status.models import ManagedFileStatus, StatusResult, StatusState
from ekp.version import get_version


@dataclass
class StatusRequest:
    path: str = "."


class StatusService:
    """Inspect local EKP ownership state without modifying the project."""

    def inspect(self, request: StatusRequest) -> StatusResult:
        project_root = resolve_project_root(request.path)
        running_version = get_version()
        store = ManifestStore(project_root)

        if not store.exists():
            return StatusResult(
                project_root=str(project_root),
                installed=False,
                state=StatusState.NOT_INSTALLED,
                running_version=running_version,
            )

        try:
            manifest = store.load()
        except InstallConflictError as exc:
            return StatusResult(
                project_root=str(project_root),
                installed=False,
                state=StatusState.INVALID,
                running_version=running_version,
                error_message=exc.message,
            )

        if manifest is None:
            return StatusResult(
                project_root=str(project_root),
                installed=False,
                state=StatusState.NOT_INSTALLED,
                running_version=running_version,
            )

        file_statuses = self._inspect_managed_files(project_root, manifest)
        unsafe_paths = [item.relative_path for item in file_statuses if item.unsafe]
        if unsafe_paths:
            return StatusResult(
                project_root=str(project_root),
                installed=True,
                state=StatusState.INVALID,
                running_version=running_version,
                schema_version=manifest.schema_version,
                installed_version=manifest.ekp_version,
                profile=manifest.profile,
                adapters=list(manifest.adapters),
                install_root=manifest.install_root,
                installed_at=manifest.installed_at,
                managed_total=len(manifest.managed_files),
                unsafe_paths=unsafe_paths,
                error_message="Ownership manifest contains unsafe managed file paths.",
            )

        missing_paths = [item.relative_path for item in file_statuses if item.missing]
        modified_paths = [item.relative_path for item in file_statuses if item.modified]
        intact_count = sum(
            1
            for item in file_statuses
            if not item.missing and not item.modified and not item.unsafe
        )

        state = self._resolve_state(
            installed_version=manifest.ekp_version,
            running_version=running_version,
            missing_count=len(missing_paths),
            modified_count=len(modified_paths),
        )

        return StatusResult(
            project_root=str(project_root),
            installed=True,
            state=state,
            running_version=running_version,
            schema_version=manifest.schema_version,
            installed_version=manifest.ekp_version,
            profile=manifest.profile,
            adapters=list(manifest.adapters),
            install_root=manifest.install_root,
            installed_at=manifest.installed_at,
            managed_total=len(manifest.managed_files),
            intact_count=intact_count,
            modified_paths=modified_paths,
            missing_paths=missing_paths,
        )

    def _inspect_managed_files(
        self, project_root: Path, manifest: InstallManifest
    ) -> list[ManagedFileStatus]:
        results: list[ManagedFileStatus] = []
        for managed in manifest.managed_files:
            boundary = check_symlink_boundary(project_root, managed.relative_path)
            if boundary:
                results.append(
                    ManagedFileStatus(
                        relative_path=managed.relative_path,
                        expected_sha256=managed.sha256,
                        unsafe=True,
                    )
                )
                continue

            try:
                target = resolve_under_root(project_root, managed.relative_path)
            except ValueError:
                results.append(
                    ManagedFileStatus(
                        relative_path=managed.relative_path,
                        expected_sha256=managed.sha256,
                        unsafe=True,
                    )
                )
                continue

            if not target.exists() or target.is_symlink():
                results.append(
                    ManagedFileStatus(
                        relative_path=managed.relative_path,
                        expected_sha256=managed.sha256,
                        missing=True,
                    )
                )
                continue

            actual = sha256_file(target)
            modified = actual != managed.sha256
            results.append(
                ManagedFileStatus(
                    relative_path=managed.relative_path,
                    expected_sha256=managed.sha256,
                    actual_sha256=actual,
                    modified=modified,
                )
            )
        return results

    def _resolve_state(
        self,
        installed_version: str,
        running_version: str,
        missing_count: int,
        modified_count: int,
    ) -> StatusState:
        if installed_version != running_version:
            return StatusState.VERSION_MISMATCH
        if missing_count > 0:
            return StatusState.INCOMPLETE
        if modified_count > 0:
            return StatusState.MODIFIED
        return StatusState.HEALTHY
