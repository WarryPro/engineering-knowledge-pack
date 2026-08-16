"""Tests for the Copilot adapter (EKP-AI30B)."""

import hashlib
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

ADAPTERS_DIR = Path(__file__).resolve().parents[1]
REPO_ROOT = ADAPTERS_DIR.parents[1]
ASSEMBLE_DIR = REPO_ROOT / "scripts" / "assemble"

if str(ADAPTERS_DIR) not in sys.path:
    sys.path.insert(0, str(ADAPTERS_DIR))
if str(ASSEMBLE_DIR) not in sys.path:
    sys.path.insert(0, str(ASSEMBLE_DIR))

from assemble import write_json
from copilot.generate import generate
from copilot.grouping import COPILOT_INSTRUCTIONS_RELPATH
from copilot.manifest import MANIFEST_NAME, build_adapter_manifest
from copilot.verify import CopilotVerifyError, verify_copilot_bundle


class CopilotAdapterTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.bundle_dir = Path(self.temp_dir) / "ekp-core"
        self.output_dir = self.bundle_dir / "copilot"

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def _generate_and_manifest(self):
        written = generate(profile_name="ekp-core", output_dir=self.output_dir)
        manifest = build_adapter_manifest(
            "ekp-core", self.output_dir, generated_at="2026-08-15T00:00:00Z"
        )
        write_json(self.output_dir / MANIFEST_NAME, manifest)
        return written, manifest

    def test_generation_writes_expected_tree(self):
        written, _manifest = self._generate_and_manifest()
        self.assertGreater(len(written), 0)
        always_on = self.output_dir / COPILOT_INSTRUCTIONS_RELPATH
        self.assertTrue(always_on.is_file())
        testing = (
            self.output_dir / ".github" / "instructions" / "testing.instructions.md"
        )
        self.assertTrue(testing.is_file())
        self.assertFalse(
            (self.output_dir / ".github" / "instructions" / "php.instructions.md").is_file()
        )

    def test_manifest_identifies_adapter_and_files(self):
        _written, manifest = self._generate_and_manifest()
        self.assertEqual(manifest["adapter"], "copilot")
        self.assertEqual(manifest["profile"], "ekp-core")
        self.assertEqual(manifest["files_count"], len(manifest["files"]))
        paths = [entry["path"] for entry in manifest["files"]]
        self.assertIn(COPILOT_INSTRUCTIONS_RELPATH, paths)
        self.assertIn(".github/instructions/testing.instructions.md", paths)

    def test_verification_passes(self):
        self._generate_and_manifest()
        verify_copilot_bundle(self.bundle_dir)

    def test_determinism(self):
        first = Path(self.temp_dir) / "first"
        second = Path(self.temp_dir) / "second"
        generate(profile_name="ekp-core", output_dir=first)
        generate(profile_name="ekp-core", output_dir=second)
        first_files = sorted(
            path.relative_to(first).as_posix()
            for path in first.rglob("*")
            if path.is_file()
        )
        second_files = sorted(
            path.relative_to(second).as_posix()
            for path in second.rglob("*")
            if path.is_file()
        )
        self.assertEqual(first_files, second_files)
        for rel in first_files:
            self.assertEqual(
                hashlib.sha256((first / rel).read_bytes()).hexdigest(),
                hashlib.sha256((second / rel).read_bytes()).hexdigest(),
            )

    def test_source_references(self):
        self._generate_and_manifest()
        for path in self.output_dir.rglob("*.md"):
            content = path.read_text(encoding="utf-8")
            self.assertIn("> **Source:**", content)
            self.assertIn("knowledge/", content)

    def test_no_cursor_metadata_leakage(self):
        self._generate_and_manifest()
        always_on = (self.output_dir / COPILOT_INSTRUCTIONS_RELPATH).read_text(
            encoding="utf-8"
        )
        self.assertNotIn("alwaysApply:", always_on)
        self.assertFalse(always_on.startswith("---"))
        testing = (
            self.output_dir / ".github" / "instructions" / "testing.instructions.md"
        ).read_text(encoding="utf-8")
        self.assertIn("applyTo:", testing)
        self.assertNotIn("alwaysApply:", testing)

    def test_foundation_principles_are_present(self):
        self._generate_and_manifest()
        always_on = (self.output_dir / COPILOT_INSTRUCTIONS_RELPATH).read_text(
            encoding="utf-8"
        )
        self.assertIn("EKP-P01", always_on)
        self.assertIn("Engineering principles", always_on)

    def test_unexpected_file_fails_verify(self):
        self._generate_and_manifest()
        extra = self.output_dir / "unexpected.txt"
        extra.write_text("nope\n", encoding="utf-8")
        with self.assertRaises(CopilotVerifyError):
            verify_copilot_bundle(self.bundle_dir)

    def test_manifest_mismatch_fails_verify(self):
        self._generate_and_manifest()
        manifest_path = self.output_dir / MANIFEST_NAME
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
        payload["files"] = []
        payload["files_count"] = 0
        manifest_path.write_text(json.dumps(payload) + "\n", encoding="utf-8")
        with self.assertRaises(CopilotVerifyError):
            verify_copilot_bundle(self.bundle_dir)


if __name__ == "__main__":
    unittest.main()
