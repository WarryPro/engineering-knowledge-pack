"""Shared helpers for evaluation foundation tooling."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any, List, Optional, Tuple

import yaml
from jsonschema import Draft202012Validator

REPO_ROOT = Path(__file__).resolve().parents[2]
EVALS_ROOT = REPO_ROOT / "evals"
SCHEMA_DIR = EVALS_ROOT / "schema"
SCENARIOS_DIR = EVALS_ROOT / "scenarios"
SHARED_DIR = EVALS_ROOT / "shared"
SYSTEM_INSTRUCTION_PATH = SHARED_DIR / "system_instruction.md"
EVIDENCE_DIR = EVALS_ROOT / "evidence"

SCHEMA_FILES = (
    "scenario.schema.json",
    "rubric.schema.json",
    "run.schema.json",
    "score-sheet.schema.json",
    "report-summary.schema.json",
)

CORE_DIMENSIONS = (
    "technical-correctness",
    "architecture-boundaries",
    "tradeoff-reasoning",
    "maintainability-change-safety",
    "testing-verifiability",
    "security-operational-risk",
    "constraint-adherence",
)

# Matches EKP concept IDs such as EKP-P01..P10 and EKP-AB12.
CONCEPT_ID_RE = re.compile(r"\bEKP-(?:P(?:0[1-9]|10)|[A-Z]{2}\d{2})\b")

SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
EMPTY_BYTES_SHA256 = hashlib.sha256(b"").hexdigest()

FORBIDDEN_METADATA_KEY_RE = re.compile(
    r"(api[_-]?key|secret|access[_-]?token|authorization|password)",
    re.IGNORECASE,
)

CONDITION_LEAK_KEYS = frozenset(
    {
        "baseline",
        "treatment",
        "condition",
        "ekp-enabled",
        "ekp_enabled",
    }
)


class EvalValidationError(Exception):
    """Single validation finding."""

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_text(text: str) -> str:
    return sha256_bytes(text.encode("utf-8"))


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def load_yaml(path: Path) -> Any:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    return data


def load_schema_validators(schema_dir: Path = SCHEMA_DIR) -> dict:
    validators = {}
    for name in SCHEMA_FILES:
        path = schema_dir / name
        schema = load_json(path)
        Draft202012Validator.check_schema(schema)
        key = name.replace(".schema.json", "")
        validators[key] = Draft202012Validator(schema)
    return validators


def validate_against(validator: Draft202012Validator, instance: Any, label: str) -> List[str]:
    errors = []
    for err in sorted(validator.iter_errors(instance), key=lambda e: list(e.path)):
        path = ".".join(str(p) for p in err.path) or "(root)"
        errors.append("{}: {}: {}".format(label, path, err.message))
    return errors


def is_unsafe_relative_path(value: str) -> Optional[str]:
    if not isinstance(value, str) or not value.strip():
        return "path must be a non-empty string"
    if Path(value).is_absolute():
        return "absolute paths are forbidden"
    if "\\" in value:
        return "use forward-slash relative paths only"
    parts = Path(value).parts
    if any(part == ".." for part in parts):
        return "path traversal ('..') is forbidden"
    if any(part == "" for part in parts):
        return "empty path segment is forbidden"
    return None


def resolve_under(root: Path, relative: str, label: str) -> Tuple[Optional[Path], Optional[str]]:
    problem = is_unsafe_relative_path(relative)
    if problem:
        return None, "{}: {}".format(label, problem)
    candidate = (root / relative).resolve()
    root_resolved = root.resolve()
    try:
        candidate.relative_to(root_resolved)
    except ValueError:
        return None, "{}: resolves outside allowed root {}".format(label, root_resolved)
    if candidate.is_symlink():
        # Reject symlink escape: target must also stay under root.
        target = candidate.resolve()
        try:
            target.relative_to(root_resolved)
        except ValueError:
            return None, "{}: symlink escapes allowed root {}".format(label, root_resolved)
    return candidate, None


def iter_scenario_dirs(scenarios_dir: Path = SCENARIOS_DIR) -> List[Path]:
    if not scenarios_dir.is_dir():
        return []
    dirs = []
    for child in sorted(scenarios_dir.iterdir(), key=lambda p: p.name):
        if child.is_dir() and not child.name.startswith("."):
            dirs.append(child)
    return dirs


def find_concept_ids(text: str) -> List[str]:
    return CONCEPT_ID_RE.findall(text)


def collect_forbidden_metadata_keys(obj: Any, prefix: str = "") -> List[str]:
    found = []
    if isinstance(obj, dict):
        for key, value in obj.items():
            path = "{}.{}".format(prefix, key) if prefix else str(key)
            if FORBIDDEN_METADATA_KEY_RE.search(str(key)):
                found.append(path)
            if str(key).lower() in CONDITION_LEAK_KEYS and prefix:
                # nested condition leaks are reported by callers when needed
                pass
            found.extend(collect_forbidden_metadata_keys(value, path))
    elif isinstance(obj, list):
        for index, item in enumerate(obj):
            path = "{}[{}]".format(prefix, index)
            found.extend(collect_forbidden_metadata_keys(item, path))
    return found


def profile_exists_and_resolves(profile_name: str, repo_root: Path = REPO_ROOT) -> Optional[str]:
    """Resolve a profile without importing the adapters package as top-level `common`."""
    import importlib.util

    module_path = REPO_ROOT / "scripts" / "adapters" / "common" / "profile_resolve.py"
    spec = importlib.util.spec_from_file_location(
        "ekp_eval_profile_resolve", module_path
    )
    if spec is None or spec.loader is None:
        return "unable to load profile resolver"
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    profile_path = repo_root / "profiles" / "{}.yaml".format(profile_name)
    if not profile_path.is_file():
        return "unknown profile '{}' (missing profiles/{}.yaml)".format(
            profile_name, profile_name
        )
    try:
        paths = module.resolve_profile_knowledge(repo_root, profile_name)
    except module.ProfileResolveError as exc:
        return "profile '{}' failed to resolve: {}".format(profile_name, exc)
    if not paths:
        return "profile '{}' resolved to an empty knowledge path list".format(profile_name)
    return None


def ensure_adapters_on_path() -> None:
    """Deprecated helper retained for compatibility; prefer importlib loading."""
    adapters = str(REPO_ROOT / "scripts" / "adapters")
    import sys

    if adapters in sys.path:
        sys.path.remove(adapters)
    sys.path.insert(0, adapters)
