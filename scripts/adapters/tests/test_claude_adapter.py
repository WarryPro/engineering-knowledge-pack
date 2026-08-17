"""Tests for the Claude adapter (EKP-AI30D)."""

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
from claude.generate import generate
from claude.grouping import CLAUDE_MD_RELPATH, SKILLS_DIR, skill_id_for_unit
from claude.manifest import MANIFEST_NAME, build_adapter_manifest
from claude.verify import ClaudeVerifyError, verify_claude_bundle
from common.selected_knowledge import KnowledgeUnit


class ClaudeAdapterTests(unittest.TestCase):
    EXPECTED_SKILLS = (
        "ekp-refactoring",
        "ekp-testing",
        "ekp-error-handling",
        "ekp-layering",
    )

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.bundle_dir = Path(self.temp_dir) / "ekp-core"
        self.output_dir = self.bundle_dir / "claude"

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def _generate_and_manifest(self):
        written = generate(profile_name="ekp-core", output_dir=self.output_dir)
        manifest = build_adapter_manifest(
            "ekp-core", self.output_dir, generated_at="2026-08-16T00:00:00Z"
        )
        write_json(self.output_dir / MANIFEST_NAME, manifest)
        return written, manifest

    def test_generation_writes_expected_tree(self):
        written, _manifest = self._generate_and_manifest()
        self.assertGreater(len(written), 0)
        self.assertTrue((self.output_dir / CLAUDE_MD_RELPATH).is_file())
        skills_root = self.output_dir / SKILLS_DIR
        self.assertTrue(skills_root.is_dir())
        for skill_id in self.EXPECTED_SKILLS:
            skill_path = skills_root / skill_id / "SKILL.md"
            self.assertTrue(skill_path.is_file(), msg=skill_id)
        self.assertFalse((self.output_dir / ".claude" / "rules").exists())

    def test_claude_md_is_compact_always_on(self):
        self._generate_and_manifest()
        content = (self.output_dir / CLAUDE_MD_RELPATH).read_text(encoding="utf-8")
        lines = content.splitlines()
        self.assertLessEqual(len(lines), 200)
        self.assertIn("AI orchestrator", content)
        self.assertIn("Engineering principles", content)
        self.assertIn("EKP-P01", content)
        # Must not dump every cursor concept filename into always-on memory.
        self.assertNotIn("concept-ekp-ai01", content.lower())
        self.assertFalse(content.lstrip().startswith("---"))

    def test_skills_have_frontmatter_and_sources(self):
        self._generate_and_manifest()
        for skill_id in self.EXPECTED_SKILLS:
            path = self.output_dir / SKILLS_DIR / skill_id / "SKILL.md"
            content = path.read_text(encoding="utf-8")
            self.assertTrue(content.startswith("---\n"))
            self.assertIn("name: {}".format(skill_id), content)
            self.assertIn("description:", content)
            self.assertIn("> **Source:**", content)
            self.assertIn("knowledge/", content)

    def test_layering_skill_alias(self):
        unit = KnowledgeUnit(
            source_path="knowledge/architecture/layering-and-boundaries.md",
            title="Layering",
            kind="document",
            flow=None,
            concepts=[],
        )
        self.assertEqual(skill_id_for_unit(unit), "ekp-layering")

    def test_manifest_identifies_adapter_and_kinds(self):
        _written, manifest = self._generate_and_manifest()
        self.assertEqual(manifest["adapter"], "claude")
        self.assertEqual(manifest["profile"], "ekp-core")
        self.assertEqual(manifest["files_count"], len(manifest["files"]))
        kinds = {entry["path"]: entry["kind"] for entry in manifest["files"]}
        self.assertEqual(kinds[CLAUDE_MD_RELPATH], "memory")
        self.assertEqual(
            kinds[".claude/skills/ekp-testing/SKILL.md"], "skill"
        )

    def test_verification_passes(self):
        self._generate_and_manifest()
        verify_claude_bundle(self.bundle_dir)

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

    def test_no_cross_adapter_leakage(self):
        self._generate_and_manifest()
        for path in self.output_dir.rglob("*"):
            if not path.is_file() or path.name == MANIFEST_NAME:
                continue
            content = path.read_text(encoding="utf-8")
            self.assertNotIn("alwaysApply:", content, msg=path.name)
            self.assertNotIn("applyTo:", content, msg=path.name)

    def test_unexpected_file_fails_verify(self):
        self._generate_and_manifest()
        extra = self.output_dir / "unexpected.txt"
        extra.write_text("nope\n", encoding="utf-8")
        with self.assertRaises(ClaudeVerifyError):
            verify_claude_bundle(self.bundle_dir)

    def test_pathless_rules_fail_verify(self):
        self._generate_and_manifest()
        rules = self.output_dir / ".claude" / "rules"
        rules.mkdir(parents=True)
        (rules / "always.md").write_text("# bad\n", encoding="utf-8")
        with self.assertRaises(ClaudeVerifyError):
            verify_claude_bundle(self.bundle_dir)

    def test_manifest_mismatch_fails_verify(self):
        self._generate_and_manifest()
        manifest_path = self.output_dir / MANIFEST_NAME
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
        payload["files"] = []
        payload["files_count"] = 0
        manifest_path.write_text(json.dumps(payload) + "\n", encoding="utf-8")
        with self.assertRaises(ClaudeVerifyError):
            verify_claude_bundle(self.bundle_dir)


if __name__ == "__main__":
    unittest.main()
