"""Install intent models and selection (composition-aware, no apply)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, List, Optional, Sequence, Tuple

from ekp.composition import (
    ComponentRegistry,
    CompositionError,
    ResolvedComposition,
    resolve_composition,
)
from ekp.config.assistants import (
    DEFAULT_PROJECT_ASSISTANT,
    canonicalize_assistants,
    default_project_assistants,
)
from ekp.config.models import ProjectConfig
from ekp.config.normalization import configuration_sha256
from ekp.detection.models import DetectionReport
from ekp.install.deploy.registry import DeployRegistry, build_default_deploy_registry
from ekp.install.errors import InstallSelectionError
from ekp.install.selection import validate_explicit_profile
from ekp.paths import get_ekp_root

MODE_LEGACY_PROFILE = "legacy-profile"
MODE_COMPOSITION = "composition"


@dataclass(frozen=True)
class InstallIntent:
    """What an install wants (no filesystem mutation during selection)."""

    mode: str
    profile: Optional[str] = None
    components: Tuple[str, ...] = ()
    assistants: Tuple[str, ...] = (DEFAULT_PROJECT_ASSISTANT,)
    composition: Optional[ResolvedComposition] = None
    additional_concerns: Tuple[str, ...] = ()
    configuration_sha256: Optional[str] = None


def _deploy_registry_or_default(
    deploy_registry: Optional[DeployRegistry],
) -> DeployRegistry:
    return deploy_registry or build_default_deploy_registry()


def validate_composition_assistants(
    assistants: Optional[Sequence[str]] = None,
    deploy_registry: Optional[DeployRegistry] = None,
) -> Tuple[str, ...]:
    """
    Validate, dedupe, and canonicalize composition assistants via DeployRegistry.

    ``None`` defaults to Cursor. Explicit empty selection is invalid.
    """
    registry = _deploy_registry_or_default(deploy_registry)
    if assistants is None:
        selected = default_project_assistants()
    else:
        selected = canonicalize_assistants(assistants)
        if not selected:
            raise InstallSelectionError("assistants must not be empty")
    for assistant_id in selected:
        if not registry.is_supported(assistant_id):
            raise InstallSelectionError(
                "Unsupported Consumer assistant: {!r}".format(assistant_id)
            )
    return selected


def intent_to_project_config(intent: InstallIntent) -> ProjectConfig:
    """Build an in-memory ProjectConfig draft from a composition intent."""
    if intent.mode != MODE_COMPOSITION:
        raise InstallSelectionError(
            "ProjectConfig draft requires composition mode install intent"
        )
    if not intent.components:
        raise InstallSelectionError("composition intent has no requested components")
    assistants = tuple(intent.assistants) or default_project_assistants()
    return ProjectConfig(
        schema_version=1,
        components=tuple(intent.components),
        assistants=assistants,
    )


def build_composition_intent(
    requested_components: Sequence[str],
    registry: ComponentRegistry,
    *,
    assistants: Optional[Sequence[str]] = None,
    additional_concerns: Sequence[str] = (),
    deploy_registry: Optional[DeployRegistry] = None,
) -> InstallIntent:
    """Validate selectable components and build a composition InstallIntent."""
    if not requested_components:
        raise InstallSelectionError("explicit components must not be empty")

    unique: List[str] = []
    seen = set()
    for raw in requested_components:
        component_id = str(raw)
        if component_id in seen:
            continue
        seen.add(component_id)
        if not registry.has(component_id):
            raise InstallSelectionError(
                "Unknown component: {!r}".format(component_id)
            )
        component = registry.get(component_id)
        if not component.selectable:
            raise InstallSelectionError(
                "Component is not selectable: {!r}".format(component_id)
            )
        unique.append(component_id)

    try:
        composition = resolve_composition(unique, registry)
    except CompositionError as exc:
        raise InstallSelectionError(str(exc)) from exc

    selected_assistants = validate_composition_assistants(
        assistants,
        deploy_registry=deploy_registry,
    )

    intent = InstallIntent(
        mode=MODE_COMPOSITION,
        profile=None,
        components=composition.requested_components,
        assistants=selected_assistants,
        composition=composition,
        additional_concerns=tuple(additional_concerns),
    )
    config = intent_to_project_config(intent)
    digest = configuration_sha256(config, registry)
    return InstallIntent(
        mode=intent.mode,
        profile=intent.profile,
        components=intent.components,
        assistants=intent.assistants,
        composition=intent.composition,
        additional_concerns=intent.additional_concerns,
        configuration_sha256=digest,
    )


def build_legacy_profile_intent(
    profile: str,
    *,
    additional_concerns: Sequence[str] = (),
    resource_root=None,
) -> InstallIntent:
    """Validate and wrap an explicit/legacy Cursor profile selection."""
    validated = validate_explicit_profile(profile, resource_root)
    return InstallIntent(
        mode=MODE_LEGACY_PROFILE,
        profile=validated,
        components=(),
        assistants=default_project_assistants(),
        composition=None,
        additional_concerns=tuple(additional_concerns),
        configuration_sha256=None,
    )


def select_install_intent(
    report: DetectionReport,
    *,
    explicit_profile: Optional[str] = None,
    explicit_components: Optional[Sequence[str]] = None,
    explicit_assistants: Optional[Sequence[str]] = None,
    assume_yes: bool = False,
    registry: Optional[ComponentRegistry] = None,
    deploy_registry: Optional[DeployRegistry] = None,
    resource_root=None,
    input_fn: Callable[[str], str] = input,
    output_fn: Callable[[str], None] = print,
) -> InstallIntent:
    """
    Resolve install intent without writing project.yaml / install.json / adapter files.

    Mutual exclusion: explicit profile cannot combine with components or assistants.
    Public CLI does not pass ``explicit_assistants`` (defaults remain Cursor-only).
    """
    if explicit_profile and explicit_components:
        raise InstallSelectionError(
            "Cannot combine --profile with explicit components.\n"
            "Choose either a legacy profile or a component composition."
        )
    if explicit_profile and explicit_assistants is not None:
        raise InstallSelectionError(
            "Cannot combine --profile with explicit assistants.\n"
            "Legacy profile installs remain Cursor-only."
        )

    loaded = registry or ComponentRegistry.load(resource_root or get_ekp_root())

    if explicit_profile:
        return build_legacy_profile_intent(
            explicit_profile,
            additional_concerns=report.additional_concerns,
            resource_root=resource_root or loaded.resource_root,
        )

    if explicit_components is not None:
        return build_composition_intent(
            explicit_components,
            loaded,
            assistants=explicit_assistants,
            additional_concerns=report.additional_concerns,
            deploy_registry=deploy_registry,
        )

    if report.proposed_components:
        # Tool signals never expand assistants; default remains Cursor.
        return build_composition_intent(
            report.proposed_components,
            loaded,
            assistants=explicit_assistants,
            additional_concerns=report.additional_concerns,
            deploy_registry=deploy_registry,
        )

    if assume_yes:
        raise InstallSelectionError(
            "No supported technology composition detected.\n\n"
            "For non-interactive installation specify an explicit profile or components."
        )

    if explicit_assistants is not None and not report.proposed_components:
        # Assistants without components still require interactive/component selection.
        pass

    return _prompt_empty_components(
        loaded,
        input_fn=input_fn,
        output_fn=output_fn,
        additional_concerns=report.additional_concerns,
        explicit_assistants=explicit_assistants,
        deploy_registry=deploy_registry,
    )


def component_display_label(component_id: str) -> str:
    """Human label for interactive component selection."""
    if component_id == "core":
        return "Core engineering knowledge only"
    if not component_id:
        return component_id
    return component_id[:1].upper() + component_id[1:]


def _prompt_empty_components(
    registry: ComponentRegistry,
    *,
    input_fn: Callable[[str], str],
    output_fn: Callable[[str], None],
    additional_concerns: Sequence[str] = (),
    explicit_assistants: Optional[Sequence[str]] = None,
    deploy_registry: Optional[DeployRegistry] = None,
) -> InstallIntent:
    selectable = [
        component
        for component in registry.list_components()
        if component.selectable
    ]
    output_fn("")
    output_fn("No supported technology detected.")
    output_fn("")
    output_fn("Select project components:")
    for index, component in enumerate(selectable, start=1):
        output_fn(
            "  {}. {}".format(index, component_display_label(component.id))
        )
    output_fn("")
    output_fn("Enter one or more numbers separated by commas:")

    while True:
        raw = input_fn("Selection: ").strip()
        if not raw:
            output_fn("Enter at least one number from the list.")
            continue
        parts = [part.strip() for part in raw.split(",") if part.strip()]
        if not parts or not all(part.isdigit() for part in parts):
            output_fn("Enter numbers separated by commas.")
            continue
        indexes = [int(part) for part in parts]
        if any(index < 1 or index > len(selectable) for index in indexes):
            output_fn("Invalid selection.")
            continue
        chosen = [selectable[index - 1].id for index in indexes]
        return build_composition_intent(
            chosen,
            registry,
            assistants=explicit_assistants,
            additional_concerns=additional_concerns,
            deploy_registry=deploy_registry,
        )
