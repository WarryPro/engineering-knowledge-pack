"""Lifecycle path-boundary helpers (assistant-agnostic)."""

from __future__ import annotations

from typing import Iterable, List, Sequence

# Symlink-boundary check roots per managed assistant (not ownership claims).
ASSISTANT_SYMLINK_ROOTS = {
    "cursor": (".cursor", ".cursor/rules"),
    "copilot": (".github", ".github/instructions"),
    "claude": (".claude", ".claude/skills", "CLAUDE.md"),
    "antigravity": (".agents", ".agents/rules"),
}


def lifecycle_symlink_check_paths(adapters: Sequence[str]) -> List[str]:
    """Deterministic symlink roots to probe for a lifecycle plan."""
    paths: List[str] = [".ekp"]
    seen = {".ekp"}
    for assistant_id in sorted(set(adapters)):
        for relative in ASSISTANT_SYMLINK_ROOTS.get(assistant_id, ()):
            if relative not in seen:
                seen.add(relative)
                paths.append(relative)
    return paths


def adapters_from_desired(desired: Iterable) -> List[str]:
    """Lexical unique adapter ids from desired managed files."""
    return sorted({item.adapter for item in desired})
