#!/usr/bin/env python3
"""Blind pair generation: operator-private mapping + rater packages.

No model execution. Synthetic or imported runs only.
"""

from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import secrets
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

_SCRIPT_DIR = Path(__file__).resolve().parent
if str(_SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPT_DIR))

from eval_common import REPO_ROOT, SCENARIOS_DIR, sha256_bytes  # noqa: E402
from scoring_common import (  # noqa: E402
    FORBIDDEN_RATER_META_RE,
    PAIR_COMPAT_FIELDS,
    RATER_INSTRUCTIONS,
    ScoringError,
    audit_rubric_identity_leakage,
    execution_order,
    load_rubric_for_scenario,
    load_runs_from_dir,
    load_synthetic_rubric,
    optional_model_version,
    pair_key,
    sampling_tuple,
    write_bytes,
    write_json,
    write_text,
    write_yaml,
)

MAPPING_NAME = "mapping.json"
SALT_NAME = "blinding-salt.hex"


def generate_salt_hex(nbytes: int = 32) -> str:
    return secrets.token_hex(nbytes)


def parse_salt_hex(value: str) -> bytes:
    text = value.strip().lower()
    if text.startswith("0x"):
        text = text[2:]
    if not re_fullmatch_hex(text) or len(text) < 32:
        raise ScoringError("salt must be hex with at least 128 bits")
    return bytes.fromhex(text)


def re_fullmatch_hex(text: str) -> bool:
    import re

    return bool(re.fullmatch(r"[0-9a-f]+", text))


def make_pair_id(salt: bytes, scenario_id: str, scenario_version: str, model_config_id: str, replicate_index: int) -> str:
    material = "{}|{}|{}|{}".format(
        scenario_id, scenario_version, model_config_id, int(replicate_index)
    ).encode("utf-8")
    digest = hmac.new(salt, material, hashlib.sha256).hexdigest()
    return "pair-{}".format(digest[:20])


def rank_key(salt: bytes, pair_id: str) -> str:
    return hmac.new(salt, pair_id.encode("utf-8"), hashlib.sha256).hexdigest()


def validate_pair_compatibility(
    baseline: Dict[str, Any],
    treatment: Dict[str, Any],
) -> None:
    for field in PAIR_COMPAT_FIELDS:
        if baseline.get(field) != treatment.get(field):
            raise ScoringError(
                "pair compatibility failed on {}: {!r} vs {!r}".format(
                    field, baseline.get(field), treatment.get(field)
                )
            )
    if sampling_tuple(baseline) != sampling_tuple(treatment):
        raise ScoringError("pair compatibility failed on sampling settings")
    if optional_model_version(baseline) != optional_model_version(treatment):
        raise ScoringError("pair compatibility failed on model_version_reported")
    if baseline.get("condition") != "baseline":
        raise ScoringError("expected baseline condition for baseline run")
    if treatment.get("condition") != "treatment":
        raise ScoringError("expected treatment condition for treatment run")
    if baseline.get("condition") == treatment.get("condition"):
        raise ScoringError("conditions must differ")
    if baseline.get("context_sha256") == treatment.get("context_sha256"):
        raise ScoringError("context_sha256 must differ between baseline and treatment")
    if baseline.get("prompt_sha256") != treatment.get("prompt_sha256"):
        raise ScoringError("prompt_sha256 mismatch blocks pair")
    if baseline.get("model_id_observed") != treatment.get("model_id_observed"):
        raise ScoringError("model_id_observed mismatch blocks pair")


def group_runs_into_pairs(
    rows: Sequence[Tuple[Dict[str, Any], Path, bytes]],
) -> List[Dict[str, Any]]:
    buckets: Dict[Tuple[Any, ...], Dict[str, Any]] = {}
    for run, path, payload in rows:
        key = pair_key(run)
        bucket = buckets.setdefault(key, {"baseline": None, "treatment": None})
        condition = run.get("condition")
        if condition not in ("baseline", "treatment"):
            raise ScoringError("invalid condition in run {}".format(run.get("run_id")))
        if bucket[condition] is not None:
            raise ScoringError(
                "duplicate {} run for pair key {}".format(condition, key)
            )
        bucket[condition] = {
            "run": run,
            "path": path,
            "response_bytes": payload,
        }

    pairs = []
    for key, bucket in sorted(buckets.items(), key=lambda item: item[0]):
        if bucket["baseline"] is None or bucket["treatment"] is None:
            missing = "baseline" if bucket["baseline"] is None else "treatment"
            raise ScoringError(
                "missing {} peer for pair key {}".format(missing, key)
            )
        baseline = bucket["baseline"]["run"]
        treatment = bucket["treatment"]["run"]
        validate_pair_compatibility(baseline, treatment)
        pairs.append(
            {
                "scenario_id": baseline["scenario_id"],
                "scenario_version": baseline["scenario_version"],
                "model_config_id": baseline["model_config_id"],
                "replicate_index": int(baseline["replicate_index"]),
                "profile": baseline["profile"],
                "ekp_commit": baseline["ekp_commit"],
                "ekp_version": baseline["ekp_version"],
                "prompt_sha256": baseline["prompt_sha256"],
                "baseline": bucket["baseline"],
                "treatment": bucket["treatment"],
                "executed_at_order": execution_order(
                    baseline.get("executed_at"), treatment.get("executed_at")
                ),
            }
        )
    if not pairs:
        raise ScoringError("no complete baseline/treatment pairs found")
    return pairs


