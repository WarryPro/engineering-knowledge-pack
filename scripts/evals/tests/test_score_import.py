"""Score import validation tests (synthetic sheets only)."""

from __future__ import annotations

import copy
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
from helpers import write_yaml  # noqa: E402
from eval_common import sha256_bytes  # noqa: E402
from score_import import ScoreImportError, import_score_sheet  # noqa: E402

SALT = "33" * 32


class ScoreImportTests(unittest.TestCase):
    def _setup_pair(self, root: Path):
        runs = root / "runs"
        write_run_bundle(
            runs,
            scenario_id="synth-alpha",
            replicate_index=1,
            baseline_text="Synthetic response A for scoring test.\n",
            treatment_text="Synthetic response B for scoring test.\n",
        )
        rubric_path = root / "rubric.yaml"
        write_yaml(rubric_path, SYNTHETIC_RUBRIC)
        blind_out = root / "blind"
        mapping = generate_blind_packages(
            runs,
            blind_out,
            salt_hex=SALT,
            rubric_paths={"synth-alpha": rubric_path},
        )
        pair = mapping["pairs"][0]
        rubric_sha = sha256_bytes(rubric_path.read_bytes())
        return blind_out, pair, rubric_path, rubric_sha

    def _base_sheet(self, pair, rubric_sha, alias="rater-01", preference="A"):
        return make_completed_score(
            pair_id=pair["pair_id"],
            scenario_id=pair["scenario_id"],
            replicate_index=pair["replicate_index"],
            rater_alias=alias,
            rubric_sha=rubric_sha,
            response_a_sha=pair["assignment"]["A"]["response_sha256"],
            response_b_sha=pair["assignment"]["B"]["response_sha256"],
            preference=preference,
        )

    def test_valid_rater_01_and_02_accepted(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            blind_out, pair, rubric_path, rubric_sha = self._setup_pair(root)
            mapping = blind_out / "operator-private" / "mapping.json"
            scores_out = root / "imported"
            for alias in ("rater-01", "rater-02"):
                sheet = self._base_sheet(pair, rubric_sha, alias=alias, preference="tie")
                path = root / "{}.yaml".format(alias)
                write_score_yaml(path, sheet)
                result = import_score_sheet(
                    path, mapping, scores_out, rubric_path=rubric_path
                )
                self.assertEqual(result["rater_alias"], alias)
                stored = (
                    scores_out / "scores" / pair["pair_id"] / "{}.yaml".format(alias)
                )
                self.assertEqual(stored.read_bytes(), path.read_bytes())

    def test_schema_invalid_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            blind_out, pair, rubric_path, rubric_sha = self._setup_pair(root)
            sheet = self._base_sheet(pair, rubric_sha)
            del sheet["pairwise_reason"]
            path = root / "bad.yaml"
            write_score_yaml(path, sheet)
            with self.assertRaises(ScoreImportError):
                import_score_sheet(
                    path,
                    blind_out / "operator-private" / "mapping.json",
                    root / "imported",
                    rubric_path=rubric_path,
                )

    def test_response_hash_mismatch_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            blind_out, pair, rubric_path, rubric_sha = self._setup_pair(root)
            sheet = self._base_sheet(pair, rubric_sha)
            sheet["response_a"]["response_sha256"] = "0" * 64
            path = root / "bad.yaml"
            write_score_yaml(path, sheet)
            with self.assertRaises(ScoreImportError) as ctx:
                import_score_sheet(
                    path,
                    blind_out / "operator-private" / "mapping.json",
                    root / "imported",
                    rubric_path=rubric_path,
                )
            self.assertIn("response_sha256", str(ctx.exception))

    def test_rubric_hash_mismatch_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            blind_out, pair, rubric_path, rubric_sha = self._setup_pair(root)
            sheet = self._base_sheet(pair, rubric_sha)
            sheet["rubric_sha256"] = "1" * 64
            path = root / "bad.yaml"
            write_score_yaml(path, sheet)
            with self.assertRaises(ScoreImportError) as ctx:
                import_score_sheet(
                    path,
                    blind_out / "operator-private" / "mapping.json",
                    root / "imported",
                    rubric_path=rubric_path,
                )
            self.assertIn("rubric_sha256", str(ctx.exception))

    def test_wrong_pair_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            blind_out, pair, rubric_path, rubric_sha = self._setup_pair(root)
            sheet = self._base_sheet(pair, rubric_sha)
            sheet["pair_id"] = "pair-does-not-exist"
            path = root / "bad.yaml"
            write_score_yaml(path, sheet)
            with self.assertRaises(ScoreImportError):
                import_score_sheet(
                    path,
                    blind_out / "operator-private" / "mapping.json",
                    root / "imported",
                    rubric_path=rubric_path,
                )

    def test_extra_and_missing_dimension_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            blind_out, pair, rubric_path, rubric_sha = self._setup_pair(root)
            mapping = blind_out / "operator-private" / "mapping.json"
            sheet = self._base_sheet(pair, rubric_sha)
            sheet["response_a"]["dimension_scores"]["testing-verifiability"] = 2
            path = root / "extra.yaml"
            write_score_yaml(path, sheet)
            with self.assertRaises(ScoreImportError) as ctx:
                import_score_sheet(path, mapping, root / "i1", rubric_path=rubric_path)
            self.assertIn("extra", str(ctx.exception))

            sheet2 = self._base_sheet(pair, rubric_sha, alias="rater-02")
            del sheet2["response_a"]["dimension_scores"]["technical-correctness"]
            path2 = root / "missing.yaml"
            write_score_yaml(path2, sheet2)
            with self.assertRaises(ScoreImportError) as ctx2:
                import_score_sheet(path2, mapping, root / "i2", rubric_path=rubric_path)
            self.assertIn("missing", str(ctx2.exception))

    def test_score_outside_range_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            blind_out, pair, rubric_path, rubric_sha = self._setup_pair(root)
            sheet = self._base_sheet(pair, rubric_sha)
            sheet["response_a"]["dimension_scores"]["technical-correctness"] = 9
            path = root / "bad.yaml"
            write_score_yaml(path, sheet)
            with self.assertRaises(ScoreImportError):
                import_score_sheet(
                    path,
                    blind_out / "operator-private" / "mapping.json",
                    root / "imported",
                    rubric_path=rubric_path,
                )

    def test_unknown_critical_failure_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            blind_out, pair, rubric_path, rubric_sha = self._setup_pair(root)
            sheet = self._base_sheet(pair, rubric_sha)
            sheet["response_a"]["critical_failures"] = ["CF-99"]
            path = root / "bad.yaml"
            write_score_yaml(path, sheet)
            with self.assertRaises(ScoreImportError) as ctx:
                import_score_sheet(
                    path,
                    blind_out / "operator-private" / "mapping.json",
                    root / "imported",
                    rubric_path=rubric_path,
                )
            self.assertIn("critical failure", str(ctx.exception).lower())

    def test_blinded_false_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            blind_out, pair, rubric_path, rubric_sha = self._setup_pair(root)
            sheet = self._base_sheet(pair, rubric_sha)
            sheet["blinded"] = False
            path = root / "bad.yaml"
            write_score_yaml(path, sheet)
            with self.assertRaises(ScoreImportError):
                import_score_sheet(
                    path,
                    blind_out / "operator-private" / "mapping.json",
                    root / "imported",
                    rubric_path=rubric_path,
                )

    def test_duplicate_rater_alias_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            blind_out, pair, rubric_path, rubric_sha = self._setup_pair(root)
            mapping = blind_out / "operator-private" / "mapping.json"
            sheet = self._base_sheet(pair, rubric_sha, alias="rater-01")
            path = root / "s1.yaml"
            write_score_yaml(path, sheet)
            import_score_sheet(path, mapping, root / "imported", rubric_path=rubric_path)
            with self.assertRaises(ScoreImportError) as ctx:
                import_score_sheet(
                    path, mapping, root / "imported", rubric_path=rubric_path
                )
            self.assertIn("duplicate", str(ctx.exception).lower())

    def test_condition_field_leakage_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            blind_out, pair, rubric_path, rubric_sha = self._setup_pair(root)
            sheet = self._base_sheet(pair, rubric_sha)
            sheet["condition"] = "treatment"
            path = root / "bad.yaml"
            write_score_yaml(path, sheet)
            with self.assertRaises(ScoreImportError):
                import_score_sheet(
                    path,
                    blind_out / "operator-private" / "mapping.json",
                    root / "imported",
                    rubric_path=rubric_path,
                )

    def test_preference_with_exclusive_critical_failure_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            blind_out, pair, rubric_path, rubric_sha = self._setup_pair(root)
            sheet = self._base_sheet(pair, rubric_sha, preference="A")
            sheet["response_a"]["critical_failures"] = ["CF-01"]
            sheet["response_b"]["critical_failures"] = []
            path = root / "bad.yaml"
            write_score_yaml(path, sheet)
            with self.assertRaises(ScoreImportError) as ctx:
                import_score_sheet(
                    path,
                    blind_out / "operator-private" / "mapping.json",
                    root / "imported",
                    rubric_path=rubric_path,
                )
            self.assertIn("critical failure", str(ctx.exception).lower())


if __name__ == "__main__":
    unittest.main()
