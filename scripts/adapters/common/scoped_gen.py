"""Shared helpers for scoped (schema2) adapter generation."""

from __future__ import annotations

from pathlib import Path

from common.selected_knowledge import collect_selected_units_for_paths
from common.source_cache import build_source_markdown_cache


class ScopedGenerationError(Exception):
    """Raised when scoped adapter generation refuses unsafe output."""


def inventory_source_paths(inventory):
    # type: (object) -> list
    return list(inventory.unique_source_paths())


def build_invocation_markdown_cache(repo_root, inventory, reader=None):
    # type: (object, object, object) -> object
    """One markdown cache for all unique sources in one adapter invocation."""
    return build_source_markdown_cache(
        repo_root, inventory_source_paths(inventory), reader=reader
    )


def units_for_paths(knowledge_paths, repo_root, get_markdown, adapter_priorities=None):
    # type: (list, object, object, list) -> list
    return collect_selected_units_for_paths(
        knowledge_paths,
        repo_root,
        adapter_priorities=adapter_priorities or ["high"],
        get_markdown=get_markdown,
        require_orchestrator=True,
    )


def global_knowledge_paths(inventory):
    # type: (object) -> list
    return [item.source_path for item in inventory.global_items()]


def workspace_path_order(inventory):
    # type: (object) -> list
    """Distinct workspace paths in inventory order."""
    ordered = []
    seen = set()
    for item in inventory.items:
        if item.scope.value != "workspace":
            continue
        path = item.workspace_path
        if path in seen:
            continue
        seen.add(path)
        ordered.append(path)
    return ordered


def workspace_knowledge_paths(inventory, workspace_path):
    # type: (object, str) -> list
    return [
        item.source_path
        for item in inventory.workspace_items(workspace_path)
    ]


def ephemeral_global_profile(knowledge_paths, outputs=None):
    # type: (list, list) -> dict
    """Profile-like contract for existing schema1 ``generate()`` on GLOBAL only."""
    return {
        "name": "project-composition",
        "description": "Scoped assembly GLOBAL knowledge",
        "knowledge": list(knowledge_paths),
        "adapter_priorities": ["high"],
        "outputs": list(outputs or []),
    }


def claim_relative_path(claimed, relpath):
    # type: (set, str) -> None
    """Refuse duplicate adapter-relative target paths (no last-writer-wins)."""
    if relpath in claimed:
        raise ScopedGenerationError(
            "Duplicate adapter output path refused: {}".format(relpath)
        )
    claimed.add(relpath)


def write_claimed_text(output_dir, relpath, content, claimed):
    # type: (Path, str, str, set) -> str
    claim_relative_path(claimed, relpath)
    target = Path(output_dir) / relpath
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")
    return str(target)
