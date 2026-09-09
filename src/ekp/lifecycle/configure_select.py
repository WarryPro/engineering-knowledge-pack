"""Interactive desired-state pickers for ``ekp configure`` (current defaults)."""

from __future__ import annotations

from typing import Callable, List, Optional, Sequence, Tuple

from ekp.composition import ComponentRegistry
from ekp.config.assistants import assistant_display_label
from ekp.install.deploy.registry import DeployRegistry, build_default_deploy_registry
from ekp.install.errors import InstallSelectionError
from ekp.install.intent import component_display_label, validate_composition_assistants


def prompt_configure_components(
    current: Sequence[str],
    registry: ComponentRegistry,
    *,
    input_fn: Callable[[str], str] = input,
    output_fn: Callable[[str], None] = print,
) -> Tuple[str, ...]:
    """Prompt for exact requested components; blank keeps ``current``."""
    selectable = [
        component
        for component in registry.list_components()
        if component.selectable
    ]
    options = [component.id for component in selectable]
    current_set = set(str(item) for item in current)

    output_fn("")
    output_fn("Select exact desired project components:")
    output_fn("(blank = keep current requested components)")
    output_fn("")
    for index, component in enumerate(selectable, start=1):
        marker = " *" if component.id in current_set else "  "
        output_fn(
            "{}{}. {}".format(
                marker, index, component_display_label(component.id)
            )
        )
    output_fn("")
    output_fn("Current: {}".format(", ".join(sorted(current_set)) or "(none)"))
    output_fn("Enter one or more numbers or component IDs separated by commas:")

    while True:
        raw = input_fn("Components: ").strip()
        if not raw:
            if not current:
                raise InstallSelectionError(
                    "configure requires at least one component.\n"
                    "Use components=['core'] for Core-only; uninstall to remove EKP."
                )
            return tuple(sorted(current_set))
        if raw.lower() in ("-", "none", "clear"):
            raise InstallSelectionError(
                "configure requires at least one component.\n"
                "Empty component selection is not allowed."
            )

        parts = [part.strip() for part in raw.split(",") if part.strip()]
        if not parts:
            output_fn("Enter at least one selection, or press Enter to keep current.")
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
                output_fn("Unknown component: {!r}".format(part))
                invalid = True
                break
            chosen.append(lowered)
        if invalid:
            continue
        if not chosen:
            output_fn("Select at least one component.")
            continue
        # Preserve first-seen order then let intent builder canonicalize.
        unique: List[str] = []
        seen = set()
        for item in chosen:
            if item not in seen:
                seen.add(item)
                unique.append(item)
        return tuple(unique)


def prompt_configure_assistants(
    current: Sequence[str],
    *,
    deploy_registry: Optional[DeployRegistry] = None,
    input_fn: Callable[[str], str] = input,
    output_fn: Callable[[str], None] = print,
) -> Tuple[str, ...]:
    """Prompt for exact assistants; blank keeps ``current`` (never injects Cursor)."""
    registry = deploy_registry or build_default_deploy_registry()
    options = list(registry.supported_assistants())
    current_set = set(str(item) for item in current)

    output_fn("")
    output_fn("Select exact desired AI assistants:")
    output_fn("(blank = keep current assistants)")
    output_fn("")
    for index, assistant_id in enumerate(options, start=1):
        marker = " *" if assistant_id in current_set else "  "
        output_fn(
            "{}{}. {}".format(
                marker, index, assistant_display_label(assistant_id)
            )
        )
    output_fn("")
    output_fn(
        "Current: {}".format(
            ", ".join(assistant_display_label(a) for a in sorted(current_set))
            or "(none)"
        )
    )
    output_fn("Enter one or more numbers or assistant IDs separated by commas:")

    while True:
        raw = input_fn("Assistants: ").strip()
        if not raw:
            if not current:
                raise InstallSelectionError(
                    "configure requires at least one assistant.\n"
                    "Use uninstall to remove EKP entirely."
                )
            return validate_composition_assistants(
                list(current), deploy_registry=registry
            )
        if raw.lower() in ("-", "none", "clear"):
            raise InstallSelectionError(
                "configure requires at least one assistant.\n"
                "Empty assistant selection is not allowed (use uninstall to remove EKP)."
            )

        parts = [part.strip() for part in raw.split(",") if part.strip()]
        if not parts:
            output_fn("Enter at least one selection, or press Enter to keep current.")
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
        try:
            return validate_composition_assistants(chosen, deploy_registry=registry)
        except InstallSelectionError as exc:
            output_fn(str(exc))
