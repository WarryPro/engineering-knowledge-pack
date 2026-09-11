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
    allow_empty: bool = False,
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
    output_fn("Select exact desired root project components:")
    output_fn("(blank = keep current requested components)")
    if allow_empty:
        output_fn("('-' / none / clear = no root components; requires workspaces)")
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
            if not current and not allow_empty:
                raise InstallSelectionError(
                    "configure requires at least one component.\n"
                    "Use components=['core'] for Core-only; uninstall to remove EKP."
                )
            return tuple(str(item) for item in current)
        if raw.lower() in ("-", "none", "clear"):
            if allow_empty:
                return ()
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


def prompt_configure_workspaces(
    current: Sequence,
    *,
    registry: ComponentRegistry,
    project_root,
    input_fn: Callable[[str], str] = input,
    output_fn: Callable[[str], None] = print,
) -> Tuple:
    """Prompt to preserve or rebuild the complete desired workspace set."""
    from ekp.cli_workspace import (
        group_workspace_cli_pairs,
        normalize_cli_workspace_path,
    )
    from ekp.config.models import WorkspaceIntent
    from ekp.config.project import validate_project_config_payload
    from ekp.config.models import ProjectConfigError

    output_fn("")
    output_fn("Current workspaces:")
    if current:
        for ws in current:
            comps = ", ".join(ws.components) if ws.components else "(none)"
            output_fn("  {}    {}".format(ws.path, comps))
    else:
        output_fn("  (none)")
    output_fn("")
    raw = input_fn("Change workspace set? [y/N]: ").strip().lower()
    if raw not in ("y", "yes"):
        return tuple(current)

    output_fn("")
    output_fn("Rebuild the complete desired workspace set.")
    output_fn("Enter workspace paths and components. Blank path finishes.")
    output_fn("")

    pairs: List[Tuple[str, str]] = []
    while True:
        path_raw = input_fn("Workspace path (blank = done): ").strip()
        if not path_raw:
            break
        try:
            path = normalize_cli_workspace_path(path_raw)
        except InstallSelectionError as exc:
            output_fn(str(exc))
            continue

        comps_raw = input_fn(
            "Components for {} (comma-separated IDs): ".format(path)
        ).strip()
        if not comps_raw:
            output_fn("Enter at least one component for this workspace.")
            continue
        parts = [part.strip() for part in comps_raw.split(",") if part.strip()]
        if not parts:
            output_fn("Enter at least one component for this workspace.")
            continue
        for component in parts:
            pairs.append((path, component))

    if not pairs:
        return ()

    try:
        workspaces = group_workspace_cli_pairs(pairs)
    except InstallSelectionError as exc:
        raise InstallSelectionError(str(exc)) from exc

    # Validate via payload path (overlap, components, filesystem).
    payload = {
        "schema_version": 2,
        "components": [],
        "assistants": ["cursor"],
        "workspaces": [
            {"path": ws.path, "components": list(ws.components)} for ws in workspaces
        ],
    }
    try:
        validate_project_config_payload(
            payload, registry, project_root=project_root
        )
    except ProjectConfigError as exc:
        raise InstallSelectionError(str(exc)) from exc
    return workspaces
