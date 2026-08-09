"""Profile YAML validation against JSON Schema."""

import json
import sys
from pathlib import Path

import yaml
from jsonschema import Draft202012Validator

SCRIPT_DIR = Path(__file__).resolve().parent
ADAPTERS_COMMON = SCRIPT_DIR.parents[1] / "adapters" / "common"
if str(ADAPTERS_COMMON) not in sys.path:
    sys.path.insert(0, str(ADAPTERS_COMMON))

from profile_resolve import (
    ProfileResolveError,
    resolve_profile_knowledge,
    validate_profile_includes,
)

SCHEMA_PATH = Path(__file__).resolve().parents[3] / "schema" / "profile.schema.json"


def load_profile_schema():
    # type: () -> dict
    with SCHEMA_PATH.open(encoding="utf-8") as handle:
        return json.load(handle)


def validate_profiles(repo_root, profiles_dir):
    # type: (Path, Path) -> list
    errors = []
    if not profiles_dir.exists():
        return errors

    schema = load_profile_schema()
    validator = Draft202012Validator(schema)

    for profile_path in sorted(profiles_dir.glob("*.yaml")):
        rel = profile_path.relative_to(repo_root).as_posix()
        text = profile_path.read_text(encoding="utf-8")

        if "rules:" in text:
            errors.append(
                "[PROFILE] {}: profiles must reference knowledge only; "
                "remove 'rules:' entries".format(rel)
            )

        try:
            data = yaml.safe_load(text)
        except yaml.YAMLError as exc:
            errors.append("[PROFILE] {}: invalid YAML: {}".format(rel, exc))
            continue

        if not isinstance(data, dict):
            errors.append("[PROFILE] {}: profile must be a mapping".format(rel))
            continue

        for error in sorted(validator.iter_errors(data), key=lambda e: list(e.path)):
            location = ".".join(str(part) for part in error.path) or "profile"
            errors.append(
                "[PROFILE] {}: {}: {}".format(rel, location, error.message)
            )

        profile_name = data.get("name")
        if isinstance(profile_name, str):
            try:
                resolved = resolve_profile_knowledge(
                    repo_root, profile_name, profiles_dir=profiles_dir
                )
            except ProfileResolveError as exc:
                errors.append("[PROFILE] {}: {}".format(rel, exc))
            else:
                for entry in resolved:
                    doc_path = repo_root / entry
                    if not doc_path.is_file():
                        errors.append(
                            "[PROFILE] {}: references missing document '{}'".format(
                                rel, entry
                            )
                        )
        elif isinstance(data.get("knowledge"), list):
            for entry in data.get("knowledge", []):
                if not isinstance(entry, str):
                    continue
                doc_path = repo_root / entry
                if not doc_path.is_file():
                    errors.append(
                        "[PROFILE] {}: references missing document '{}'".format(
                            rel, entry
                        )
                    )

    errors.extend(validate_profile_includes(repo_root, profiles_dir))

    return errors
