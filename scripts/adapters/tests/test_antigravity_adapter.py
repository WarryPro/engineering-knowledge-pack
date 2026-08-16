"""Tests for the Antigravity adapter (EKP-AI30B)."""

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
from antigravity.generate import generate
from antigravity.grouping import (
    FOUNDATION_FILENAME,
    MAX_RULE_CHARS,
    ORCHESTRATOR_FILENAME,
    RULES_DIR,
    SPLIT_THRESHOLD_CHARS,
    part_filename,
)
from antigravity.manifest import MANIFEST_NAME, build_adapter_manifest
from antigravity.verify import AntigravityVerifyError, verify_antigravity_bundle
from antigravity.writer import render_unit_files
from common.selected_knowledge import KnowledgeUnit


class AntigravityAdapterTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.bundle_dir = Path(self.temp_dir) / "ekp-core"
        self.output_dir = self.bundle_dir / "antigravity"

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
        rules_dir = self.output_dir / RULES_DIR
        self.assertTrue((rules_dir / ORCHESTRATOR_FILENAME).is_file())
        self.assertTrue((rules_dir / FOUNDATION_FILENAME).is_file())
        stems = sorted(path.name for path in rules_dir.glob("*.md"))
        self.assertTrue(any(name.endswith("testing.md") for name in stems))
        self.assertTrue(any("refactoring.md" in name for name in stems))

    def test_manifest_identifies_adapter_and_files(self):
        _written, manifest = self._generate_and_manifest()
        self.assertEqual(manifest["adapter"], "antigravity")
        self.assertEqual(manifest["profile"], "ekp-core")
        self.assertEqual(manifest["files_count"], len(manifest["files"]))
        paths = [entry["path"] for entry in manifest["files"]]
        self.assertIn("{}/{}".format(RULES_DIR, ORCHESTRATOR_FILENAME), paths)

    def test_verification_passes(self):
        self._generate_and_manifest()
        verify_antigravity_bundle(self.bundle_dir)

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
        for path in (self.output_dir / RULES_DIR).glob("*.md"):
            content = path.read_text(encoding="utf-8")
            self.assertIn("> **Source:**", content)
            self.assertIn("knowledge/", content)

    def test_character_limit(self):
        self._generate_and_manifest()
        for path in (self.output_dir / RULES_DIR).glob("*.md"):
            content = path.read_text(encoding="utf-8")
            self.assertLess(len(content), MAX_RULE_CHARS, msg=path.name)

    def test_foundation_principles_are_present(self):
        self._generate_and_manifest()
        content = (
            self.output_dir / RULES_DIR / FOUNDATION_FILENAME
        ).read_text(encoding="utf-8")
        self.assertIn("EKP-P01", content)
        self.assertIn("EKP-P10", content)

    def test_no_cursor_frontmatter_leakage(self):
        self._generate_and_manifest()
        for path in (self.output_dir / RULES_DIR).glob("*.md"):
            content = path.read_text(encoding="utf-8")
            self.assertFalse(content.lstrip().startswith("---"), msg=path.name)
            self.assertNotIn("alwaysApply:", content)

    def test_split_on_concept_boundaries(self):
        huge = "x" * (SPLIT_THRESHOLD_CHARS // 2)
        unit = KnowledgeUnit(
            source_path="knowledge/engineering/error-handling.md",
            title="Error handling",
            kind="document",
            flow=None,
            concepts=[
                type(
                    "C",
                    (),
                    {
                        "concept_id": "EKP-EH01",
                        "title": "One",
                        "intent": huge,
                        "rules": [huge],
                        "implements": [],
                        "source_document": "knowledge/engineering/error-handling.md",
                    },
                )(),
                type(
                    "C",
                    (),
                    {
                        "concept_id": "EKP-EH02",
                        "title": "Two",
                        "intent": huge,
                        "rules": [huge],
                        "implements": [],
                        "source_document": "knowledge/engineering/error-handling.md",
                    },
                )(),
            ],
        )
        parts = render_unit_files(unit, "10-error-handling.md")
        self.assertGreater(len(parts), 1)
        self.assertEqual(parts[0][0], part_filename("10-error-handling.md", 1))
        for _name, content in parts:
            self.assertLess(len(content), MAX_RULE_CHARS)
            self.assertFalse(content.lstrip().startswith("---"))

    def test_unexpected_file_fails_verify(self):
        self._generate_and_manifest()
        extra = self.output_dir / "unexpected.txt"
        extra.write_text("nope\n", encoding="utf-8")
        with self.assertRaises(AntigravityVerifyError):
            verify_antigravity_bundle(self.bundle_dir)

    def test_manifest_mismatch_fails_verify(self):
        self._generate_and_manifest()
        manifest_path = self.output_dir / MANIFEST_NAME
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
        payload["files"] = []
        payload["files_count"] = 0
        manifest_path.write_text(json.dumps(payload) + "\n", encoding="utf-8")
        with self.assertRaises(AntigravityVerifyError):
            verify_antigravity_bundle(self.bundle_dir)


if __name__ == "__main__":
    unittest.main()
