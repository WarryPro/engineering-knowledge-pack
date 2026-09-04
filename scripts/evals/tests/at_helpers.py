"""Helpers for AT blind/scoring pipeline tests (synthetic only)."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import yaml

from helpers import EMPTY_SHA, write_json, write_yaml

SYNTHETIC_RUBRIC = {
    "scenario_id": "synth-alpha",
    "scenario_version": "1.0.0",
    "version": "1.0.0",
    "dimensions": [
        "technical-correctness",
        "architecture-boundaries",
        "tradeoff-reasoning",
        "constraint-adherence",
    ],
    "criteria": {
        "technical-correctness": "Technically coherent synthetic answer.",
    },
    "critical_failures": [
        {"id": "CF-01", "description": "Materially unsafe synthetic recommendation."},
        {"id": "CF-02", "description": "Ignores explicit synthetic constraint."},
    ],
    "strong_outcomes": ["Clear synthetic engineering reasoning."],
    "acceptable_alternatives": ["Multiple synthetic designs may exist."],
    "important_tradeoffs": ["Complexity versus simplicity."],
}


def write_run_bundle(
    runs_dir: Path,
    *,
    scenario_id: str,
    replicate_index: int,
    baseline_text: str,
    treatment_text: str,
    model_config_id: str = "synthetic-config",
    prompt_sha: Optional[str] = None,
    baseline_at: str = "2026-09-04T01:00:00Z",
    treatment_at: str = "2026-09-04T02:00:00Z",
    **overrides: Any,
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    prompt_sha = prompt_sha or ("b" * 64)
    shared = {
        "scenario_id": scenario_id,
        "scenario_version": "1.0.0",
        "ekp_commit": "a" * 40,
        "ekp_version": "0.17.0.dev0",
        "profile": "cursor-core",
        "provider": "synthetic",
        "model_config_id": model_config_id,
        "model_id_observed": "synthetic-model",
        "replicate_index": replicate_index,
        "sampling": {
            "temperature": 0.0,
            "top_p": None,
            "seed": None,
            "seed_supported": False,
            "max_output": 1024,
        },
        "tools_enabled": False,
        "session_isolation": "fresh",
        "prompt_sha256": prompt_sha,
    }
    shared.update({k: v for k, v in overrides.items() if k not in ("condition",)})

    def _one(condition: str, text: str, executed_at: str) -> Dict[str, Any]:
        payload = text.encode("utf-8")
        digest = hashlib.sha256(payload).hexdigest()
        run_id = "{}-{}-r{}-{}".format(scenario_id, condition, replicate_index, digest[:8])
        folder = runs_dir / run_id
        folder.mkdir(parents=True, exist_ok=True)
        (folder / "response.txt").write_bytes(payload)
        run = dict(shared)
        run.update(
            {
                "run_id": run_id,
                "condition": condition,
                "executed_at": executed_at,
                "context_sha256": EMPTY_SHA
                if condition == "baseline"
                else hashlib.sha256(b"synthetic-ctx").hexdigest(),
                "response_sha256": digest,
                "response_file": "response.txt",
            }
        )
        write_json(folder / "run.json", run)
        return run

    baseline = _one("baseline", baseline_text, baseline_at)
    treatment = _one("treatment", treatment_text, treatment_at)
    return baseline, treatment


def default_dims(score: int = 2) -> Dict[str, int]:
    return {
        "technical-correctness": score,
        "architecture-boundaries": score,
        "tradeoff-reasoning": score,
        "constraint-adherence": score,
    }


def make_completed_score(
    *,
    pair_id: str,
    scenario_id: str,
    replicate_index: int,
    rater_alias: str,
    rubric_sha: str,
    response_a_sha: str,
    response_b_sha: str,
    preference: str,
    reason: str = "Synthetic engineering judgment.",
    dims_a: Optional[Dict[str, int]] = None,
    dims_b: Optional[Dict[str, int]] = None,
    cf_a: Optional[List[str]] = None,
    cf_b: Optional[List[str]] = None,
) -> Dict[str, Any]:
    return {
        "score_id": "{}--{}".format(pair_id, rater_alias),
        "pair_id": pair_id,
        "scenario_id": scenario_id,
        "scenario_version": "1.0.0",
        "rubric_version": "1.0.0",
        "rubric_sha256": rubric_sha,
        "replicate_index": replicate_index,
        "rater_alias": rater_alias,
        "blinded": True,
        "response_a": {
            "response_id": "response-A",
            "response_sha256": response_a_sha,
            "dimension_scores": dict(dims_a or default_dims(2)),
            "critical_failures": list(cf_a or []),
            "notes": "",
        },
        "response_b": {
            "response_id": "response-B",
            "response_sha256": response_b_sha,
            "dimension_scores": dict(dims_b or default_dims(2)),
            "critical_failures": list(cf_b or []),
            "notes": "",
        },
        "pairwise_preference": preference,
        "pairwise_reason": reason,
        "scored_at": "2026-09-04T12:00:00Z",
    }


def write_score_yaml(path: Path, sheet: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(sheet, sort_keys=False), encoding="utf-8")
