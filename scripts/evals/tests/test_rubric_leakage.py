"""Rubric identity leakage audit for real evaluator materials."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPTS_EVALS = REPO_ROOT / "scripts" / "evals"
SCENARIOS = REPO_ROOT / "evals" / "scenarios"
if str(SCRIPTS_EVALS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_EVALS))

from scoring_common import audit_rubric_identity_leakage  # noqa: E402


class RubricLeakageAuditTests(unittest.TestCase):
    def test_all_active_rubrics_have_no_experiment_identity(self):
        rubrics = sorted(SCENARIOS.glob("*/rubric.yaml"))
        self.assertEqual(len(rubrics), 8)
        for path in rubrics:
            text = path.read_text(encoding="utf-8")
            findings = audit_rubric_identity_leakage(text)
            self.assertEqual(findings, [], msg="{}: {}".format(path, findings))


if __name__ == "__main__":
    unittest.main()
