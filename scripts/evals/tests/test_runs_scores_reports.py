"""Run, score-sheet, and report evidence validation tests."""

from __future__ import annotations

import hashlib
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
EVALS_DIR = REPO_ROOT / "evals"
SCRIPTS_EVALS = REPO_ROOT / "scripts" / "evals"
if str(SCRIPTS_EVALS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_EVALS))

from eval_common import EMPTY_BYTES_SHA256
from validate import EvalValidator

from helpers import (
    copy_real_schemas,
    make_report,
    make_run,
    make_score_sheet,
    write_json,
)


class RunEvidenceTests(unittest.TestCase):
    def _evals_with_run(self, run_data, response_text="hello\n"):
        tmp = tempfile.TemporaryDirectory()
        evals = Path(tmp.name) / "evals"
        copy_real_schemas(evals, EVALS_DIR)
        evidence = evals / "evidence" / "synthetic" / "runs"
        evidence.mkdir(parents=True)
        response_path = evidence / "response.txt"
        payload = response_text.encode("utf-8")
        response_path.write_bytes(payload)
        run_data = dict(run_data)
        run_data["response_sha256"] = hashlib.sha256(payload).hexdigest()
        run_data["response_file"] = "response.txt"
        write_json(evidence / "run-001.json", run_data)
        return tmp, evals

    def test_valid_baseline_run(self):
        run = make_run(condition="baseline")
        tmp, evals = self._evals_with_run(run)
        with tmp:
            validator = EvalValidator(repo_root=REPO_ROOT, evals_root=evals)
            status = validator.validate()
            self.assertEqual(status, 0, msg=validator.errors)

    def test_malformed_sha_rejected(self):
        run = make_run()
        run["prompt_sha256"] = "not-a-sha"
        tmp, evals = self._evals_with_run(run)
        with tmp:
            validator = EvalValidator(repo_root=REPO_ROOT, evals_root=evals)
            status = validator.validate()
            self.assertEqual(status, 1)
            self.assertTrue(any("prompt_sha256" in e for e in validator.errors))

    def test_response_hash_mismatch(self):
        run = make_run()
        tmp, evals = self._evals_with_run(run, response_text="hello\n")
        with tmp:
            # Corrupt stored hash after write helper set correct one
            path = evals / "evidence" / "synthetic" / "runs" / "run-001.json"
            data = make_run()
            data["response_file"] = "response.txt"
            data["response_sha256"] = "0" * 64
            write_json(path, data)
            validator = EvalValidator(repo_root=REPO_ROOT, evals_root=evals)
            status = validator.validate()
            self.assertEqual(status, 1)
            self.assertTrue(any("response_sha256 mismatch" in e for e in validator.errors))

    def test_forbidden_secret_metadata(self):
        run = make_run()
        run["api_key"] = "should-not-appear"
        tmp, evals = self._evals_with_run(run)
        with tmp:
            # additionalProperties false should also catch this; ensure either schema or guard fires
            validator = EvalValidator(repo_root=REPO_ROOT, evals_root=evals)
            status = validator.validate()
            self.assertEqual(status, 1)
            self.assertTrue(
                any(
                    "api_key" in e or "additional" in e.lower() or "forbidden" in e
                    for e in validator.errors
                )
            )

    def test_invalid_condition(self):
        run = make_run()
        run["condition"] = "maybe"
        tmp, evals = self._evals_with_run(run)
        with tmp:
            validator = EvalValidator(repo_root=REPO_ROOT, evals_root=evals)
            status = validator.validate()
            self.assertEqual(status, 1)
            self.assertTrue(any("condition" in e for e in validator.errors))

    def test_baseline_requires_empty_context_hash(self):
        run = make_run(condition="baseline")
        run["context_sha256"] = hashlib.sha256(b"not-empty").hexdigest()
        tmp, evals = self._evals_with_run(run)
        with tmp:
            validator = EvalValidator(repo_root=REPO_ROOT, evals_root=evals)
            status = validator.validate()
            self.assertEqual(status, 1)
            self.assertTrue(any("empty bytes" in e for e in validator.errors))
            self.assertEqual(
                EMPTY_BYTES_SHA256,
                "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
            )


class ScoreSheetTests(unittest.TestCase):
    def _validate_sheet(self, sheet):
        tmp = tempfile.TemporaryDirectory()
        with tmp:
            evals = Path(tmp.name) / "evals"
            copy_real_schemas(evals, EVALS_DIR)
            scores = evals / "evidence" / "synthetic" / "scores"
            write_json(scores / "score-001.json", sheet)
            validator = EvalValidator(repo_root=REPO_ROOT, evals_root=evals)
            return validator.validate(), validator.errors

    def test_invalid_dimension_score(self):
        sheet = make_score_sheet()
        sheet["response_a"]["dimension_scores"]["technical-correctness"] = 9
        status, errors = self._validate_sheet(sheet)
        self.assertEqual(status, 1)
        self.assertTrue(any("0..3" in e or "maximum" in e.lower() or "technical-correctness" in e for e in errors))

    def test_condition_field_rejected(self):
        sheet = make_score_sheet()
        sheet["condition"] = "treatment"
        status, errors = self._validate_sheet(sheet)
        self.assertEqual(status, 1)
        self.assertTrue(any("condition" in e for e in errors))

    def test_unknown_critical_failure_pattern(self):
        sheet = make_score_sheet()
        sheet["response_a"]["critical_failures"] = ["NOT-A-CF"]
        status, errors = self._validate_sheet(sheet)
        self.assertEqual(status, 1)
        self.assertTrue(any("critical_failures" in e or "CF-" in e for e in errors))


class ReportTests(unittest.TestCase):
    def test_report_roundtrip(self):
        tmp = tempfile.TemporaryDirectory()
        with tmp:
            evals = Path(tmp.name) / "evals"
            copy_real_schemas(evals, EVALS_DIR)
            write_json(
                evals / "evidence" / "synthetic" / "report-summary.json",
                make_report(outcomes={
                    "improved": 1,
                    "tied": 2,
                    "regressed": 0,
                    "disputed": 1,
                }),
            )
            validator = EvalValidator(repo_root=REPO_ROOT, evals_root=evals)
            status = validator.validate()
            self.assertEqual(status, 0, msg=validator.errors)

    def test_magic_score_rejected(self):
        tmp = tempfile.TemporaryDirectory()
        with tmp:
            evals = Path(tmp.name) / "evals"
            copy_real_schemas(evals, EVALS_DIR)
            report = make_report()
            report["quality_percentage"] = 99
            write_json(evals / "evidence" / "synthetic" / "report-summary.json", report)
            validator = EvalValidator(repo_root=REPO_ROOT, evals_root=evals)
            status = validator.validate()
            self.assertEqual(status, 1)
            self.assertTrue(any("quality_percentage" in e or "additional" in e.lower() for e in validator.errors))


if __name__ == "__main__":
    unittest.main()
