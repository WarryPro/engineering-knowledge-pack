"""Shared helpers for blind scoring, consensus, and reporting."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

import yaml

from eval_common import (
    REPO_ROOT,
    SCHEMA_DIR,
    SCENARIOS_DIR,
    load_json,
    load_schema_validators,
    load_yaml,
    sha256_bytes,
    sha256_file,
    validate_against,
)

PAIR_COMPAT_FIELDS = (
    "scenario_id",
    "scenario_version",
    "profile",
    "ekp_commit",
    "ekp_version",
    "provider",
    "model_config_id",
    "model_id_observed",
    "replicate_index",
    "tools_enabled",
    "session_isolation",
    "prompt_sha256",
)

SAMPLING_FIELDS = ("temperature", "top_p", "seed", "seed_supported", "max_output")

MANDATORY_LIMITATIONS = (
    "unequal context size between baseline and treatment",
    "public benchmark contamination risk",
    "hosted-model drift",
    "stochasticity of model outputs",
    "small sample size",
    "human rater disagreement",
    "single-model scope where applicable",
    "moderate core coverage for API/DB/AuthZ scenarios",
)

RATER_INSTRUCTIONS = """# Blind scoring instructions

Evaluate Response A and Response B independently against the rubric.
Do not infer hidden experimental conditions.
Score only the engineering quality of each response.
Then record A better, B better, or tie with a short reason.

