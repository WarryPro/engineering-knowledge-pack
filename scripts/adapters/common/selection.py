"""Shared concept selection for adapter generation."""

import json
from pathlib import Path

from common.paths import get_dist_path, get_repo_root


def load_json(path):
    # type: (Path) -> dict
    """Load a JSON file from disk."""
    return json.loads(path.read_text(encoding="utf-8"))


def load_generation_indexes(dist_dir=None):
    # type: (Path) -> tuple
    """Load concept-index and adapter-manifest from dist/."""
    target = dist_dir or get_dist_path()
    concept_index = load_json(target / "concept-index.json")
    manifest = load_json(target / "adapter-manifest.json")
    return concept_index, manifest


def read_knowledge_document(repo_root, relative_path):
    # type: (Path, str) -> str
    """Read a knowledge markdown file."""
    return (repo_root / relative_path).read_text(encoding="utf-8")


def select_manifest_rules(manifest, knowledge_paths, adapter_priorities):
    # type: (dict, list, list) -> list
    """
    Select adapter-manifest rule entries for a profile.

    Filters by adapter_priority and knowledge path membership, preserving
    deterministic concept-id ordering.
    """
    knowledge_set = set(knowledge_paths)
    priorities = set(adapter_priorities)
    selected = [
        entry
        for entry in manifest.get("rules", [])
        if entry.get("priority") in priorities
        and entry.get("source") in knowledge_set
    ]
    selected.sort(key=lambda entry: entry.get("concept", ""))
    return selected


def markdown_cache_for_profile(repo_root, knowledge_paths):
    # type: (Path, list) -> dict
    """Build a lazy markdown loader cache for profile knowledge paths."""
    cache = {}

    def get_markdown(path):
        # type: (str) -> str
        if path not in cache:
            cache[path] = read_knowledge_document(repo_root, path)
        return cache[path]

    return get_markdown
