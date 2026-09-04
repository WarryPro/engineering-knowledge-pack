"""Consensus outcome tests (synthetic scores only)."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPTS_EVALS = REPO_ROOT / "scripts" / "evals"
if str(SCRIPTS_EVALS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_EVALS))

from at_helpers import default_dims, make_completed_score  # noqa: E402
from consensus import compute_pair_consensus  # noqa: E402


def _mapping_pair(treatment_as: str = "A") -> dict:
    baseline_side = "B" if treatment_as == "A" else "A"
    treatment_side = treatment_as
    assignment = {
        treatment_side: {
            "condition": "treatment",
            "run_id": "run-treatment",
            "response_sha256": "t" * 64,
        },
        baseline_side: {
            "condition": "baseline",
            "run_id": "run-baseline",
            "response_sha256": "b" * 64,
        },
    }
    return {
        "pair_id": "pair-synth-001",
        "scenario_id": "synth-alpha",
        "scenario_version": "1.0.0",
        "replicate_index": 1,
        "model_config_id": "synthetic-config",
        "assignment": {"A": assignment["A"], "B": assignment["B"]},
        "executed_at_order": "baseline-first",
    }


def _sheet(alias: str, preference: str, dims_a=None, dims_b=None, cf_a=None, cf_b=None):
    pair = _mapping_pair("A")
    return make_completed_score(
        pair_id=pair["pair_id"],
        scenario_id=pair["scenario_id"],
        replicate_index=1,
        rater_alias=alias,
        rubric_sha="d" * 64,
        response_a_sha=pair["assignment"]["A"]["response_sha256"],
        response_b_sha=pair["assignment"]["B"]["response_sha256"],
        preference=preference,
        dims_a=dims_a,
        dims_b=dims_b,
        cf_a=cf_a,
        cf_b=cf_b,
    )


class ConsensusTests(unittest.TestCase):
    def test_both_treatment_improved(self):
        pair = _mapping_pair("A")  # A=treatment
        scores = [_sheet("rater-01", "A"), _sheet("rater-02", "A")]
        result = compute_pair_consensus(pair, scores, ["1" * 64, "2" * 64])
        self.assertEqual(result["outcome"], "improved")

    def test_both_baseline_regressed(self):
        pair = _mapping_pair("A")  # B=baseline
        scores = [_sheet("rater-01", "B"), _sheet("rater-02", "B")]
        result = compute_pair_consensus(pair, scores, ["1" * 64, "2" * 64])
        self.assertEqual(result["outcome"], "regressed")

    def test_both_tie_tied(self):
        pair = _mapping_pair("A")
        scores = [_sheet("rater-01", "tie"), _sheet("rater-02", "tie")]
        result = compute_pair_consensus(pair, scores, ["1" * 64, "2" * 64])
        self.assertEqual(result["outcome"], "tied")

    def test_treatment_tie_disputed(self):
        pair = _mapping_pair("A")
        scores = [_sheet("rater-01", "A"), _sheet("rater-02", "tie")]
        result = compute_pair_consensus(pair, scores, ["1" * 64, "2" * 64])
        self.assertEqual(result["outcome"], "disputed")

    def test_baseline_tie_disputed(self):
        pair = _mapping_pair("A")
        scores = [_sheet("rater-01", "B"), _sheet("rater-02", "tie")]
        result = compute_pair_consensus(pair, scores, ["1" * 64, "2" * 64])
        self.assertEqual(result["outcome"], "disputed")

    def test_treatment_baseline_disputed(self):
        pair = _mapping_pair("A")
        scores = [_sheet("rater-01", "A"), _sheet("rater-02", "B")]
        result = compute_pair_consensus(pair, scores, ["1" * 64, "2" * 64])
        self.assertEqual(result["outcome"], "disputed")

    def test_same_preference_cf_disagreement_disputed(self):
        pair = _mapping_pair("A")
        scores = [
            _sheet("rater-01", "A", cf_a=["CF-01"], cf_b=["CF-01"]),
            _sheet("rater-02", "A", cf_a=["CF-01", "CF-02"], cf_b=["CF-01"]),
        ]
        result = compute_pair_consensus(pair, scores, ["1" * 64, "2" * 64])
        self.assertEqual(result["outcome"], "disputed")
        self.assertIn("critical-failure", result["dispute_reason"])

    def test_absolute_score_disagreement_alone_not_disputed(self):
        pair = _mapping_pair("A")
        scores = [
            _sheet("rater-01", "A", dims_a=default_dims(2)),
            _sheet("rater-02", "A", dims_a=default_dims(3)),
        ]
        result = compute_pair_consensus(pair, scores, ["1" * 64, "2" * 64])
        self.assertEqual(result["outcome"], "improved")
        self.assertTrue(result["absolute_score_disagreements"])

    def test_treatment_as_b_orientation(self):
        pair = _mapping_pair("B")  # B=treatment, A=baseline
        # Both prefer B (treatment) → improved
        scores = [_sheet("rater-01", "B"), _sheet("rater-02", "B")]
        # Fix response hashes to match mapping orientation
        for s in scores:
            s["response_a"]["response_sha256"] = pair["assignment"]["A"]["response_sha256"]
            s["response_b"]["response_sha256"] = pair["assignment"]["B"]["response_sha256"]
        result = compute_pair_consensus(pair, scores, ["1" * 64, "2" * 64])
        self.assertEqual(result["outcome"], "improved")

        # Both prefer A (baseline) → regressed
        scores2 = [_sheet("rater-01", "A"), _sheet("rater-02", "A")]
        for s in scores2:
            s["response_a"]["response_sha256"] = pair["assignment"]["A"]["response_sha256"]
            s["response_b"]["response_sha256"] = pair["assignment"]["B"]["response_sha256"]
        result2 = compute_pair_consensus(pair, scores2, ["3" * 64, "4" * 64])
        self.assertEqual(result2["outcome"], "regressed")

    def test_dimension_delta_sign(self):
        pair = _mapping_pair("A")  # A treatment, B baseline
        scores = [
            _sheet(
                "rater-01",
                "A",
                dims_a=default_dims(3),
                dims_b=default_dims(1),
            ),
            _sheet(
                "rater-02",
                "A",
                dims_a=default_dims(3),
                dims_b=default_dims(1),
            ),
        ]
        result = compute_pair_consensus(pair, scores, ["1" * 64, "2" * 64])
        deltas = result["dimension_deltas"][0]["deltas"]
        self.assertEqual(deltas["technical-correctness"], 2)


if __name__ == "__main__":
    unittest.main()
