"""Internal composition install service (AW-E1 — no public CLI activation)."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, List, Optional

from ekp.assembly import AssemblyService, CompositionAssemblyRequest
from ekp.composition import PROJECT_COMPOSITION_PROFILE, ComponentRegistry
from ekp.config.models import (
    PROJECT_CONFIG_RELATIVE,
    ProjectConfig,
    ProjectConfigError,
)
from ekp.config.normalization import configuration_sha256
from ekp.config.project import ProjectConfigStore, render_project_config_yaml
from ekp.install.cursor_deploy import AppliedManagedFiles, CursorDeployService
from ekp.install.errors import (
    EXIT_SUCCESS,
    InstallConflictError,
    InstallError,
    InstallFilesystemError,
    InstallSelectionError,
)
from ekp.install.intent import (
    MODE_COMPOSITION,
    InstallIntent,
    intent_to_project_config,
)
from ekp.install.manifest import (
    INSTALL_MODE_COMPOSITION,
    MANIFEST_RELATIVE,
    InstallManifest,
    ManifestStore,
    utc_now_iso,
)
from ekp.install.paths import check_symlink_boundary, resolve_under_root
from ekp.install.plan import InstallPlan
from ekp.paths import get_ekp_root
from ekp.version import get_version

CONFIG_ACTION_CREATE = "create"
CONFIG_ACTION_REUSE = "reuse"


@dataclass
class CompositionInstallPlan:
    """Composition-specific install plan wrapping Cursor file deployment."""

    project_root: Path
    intent: InstallIntent
    project_config: ProjectConfig
    configuration_sha256: str
    config_action: str
    cursor_plan: InstallPlan
    conflicts: List[str] = field(default_factory=list)
    dry_run: bool = False

    @property
    def has_conflicts(self) -> bool:
        return bool(self.conflicts) or self.cursor_plan.has_conflicts

    @property
    def rules_count(self) -> int:
        return self.cursor_plan.rules_count


@dataclass
class CompositionInstallResult:
    """Structured internal composition install outcome."""

    exit_code: int
    message: str = ""
    intent: Optional[InstallIntent] = None
    plan: Optional[CompositionInstallPlan] = None
    manifest: Optional[InstallManifest] = None


class CompositionInstallService:
    """Persist a composed EKP installation (Consumer + programmatic)."""

    def __init__(
        self,
        assembly_service: Optional[AssemblyService] = None,
        deploy_service: Optional[CursorDeployService] = None,
        registry: Optional[ComponentRegistry] = None,
        resource_root: Optional[Path] = None,
    ):
        self.assembly_service = assembly_service or AssemblyService()
        self.deploy_service = deploy_service or CursorDeployService()
        self._registry = registry
        self._resource_root = Path(resource_root) if resource_root is not None else None
        # Test hooks (None in production): called during apply after named steps.
        self._after_config_hook: Optional[Callable[[CompositionInstallPlan], None]] = None
        self._after_managed_files_hook: Optional[
            Callable[[CompositionInstallPlan, AppliedManagedFiles], None]
        ] = None

    def _registry_or_load(self) -> ComponentRegistry:
        if self._registry is not None:
            return self._registry
        return ComponentRegistry.load(self._resource_root or get_ekp_root())

    def install(
        self,
        project_root: Path,
        intent: InstallIntent,
        *,
        dry_run: bool = False,
    ) -> CompositionInstallResult:
        try:
            return self._install(Path(project_root).resolve(), intent, dry_run=dry_run)
        except InstallError as exc:
            return CompositionInstallResult(
                exit_code=exc.exit_code,
                message=exc.message,
                intent=intent,
            )

    def _install(
        self,
        project_root: Path,
        intent: InstallIntent,
        *,
        dry_run: bool,
    ) -> CompositionInstallResult:
        self._validate_intent(intent)
        registry = self._registry_or_load()
        resource_root = self._resource_root or registry.resource_root

        assembly_result = self.assembly_service.assemble_composition(
            CompositionAssemblyRequest(
                components=list(intent.components),
                outputs=["cursor"],
                verify=True,
                clean=True,
                resource_root=resource_root,
            )
        )
        try:
            plan = self._build_plan(
                project_root,
                intent,
                dry_run=dry_run,
                assembly_result=assembly_result,
                registry=registry,
            )
            if plan.has_conflicts:
                return CompositionInstallResult(
                    exit_code=InstallConflictError.exit_code,
                    message=self._render_conflicts(plan),
                    intent=intent,
                    plan=plan,
                )

            if dry_run:
                return CompositionInstallResult(
                    exit_code=EXIT_SUCCESS,
                    message=self._render_dry_run(plan),
                    intent=intent,
                    plan=plan,
                )

            manifest = self._apply(plan, registry=registry)
            return CompositionInstallResult(
                exit_code=EXIT_SUCCESS,
                message="Composition install completed ({} Cursor rules).".format(
                    plan.rules_count
                ),
                intent=intent,
                plan=plan,
                manifest=manifest,
            )
        finally:
            temp_ctx = getattr(assembly_result, "_temp_ctx", None)
            if temp_ctx is not None:
                temp_ctx.cleanup()

    def _validate_intent(self, intent: InstallIntent) -> None:
        if intent.mode != MODE_COMPOSITION:
            raise InstallSelectionError(
                "Composition install requires mode={!r}, found {!r}".format(
                    MODE_COMPOSITION, intent.mode
                )
            )
        if not intent.components:
            raise InstallSelectionError("composition intent has no requested components")
        if intent.composition is None:
            raise InstallSelectionError("composition intent is missing resolved composition")
        if not intent.configuration_sha256:
            raise InstallSelectionError(
                "composition intent is missing configuration_sha256"
            )
        assistants = tuple(intent.assistants) or ("cursor",)
        if assistants != ("cursor",):
            raise InstallSelectionError(
                "AW-E1 composition install supports only assistants=['cursor']"
            )

    def _build_plan(
        self,
        project_root: Path,
        intent: InstallIntent,
        *,
        dry_run: bool,
        assembly_result,
        registry: Optional[ComponentRegistry] = None,
    ) -> CompositionInstallPlan:
        self._validate_intent(intent)
        registry = registry or self._registry_or_load()
        conflicts: List[str] = []

        for relative in (".cursor", ".cursor/rules", ".ekp", PROJECT_CONFIG_RELATIVE):
            message = check_symlink_boundary(project_root, relative)
            if message:
                conflicts.append(message)

        if ManifestStore(project_root).exists():
            conflicts.append(
                "Ownership manifest already exists: {}".format(MANIFEST_RELATIVE)
            )

        project_config, config_action, config_conflicts = self._resolve_project_config(
            project_root, intent, registry
        )
        conflicts.extend(config_conflicts)

        digest = intent.configuration_sha256 or ""
        if project_config is not None and not config_conflicts:
            computed = configuration_sha256(project_config, registry)
            if computed != digest:
                conflicts.append(
                    "project config semantic hash does not match install intent"
                )

        if assembly_result is None or assembly_result.bundle_path is None:
            raise InstallFilesystemError("Composition assembly did not produce a bundle")

        cursor_plan = self.deploy_service.build_plan(
            project_root=project_root,
            bundle_path=assembly_result.bundle_path,
            profile=PROJECT_COMPOSITION_PROFILE,
            ekp_version=get_version(),
            existing_manifest=None,
            additional_concerns=list(intent.additional_concerns),
            dry_run=dry_run,
        )

        for op in cursor_plan.operations:
            if op.relative_path == PROJECT_CONFIG_RELATIVE:
                conflicts.append(
                    "Cursor plan must not manage {}".format(PROJECT_CONFIG_RELATIVE)
                )

        return CompositionInstallPlan(
            project_root=project_root,
            intent=intent,
            project_config=project_config
            if project_config is not None
            else intent_to_project_config(intent),
            configuration_sha256=digest,
            config_action=config_action,
            cursor_plan=cursor_plan,
            conflicts=conflicts,
            dry_run=dry_run,
        )

    def _resolve_project_config(
        self,
        project_root: Path,
        intent: InstallIntent,
        registry: ComponentRegistry,
    ):
        store = ProjectConfigStore(
            project_root,
            registry=registry,
            resource_root=self._resource_root or registry.resource_root,
        )
        draft = intent_to_project_config(intent)
        expected = intent.configuration_sha256

        try:
            if not store.exists():
                return draft, CONFIG_ACTION_CREATE, []

            loaded = store.load()
            if loaded is None:
                return draft, CONFIG_ACTION_CREATE, []

            digest = configuration_sha256(loaded, registry)
            if digest != expected:
                return loaded, CONFIG_ACTION_REUSE, [
                    "Existing project config semantic hash differs from install intent "
                    "(automatic reconfiguration is not supported)."
                ]
            return loaded, CONFIG_ACTION_REUSE, []
        except ProjectConfigError as exc:
            raise InstallSelectionError(str(exc)) from exc

    def _apply(
        self,
        plan: CompositionInstallPlan,
        *,
        registry: ComponentRegistry,
    ) -> InstallManifest:
        if plan.has_conflicts:
            raise InstallConflictError("Cannot apply composition install with conflicts.")
        if plan.dry_run:
            raise InstallFilesystemError("Dry-run composition plans cannot be applied.")

        store = ProjectConfigStore(
            plan.project_root,
            registry=registry,
            resource_root=self._resource_root or registry.resource_root,
        )
        config_path = store.config_path
        created_config_bytes: Optional[bytes] = None
        applied: Optional[AppliedManagedFiles] = None
        created_ekp_dir = False
        ekp_dir = resolve_under_root(plan.project_root, ".ekp")
        ekp_preexisted = ekp_dir.exists()

        try:
            self._pre_apply_revalidate(plan, store, registry)

            if plan.config_action == CONFIG_ACTION_CREATE:
                if config_path.exists() or config_path.is_symlink():
                    raise InstallConflictError(
                        "project config appeared before create: {}".format(
                            PROJECT_CONFIG_RELATIVE
                        )
                    )
                if not ekp_preexisted:
                    ekp_dir.mkdir(parents=True, exist_ok=True)
                    created_ekp_dir = True
                store.create(plan.project_config)
                created_config_bytes = config_path.read_bytes()
                if self._after_config_hook is not None:
                    self._after_config_hook(plan)
            else:
                self._revalidate_reuse(store, registry, plan.configuration_sha256)

            applied = self.deploy_service.apply_managed_files(
                plan.cursor_plan,
                extra_directories=(
                    [".ekp"] if plan.config_action == CONFIG_ACTION_CREATE else None
                ),
                rollback_on_error=True,
            )
            if self._after_managed_files_hook is not None:
                self._after_managed_files_hook(plan, applied)

            snapshot = store.load_snapshot()
            if snapshot is None:
                raise InstallFilesystemError(
                    "project config missing before ownership manifest commit"
                )
            if snapshot.configuration_sha256 != plan.configuration_sha256:
                raise InstallConflictError(
                    "project config semantic hash drifted before ownership manifest commit"
                )

            if ManifestStore(plan.project_root).exists():
                raise InstallConflictError(
                    "Ownership manifest already exists: {}".format(MANIFEST_RELATIVE)
                )

            created_dirs = list(applied.created_directory_names)
            if created_ekp_dir and ".ekp" not in created_dirs:
                created_dirs.append(".ekp")

            manifest = InstallManifest(
                schema_version=1,
                ekp_version=plan.cursor_plan.ekp_version,
                profile=PROJECT_COMPOSITION_PROFILE,
                adapters=["cursor"],
                installed_at=utc_now_iso(),
                install_root=".",
                managed_files=applied.managed_files,
                created_directories=sorted(set(created_dirs)),
                mode=INSTALL_MODE_COMPOSITION,
                configuration_sha256=plan.configuration_sha256,
            )
            ManifestStore(plan.project_root).create(manifest)
            return manifest
        except Exception as exc:
            notes = self._rollback_transaction(
                applied=applied,
                config_path=config_path,
                created_config_bytes=created_config_bytes,
                created_ekp_dir=created_ekp_dir,
                ekp_dir=ekp_dir,
            )
            if notes:
                suffix = " Rollback: {}.".format("; ".join(notes))
                if isinstance(exc, InstallError):
                    raise type(exc)(exc.message + suffix) from exc
                raise InstallFilesystemError(
                    "Composition install failed.{}".format(suffix)
                ) from exc
            raise

    def _pre_apply_revalidate(
        self,
        plan: CompositionInstallPlan,
        store: ProjectConfigStore,
        registry: ComponentRegistry,
    ) -> None:
        if ManifestStore(plan.project_root).exists():
            raise InstallConflictError(
                "Ownership manifest already exists: {}".format(MANIFEST_RELATIVE)
            )
        if plan.config_action == CONFIG_ACTION_CREATE:
            if store.exists():
                raise InstallConflictError(
                    "project config appeared before create: {}".format(
                        PROJECT_CONFIG_RELATIVE
                    )
                )
        else:
            self._revalidate_reuse(store, registry, plan.configuration_sha256)

        for operation in plan.cursor_plan.files_to_write:
            target = resolve_under_root(plan.project_root, operation.relative_path)
            if target.exists() or target.is_symlink():
                raise InstallConflictError(
                    "Refusing to overwrite unexpected target: {}".format(
                        operation.relative_path
                    )
                )

    def _revalidate_reuse(
        self,
        store: ProjectConfigStore,
        registry: ComponentRegistry,
        expected_sha256: str,
    ) -> None:
        try:
            snapshot = store.load_snapshot()
        except ProjectConfigError as exc:
            raise InstallSelectionError(str(exc)) from exc
        if snapshot is None:
            raise InstallConflictError(
                "project config disappeared before reuse apply: {}".format(
                    PROJECT_CONFIG_RELATIVE
                )
            )
        if snapshot.configuration_sha256 != expected_sha256:
            raise InstallConflictError(
                "project config semantic hash changed before reuse apply"
            )

    def _rollback_transaction(
        self,
        *,
        applied: Optional[AppliedManagedFiles],
        config_path: Path,
        created_config_bytes: Optional[bytes],
        created_ekp_dir: bool,
        ekp_dir: Path,
    ) -> List[str]:
        notes: List[str] = []

        if applied is not None:
            self.deploy_service.rollback_managed_files(applied)

        if created_config_bytes is not None:
            try:
                if config_path.is_symlink():
                    notes.append("cannot rollback symlinked project config")
                elif config_path.is_file():
                    current = config_path.read_bytes()
                    if current == created_config_bytes:
                        config_path.unlink()
                    else:
                        notes.append(
                            "project config changed during failed install; left in place"
                        )
            except OSError as exc:
                notes.append("unable to rollback project config: {}".format(exc))

        if created_ekp_dir:
            try:
                if ekp_dir.is_dir() and not any(ekp_dir.iterdir()):
                    ekp_dir.rmdir()
            except OSError:
                pass

        return notes

    @staticmethod
    def _render_conflicts(plan: CompositionInstallPlan) -> str:
        lines = ["Composition install conflicts detected:"]
        for item in plan.conflicts:
            lines.append("  - {}".format(item))
        for item in plan.cursor_plan.conflicts:
            lines.append("  - {}".format(item))
        return "\n".join(lines)

    @staticmethod
    def _render_dry_run(plan: CompositionInstallPlan) -> str:
        intent = plan.intent
        composition = intent.composition
        lines = [
            "Composition install dry-run",
            "  mode: {}".format(MODE_COMPOSITION),
            "  profile: {}".format(PROJECT_COMPOSITION_PROFILE),
            "  config_action: {}".format(plan.config_action),
            "  configuration_sha256: {}".format(plan.configuration_sha256),
            "  requested_components: {}".format(",".join(intent.components)),
            "  resolved_components: {}".format(
                ",".join(composition.resolved_components) if composition else ""
            ),
            "  assistants: {}".format(",".join(intent.assistants)),
            "  cursor_rules: {}".format(plan.rules_count),
            "  file_operations: {}".format(len(plan.cursor_plan.files_to_write)),
        ]
        return "\n".join(lines)


def preview_project_config_bytes(config: ProjectConfig) -> bytes:
    """Exact bytes CompositionInstallService would write for a new project.yaml."""
    return render_project_config_yaml(config).encode("utf-8")
