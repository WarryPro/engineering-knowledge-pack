"""Load EKP profiles for adapter generation."""

from pathlib import Path

from common.profile_resolve import load_profile_yaml, resolve_profile_knowledge
from common.paths import get_repo_root

# Canonical adapter identifiers (registry must stay in sync).
KNOWN_ADAPTERS = ("cursor", "copilot", "antigravity", "claude")
IMPLEMENTED_ADAPTERS = ("cursor", "copilot", "antigravity")


def resolve_profile_outputs(profile_data):
    # type: (dict) -> list
    """
    Resolve requested adapter outputs for a profile.

    ``outputs`` is canonical. ``adapter.target`` is a legacy alias when
    ``outputs`` is absent (ADR-0009).
    """
    outputs = profile_data.get("outputs")
    if isinstance(outputs, list) and outputs:
        return [str(item) for item in outputs if isinstance(item, str)]

    adapter = profile_data.get("adapter")
    if isinstance(adapter, dict):
        targets = adapter.get("target")
        if isinstance(targets, list) and targets:
            return [str(item) for item in targets if isinstance(item, str)]

    return ["cursor"]


def resolve_adapter_priorities(profile_data):
    # type: (dict) -> list
    """Read adapter_priority filters from profile adapter.include settings."""
    adapter_priorities = ["high"]
    adapter = profile_data.get("adapter")
    if isinstance(adapter, dict):
        include = adapter.get("include")
        if isinstance(include, dict):
            priorities = include.get("adapter_priority")
            if isinstance(priorities, list) and priorities:
                adapter_priorities = [str(p) for p in priorities]
    return adapter_priorities


def load_profile(profile_path, repo_root=None):
    # type: (Path, Path) -> dict
    """Load a profile with resolved knowledge paths and adapter settings."""
    root = repo_root or get_repo_root()
    data = load_profile_yaml(profile_path)

    name = data.get("name")
    if not isinstance(name, str) or not name:
        raise ValueError("Profile missing name: {}".format(profile_path))

    knowledge = resolve_profile_knowledge(root, name)
    description = data.get("description")
    if not isinstance(description, str):
        description = ""

    return {
        "name": name,
        "description": description.strip(),
        "knowledge": knowledge,
        "adapter_priorities": resolve_adapter_priorities(data),
        "outputs": resolve_profile_outputs(data),
    }


def load_profile_by_name(profile_name, repo_root=None):
    # type: (str, Path) -> dict
    """Load a profile YAML by profile name."""
    root = repo_root or get_repo_root()
    profile_path = root / "profiles" / "{}.yaml".format(profile_name)
    if not profile_path.is_file():
        raise ValueError("Profile not found: {}".format(profile_path))
    return load_profile(profile_path, repo_root=root)
