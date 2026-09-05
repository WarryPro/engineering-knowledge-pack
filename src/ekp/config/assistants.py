"""Project assistant defaults and canonical ordering (not capability SoT)."""

from __future__ import annotations

from typing import Sequence, Tuple

DEFAULT_PROJECT_ASSISTANT = "cursor"


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