Do not discuss scores with other raters before both have finished.
"""

FORBIDDEN_RATER_META_RE = re.compile(
    r"\b(baseline|treatment|condition|context_sha256|ekp_commit|ekp_version)\b",
    re.IGNORECASE,
)


class ScoringError(Exception):
    """Fatal scoring / blinding / consensus error."""

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    # Python 3.9: Path.write_text has no newline=; open() preserves LF.
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write(text)


def write_bytes(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)


def write_json(path: Path, data: Any) -> None:
    write_text(path, json.dumps(data, indent=2, sort_keys=True) + "\n")


def write_yaml(path: Path, data: Any) -> None:
    write_text(path, yaml.safe_dump(data, sort_keys=False, allow_unicode=True))


def dump_json_bytes(data: Any) -> bytes:
    return (json.dumps(data, indent=2, sort_keys=True) + "\n").encode("utf-8")


def load_run_record(path: Path) -> Dict[str, Any]:
    data = load_json(path)
    if not isinstance(data, dict):
        raise ScoringError("run record must be an object: {}".format(path))
    return data


def resolve_response_bytes(run: Dict[str, Any], run_path: Path) -> bytes:
    rel = run.get("response_file")
    if not isinstance(rel, str) or not rel.strip():
        raise ScoringError("run {} missing response_file".format(run.get("run_id")))
    response_path = (run_path.parent / rel).resolve()
    if not response_path.is_file():
        raise ScoringError(
            "response file missing for run {}: {}".format(run.get("run_id"), response_path)
        )
    data = response_path.read_bytes()
    expected = run.get("response_sha256")
    actual = sha256_bytes(data)
    if expected != actual:
        raise ScoringError(
            "response_sha256 mismatch for {}: expected {}, got {}".format(
                run.get("run_id"), expected, actual
            )
        )
    return data


def load_runs_from_dir(runs_dir: Path) -> List[Tuple[Dict[str, Any], Path, bytes]]:
    if not runs_dir.is_dir():
        raise ScoringError("runs directory does not exist: {}".format(runs_dir))
    rows: List[Tuple[Dict[str, Any], Path, bytes]] = []
    for path in sorted(runs_dir.rglob("*.json"), key=lambda p: p.as_posix()):
        if path.name.startswith("."):
            continue
        # Skip non-run JSON (mapping, indexes) by requiring condition enum.
        try:
            data = load_run_record(path)
        except Exception:
            continue
        if data.get("condition") not in ("baseline", "treatment"):
            continue
        if "run_id" not in data or "response_file" not in data:
            continue
        payload = resolve_response_bytes(data, path)
        rows.append((data, path, payload))
    return rows


def pair_key(run: Dict[str, Any]) -> Tuple[Any, ...]:
    return (
        run.get("scenario_id"),
        run.get("scenario_version"),
        run.get("model_config_id"),
        run.get("replicate_index"),
    )


def sampling_tuple(run: Dict[str, Any]) -> Tuple[Any, ...]:
    sampling = run.get("sampling") or {}
    if not isinstance(sampling, dict):
        raise ScoringError("sampling must be an object for run {}".format(run.get("run_id")))
    return tuple(sampling.get(field) for field in SAMPLING_FIELDS)


def optional_model_version(run: Dict[str, Any]) -> Any:
    return run.get("model_version_reported", None)


def load_rubric_for_scenario(
    scenario_id: str,
    scenarios_dir: Path = SCENARIOS_DIR,
) -> Tuple[Dict[str, Any], bytes, str]:
    scenario_dir = scenarios_dir / scenario_id
    scenario_path = scenario_dir / "scenario.yaml"
    if not scenario_path.is_file():
        raise ScoringError("missing scenario.yaml for {}".format(scenario_id))
    scenario = load_yaml(scenario_path)
    rubric_rel = scenario.get("rubric_file") or "rubric.yaml"
    rubric_path = scenario_dir / rubric_rel
    if not rubric_path.is_file():
        raise ScoringError("missing rubric for scenario {}".format(scenario_id))
    raw = rubric_path.read_bytes()
    rubric = yaml.safe_load(raw.decode("utf-8"))
    if not isinstance(rubric, dict):
        raise ScoringError("rubric must be an object for {}".format(scenario_id))
    return rubric, raw, sha256_bytes(raw)


def load_synthetic_rubric(path: Path) -> Tuple[Dict[str, Any], bytes, str]:
    raw = path.read_bytes()
    rubric = yaml.safe_load(raw.decode("utf-8"))
    if not isinstance(rubric, dict):
        raise ScoringError("rubric must be an object: {}".format(path))
    return rubric, raw, sha256_bytes(raw)


def rubric_cf_ids(rubric: Dict[str, Any]) -> List[str]:
    ids = []
    for row in rubric.get("critical_failures") or []:
        if isinstance(row, dict) and row.get("id"):
            ids.append(str(row["id"]))
    return ids


def rubric_dimensions(rubric: Dict[str, Any]) -> List[str]:
    dims = rubric.get("dimensions") or []
    if not isinstance(dims, list) or not dims:
        raise ScoringError("rubric dimensions missing")
    return [str(d) for d in dims]


def preference_to_condition(preference: str, assignment: Dict[str, Any]) -> str:
    """Map A/B/tie preference to baseline/treatment/tie using mapping assignment."""
    if preference == "tie":
        return "tie"
    if preference not in ("A", "B"):
        raise ScoringError("invalid pairwise preference {!r}".format(preference))
    side = assignment.get(preference) or {}
    condition = side.get("condition")
    if condition not in ("baseline", "treatment"):
        raise ScoringError("mapping assignment missing condition for {}".format(preference))
    return condition


def cf_sets_compatible(a: Sequence[str], b: Sequence[str]) -> bool:
    return set(a) == set(b)


def validate_preference_against_critical_failures(
    preference: str,
    cf_a: Sequence[str],
    cf_b: Sequence[str],
) -> Optional[str]:
    a_has = len(cf_a) >= 1
    b_has = len(cf_b) >= 1
    if a_has and not b_has:
        if preference in ("A", "tie"):
            return "preference {!r} inconsistent with exclusive critical failure on A".format(
                preference
            )
    if b_has and not a_has:
        if preference in ("B", "tie"):
            return "preference {!r} inconsistent with exclusive critical failure on B".format(
                preference
            )
    return None


def execution_order(baseline_at: Any, treatment_at: Any) -> str:
    if not isinstance(baseline_at, str) or not isinstance(treatment_at, str):
        return "unknown"
    if baseline_at == treatment_at:
        return "same"
    if baseline_at < treatment_at:
        return "baseline-first"
    if treatment_at < baseline_at:
        return "treatment-first"
    return "unknown"


def audit_rubric_identity_leakage(text: str) -> List[str]:
    """Return leakage findings for evaluator-visible rubric text."""
    findings = []
    lowered = text.lower()
    for token in ("baseline", "treatment"):
        if re.search(r"\b{}\b".format(token), lowered):
            findings.append("rubric contains experiment identity token {!r}".format(token))
    if re.search(r"\bekp\b", text, re.IGNORECASE):
        findings.append("rubric contains experiment identity token 'EKP'")
    return findings


def schema_validators():
    return load_schema_validators(SCHEMA_DIR)
