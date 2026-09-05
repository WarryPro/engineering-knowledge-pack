"""Read-only installation status inspection."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

from ekp.composition import ComponentRegistry, resolve_composition
from ekp.config.models import ProjectConfigError
from ekp.config.project import ProjectConfigStore
from ekp.install.cursor_deploy import sha256_file
from ekp.install.errors import InstallConflictError
from ekp.install.manifest import (
    INSTALL_MODE_COMPOSITION,
    INSTALL_MODE_LEGACY_PROFILE,
    InstallManifest,
    ManifestStore,
)
from ekp.install.paths import check_symlink_boundary, resolve_project_root, resolve_under_root
from ekp.paths import get_ekp_root
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

        mode = manifest.effective_mode
        composition_fields = self._empty_composition_fields(mode)

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
                **composition_fields,
            )

        missing_paths = [item.relative_path for item in file_statuses if item.missing]
        modified_paths = [item.relative_path for item in file_statuses if item.modified]
        intact_count = sum(
            1
            for item in file_statuses
            if not item.missing and not item.modified and not item.unsafe
        )

        if mode == INSTALL_MODE_COMPOSITION:
            return self._inspect_composition(
                project_root=project_root,
                manifest=manifest,
                running_version=running_version,
                missing_paths=missing_paths,
                modified_paths=modified_paths,
                intact_count=intact_count,
            )

        state = self._resolve_legacy_state(
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
            **composition_fields,
        )

    def _inspect_composition(
        self,
        *,
        project_root: Path,
        manifest: InstallManifest,
        running_version: str,
        missing_paths: List[str],
        modified_paths: List[str],
        intact_count: int,
    ) -> StatusResult:
        mode = INSTALL_MODE_COMPOSITION
        bound_hash = manifest.configuration_sha256
        composition_fields = {
            "mode": mode,
            "configuration_sha256": bound_hash,
            "current_configuration_sha256": None,
            "requested_components": [],
            "resolved_components": [],
            "assistants": [],
            "configuration_drift": None,
        }

        try:
            registry = ComponentRegistry.load(get_ekp_root())
            store = ProjectConfigStore(project_root, registry=registry)
            if not store.exists():
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
                    intact_count=intact_count,
                    modified_paths=modified_paths,
                    missing_paths=missing_paths,
                    error_message=(
                        "Composition install is missing .ekp/project.yaml "
                        "(project intent required for mode=composition)."
                    ),
                    **composition_fields,
                )

            snapshot = store.load_snapshot()
            if snapshot is None:
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
                    intact_count=intact_count,
                    modified_paths=modified_paths,
                    missing_paths=missing_paths,
                    error_message="Composition install is missing .ekp/project.yaml.",
                    **composition_fields,
                )
        except ProjectConfigError as exc:
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
                intact_count=intact_count,
                modified_paths=modified_paths,
                missing_paths=missing_paths,
                error_message="Invalid project configuration: {}".format(exc),
                **composition_fields,
            )
        except InstallConflictError as exc:
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
                intact_count=intact_count,
                modified_paths=modified_paths,
                missing_paths=missing_paths,
                error_message=exc.message,
                **composition_fields,
            )

        current_hash = snapshot.configuration_sha256
        drift = current_hash != bound_hash
        try:
            composition = resolve_composition(snapshot.config.components, registry)
            resolved = list(composition.resolved_components)
        except Exception:
            resolved = []

        composition_fields = {
            "mode": mode,
            "configuration_sha256": bound_hash,
            "current_configuration_sha256": current_hash,
            "requested_components": list(snapshot.config.components),
            "resolved_components": resolved,
            "assistants": list(snapshot.config.assistants),
            "configuration_drift": drift,
        }

        state = self._resolve_composition_state(
            installed_version=manifest.ekp_version,
            running_version=running_version,
            drift=drift,
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
            **composition_fields,
        )

    @staticmethod
    def _empty_composition_fields(mode: str) -> dict:
        return {
            "mode": mode,
            "configuration_sha256": None,
            "current_configuration_sha256": None,
            "requested_components": [],
            "resolved_components": [],
            "assistants": [],
            "configuration_drift": None,
        }

    def _inspect_managed_files(
        self, project_root: Path, manifest: InstallManifest
    ) -> list:
        results: List[ManagedFileStatus] = []
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

    def _resolve_legacy_state(
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

    def _resolve_composition_state(
        self,
        *,
        installed_version: str,
        running_version: str,
        drift: bool,
        missing_count: int,
        modified_count: int,
    ) -> StatusState:
        # Precedence: INVALID handled earlier; then drift; version; incomplete; modified; healthy.
        if drift:
            return StatusState.CONFIGURATION_DRIFT
        if installed_version != running_version:
            return StatusState.VERSION_MISMATCH
        if missing_count > 0:
            return StatusState.INCOMPLETE
        if modified_count > 0:
            return StatusState.MODIFIED
        return StatusState.HEALTHY
