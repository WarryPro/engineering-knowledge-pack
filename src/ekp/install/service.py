"""Install orchestration service."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Optional, Sequence

from ekp.assembly import AssemblyRequest, AssemblyService
from ekp.detection.service import DetectionService
from ekp.install.composition_install import CompositionInstallService
from ekp.install.cursor_deploy import CursorDeployService
from ekp.install.errors import (
    InstallCancelled,
    InstallConflictError,
    InstallError,
    InstallSelectionError,
)
from ekp.install.intent import (
    MODE_COMPOSITION,
    build_legacy_profile_intent,
    select_install_intent,
)
from ekp.install.manifest import (
    INSTALL_MODE_COMPOSITION,
    INSTALL_MODE_LEGACY_PROFILE,
    ManifestStore,
)
from ekp.install.render import (
    render_composition_confirmation,
    render_composition_dry_run,
    render_composition_success,
    render_confirmation,
    render_conflict_message,
    render_dry_run,
    render_success,
)
from ekp.install.selection import validate_explicit_profile
from ekp.resolution.resolver import apply_resolution
from ekp.version import get_version


@dataclass
class InstallRequest:
    path: str = "."
    profile: Optional[str] = None
    components: Optional[Sequence[str]] = None
    assume_yes: bool = False
    dry_run: bool = False


@dataclass
class InstallResult:
    exit_code: int
    message: str = ""


class InstallService:
    """Consumer install workflow (legacy profile + composition)."""

    def __init__(
        self,
        assembly_service: Optional[AssemblyService] = None,
        deploy_service: Optional[CursorDeployService] = None,
        detection_service: Optional[DetectionService] = None,
        composition_service: Optional[CompositionInstallService] = None,
        input_fn: Callable[[str], str] = input,
        output_fn: Callable[[str], None] = print,
    ):
        self.assembly_service = assembly_service or AssemblyService()
        self.deploy_service = deploy_service or CursorDeployService()
        self.detection_service = detection_service or DetectionService()
        self.composition_service = composition_service or CompositionInstallService(
            assembly_service=self.assembly_service,
            deploy_service=self.deploy_service,
        )
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

        sticky = self._existing_install_gate(existing_manifest, request)
        if sticky is not None:
            return sticky

        if existing_manifest is not None and existing_manifest.effective_mode == (
            INSTALL_MODE_LEGACY_PROFILE
        ):
            # Mode is sticky: keep legacy reinstall semantics (no composition adoption).
            profile = request.profile or existing_manifest.profile
            intent = build_legacy_profile_intent(
                profile,
                additional_concerns=(),
            )
            return self._install_legacy(
                project_root, intent, existing_manifest, ekp_version, request
            )

        report = apply_resolution(self.detection_service.detect(path=str(project_root)))
        intent = select_install_intent(
            report=report,
            explicit_profile=request.profile,
            explicit_components=list(request.components)
            if request.components is not None
            else None,
            assume_yes=request.assume_yes,
            input_fn=self.input_fn,
            output_fn=self.output_fn,
        )

        if intent.mode == MODE_COMPOSITION:
            return self._install_composition(project_root, intent, request)

        return self._install_legacy(project_root, intent, existing_manifest, ekp_version, request)

    def _existing_install_gate(self, existing_manifest, request: InstallRequest):
        if existing_manifest is None:
            return None

        mode = existing_manifest.effective_mode
        if mode == INSTALL_MODE_COMPOSITION:
            return InstallResult(
                exit_code=InstallSelectionError.exit_code,
                message=(
                    "EKP is already installed in composition mode.\n"
                    "Use `ekp status` or `ekp update`."
                ),
            )

        # Legacy sticky mode: refuse composition intent / mode change.
        if request.components is not None:
            return InstallResult(
                exit_code=InstallSelectionError.exit_code,
                message=(
                    "EKP is already installed in legacy-profile mode "
                    "(profile={}).\n\n"
                    "Changing installation mode / project composition is not "
                    "supported by install.\n"
                    "Use `ekp status` or `ekp update`, or uninstall first.".format(
                        existing_manifest.profile
                    )
                ),
            )

        return None

    def _install_composition(self, project_root, intent, request: InstallRequest) -> InstallResult:
        # Plan via dry-run path first when confirmation is needed.
        if not request.dry_run and not request.assume_yes:
            preview = self.composition_service.install(
                project_root, intent, dry_run=True
            )
            if preview.exit_code != 0:
                return InstallResult(exit_code=preview.exit_code, message=preview.message)
            if preview.plan is None:
                return InstallResult(
                    exit_code=InstallSelectionError.exit_code,
                    message=preview.message or "Unable to plan composition install.",
                )
            if preview.plan.has_conflicts:
                return InstallResult(
                    exit_code=InstallConflictError.exit_code,
                    message=preview.message,
                )
            self.output_fn(render_composition_confirmation(preview.plan))
            answer = self.input_fn("").strip().lower()
            if answer not in ("", "y", "yes"):
                raise InstallCancelled()

        result = self.composition_service.install(
            project_root, intent, dry_run=request.dry_run
        )
        if result.exit_code != 0:
            return InstallResult(exit_code=result.exit_code, message=result.message)

        if request.dry_run and result.plan is not None:
            return InstallResult(
                exit_code=0,
                message=render_composition_dry_run(result.plan),
            )
        if result.plan is not None:
            return InstallResult(
                exit_code=0,
                message=render_composition_success(result.plan),
            )
        return InstallResult(exit_code=0, message=result.message)

    def _install_legacy(
        self,
        project_root,
        intent,
        existing_manifest,
        ekp_version: str,
        request: InstallRequest,
    ) -> InstallResult:
        profile = intent.profile
        if not profile:
            raise InstallSelectionError("Legacy install intent is missing a profile")
        # Re-validate explicit profiles for clear errors (already validated in intent).
        validate_explicit_profile(profile)
        additional_concerns = list(intent.additional_concerns)

        try:
            self.deploy_service.validate_install_compatibility(
                existing_manifest, profile, ekp_version
            )
        except InstallError as exc:
            return InstallResult(exit_code=exc.exit_code, message=exc.message)

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
