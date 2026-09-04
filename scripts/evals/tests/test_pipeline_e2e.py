"""Synthetic end-to-end blind → score → consensus → report gate."""

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

from at_helpers import (  # noqa: E402
    SYNTHETIC_RUBRIC,
    make_completed_score,
    write_run_bundle,
    write_score_yaml,
)
from blind import generate_blind_packages  # noqa: E402
from consensus import consensus_from_imported_scores  # noqa: E402
from helpers import write_yaml  # noqa: E402
from eval_common import sha256_bytes  # noqa: E402
from report import generate_report  # noqa: E402
from score_import import import_score_sheet  # noqa: E402

SALT = "44" * 32


class SyntheticPipelineE2ETests(unittest.TestCase):
    def test_four_outcome_classes_end_to_end(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            runs = root / "runs"
            # Four synthetic scenarios/replicates → four pairs covering all outcomes.
            cases = [
                ("synth-alpha", 1, "Synthetic baseline improved case.\n", "Synthetic treatment improved case.\n"),
                ("synth-alpha", 2, "Synthetic baseline tied case.\n", "Synthetic treatment tied case.\n"),
                ("synth-beta", 1, "Synthetic baseline regressed case.\n", "Synthetic treatment regressed case.\n"),
                ("synth-beta", 2, "Synthetic baseline disputed case.\n", "Synthetic treatment disputed case.\n"),
            ]
            for scenario_id, replicate, base, treat in cases:
                write_run_bundle(
                    runs,
                    scenario_id=scenario_id,
                    replicate_index=replicate,
                    baseline_text=base,
                    treatment_text=treat,
                )

            # Shared synthetic rubric for both scenario ids.
            rubric_alpha = root / "rubric-alpha.yaml"
            rubric_beta = root / "rubric-beta.yaml"
            ra = dict(SYNTHETIC_RUBRIC)
            ra["scenario_id"] = "synth-alpha"
            rb = dict(SYNTHETIC_RUBRIC)
            rb["scenario_id"] = "synth-beta"
            write_yaml(rubric_alpha, ra)
            write_yaml(rubric_beta, rb)

            blind_out = root / "blind"
            mapping = generate_blind_packages(
                runs_dir=runs,
                output_dir=blind_out,
                salt_hex=SALT,
                rubric_paths={
                    "synth-alpha": rubric_alpha,
                    "synth-beta": rubric_beta,
                },
            )
            self.assertEqual(mapping["pair_count"], 4)
            mapping_path = blind_out / "operator-private" / "mapping.json"
            scores_root = root / "imported"

            # Desired revealed outcomes by (scenario, replicate)
            desired = {
                ("synth-alpha", 1): "improved",
                ("synth-alpha", 2): "tied",
                ("synth-beta", 1): "regressed",
                ("synth-beta", 2): "disputed",
            }

            for pair in mapping["pairs"]:
                key = (pair["scenario_id"], pair["replicate_index"])
                target = desired[key]
                treatment_side = pair["treatment_as"]
                baseline_side = "B" if treatment_side == "A" else "A"
                rubric_path = (
                    rubric_alpha if pair["scenario_id"] == "synth-alpha" else rubric_beta
                )
                rubric_sha = sha256_bytes(rubric_path.read_bytes())

                def pref_for(target_outcome: str, rater_index: int) -> str:
                    if target_outcome == "improved":
                        return treatment_side
                    if target_outcome == "regressed":
                        return baseline_side
                    if target_outcome == "tied":
                        return "tie"
                    # disputed: rater-01 treatment, rater-02 baseline
                    return treatment_side if rater_index == 0 else baseline_side

                for idx, alias in enumerate(("rater-01", "rater-02")):
                    sheet = make_completed_score(
                        pair_id=pair["pair_id"],
                        scenario_id=pair["scenario_id"],
                        replicate_index=pair["replicate_index"],
                        rater_alias=alias,
                        rubric_sha=rubric_sha,
                        response_a_sha=pair["assignment"]["A"]["response_sha256"],
                        response_b_sha=pair["assignment"]["B"]["response_sha256"],
                        preference=pref_for(target, idx),
                        reason="Synthetic E2E judgment for {}.".format(target),
                    )
                    path = root / "{}-{}-{}.yaml".format(
                        pair["scenario_id"], pair["replicate_index"], alias
                    )
                    write_score_yaml(path, sheet)
                    import_score_sheet(
                        path, mapping_path, scores_root, rubric_path=rubric_path
                    )

            consensus_dir = root / "consensus_out"
            results = consensus_from_imported_scores(
                mapping_path=mapping_path,
                scores_root=scores_root,
                output_dir=consensus_dir,
                require_raters=2,
            )
            got = {
                (r["scenario_id"], r["replicate_index"]): r["outcome"] for r in results
            }
            self.assertEqual(got, desired)

            report_dir = root / "report"
            md, js, summary = generate_report(
                consensus_dir=consensus_dir / "consensus",
                output_dir=report_dir,
                evaluation_id="eval-synthetic-at-e2e",
                ekp_version="0.17.0.dev0",
                ekp_commit="a" * 40,
                model_config_id="synthetic-config",
            )
            self.assertEqual(
                summary["outcomes"],
                {"improved": 1, "tied": 1, "regressed": 1, "disputed": 1},
            )
            text = md.decode("utf-8")
            self.assertIn("improved: 1", text)
            self.assertIn("regressed", text)
            self.assertIn("disputed", text)
            self.assertNotIn("EKP improves", text)
            # Ensure synthetic markers only — no real scenario answers.
            self.assertIn("Synthetic", (root / "runs").joinpath(
                next(p.name for p in (root / "runs").iterdir())
            ).joinpath("response.txt").read_text(encoding="utf-8"))
            parsed = json.loads(js.decode("utf-8"))
            self.assertEqual(parsed["pair_count"], 4)


if __name__ == "__main__":
    unittest.main()
