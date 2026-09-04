#!/usr/bin/env python3
"""Reveal conditions and compute dual-rater consensus (no adjudication)."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

import yaml

_SCRIPT_DIR = Path(__file__).resolve().parent
if str(_SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPT_DIR))

from eval_common import load_json, sha256_bytes  # noqa: E402
from scoring_common import (  # noqa: E402
    ScoringError,
    cf_sets_compatible,
    preference_to_condition,
    write_json,
)


class ConsensusError(ScoringError):
    pass


def load_score_file(path: Path) -> Tuple[Dict[str, Any], str]:
    raw = path.read_bytes()
    if path.suffix.lower() in (".yaml", ".yml"):
        data = yaml.safe_load(raw.decode("utf-8"))
    else:
        data = json.loads(raw.decode("utf-8"))
    if not isinstance(data, dict):
        raise ConsensusError("score sheet must be an object: {}".format(path))
    return data, sha256_bytes(raw)


def _side_condition(assignment: Dict[str, Any], side: str) -> str:
    return (assignment.get(side) or {}).get("condition")


def _scores_for_condition(sheet: Dict[str, Any], assignment: Dict[str, Any], condition: str) -> Dict[str, int]:
    for side in ("A", "B"):
        if _side_condition(assignment, side) == condition:
            block = sheet["response_a"] if side == "A" else sheet["response_b"]
            return dict((block.get("dimension_scores") or {}))
    raise ConsensusError("condition {!r} missing from assignment".format(condition))


def _cf_for_side(sheet: Dict[str, Any], side: str) -> List[str]:
    block = sheet["response_a"] if side == "A" else sheet["response_b"]
    return list(block.get("critical_failures") or [])


def dimension_deltas(
    sheet: Dict[str, Any], assignment: Dict[str, Any]
) -> Dict[str, int]:
    base = _scores_for_condition(sheet, assignment, "baseline")
    treat = _scores_for_condition(sheet, assignment, "treatment")
    keys = sorted(set(base) | set(treat))
    deltas = {}
    for key in keys:
        if key in base and key in treat:
            deltas[key] = int(treat[key]) - int(base[key])
    return deltas


def compute_pair_consensus(
    mapping_pair: Dict[str, Any],
    scores: Sequence[Dict[str, Any]],
    score_hashes: Sequence[str],
    require_raters: int = 2,
) -> Dict[str, Any]:
    if require_raters and len(scores) < require_raters:
        raise ConsensusError(
            "pair {} requires {} rater scores, found {}".format(
                mapping_pair.get("pair_id"), require_raters, len(scores)
            )
        )
    if len(scores) != len(score_hashes):
        raise ConsensusError("score hash list length mismatch")

    aliases = [s.get("rater_alias") for s in scores]
    if len(set(aliases)) != len(aliases):
        raise ConsensusError("duplicate rater aliases in consensus input")

    assignment = mapping_pair["assignment"]
    revealed_prefs = []
    blind_prefs = []
    for sheet in scores:
        pref = sheet["pairwise_preference"]
        blind_prefs.append({"rater_alias": sheet["rater_alias"], "preference": pref})
        revealed_prefs.append(
            {
                "rater_alias": sheet["rater_alias"],
                "blind_preference": pref,
                "revealed_preference": preference_to_condition(pref, assignment),
            }
        )

    # Critical-failure set agreement on A and B independently.
    cf_a_sets = [_cf_for_side(s, "A") for s in scores]
    cf_b_sets = [_cf_for_side(s, "B") for s in scores]
    cf_a_agree = all(cf_sets_compatible(cf_a_sets[0], other) for other in cf_a_sets[1:])
    cf_b_agree = all(cf_sets_compatible(cf_b_sets[0], other) for other in cf_b_sets[1:])
    cf_agreement = cf_a_agree and cf_b_agree

    revealed_values = [row["revealed_preference"] for row in revealed_prefs]
    pairwise_agree = len(set(revealed_values)) == 1

    if not cf_agreement:
        outcome = "disputed"
        dispute_reason = "critical-failure set disagreement"
    elif not pairwise_agree:
        outcome = "disputed"
        dispute_reason = "pairwise preference disagreement"
    else:
        only = revealed_values[0]
        if only == "treatment":
            outcome = "improved"
        elif only == "baseline":
            outcome = "regressed"
        elif only == "tie":
            outcome = "tied"
        else:
            raise ConsensusError("unexpected revealed preference {!r}".format(only))
        dispute_reason = None

    # Absolute score disagreement (informational; does not force dispute alone).
    score_disagreements = []
    if len(scores) >= 2:
        dims_a = sorted(
            set(scores[0]["response_a"]["dimension_scores"])
            | set(scores[1]["response_a"]["dimension_scores"])
        )
        for dim in dims_a:
            vals = [
                s["response_a"]["dimension_scores"].get(dim)
                for s in scores
            ]
            if len(set(vals)) > 1:
                score_disagreements.append(
                    {"side": "A", "dimension": dim, "values": vals}
                )
        dims_b = sorted(
            set(scores[0]["response_b"]["dimension_scores"])
            | set(scores[1]["response_b"]["dimension_scores"])
        )
        for dim in dims_b:
            vals = [
                s["response_b"]["dimension_scores"].get(dim)
                for s in scores
            ]
            if len(set(vals)) > 1:
                score_disagreements.append(
                    {"side": "B", "dimension": dim, "values": vals}
                )

    per_rater_deltas = []
    for sheet in scores:
        per_rater_deltas.append(
            {
                "rater_alias": sheet["rater_alias"],
                "deltas": dimension_deltas(sheet, assignment),
            }
        )

    return {
        "pair_id": mapping_pair["pair_id"],
        "scenario_id": mapping_pair["scenario_id"],
        "scenario_version": mapping_pair["scenario_version"],
        "replicate_index": mapping_pair["replicate_index"],
        "model_config_id": mapping_pair["model_config_id"],
        "rater_score_ids": [s.get("score_id") for s in scores],
        "rater_score_sha256": list(score_hashes),
        "rater_aliases": aliases,
        "blind_preferences": blind_prefs,
        "revealed_preferences": revealed_prefs,
        "assignment": {
            "A": {
                "condition": assignment["A"]["condition"],
                "run_id": assignment["A"]["run_id"],
                "response_sha256": assignment["A"]["response_sha256"],
            },
            "B": {
                "condition": assignment["B"]["condition"],
                "run_id": assignment["B"]["run_id"],
                "response_sha256": assignment["B"]["response_sha256"],
            },
        },
        "critical_failure_agreement": cf_agreement,
        "critical_failures": {
            "A": {alias: _cf_for_side(s, "A") for alias, s in zip(aliases, scores)},
            "B": {alias: _cf_for_side(s, "B") for alias, s in zip(aliases, scores)},
        },
        "absolute_score_disagreements": score_disagreements,
        "dimension_deltas": per_rater_deltas,
        "outcome": outcome,
        "dispute_reason": dispute_reason,
        "executed_at_order": mapping_pair.get("executed_at_order"),
    }


def consensus_from_imported_scores(
    mapping_path: Path,
    scores_root: Path,
    output_dir: Path,
    require_raters: int = 2,
) -> List[Dict[str, Any]]:
    mapping = load_json(mapping_path)
    results = []
    for pair in sorted(
        mapping.get("pairs") or [],
        key=lambda p: (p["scenario_id"], p["replicate_index"], p["pair_id"]),
    ):
        pair_id = pair["pair_id"]
        index_path = scores_root / "scores" / pair_id / "index.json"
        if not index_path.is_file():
            if require_raters:
                raise ConsensusError(
                    "missing imported scores for pair {} (evidence-grade incomplete)".format(
                        pair_id
                    )
                )
            continue
        index = load_json(index_path)
        score_entries = index.get("scores") or {}
        if require_raters and len(score_entries) < require_raters:
            raise ConsensusError(
                "pair {} has {} scores; require {}".format(
                    pair_id, len(score_entries), require_raters
                )
            )
        sheets = []
        hashes = []
        for alias in sorted(score_entries.keys()):
            entry = score_entries[alias]
            path = scores_root / "scores" / pair_id / entry["path"]
            sheet, digest = load_score_file(path)
            if digest != entry.get("score_sheet_sha256"):
                raise ConsensusError(
                    "score sheet hash drift for {} / {}".format(pair_id, alias)
                )
            sheets.append(sheet)
            hashes.append(digest)
        artifact = compute_pair_consensus(
            pair, sheets, hashes, require_raters=require_raters
        )
        write_json(output_dir / "consensus" / "{}.json".format(pair_id), artifact)
        results.append(artifact)
    return results


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Compute dual-rater consensus after reveal")
    parser.add_argument("--mapping", required=True)
    parser.add_argument("--scores", required=True, help="Imported scores root")
    parser.add_argument("--output", required=True)
    parser.add_argument("--require-raters", type=int, default=2)
    args = parser.parse_args(list(argv) if argv is not None else None)
    try:
        results = consensus_from_imported_scores(
            mapping_path=Path(args.mapping),
            scores_root=Path(args.scores),
            output_dir=Path(args.output),
            require_raters=args.require_raters,
        )
    except ConsensusError as exc:
        print("Consensus failed: {}".format(exc.message), file=sys.stderr)
        return 1
    counts = {"improved": 0, "tied": 0, "regressed": 0, "disputed": 0}
    for row in results:
        counts[row["outcome"]] += 1
    print("Consensus pairs: {}".format(len(results)))
    print(
        "improved={improved} tied={tied} regressed={regressed} disputed={disputed}".format(
            **counts
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
