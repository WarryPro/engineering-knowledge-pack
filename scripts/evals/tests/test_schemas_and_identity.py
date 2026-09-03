"""Schema and foundation validator tests."""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
EVALS_DIR = REPO_ROOT / "evals"
SCRIPTS_EVALS = REPO_ROOT / "scripts" / "evals"
if str(SCRIPTS_EVALS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_EVALS))

from eval_common import EMPTY_BYTES_SHA256, load_json, load_schema_validators, validate_against
from validate import EvalValidator, main

from helpers import (
    MIN_RUBRIC,
    MIN_SCENARIO,
    add_scenario,
    copy_real_schemas,
    make_report,
    make_run,
    make_score_sheet,
    write_json,
    write_yaml,
)


class SchemaContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.validators = load_schema_validators(EVALS_DIR / "schema")

    def test_schemas_themselves_valid(self):
        self.assertEqual(len(self.validators), 5)

    def test_valid_minimal_scenario(self):
        errors = validate_against(self.validators["scenario"], MIN_SCENARIO, "scenario")
        self.assertEqual(errors, [])

    def test_valid_minimal_rubric(self):
        errors = validate_against(self.validators["rubric"], MIN_RUBRIC, "rubric")
        self.assertEqual(errors, [])

    def test_invalid_scenario_enum(self):
        bad = dict(MIN_SCENARIO)
        bad["category"] = "not-a-category"
        errors = validate_against(self.validators["scenario"], bad, "scenario")
        self.assertTrue(errors)

    def test_additional_property_rejected_on_scenario(self):
        bad = dict(MIN_SCENARIO)
        bad["unexpected_field"] = True
        errors = validate_against(self.validators["scenario"], bad, "scenario")
        self.assertTrue(errors)

    def test_report_accepts_disputed_counts(self):
        report = make_report()
        report["outcomes"]["disputed"] = 2
        errors = validate_against(self.validators["report-summary"], report, "report")
        self.assertEqual(errors, [])

    def test_report_rejects_magic_score(self):
        report = make_report()
        report["overall_score"] = 87.42
        errors = validate_against(self.validators["report-summary"], report, "report")
        self.assertTrue(errors)

    def test_score_sheet_rejects_condition_field(self):
        sheet = make_score_sheet()
        sheet["condition"] = "baseline"
        errors = validate_against(self.validators["score-sheet"], sheet, "score")
        self.assertTrue(errors)

    def test_empty_bytes_sha_constant(self):
        self.assertEqual(
            EMPTY_BYTES_SHA256,
            "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
        )


class FoundationZeroScenarioTests(unittest.TestCase):
    def test_repo_foundation_passes_with_zero_scenarios(self):
        validator = EvalValidator(repo_root=REPO_ROOT)
        status = validator.validate()
        self.assertEqual(status, 0, msg=validator.errors)
        self.assertEqual(validator.scenario_count, 0)

    def test_main_exit_zero(self):
        self.assertEqual(main([]), 0)


class ScenarioIdentityTests(unittest.TestCase):
    def _harness(self):
        tmp = tempfile.TemporaryDirectory()
        root = Path(tmp.name)
        # Point validator at a fake repo that still has real profiles via repo_root.
        evals = root / "evals"
        copy_real_schemas(evals, EVALS_DIR)
        return tmp, root, evals

    def test_duplicate_scenario_id(self):
        tmp, root, evals = self._harness()
        with tmp:
            add_scenario(evals)
            add_scenario(evals, scenario_dirname="other-dir")
            # Force duplicate id in second dir
            second = evals / "scenarios" / "other-dir" / "scenario.yaml"
            data = dict(MIN_SCENARIO)
            write_yaml(second, data)
            validator = EvalValidator(repo_root=REPO_ROOT, evals_root=evals)
            # profiles resolve against REPO_ROOT; scenarios against evals_root
            status = validator.validate()
            self.assertEqual(status, 1)
            self.assertTrue(any("duplicate scenario id" in e for e in validator.errors))

    def test_directory_id_mismatch(self):
        tmp, root, evals = self._harness()
        with tmp:
            add_scenario(evals, scenario_dirname="wrong-name")
            validator = EvalValidator(repo_root=REPO_ROOT, evals_root=evals)
            status = validator.validate()
            self.assertEqual(status, 1)
            self.assertTrue(any("must equal scenario id" in e for e in validator.errors))

    def test_unknown_profile(self):
        tmp, root, evals = self._harness()
        with tmp:
            scenario = dict(MIN_SCENARIO)
            scenario["profile"] = "does-not-exist"
            add_scenario(evals, scenario=scenario)
            validator = EvalValidator(repo_root=REPO_ROOT, evals_root=evals)
            status = validator.validate()
            self.assertEqual(status, 1)
            self.assertTrue(any("unknown profile" in e for e in validator.errors))

    def test_valid_synthetic_scenario_passes(self):
        tmp, root, evals = self._harness()
        with tmp:
            add_scenario(evals)
            validator = EvalValidator(repo_root=REPO_ROOT, evals_root=evals)
            status = validator.validate()
            self.assertEqual(status, 0, msg=validator.errors)
            self.assertEqual(validator.scenario_count, 1)


if __name__ == "__main__":
    unittest.main()