def assign_ab(
    salt: bytes, pairs: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    ranked = sorted(
        pairs,
        key=lambda p: (
            rank_key(salt, p["pair_id"]),
            p["scenario_id"],
            p["replicate_index"],
            p["model_config_id"],
        ),
    )
    n = len(ranked)
    treatment_as_a = n // 2
    # For odd n, difference <= 1 automatically with n//2 vs n - n//2
    for index, pair in enumerate(ranked):
        if index < treatment_as_a:
            pair["treatment_side"] = "A"
            pair["baseline_side"] = "B"
        else:
            pair["treatment_side"] = "B"
            pair["baseline_side"] = "A"
    # Restore deterministic scenario order for packaging, keeping assignment.
    return sorted(
        ranked,
        key=lambda p: (
            p["scenario_id"],
            p["replicate_index"],
            p["model_config_id"],
            p["pair_id"],
        ),
    )


def balance_counts(pairs: Sequence[Dict[str, Any]]) -> Tuple[int, int]:
    a = sum(1 for p in pairs if p.get("treatment_side") == "A")
    b = sum(1 for p in pairs if p.get("treatment_side") == "B")
    return a, b


def _side_record(condition: str, entry: Dict[str, Any]) -> Dict[str, Any]:
    run = entry["run"]
    return {
        "condition": condition,
        "run_id": run["run_id"],
        "response_sha256": run["response_sha256"],
        "response_file": run.get("response_file"),
        "executed_at": run.get("executed_at"),
    }


def build_mapping_document(
    salt: bytes,
    pairs: Sequence[Dict[str, Any]],
) -> Dict[str, Any]:
    out_pairs = []
    for pair in pairs:
        assignment = {
            pair["treatment_side"]: _side_record("treatment", pair["treatment"]),
            pair["baseline_side"]: _side_record("baseline", pair["baseline"]),
        }
        out_pairs.append(
            {
                "pair_id": pair["pair_id"],
                "scenario_id": pair["scenario_id"],
                "scenario_version": pair["scenario_version"],
                "model_config_id": pair["model_config_id"],
                "replicate_index": pair["replicate_index"],
                "profile": pair["profile"],
                "ekp_commit": pair["ekp_commit"],
                "ekp_version": pair["ekp_version"],
                "prompt_sha256": pair["prompt_sha256"],
                "assignment": {
                    "A": assignment["A"],
                    "B": assignment["B"],
                },
                "treatment_as": pair["treatment_side"],
                "executed_at_order": pair["executed_at_order"],
            }
        )
    treatment_a, treatment_b = balance_counts(pairs)
    return {
        "format_version": 1,
        "blinding_salt_sha256": sha256_bytes(salt),
        "pair_count": len(out_pairs),
        "treatment_as_a": treatment_a,
        "treatment_as_b": treatment_b,
        "pairs": out_pairs,
    }


def _load_participant_and_system(
    pair: Dict[str, Any],
    packages_root: Optional[Path],
    materials: Dict[str, Dict[str, bytes]],
) -> Tuple[bytes, bytes]:
    prompt_sha = pair["prompt_sha256"]
    if prompt_sha in materials:
        return materials[prompt_sha]["participant"], materials[prompt_sha]["system"]
    if packages_root is None:
        # Synthetic fallback materials (tests / smoke without prepared packages).
        participant = (
            "# Synthetic participant\n\n"
            "Synthetic scoring task for pair {}.\n".format(pair["pair_id"])
        ).encode("utf-8")
        system = (
            "Act as a senior software engineer.\n"
            "Analyze the task and propose the most appropriate solution.\n"
        ).encode("utf-8")
        return participant, system

    # Prefer baseline package (participant identical).
    scenario_id = pair["scenario_id"]
    for condition in ("baseline", "treatment"):
        pkg = packages_root / scenario_id / condition
        participant_path = pkg / "participant.md"
        system_path = pkg / "system_instruction.md"
        if participant_path.is_file() and system_path.is_file():
            participant = participant_path.read_bytes()
            system = system_path.read_bytes()
            if sha256_bytes(participant) != prompt_sha:
                raise ScoringError(
                    "prepared participant hash mismatch for {}".format(scenario_id)
                )
            return participant, system
    raise ScoringError(
        "prepared package materials missing for scenario {}".format(scenario_id)
    )


def build_score_template(
    pair: Dict[str, Any],
    rubric: Dict[str, Any],
    rubric_sha: str,
    rater_alias: str,
    response_a_sha: str,
    response_b_sha: str,
) -> Dict[str, Any]:
    dims = {d: None for d in rubric.get("dimensions") or []}
    return {
        "score_id": "{}--{}".format(pair["pair_id"], rater_alias),
        "pair_id": pair["pair_id"],
        "scenario_id": pair["scenario_id"],
        "scenario_version": pair["scenario_version"],
        "rubric_version": rubric.get("version"),
        "rubric_sha256": rubric_sha,
        "replicate_index": pair["replicate_index"],
        "rater_alias": rater_alias,
        "blinded": True,
        "response_a": {
            "response_id": "response-A",
            "response_sha256": response_a_sha,
            "dimension_scores": dims,
            "critical_failures": [],
            "notes": "",
        },
        "response_b": {
            "response_id": "response-B",
            "response_sha256": response_b_sha,
            "dimension_scores": dict(dims),
            "critical_failures": [],
            "notes": "",
        },
        "pairwise_preference": None,
        "pairwise_reason": "",
        "scored_at": "",
        "_template": True,
        "_instructions": (
            "Replace null dimension scores with 0-3. "
            "Set pairwise_preference to A, B, or tie. "
            "Remove _template before import."
        ),
    }


def _assert_no_rater_leakage(path: Path, text: str) -> None:
    # Allow leakage only inside response body files (raw model output).
    if path.name in ("response-A.md", "response-B.md"):
        return
    if FORBIDDEN_RATER_META_RE.search(text):
        raise ScoringError(
            "rater package leakage in {}: matches experiment identity metadata".format(
                path.as_posix()
            )
        )


def write_rater_pair_package(
    pair_dir: Path,
    pair: Dict[str, Any],
    rubric: Dict[str, Any],
    rubric_raw: bytes,
    rubric_sha: str,
    participant: bytes,
    system: bytes,
    response_a: bytes,
    response_b: bytes,
    rater_aliases: Sequence[str],
) -> None:
    findings = audit_rubric_identity_leakage(rubric_raw.decode("utf-8"))
    if findings:
        raise ScoringError(
            "rubric identity leakage for {}: {}".format(
                pair["scenario_id"], "; ".join(findings)
            )
        )

    write_bytes(pair_dir / "participant.md", participant)
    write_bytes(pair_dir / "system_instruction.md", system)
    write_bytes(pair_dir / "rubric.yaml", rubric_raw)
    write_bytes(pair_dir / "response-A.md", response_a)
    write_bytes(pair_dir / "response-B.md", response_b)

    meta = {
        "pair_id": pair["pair_id"],
        "scenario_id": pair["scenario_id"],
        "scenario_version": pair["scenario_version"],
        "replicate_index": pair["replicate_index"],
        "rubric_sha256": rubric_sha,
        "response_a_sha256": sha256_bytes(response_a),
        "response_b_sha256": sha256_bytes(response_b),
        "blinded": True,
    }
    meta_text = json.dumps(meta, indent=2, sort_keys=True) + "\n"
    _assert_no_rater_leakage(pair_dir / "pair-meta.json", meta_text)
    write_text(pair_dir / "pair-meta.json", meta_text)

    for alias in rater_aliases:
        template = build_score_template(
            pair,
            rubric,
            rubric_sha,
            alias,
            sha256_bytes(response_a),
            sha256_bytes(response_b),
        )
        # Templates intentionally incomplete; store as YAML for humans.
        # Strip nulls that could confuse — keep structure with comments via _template.
        yaml_text = __import__("yaml").safe_dump(template, sort_keys=False)
        _assert_no_rater_leakage(pair_dir / "score-template-{}.yaml".format(alias), yaml_text)
        write_text(pair_dir / "score-template-{}.yaml".format(alias), yaml_text)

    for name in (
        "participant.md",
        "system_instruction.md",
        "rubric.yaml",
        "pair-meta.json",
    ):
        _assert_no_rater_leakage(pair_dir / name, (pair_dir / name).read_text(encoding="utf-8"))


def generate_blind_packages(
    runs_dir: Path,
    output_dir: Path,
    salt_hex: Optional[str] = None,
    packages_root: Optional[Path] = None,
    scenarios_dir: Path = SCENARIOS_DIR,
    rubric_paths: Optional[Dict[str, Path]] = None,
    rater_aliases: Sequence[str] = ("rater-01", "rater-02"),
    materials_by_prompt_sha: Optional[Dict[str, Dict[str, bytes]]] = None,
) -> Dict[str, Any]:
    """Generate operator-private mapping and rater packages.

    Refuses to overwrite an existing mapping.json.
    """
    operator_dir = output_dir / "operator-private"
    rater_dir = output_dir / "rater"
    mapping_path = operator_dir / MAPPING_NAME
    if mapping_path.is_file():
        raise ScoringError(
            "refusing to overwrite existing mapping at {} "
            "(regenerate into a new directory)".format(mapping_path)
        )

    salt = parse_salt_hex(salt_hex) if salt_hex else bytes.fromhex(generate_salt_hex())
    rows = load_runs_from_dir(runs_dir)
    pairs = group_runs_into_pairs(rows)
    for pair in pairs:
        pair["pair_id"] = make_pair_id(
            salt,
            pair["scenario_id"],
            pair["scenario_version"],
            pair["model_config_id"],
            pair["replicate_index"],
        )
        if "baseline" in pair["pair_id"] or "treatment" in pair["pair_id"]:
            raise ScoringError("pair_id unexpectedly encodes condition")

    pairs = assign_ab(salt, pairs)
    mapping = build_mapping_document(salt, pairs)

    materials = materials_by_prompt_sha or {}
    write_bytes(operator_dir / SALT_NAME, salt.hex().encode("ascii") + b"\n")
    write_json(mapping_path, mapping)
    write_text(rater_dir / "instructions.md", RATER_INSTRUCTIONS)

    for pair in pairs:
        scenario_id = pair["scenario_id"]
        if rubric_paths and scenario_id in rubric_paths:
            rubric, rubric_raw, rubric_sha = load_synthetic_rubric(rubric_paths[scenario_id])
        else:
            rubric, rubric_raw, rubric_sha = load_rubric_for_scenario(
                scenario_id, scenarios_dir=scenarios_dir
            )
        participant, system = _load_participant_and_system(pair, packages_root, materials)
        response_a = (
            pair["treatment"]["response_bytes"]
            if pair["treatment_side"] == "A"
            else pair["baseline"]["response_bytes"]
        )
        response_b = (
            pair["treatment"]["response_bytes"]
            if pair["treatment_side"] == "B"
            else pair["baseline"]["response_bytes"]
        )
        pair_dir = rater_dir / "pairs" / pair["pair_id"]
        write_rater_pair_package(
            pair_dir,
            pair,
            rubric,
            rubric_raw,
            rubric_sha,
            participant,
            system,
            response_a,
            response_b,
            rater_aliases,
        )
        # Separate per-rater workspaces without cross-score leakage.
        for alias in rater_aliases:
            workspace = rater_dir / "workspaces" / alias / pair["pair_id"]
            for name in (
                "participant.md",
                "system_instruction.md",
                "rubric.yaml",
                "response-A.md",
                "response-B.md",
                "pair-meta.json",
                "score-template-{}.yaml".format(alias),
            ):
                src = pair_dir / name
                if src.is_file():
                    write_bytes(workspace / name, src.read_bytes())
            write_text(workspace / "instructions.md", RATER_INSTRUCTIONS)

    return mapping


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Generate blind rater packages from imported runs")
    parser.add_argument("--runs", required=True, help="Directory of imported run JSON + responses")
    parser.add_argument("--output", required=True, help="Output directory for blind packages")
    parser.add_argument(
        "--salt",
        default=None,
        help="Optional hex salt for deterministic tests (omit for secure random salt)",
    )
    parser.add_argument(
        "--packages",
        default=None,
        help="Optional prepared packages root (dist/evals/prepared)",
    )
    parser.add_argument(
        "--scenarios-dir",
        default=str(SCENARIOS_DIR),
        help="Scenarios directory for rubrics",
    )
    args = parser.parse_args(list(argv) if argv is not None else None)
    try:
        mapping = generate_blind_packages(
            runs_dir=Path(args.runs),
            output_dir=Path(args.output),
            salt_hex=args.salt,
            packages_root=Path(args.packages) if args.packages else None,
            scenarios_dir=Path(args.scenarios_dir),
        )
    except ScoringError as exc:
        print("Blind generation failed: {}".format(exc.message), file=sys.stderr)
        return 1
    print("Blind packages generated.")
    print("Pairs: {}".format(mapping["pair_count"]))
    print("Treatment-as-A: {}".format(mapping["treatment_as_a"]))
    print("Treatment-as-B: {}".format(mapping["treatment_as_b"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
