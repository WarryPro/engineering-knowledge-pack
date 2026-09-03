"""Path safety and prompt isolation tests."""

from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
EVALS_DIR = REPO_ROOT / "evals"
SCRIPTS_EVALS = REPO_ROOT / "scripts" / "evals"
if str(SCRIPTS_EVALS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_EVALS))

from validate import EvalValidator

from helpers import MIN_SCENARIO, add_scenario, copy_real_schemas, write_yaml


class PathSafetyTests(unittest.TestCase):
    def _harness(self):
        tmp = tempfile.TemporaryDirectory()
        evals = Path(tmp.name) / "evals"
        copy_real_schemas(evals, EVALS_DIR)
        return tmp, evals

    def test_prompt_traversal_rejected(self):
        tmp, evals = self._harness()
        with tmp:
            scenario = dict(MIN_SCENARIO)
            scenario["prompt_file"] = "../shared/system_instruction.md"
            add_scenario(evals, scenario=scenario)
            validator = EvalValidator(repo_root=REPO_ROOT, evals_root=evals)
            status = validator.validate()
            self.assertEqual(status, 1)
            self.assertTrue(any("traversal" in e or "outside" in e for e in validator.errors))

    def test_rubric_traversal_rejected(self):
        tmp, evals = self._harness()
        with tmp:
            scenario = dict(MIN_SCENARIO)
            scenario["rubric_file"] = "../../pyproject.toml"
            add_scenario(evals, scenario=scenario)
            # add_scenario wrote rubric at wrong place; still should fail path check
            validator = EvalValidator(repo_root=REPO_ROOT, evals_root=evals)
            status = validator.validate()
            self.assertEqual(status, 1)
            self.assertTrue(any("rubric_file" in e for e in validator.errors))

    def test_fixture_traversal_rejected(self):
        tmp, evals = self._harness()
        with tmp:
            scenario = dict(MIN_SCENARIO)
            scenario["fixture"] = "../"
            add_scenario(evals, scenario=scenario)
            validator = EvalValidator(repo_root=REPO_ROOT, evals_root=evals)
            status = validator.validate()
            self.assertEqual(status, 1)
            self.assertTrue(any("fixture" in e for e in validator.errors))

    def test_absolute_path_rejected(self):
        tmp, evals = self._harness()
        with tmp:
            scenario = dict(MIN_SCENARIO)
            if os.name == "nt":
                scenario["prompt_file"] = "C:/Windows/system.ini"
            else:
                scenario["prompt_file"] = "/etc/passwd"
            scenario_dir = add_scenario(evals, scenario=scenario)
            # Ensure scenario.yaml has absolute path (add_scenario also tried to write prompt)
            write_yaml(scenario_dir / "scenario.yaml", scenario)
            validator = EvalValidator(repo_root=REPO_ROOT, evals_root=evals)
            status = validator.validate()
            self.assertEqual(status, 1)
            self.assertTrue(any("absolute" in e for e in validator.errors))

    def test_unix_symlink_escape(self):
        if os.name == "nt":
            self.skipTest("Unix symlink escape coverage")
        tmp, evals = self._harness()
        with tmp:
            add_scenario(evals)
            scenario_dir = evals / "scenarios" / "synthetic-demo"
            outside = Path(tmp.name) / "outside.txt"
            outside.write_text("secret", encoding="utf-8")
            link = scenario_dir / "escape.md"
            link.symlink_to(outside)
            scenario = dict(MIN_SCENARIO)
            scenario["prompt_file"] = "escape.md"
            write_yaml(scenario_dir / "scenario.yaml", scenario)
            validator = EvalValidator(repo_root=REPO_ROOT, evals_root=evals)
            status = validator.validate()
            self.assertEqual(status, 1)
            self.assertTrue(
                any("symlink" in e or "outside" in e for e in validator.errors)
            )


class PromptIsolationTests(unittest.TestCase):
    def test_prompt_with_concept_id_rejected(self):
        tmp = tempfile.TemporaryDirectory()
        with tmp:
            evals = Path(tmp.name) / "evals"
            copy_real_schemas(evals, EVALS_DIR)
            add_scenario(
                evals,
                prompt="Please apply EKP-P01 carefully when designing boundaries.\n",
            )
            validator = EvalValidator(repo_root=REPO_ROOT, evals_root=evals)
            status = validator.validate()
            self.assertEqual(status, 1)
            self.assertTrue(any("concept ID" in e for e in validator.errors))


class RubricBindingTests(unittest.TestCase):
    def test_invalid_dimension(self):
        tmp = tempfile.TemporaryDirectory()
        with tmp:
            evals = Path(tmp.name) / "evals"
            copy_real_schemas(evals, EVALS_DIR)
            from helpers import MIN_RUBRIC

            rubric = dict(MIN_RUBRIC)
            rubric["dimensions"] = ["not-a-real-dimension"]
            add_scenario(evals, rubric=rubric)
            validator = EvalValidator(repo_root=REPO_ROOT, evals_root=evals)
            status = validator.validate()
            self.assertEqual(status, 1)
            self.assertTrue(
                any("dimension" in e.lower() for e in validator.errors)
            )

    def test_duplicate_critical_failure_id(self):
        tmp = tempfile.TemporaryDirectory()
        with tmp:
            evals = Path(tmp.name) / "evals"
            copy_real_schemas(evals, EVALS_DIR)
            from helpers import MIN_RUBRIC

            rubric = dict(MIN_RUBRIC)
            rubric["critical_failures"] = [
                {"id": "CF-01", "description": "One"},
                {"id": "CF-01", "description": "Two"},
            ]
            add_scenario(evals, rubric=rubric)
            validator = EvalValidator(repo_root=REPO_ROOT, evals_root=evals)
            status = validator.validate()
            self.assertEqual(status, 1)
            self.assertTrue(any("duplicate critical-failure" in e for e in validator.errors))

    def test_scenario_rubric_version_mismatch(self):
        tmp = tempfile.TemporaryDirectory()
        with tmp:
            evals = Path(tmp.name) / "evals"
            copy_real_schemas(evals, EVALS_DIR)
            from helpers import MIN_RUBRIC

            rubric = dict(MIN_RUBRIC)
            rubric["scenario_version"] = "9.9.9"
            add_scenario(evals, rubric=rubric)
            # add_scenario overwrites scenario_version — force mismatch after
            scenario_dir = evals / "scenarios" / "synthetic-demo"
            write_yaml(scenario_dir / "rubric.yaml", rubric)
            validator = EvalValidator(repo_root=REPO_ROOT, evals_root=evals)
            status = validator.validate()
            self.assertEqual(status, 1)
            self.assertTrue(any("scenario_version" in e for e in validator.errors))


if __name__ == "__main__":
    unittest.main()
