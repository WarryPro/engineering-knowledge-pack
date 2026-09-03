"""Run importer tests."""

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

from eval_common import EMPTY_BYTES_SHA256, sha256_bytes  # noqa: E402
from import_run import ImportRunError, import_run  # noqa: E402
from prepare import prepare_all  # noqa: E402


def _execution(**overrides):
    data = {
        "provider": "synthetic",
        "model_config_id": "synthetic-model-a",
        "model_id_observed": "synthetic-model-a",
        "executed_at": "2026-09-04T00:00:00Z",
        "replicate_index": 1,
        "sampling": {
            "temperature": 0.0,
            "top_p": None,
            "seed": None,
            "seed_supported": False,
            "max_output": 512,
        },
    }
    data.update(overrides)
    return data


class ImportRunTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not (REPO_ROOT / "dist" / "adapter-manifest.json").is_file():
            raise unittest.SkipTest("dist indexes missing")

    def _prepare_one(self, tmp: Path, scenario_id: str = "core-test-strategy"):
        prepare_all(
            output_root=tmp / "prepared",
            repo_root=REPO_ROOT,
            scenario_id=scenario_id,
            ekp_commit="d" * 40,
            ekp_version="0.17.0.dev0",
        )
        return tmp / "prepared" / scenario_id

    def test_valid_baseline_and_treatment_import(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            packages = self._prepare_one(root)
            for condition in ("baseline", "treatment"):
                response = root / "resp-{}.txt".format(condition)
                payload = "SYNTHETIC RESPONSE {} — not a real answer.\n".format(condition)
                response.write_bytes(payload.encode("utf-8"))
                run = import_run(
                    package_dir=packages / condition,
                    response_path=response,
                    execution=_execution(replicate_index=1),
                    output_dir=root / "runs" / condition,
                )
                self.assertEqual(run["condition"], condition)
                self.assertEqual(run["response_sha256"], sha256_bytes(payload.encode("utf-8")))
                stored = (root / "runs" / condition / "response.txt").read_bytes()
                self.assertEqual(stored, payload.encode("utf-8"))
                if condition == "baseline":
                    self.assertEqual(run["context_sha256"], EMPTY_BYTES_SHA256)

    def test_tampering_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            packages = self._prepare_one(root)
            package = packages / "baseline"
            response = root / "resp.txt"
            response.write_text("ok\n", encoding="utf-8")
            # Tamper participant
            part = package / "participant.md"
            part.write_bytes(part.read_bytes() + b"x")
            with self.assertRaises(ImportRunError):
                import_run(package, response, _execution(), root / "out")

    def test_context_tampering_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            packages = self._prepare_one(root)
            package = packages / "treatment"
            response = root / "resp.txt"
            response.write_text("ok\n", encoding="utf-8")
            ctx = package / "context.md"
            ctx.write_bytes(ctx.read_bytes() + b"\n")
            with self.assertRaises(ImportRunError):
                import_run(package, response, _execution(), root / "out")

    def test_empty_response_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            packages = self._prepare_one(root)
            response = root / "resp.txt"
            response.write_bytes(b"")
            with self.assertRaises(ImportRunError):
                import_run(packages / "baseline", response, _execution(), root / "out")

    def test_invalid_utf8_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            packages = self._prepare_one(root)
            response = root / "resp.txt"
            response.write_bytes(b"\xff\xfe not utf8")
            with self.assertRaises(ImportRunError):
                import_run(packages / "baseline", response, _execution(), root / "out")

    def test_secret_metadata_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            packages = self._prepare_one(root)
            response = root / "resp.txt"
            response.write_text("ok\n", encoding="utf-8")
            with self.assertRaises(ImportRunError):
                import_run(
                    packages / "baseline",
                    response,
                    _execution(api_key="nope"),
                    root / "out",
                )

    def test_condition_override_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            packages = self._prepare_one(root)
            response = root / "resp.txt"
            response.write_text("ok\n", encoding="utf-8")
            with self.assertRaises(ImportRunError):
                import_run(
                    packages / "baseline",
                    response,
                    _execution(condition="treatment"),
                    root / "out",
                )

    def test_deterministic_import_same_input(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            packages = self._prepare_one(root)
            response = root / "resp.txt"
            response.write_bytes(b"same-bytes\n")
            run1 = import_run(packages / "baseline", response, _execution(), root / "o1")
            run2 = import_run(packages / "baseline", response, _execution(), root / "o2")
            self.assertEqual(run1["run_id"], run2["run_id"])
            self.assertEqual(run1["response_sha256"], run2["response_sha256"])

    def test_different_response_different_identity(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            packages = self._prepare_one(root)
            r1 = root / "r1.txt"
            r2 = root / "r2.txt"
            r1.write_bytes(b"one\n")
            r2.write_bytes(b"two\n")
            run1 = import_run(packages / "baseline", r1, _execution(), root / "o1")
            run2 = import_run(packages / "baseline", r2, _execution(), root / "o2")
            self.assertNotEqual(run1["response_sha256"], run2["response_sha256"])
            self.assertNotEqual(run1["run_id"], run2["run_id"])


if __name__ == "__main__":
    unittest.main()
