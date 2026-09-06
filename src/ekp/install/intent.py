"""Install intent models and selection (composition-aware, no apply)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, List, Optional, Sequence, Set, Tuple

from ekp.composition import (
    ComponentRegistry,
    CompositionError,
    ResolvedComposition,
    resolve_composition,
)
from ekp.config.assistants import (
    DEFAULT_PROJECT_ASSISTANT,
    assistant_display_label,
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
    supported = registry.supported_assistants()
    for assistant_id in selected:
        if not registry.is_supported(assistant_id):
            raise InstallSelectionError(
                "Unsupported Consumer assistant: {!r}.\n"
                "Supported assistants: {}".format(
                    assistant_id, ", ".join(supported)
                )
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
    When ``explicit_assistants`` is omitted and ``assume_yes`` is true, Cursor is default.
    Interactive installs prompt for assistants after components are known.
    Tool signals never auto-select assistants.
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
    deploy = _deploy_registry_or_default(deploy_registry)
    signal_ids = _tool_signal_assistant_ids(report)

    if explicit_profile:
        return build_legacy_profile_intent(
            explicit_profile,
            additional_concerns=report.additional_concerns,
            resource_root=resource_root or loaded.resource_root,
        )

    if explicit_components is not None:
        assistants = _resolve_assistants_for_composition(
            explicit_assistants=explicit_assistants,
            assume_yes=assume_yes,
            deploy_registry=deploy,
            signal_ids=signal_ids,
            input_fn=input_fn,
            output_fn=output_fn,
        )
        return build_composition_intent(
            explicit_components,
            loaded,
            assistants=assistants,
            additional_concerns=report.additional_concerns,
            deploy_registry=deploy,
        )

    if report.proposed_components:
        assistants = _resolve_assistants_for_composition(
            explicit_assistants=explicit_assistants,
            assume_yes=assume_yes,
            deploy_registry=deploy,
            signal_ids=signal_ids,
            input_fn=input_fn,
            output_fn=output_fn,
        )
        return build_composition_intent(
            report.proposed_components,
            loaded,
            assistants=assistants,
            additional_concerns=report.additional_concerns,
            deploy_registry=deploy,
        )

    if assume_yes:
        if explicit_assistants is not None:
            raise InstallSelectionError(
                "No supported technology composition detected.\n\n"
                "Assistant selection does not replace technology selection.\n"
                "Specify --component or --profile, or provide .ekp/project.yaml."
            )
        raise InstallSelectionError(
            "No supported technology composition detected.\n\n"
            "For non-interactive installation specify an explicit profile or components."
        )

    return _prompt_empty_components(
        loaded,
        input_fn=input_fn,
        output_fn=output_fn,
        additional_concerns=report.additional_concerns,
        explicit_assistants=explicit_assistants,
        deploy_registry=deploy,
        signal_ids=signal_ids,
    )


def _resolve_assistants_for_composition(
    *,
    explicit_assistants: Optional[Sequence[str]],
    assume_yes: bool,
    deploy_registry: DeployRegistry,
    signal_ids: Set[str],
    input_fn: Callable[[str], str],
    output_fn: Callable[[str], None],
) -> Optional[Sequence[str]]:
    if explicit_assistants is not None:
        return validate_composition_assistants(
            explicit_assistants, deploy_registry=deploy_registry
        )
    if assume_yes:
        return None  # validate_composition_assistants defaults to Cursor
    return prompt_assistants(
        deploy_registry=deploy_registry,
        signal_ids=signal_ids,
        input_fn=input_fn,
        output_fn=output_fn,
    )


def _tool_signal_assistant_ids(report: DetectionReport) -> Set[str]:
    return {signal.tool for signal in getattr(report, "tool_signals", []) or []}


def component_display_label(component_id: str) -> str:
    """Human label for interactive component selection."""
    if component_id == "core":
        return "Core engineering knowledge only"
    if not component_id:
        return component_id
    return component_id[:1].upper() + component_id[1:]


def prompt_assistants(
    *,
    deploy_registry: Optional[DeployRegistry] = None,
    signal_ids: Optional[Set[str]] = None,
    input_fn: Callable[[str], str] = input,
    output_fn: Callable[[str], None] = print,
) -> Tuple[str, ...]:
    """
    Interactive multi-assistant selection.

    Blank / Enter accepts Cursor only. Tool signals may be annotated but never
    auto-selected.
    """
    registry = _deploy_registry_or_default(deploy_registry)
    options = list(registry.supported_assistants())
    signals = signal_ids or set()

    output_fn("")
    output_fn("Select AI assistants (default: Cursor):")
    for index, assistant_id in enumerate(options, start=1):
        label = assistant_display_label(assistant_id)
        if assistant_id in signals:
            output_fn(
                "  {}. {} — detected project signal".format(index, label)
            )
        else:
            output_fn("  {}. {}".format(index, label))
    output_fn("")
    output_fn(
        "Enter one or more numbers or assistant IDs separated by commas "
        "(blank = Cursor only):"
    )

    while True:
        raw = input_fn("Assistants: ").strip()
        if not raw:
            return default_project_assistants()

        parts = [part.strip() for part in raw.split(",") if part.strip()]
        if not parts:
            output_fn("Enter at least one selection, or press Enter for Cursor.")
            continue

        chosen: List[str] = []
        invalid = False
        for part in parts:
            if part.isdigit():
                index = int(part)
                if index < 1 or index > len(options):
                    output_fn("Invalid selection number: {}".format(part))
                    invalid = True
                    break
                chosen.append(options[index - 1])
                continue
            lowered = part.lower()
            if lowered not in options:
                output_fn(
                    "Unsupported assistant: {!r}. Supported: {}".format(
                        part, ", ".join(options)
                    )
                )
                invalid = True
                break
            chosen.append(lowered)
        if invalid:
            continue
        return validate_composition_assistants(chosen, deploy_registry=registry)


def _prompt_empty_components(
    registry: ComponentRegistry,
    *,
    input_fn: Callable[[str], str],
    output_fn: Callable[[str], None],
    additional_concerns: Sequence[str] = (),
    explicit_assistants: Optional[Sequence[str]] = None,
    deploy_registry: Optional[DeployRegistry] = None,
    signal_ids: Optional[Set[str]] = None,
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
        assistants = explicit_assistants
        if assistants is None:
            assistants = prompt_assistants(
                deploy_registry=deploy_registry,
                signal_ids=signal_ids,
                input_fn=input_fn,
                output_fn=output_fn,
            )
        return build_composition_intent(
            chosen,
            registry,
            assistants=assistants,
            additional_concerns=additional_concerns,
            deploy_registry=deploy_registry,
        )
