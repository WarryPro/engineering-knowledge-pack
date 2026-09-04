"""Report generation tests (synthetic consensus only)."""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPTS_EVALS = REPO_ROOT / "scripts" / "evals"
if str(SCRIPTS_EVALS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_EVALS))

from helpers import write_json  # noqa: E402
from report import ReportError, generate_report  # noqa: E402
from scoring_common import MANDATORY_LIMITATIONS  # noqa: E402


def _artifact(
    *,
    pair_id: str,
    scenario_id: str,
    replicate: int,
    outcome: str,
    dispute_reason=None,
) -> dict:
    return {
        "pair_id": pair_id,
        "scenario_id": scenario_id,
        "scenario_version": "1.0.0",
        "replicate_index": replicate,
        "model_config_id": "synthetic-config",
        "rater_score_ids": ["s1", "s2"],
        "rater_score_sha256": ["1" * 64, "2" * 64],
        "rater_aliases": ["rater-01", "rater-02"],
        "blind_preferences": [
            {"rater_alias": "rater-01", "preference": "A"},
            {"rater_alias": "rater-02", "preference": "A"},
        ],
        "revealed_preferences": [
            {
                "rater_alias": "rater-01",
                "blind_preference": "A",
                "revealed_preference": "treatment"
                if outcome == "improved"
                else "baseline"
                if outcome == "regressed"
                else "tie"
                if outcome == "tied"
                else "treatment",
            },
            {
                "rater_alias": "rater-02",
                "blind_preference": "B" if outcome == "disputed" else "A",
                "revealed_preference": "baseline"
                if outcome == "disputed"
                else (
                    "treatment"
                    if outcome == "improved"
                    else "baseline"
                    if outcome == "regressed"
                    else "tie"
                ),
            },
        ],
        "assignment": {
            "A": {
                "condition": "treatment",
                "run_id": "run-t",
                "response_sha256": "a" * 64,
            },
            "B": {
                "condition": "baseline",
                "run_id": "run-b",
                "response_sha256": "b" * 64,
            },
        },
        "critical_failure_agreement": outcome != "disputed" or dispute_reason != "cf",
        "critical_failures": {
            "A": {"rater-01": [], "rater-02": []},
            "B": {"rater-01": [], "rater-02": []},
        },
        "absolute_score_disagreements": [],
        "dimension_deltas": [
            {
                "rater_alias": "rater-01",
                "deltas": {
                    "technical-correctness": 1 if outcome == "improved" else -1 if outcome == "regressed" else 0,
                    "architecture-boundaries": 0,
                },
            },
            {
                "rater_alias": "rater-02",
                "deltas": {
                    "technical-correctness": 1 if outcome == "improved" else -1 if outcome == "regressed" else 0,
                    "architecture-boundaries": 0,
                },
            },
        ],
        "outcome": outcome,
        "dispute_reason": dispute_reason,
        "executed_at_order": "baseline-first",
    }


class ReportTests(unittest.TestCase):
    def _write_four(self, consensus_dir: Path):
        rows = [
            _artifact(
                pair_id="pair-i",
                scenario_id="synth-alpha",
                replicate=1,
                outcome="improved",
            ),
            _artifact(
                pair_id="pair-t",
                scenario_id="synth-alpha",
                replicate=2,
                outcome="tied",
            ),
            _artifact(
                pair_id="pair-r",
                scenario_id="synth-beta",
                replicate=1,
                outcome="regressed",
            ),
            _artifact(
                pair_id="pair-d",
                scenario_id="synth-beta",
                replicate=2,
                outcome="disputed",
                dispute_reason="pairwise preference disagreement",
            ),
        ]
        for row in rows:
            write_json(consensus_dir / "{}.json".format(row["pair_id"]), row)
        return rows

    def test_report_outcomes_visibility_limitations_determinism(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            consensus = root / "consensus"
            out1 = root / "out1"
            out2 = root / "out2"
            self._write_four(consensus)
            kwargs = dict(
                consensus_dir=consensus,
                evaluation_id="eval-synthetic-at",
                ekp_version="0.17.0.dev0",
                ekp_commit="a" * 40,
                model_config_id="synthetic-config",
            )
            md1, js1, summary = generate_report(output_dir=out1, **kwargs)
            md2, js2, _ = generate_report(output_dir=out2, **kwargs)
            self.assertEqual(md1, md2)
            self.assertEqual(js1, js2)
            self.assertEqual(
                summary["outcomes"],
                {"improved": 1, "tied": 1, "regressed": 1, "disputed": 1},
            )
            text = md1.decode("utf-8")
            self.assertIn("replicate 1: **regressed**", text)
            self.assertIn("Disputes", text)
            self.assertIn("pair-d", text)
            self.assertIn("No scenario-level winner", text)
            self.assertNotIn("scenario winner =", text.lower())
            self.assertNotIn("ekp improves", text.lower())
            self.assertNotIn("quality_percentage", text.lower())
            for limitation in MANDATORY_LIMITATIONS:
                self.assertIn(limitation, summary["limitations"])
            # JSON schema already validated inside generate_report
            parsed = json.loads(js1.decode("utf-8"))
            self.assertEqual(parsed["pair_count"], 4)
            dists = {d["scenario_id"]: d for d in parsed["scenario_distributions"]}
            self.assertEqual(dists["synth-alpha"]["improved"], 1)
            self.assertEqual(dists["synth-alpha"]["tied"], 1)
            self.assertEqual(dists["synth-beta"]["regressed"], 1)
            self.assertEqual(dists["synth-beta"]["disputed"], 1)

    def test_evidence_grade_incomplete_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            consensus = root / "consensus"
            self._write_four(consensus)
            with self.assertRaises(ReportError):
                generate_report(
                    consensus_dir=consensus,
                    output_dir=root / "out",
                    evaluation_id="eval-synthetic-at",
                    ekp_version="0.17.0.dev0",
                    ekp_commit="a" * 40,
                    model_config_id="synthetic-config",
                    require_complete=True,
                    expected_pair_count=24,
                )


if __name__ == "__main__":
    unittest.main()
