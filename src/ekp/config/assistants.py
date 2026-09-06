"""Project assistant defaults and display labels (not capability SoT)."""

from __future__ import annotations

from typing import Sequence, Tuple

DEFAULT_PROJECT_ASSISTANT = "cursor"

# UX labels only — DeployRegistry remains capability SoT.
ASSISTANT_DISPLAY_LABELS = {
    "cursor": "Cursor",
    "copilot": "GitHub Copilot",
    "claude": "Claude",
    "antigravity": "Google Antigravity",
}


def default_project_assistants() -> Tuple[str, ...]:
    """Backward-compatible default when no assistants are selected."""
    return (DEFAULT_PROJECT_ASSISTANT,)


def canonicalize_assistants(assistants: Sequence[str]) -> Tuple[str, ...]:
    """
    Dedupe and lexically sort assistant ids.

    Empty input remains empty (callers decide defaulting / errors).
    """
    unique = set()
    for raw in assistants:
        assistant_id = str(raw).strip()
        if assistant_id:
            unique.add(assistant_id)
    return tuple(sorted(unique))


def assistant_display_label(assistant_id: str) -> str:
    """Human label for interactive / confirmation UX."""
    return ASSISTANT_DISPLAY_LABELS.get(assistant_id, assistant_id)
