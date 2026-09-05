"""Safe Cursor rule deployment (compatibility facade over shared engine)."""

from __future__ import annotations

from pathlib import Path
from typing import Iterable, List, Optional, Tuple

from ekp.install.deploy.cursor import CURSOR_ADAPTER, CURSOR_RULES_DIR, CursorDeployer
from ekp.install.deploy.engine import AppliedManagedFiles, SharedDeploymentEngine
from ekp.install.deploy.hashing import sha256_file, sha256_text
from ekp.install.errors import InstallConflictError, InstallFilesystemError, InstallSelectionError
from ekp.install.manifest import InstallManifest, ManifestStore, utc_now_iso
from ekp.install.paths import check_symlink_boundary
from ekp.install.plan import InstallPlan

# Re-export names used by historical callers / tests.
__all__ = [
    "CURSOR_ADAPTER",
    "CURSOR_RULES_DIR",
    "AppliedManagedFiles",
    "CursorDeployService",
    "InstallSelectionErrorProfileMismatch",
    "InstallSelectionErrorVersionMismatch",
    "sha256_file",
    "sha256_text",
]


class CursorDeployService:
    """Build and apply Cursor install plans via CursorDeployer + SharedDeploymentEngine."""

    def __init__(
        self,
        deployer: Optional[CursorDeployer] = None,
        engine: Optional[SharedDeploymentEngine] = None,
    ) -> None:
        self._deployer = deployer or CursorDeployer()
        self._engine = engine or SharedDeploymentEngine()

    def inventory_bundle(self, bundle_path: Path) -> List[Tuple[str, Path, str]]:
        desired = self._deployer.collect_desired_files(bundle_path)
        return [
            (item.relative_path, item.source_path, item.sha256)
            for item in self._engine.normalize_desired_files(desired)
        ]

    def validate_install_compatibility(
        self,
        existing_manifest: Optional[InstallManifest],
        profile: str,
        ekp_version: str,
    ) -> None:
        """Raise when an existing install cannot accept the requested profile/version."""
        self._validate_existing_manifest(existing_manifest, profile, ekp_version)

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
        desired = self._deployer.collect_desired_files(bundle_path)
        inventory = self._engine.normalize_desired_files(desired)
        conflicts: List[str] = []

        self._validate_existing_manifest(existing_manifest, profile, ekp_version)

        for relative in (".cursor", CURSOR_RULES_DIR, ".ekp"):
            message = check_symlink_boundary(project_root, relative)
            if message:
                conflicts.append(message)

        if existing_manifest is None:
            operations, install_conflicts = self._engine.plan_first_install(
                project_root, inventory
            )
            conflicts.extend(install_conflicts)
        else:
            operations, install_conflicts = self._engine.plan_reinstall(
                project_root, inventory, existing_manifest.managed_by_path()
            )
            conflicts.extend(install_conflicts)

        directories_to_create = self._engine.directories_to_create(project_root, operations)

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

    def apply_managed_files(
        self,
        plan: InstallPlan,
        *,
        extra_directories: Optional[Iterable[str]] = None,
        rollback_on_error: bool = True,
    ) -> AppliedManagedFiles:
        """
        Create directories and write managed adapter files.

        Does not create ``install.json``. Callers that need ownership persistence
        must commit the manifest separately (composition installs require this).
        """
        return self._engine.apply_managed_files(
            plan,
            extra_directories=extra_directories,
            rollback_on_error=rollback_on_error,
        )

    def apply(self, plan: InstallPlan) -> InstallManifest:
        applied = self.apply_managed_files(plan, rollback_on_error=True)
        try:
            manifest = InstallManifest(
                schema_version=1,
                ekp_version=plan.ekp_version,
                profile=plan.profile,
                adapters=[plan.adapter],
                installed_at=utc_now_iso(),
                install_root=".",
                managed_files=applied.managed_files,
                created_directories=applied.created_directory_names,
            )
            ManifestStore(plan.project_root).save(manifest)
            return manifest
        except OSError as exc:
            self._engine.rollback(
                applied.created_files,
                applied.created_dirs,
                applied.preexisting_dirs,
            )
            raise InstallFilesystemError("Installation failed: {}".format(exc)) from exc
        except Exception:
            self._engine.rollback(
                applied.created_files,
                applied.created_dirs,
                applied.preexisting_dirs,
            )
            raise

    def rollback_managed_files(self, applied: AppliedManagedFiles) -> None:
        """Best-effort rollback of files/dirs created by ``apply_managed_files``."""
        self._engine.rollback(
            applied.created_files,
            applied.created_dirs,
            applied.preexisting_dirs,
        )

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


class InstallSelectionErrorProfileMismatch(InstallSelectionError):
    def __init__(self, installed_profile: str):
        super().__init__(
            "EKP is already installed with profile {}.\n\n"
            "Profile replacement is not supported by this EKP installer.".format(
                installed_profile
            )
        )


class InstallSelectionErrorVersionMismatch(InstallSelectionError):
    def __init__(self, installed_version: str, running_version: str):
        super().__init__(
            "Installed EKP version: {}\n"
            "Running EKP version: {}\n\n"
            "Run `ekp update` to synchronize this project with the running EKP version.".format(
                installed_version, running_version
            )
        )
