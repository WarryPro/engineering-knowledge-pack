"""Install orchestration service."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional

from ekp.assembly import AssemblyRequest, AssemblyService
from ekp.detection.service import DetectionService
from ekp.install.cursor_deploy import CursorDeployService
from ekp.install.errors import InstallCancelled, InstallConflictError, InstallError
from ekp.install.manifest import ManifestStore
from ekp.install.plan import InstallPlan
from ekp.install.render import (
    render_confirmation,
    render_conflict_message,
    render_dry_run,
    render_success,
)
from ekp.install.selection import select_profile
from ekp.resolution.resolver import apply_resolution
from ekp.version import get_version


@dataclass
class InstallRequest:
    path: str = "."
    profile: Optional[str] = None
    assume_yes: bool = False
    dry_run: bool = False


@dataclass
class InstallResult:
    exit_code: int
    message: str = ""


class InstallService:
    """Consumer install workflow."""

    def __init__(
        self,
        assembly_service: Optional[AssemblyService] = None,
        deploy_service: Optional[CursorDeployService] = None,
        detection_service: Optional[DetectionService] = None,
        input_fn: Callable[[str], str] = input,
        output_fn: Callable[[str], None] = print,
    ):
        self.assembly_service = assembly_service or AssemblyService()
        self.deploy_service = deploy_service or CursorDeployService()
        self.detection_service = detection_service or DetectionService()
        self.input_fn = input_fn
        self.output_fn = output_fn

    def install(self, request: InstallRequest) -> InstallResult:
        try:
            return self._install(request)
        except InstallCancelled as exc:
            return InstallResult(exit_code=exc.exit_code, message="Installation cancelled.")
        except InstallError as exc:
            return InstallResult(exit_code=exc.exit_code, message=exc.message)

    def _install(self, request: InstallRequest) -> InstallResult:
        from ekp.install.paths import resolve_project_root

        project_root = resolve_project_root(request.path)
        ekp_version = get_version()
        manifest_store = ManifestStore(project_root)
        existing_manifest = manifest_store.load()

        report = apply_resolution(self.detection_service.detect(path=str(project_root)))
        profile, additional_concerns = select_profile(
            report=report,
            explicit_profile=request.profile,
            assume_yes=request.assume_yes,
            input_fn=self.input_fn,
            output_fn=self.output_fn,
        )

        assembly_result = self.assembly_service.assemble(
            AssemblyRequest(profile=profile, verify=True, clean=True)
        )
        try:
            plan = self.deploy_service.build_plan(
                project_root=project_root,
                bundle_path=assembly_result.bundle_path,
                profile=profile,
                ekp_version=ekp_version,
                existing_manifest=existing_manifest,
                additional_concerns=additional_concerns,
                dry_run=request.dry_run,
            )

            if plan.has_conflicts:
                return InstallResult(
                    exit_code=InstallConflictError.exit_code,
                    message=render_conflict_message(plan),
                )

            if request.dry_run:
                return InstallResult(exit_code=0, message=render_dry_run(plan))

            if plan.is_noop:
                return InstallResult(
                    exit_code=0,
                    message=render_success(plan, noop=True),
                )

            if not request.assume_yes:
                self.output_fn(render_confirmation(plan))
                answer = self.input_fn("").strip().lower()
                if answer not in ("", "y", "yes"):
                    raise InstallCancelled()

            self.deploy_service.apply(plan)
            return InstallResult(exit_code=0, message=render_success(plan))
        finally:
            temp_ctx = getattr(assembly_result, "_temp_ctx", None)
            if temp_ctx is not None:
                temp_ctx.cleanup()
