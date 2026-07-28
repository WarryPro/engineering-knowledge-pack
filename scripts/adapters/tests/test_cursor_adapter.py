"""Tests for Cursor adapter generation."""

import hashlib
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

ADAPTERS_DIR = Path(__file__).resolve().parents[1]
if str(ADAPTERS_DIR) not in sys.path:
    sys.path.insert(0, str(ADAPTERS_DIR))

from cursor.generate import generate
from cursor.naming import orchestrator_filename

ORCHESTRATOR_SOURCE = "knowledge/ai/ai-assisted-development.md"


class CursorAdapterTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.output_dir = Path(self.temp_dir) / "cursor"

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_profile_generates_output(self):
        written = generate(profile_name="cursor-core", output_dir=self.output_dir)

        self.assertGreater(len(written), 0)
        self.assertTrue(all(Path(path).exists() for path in written))
        self.assertTrue(all(path.endswith(".mdc") for path in written))

    def test_orchestrator_exists(self):
        generate(profile_name="cursor-core", output_dir=self.output_dir)
        orchestrator = self.output_dir / orchestrator_filename()

        self.assertTrue(orchestrator.exists())
        content = orchestrator.read_text(encoding="utf-8")
        self.assertIn("alwaysApply: true", content)
        self.assertIn(ORCHESTRATOR_SOURCE, content)

    def test_ai_decision_flow_included(self):
        generate(profile_name="cursor-core", output_dir=self.output_dir)
        orchestrator = self.output_dir / orchestrator_filename()
        content = orchestrator.read_text(encoding="utf-8")

        self.assertIn("Scope verification", content)
        self.assertIn("Completion verification", content)
        self.assertIn("EKP-AI01", content)

    def test_ekp_ai_concepts_generated(self):
        generate(profile_name="cursor-core", output_dir=self.output_dir)
        ai_concepts = sorted(self.output_dir.glob("concept-ekp-ai*.mdc"))

        self.assertEqual(len(ai_concepts), 12)
        self.assertTrue(any("ekp-ai01" in path.name for path in ai_concepts))

    def test_source_references_exist(self):
        generate(profile_name="cursor-core", output_dir=self.output_dir)

        for path in self.output_dir.glob("*.mdc"):
            content = path.read_text(encoding="utf-8")
            self.assertIn("> **Source:**", content)
            self.assertIn("knowledge/", content)

    def test_output_is_deterministic(self):
        first_dir = Path(self.temp_dir) / "first"
        second_dir = Path(self.temp_dir) / "second"

        generate(profile_name="cursor-core", output_dir=first_dir)
        generate(profile_name="cursor-core", output_dir=second_dir)

        first_files = sorted(path.name for path in first_dir.glob("*.mdc"))
        second_files = sorted(path.name for path in second_dir.glob("*.mdc"))
        self.assertEqual(first_files, second_files)

        for name in first_files:
            first_hash = hashlib.sha256(
                (first_dir / name).read_bytes()
            ).hexdigest()
            second_hash = hashlib.sha256(
                (second_dir / name).read_bytes()
            ).hexdigest()
            self.assertEqual(first_hash, second_hash)


if __name__ == "__main__":
    unittest.main()
