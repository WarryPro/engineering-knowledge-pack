"""Test helpers for evaluation foundation validator tests."""

from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path
from typing import Any, Dict, Optional

import yaml

EMPTY_SHA = hashlib.sha256(b"").hexdigest()

MIN_SCENARIO = {
    "id": "synthetic-demo",
    "version": "1.0.0",
    "title": "Synthetic demo scenario",
    "description": "Test-only scenario for structural validation.",
    "category": "architecture",
    "difficulty": "intro",
    "profile": "cursor-core",
    "task_type": "decision",
    "prompt_file": "prompt.md",
    "rubric_file": "rubric.yaml",
    "fixture": None,
    "tags": ["synthetic"],
    "status": "draft",
    "shared_system_instruction_ref": "shared/system_instruction.md",
}

MIN_RUBRIC = {
    "scenario_id": "synthetic-demo",
    "scenario_version": "1.0.0",
    "version": "1.0.0",
    "dimensions": [
        "technical-correctness",
        "architecture-boundaries",
        "tradeoff-reasoning",
        "constraint-adherence",
    ],
    "criteria": {
        "technical-correctness": "Solution is technically sound for the stated task."
    },
    "checks": [{"id": "CHK-01", "description": "Respects stated constraints."}],
    "critical_failures": [
        {"id": "CF-01", "description": "Recommends a materially unsafe change."}
    ],
    "strong_outcomes": ["Clear boundaries between policy and infrastructure."],
    "acceptable_alternatives": ["Multiple valid designs may exist."],
    "important_tradeoffs": ["Complexity versus isolation."],
}


def write_yaml(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def copy_real_schemas(dst_evals: Path, src_evals: Path) -> None:
    shutil.copytree(src_evals / "schema", dst_evals / "schema")
    shared = dst_evals / "shared"
    shared.mkdir(parents=True, exist_ok=True)
    (shared / "system_instruction.md").write_text(
        "Act as a senior software engineer.\n"
        "Analyze the task and propose the most appropriate solution.\n"
        "Explain important trade-offs and respect the stated constraints.\n",
        encoding="utf-8",
    )
    (dst_evals / "scenarios").mkdir(parents=True, exist_ok=True)


def add_scenario(
    evals_root: Path,
    scenario: Optional[Dict[str, Any]] = None,
    rubric: Optional[Dict[str, Any]] = None,
    prompt: str = "Design an approach for the described engineering problem.\n",
    scenario_dirname: Optional[str] = None,
) -> Path:
    scenario = dict(scenario or MIN_SCENARIO)
    rubric = dict(rubric or MIN_RUBRIC)
    rubric["scenario_id"] = scenario["id"]
    rubric["scenario_version"] = scenario["version"]
    dirname = scenario_dirname or scenario["id"]
    scenario_dir = evals_root / "scenarios" / dirname
    scenario_dir.mkdir(parents=True, exist_ok=True)
    write_yaml(scenario_dir / "scenario.yaml", scenario)
    # Only materialize local relative artifacts (skip unsafe traversal/absolute paths).
    rubric_rel = scenario["rubric_file"]
    prompt_rel = scenario["prompt_file"]
    if isinstance(rubric_rel, str) and ".." not in Path(rubric_rel).parts and not Path(rubric_rel).is_absolute():
        write_yaml(scenario_dir / rubric_rel, rubric)
    if isinstance(prompt_rel, str) and ".." not in Path(prompt_rel).parts and not Path(prompt_rel).is_absolute():
        (scenario_dir / prompt_rel).write_text(prompt, encoding="utf-8")
    return scenario_dir


def make_run(
    response_text: str = "Synthetic model response for tests only.\n",
    condition: str = "baseline",
    **overrides: Any,
) -> Dict[str, Any]:
    response_sha = hashlib.sha256(response_text.encode("utf-8")).hexdigest()
    context_sha = EMPTY_SHA if condition == "baseline" else hashlib.sha256(b"ctx").hexdigest()
    data = {
        "run_id": "run-synthetic-001",
        "scenario_id": "synthetic-demo",
        "scenario_version": "1.0.0",
        "ekp_commit": "a" * 40,
        "ekp_version": "0.17.0.dev0",
        "profile": "cursor-core",
        "condition": condition,
        "provider": "synthetic",
        "model_config_id": "synthetic-config",
        "model_id_observed": "synthetic-model",
        "executed_at": "2026-09-04T00:00:00Z",
        "replicate_index": 1,
        "sampling": {
            "temperature": 0.0,
            "top_p": None,
            "seed": None,
            "seed_supported": False,
            "max_output": 1024,
            "reasoning_effort": None,
        },
        "tools_enabled": False,
        "session_isolation": "fresh",
        "prompt_sha256": "b" * 64,
        "context_sha256": context_sha,
        "response_sha256": response_sha,
        "response_file": "response.txt",
    }
    data.update(overrides)
    return data


def make_score_sheet(**overrides: Any) -> Dict[str, Any]:
    dims = {
        "technical-correctness": 2,
        "architecture-boundaries": 2,
        "tradeoff-reasoning": 2,
        "constraint-adherence": 2,
    }
    response = {
        "response_id": "resp-a",
        "response_sha256": "c" * 64,
        "dimension_scores": dict(dims),
        "critical_failures": [],
        "notes": "",
    }
    data = {
        "score_id": "score-001",
        "pair_id": "pair-001",
        "scenario_id": "synthetic-demo",
        "scenario_version": "1.0.0",
        "rubric_version": "1.0.0",
        "rubric_sha256": "d" * 64,
        "replicate_index": 1,
        "rater_alias": "rater-x",
        "blinded": True,
        "response_a": response,
        "response_b": {
            "response_id": "resp-b",
            "response_sha256": "e" * 64,
            "dimension_scores": dict(dims),
            "critical_failures": [],
        },
        "pairwise_preference": "tie",
        "pairwise_reason": "Comparable engineering quality.",
        "scored_at": "2026-09-04T00:00:00Z",
    }
    data.update(overrides)
    return data


def make_report(**overrides: Any) -> Dict[str, Any]:
    data = {
        "evaluation_id": "eval-synthetic",
        "ekp_version": "0.17.0.dev0",
        "ekp_commit": "a" * 40,
        "model_config_id": "synthetic-config",
        "scenario_count": 0,
        "pair_count": 0,
        "outcomes": {
            "improved": 0,
            "tied": 0,
            "regressed": 0,
            "disputed": 0,
        },
        "limitations": [
            "Synthetic test report only.",
            "Small sample.",
        ],
    }
    data.update(overrides)
    return data
