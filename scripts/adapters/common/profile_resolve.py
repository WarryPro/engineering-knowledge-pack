"""Profile composition: resolve includes into flat knowledge path lists."""

from pathlib import Path

import yaml

PROFILE_NAME_RE = r"^[a-z0-9-]+$"


class ProfileResolveError(Exception):
    """Raised when profile includes cannot be resolved."""


def load_profile_yaml(profile_path):
    # type: (Path) -> dict
    """Load a profile YAML file. Raises ProfileResolveError on invalid YAML."""
    try:
        data = yaml.safe_load(profile_path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise ProfileResolveError(
            "invalid YAML in {}: {}".format(profile_path, exc)
        )

    if not isinstance(data, dict):
        raise ProfileResolveError(
            "{}: profile must be a mapping".format(profile_path)
        )
    return data


def _profile_file(repo_root, profile_name, profiles_dir=None):
    # type: (Path, str, Path) -> Path
    if profiles_dir is None:
        profiles_dir = repo_root / "profiles"
    return profiles_dir / "{}.yaml".format(profile_name)


def resolve_profile_knowledge(repo_root, profile_name, stack=None, profiles_dir=None):
    # type: (Path, str, list) -> list
    """
    Resolve includes depth-first and return deduplicated knowledge paths.

    Included paths precede local paths. First occurrence wins on dedupe.
    """
    if stack is None:
        stack = []

    if profile_name in stack:
        chain = " -> ".join(stack + [profile_name])
        raise ProfileResolveError(
            "circular profile include: {}".format(chain)
        )

    profile_path = _profile_file(repo_root, profile_name, profiles_dir)
    if not profile_path.is_file():
        raise ProfileResolveError(
            "unknown profile include: '{}' (no profiles/{}.yaml)".format(
                profile_name, profile_name
            )
        )

    data = load_profile_yaml(profile_path)
    includes = data.get("includes") or []
    local_knowledge = data.get("knowledge") or []

    if not isinstance(includes, list):
        raise ProfileResolveError(
            "{}: includes must be a list".format(profile_path)
        )
    if not isinstance(local_knowledge, list):
        raise ProfileResolveError(
            "{}: knowledge must be a list".format(profile_path)
        )

    merged = []
    seen = set()

    def add_path(path):
        if path not in seen:
            seen.add(path)
            merged.append(path)

    next_stack = stack + [profile_name]
    for included in includes:
        if not isinstance(included, str):
            raise ProfileResolveError(
                "{}: includes entries must be strings".format(profile_path)
            )
        for path in resolve_profile_knowledge(
            repo_root, included, next_stack, profiles_dir
        ):
            add_path(path)

    for path in local_knowledge:
        if not isinstance(path, str):
            continue
        add_path(path)

    return merged


def validate_profile_includes(repo_root, profiles_dir):
    # type: (Path, Path) -> list
    """Validate includes for all profiles. Returns error strings."""
    errors = []

    if not profiles_dir.is_dir():
        return errors

    for profile_path in sorted(profiles_dir.glob("*.yaml")):
        rel = profile_path.relative_to(repo_root).as_posix()
        try:
            data = load_profile_yaml(profile_path)
        except ProfileResolveError as exc:
            errors.append("[PROFILE] {}: {}".format(rel, exc))
            continue

        profile_name = data.get("name")
        if not isinstance(profile_name, str):
            continue

        includes = data.get("includes") or []
        if not isinstance(includes, list):
            errors.append("[PROFILE] {}: includes must be a list".format(rel))
            continue

        for included in includes:
            if not isinstance(included, str):
                errors.append(
                    "[PROFILE] {}: includes entries must be strings".format(rel)
                )
                continue
            inc_path = profiles_dir / "{}.yaml".format(included)
            if not inc_path.is_file():
                errors.append(
                    "[PROFILE] {}: unknown include '{}'".format(rel, included)
                )

        try:
            resolve_profile_knowledge(repo_root, profile_name, profiles_dir=profiles_dir)
        except ProfileResolveError as exc:
            errors.append("[PROFILE] {}: {}".format(rel, exc))

    return errors
