"""Read-only CLI discovery helpers (package resources only).

Release and consumer tooling — no project mutation, detection, or prompts.
"""

from __future__ import annotations

from typing import List, Sequence, Tuple

from ekp.composition import ComponentRegistry
from ekp.config.assistants import (
    DEFAULT_PROJECT_ASSISTANT,
    assistant_display_label,
)
from ekp.install.deploy.registry import build_default_deploy_registry
from ekp.install.intent import component_display_label
from ekp.paths import get_ekp_root


def list_selectable_components(
    registry: ComponentRegistry | None = None,
) -> List[Tuple[str, str]]:
    """Return sorted ``(id, description)`` for selectable components."""
    loaded = registry if registry is not None else ComponentRegistry.load(get_ekp_root())
    rows: List[Tuple[str, str]] = []
    for component in loaded.list_components():
        if not component.selectable:
            continue
        rows.append((component.id, component_display_label(component.id)))
    rows.sort(key=lambda item: item[0])
    return rows


def list_supported_assistants() -> List[Tuple[str, str]]:
    """Return sorted ``(id, description)`` for supported Consumer assistants."""
    rows: List[Tuple[str, str]] = []
    for assistant_id in build_default_deploy_registry().supported_assistants():
        label = assistant_display_label(assistant_id)
        if assistant_id == DEFAULT_PROJECT_ASSISTANT:
            label = "{} (default)".format(label)
        rows.append((assistant_id, label))
    rows.sort(key=lambda item: item[0])
    return rows


def format_discovery_table(rows: Sequence[Tuple[str, str]]) -> str:
    """Format id/description rows with deterministic alignment."""
    if not rows:
        return ""
    width = max(len(item_id) for item_id, _ in rows)
    lines = [
        "{}  {}".format(item_id.ljust(width), description)
        for item_id, description in rows
    ]
    return "\n".join(lines) + "\n"
