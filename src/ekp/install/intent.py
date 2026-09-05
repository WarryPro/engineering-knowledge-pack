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
from ekp.config.models import (
    SUPPORTED_PROJECT_ASSISTANTS,
    ProjectConfig,
)
from ekp.config.normalization import configuration_sha256
from ekp.detection.models import DetectionReport
from ekp.install.errors import InstallSelectionError
from ekp.install.selection import validate_explicit_profile
from ekp.paths import get_ekp_root

MODE_LEGACY_PROFILE = "legacy-profile"
MODE_COMPOSITION = "composition"


@dataclass(frozen=True)
class InstallIntent:
    """What a future install wants (no filesystem mutation in AW-D)."""

    mode: str
    profile: Optional[str] = None
    components: Tuple[str, ...] = ()
    assistants: Tuple[str, ...] = SUPPORTED_PROJECT_ASSISTANTS
    composition: Optional[ResolvedComposition] = None
    additional_concerns: Tuple[str, ...] = ()
    configuration_sha256: Optional[str] = None


def intent_to_project_config(intent: InstallIntent) -> ProjectConfig:
    """Build an in-memory ProjectConfig draft from a composition intent."""
    if intent.mode != MODE_COMPOSITION:
        raise InstallSelectionError(
            "ProjectConfig draft requires composition mode install intent"
        )
    if not intent.components:
        raise InstallSelectionError("composition intent has no requested components")
    return ProjectConfig(
        schema_version=1,
        components=tuple(intent.components),
        assistants=tuple(intent.assistants) or SUPPORTED_PROJECT_ASSISTANTS,
    )


def build_composition_intent(
    requested_components: Sequence[str],
    registry: ComponentRegistry,
    *,
    assistants: Sequence[str] = SUPPORTED_PROJECT_ASSISTANTS,
    additional_concerns: Sequence[str] = (),
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

    intent = InstallIntent(
        mode=MODE_COMPOSITION,
        profile=None,
        components=composition.requested_components,
        assistants=tuple(assistants) or SUPPORTED_PROJECT_ASSISTANTS,
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
        assistants=SUPPORTED_PROJECT_ASSISTANTS,
        composition=None,
        additional_concerns=tuple(additional_concerns),
        configuration_sha256=None,
    )


def select_install_intent(
    report: DetectionReport,
    *,
    explicit_profile: Optional[str] = None,
    explicit_components: Optional[Sequence[str]] = None,
    assume_yes: bool = False,
    registry: Optional[ComponentRegistry] = None,
    resource_root=None,
    input_fn: Callable[[str], str] = input,
    output_fn: Callable[[str], None] = print,
) -> InstallIntent:
    """
    Resolve install intent without writing project.yaml / install.json / Cursor files.

    Mutual exclusion: explicit profile and explicit components cannot combine.
    """
    if explicit_profile and explicit_components:
        raise InstallSelectionError(
            "Cannot combine --profile with explicit components.\n"
            "Choose either a legacy profile or a component composition."
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
            additional_concerns=report.additional_concerns,
        )

    if report.proposed_components:
        # Medium/high detections produce a deterministic composition proposal.
        # Multi-component proposals are valid (not install ambiguity).
        return build_composition_intent(
            report.proposed_components,
            loaded,
            additional_concerns=report.additional_concerns,
        )

    # No automatic composition proposal (empty or low-confidence only).
    if assume_yes:
        raise InstallSelectionError(
            "No supported technology composition detected.\n\n"
            "For non-interactive installation specify an explicit profile or components."
        )

    return _prompt_empty_components(
        loaded,
        input_fn=input_fn,
        output_fn=output_fn,
        additional_concerns=report.additional_concerns,
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
            additional_concerns=additional_concerns,
        )
