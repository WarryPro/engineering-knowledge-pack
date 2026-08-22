"""Integration tests for ekp-typescript (Cursor + Copilot stack profile MVP)."""

import hashlib
import json
import re
import sys
import unittest
from pathlib import Path

import yaml

ASSEMBLE_DIR = Path(__file__).resolve().parents[1]
REPO_ROOT = ASSEMBLE_DIR.parents[1]
ADAPTERS_DIR = REPO_ROOT / "scripts" / "adapters"

if str(ASSEMBLE_DIR) not in sys.path:
    sys.path.insert(0, str(ASSEMBLE_DIR))
if str(ADAPTERS_DIR) not in sys.path:
    sys.path.insert(0, str(ADAPTERS_DIR))

from assemble import ASSEMBLE_MANIFEST_NAME, assemble, verify_indexes
from common.paths import get_dist_path
from common.profile_loader import load_profile_by_name, resolve_profile_outputs
from common.profile_resolve import resolve_profile_knowledge

APPLY_TO_RE = re.compile(r'^applyTo:\s*"([^"]+)"\s*$', re.MULTILINE)


class EkpTypescriptProfileTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if verify_indexes(get_dist_path()):
            raise unittest.SkipTest(
                "dist indexes not available; run validate --generate-index"
            )
        assemble(profile_name="cursor-typescript", clean=True, verify=True)
        assemble(profile_name="ekp-typescript", clean=True, verify=True)
        cls.ekp_dir = get_dist_path() / "ekp-typescript"
        cls.cursor_ts_dir = get_dist_path() / "cursor-typescript"

    def test_ekp_typescript_loads_successfully(self):
        profile = load_profile_by_name("ekp-typescript", repo_root=REPO_ROOT)
        self.assertEqual(profile["name"], "ekp-typescript")
        self.assertTrue(profile["knowledge"])

    def test_ekp_typescript_outputs_cursor_and_copilot(self):
        profile = load_profile_by_name("ekp-typescript", repo_root=REPO_ROOT)
        self.assertEqual(profile["outputs"], ["cursor", "copilot"])

    def test_cursor_profiles_remain_cursor_only(self):
        profiles_dir = REPO_ROOT / "profiles"
        for profile_path in sorted(profiles_dir.glob("cursor-*.yaml")):
            data = yaml.safe_load(profile_path.read_text(encoding="utf-8"))
            self.assertEqual(
                resolve_profile_outputs(data),
                ["cursor"],
                msg=profile_path.name,
            )

    def test_resolved_knowledge_matches_cursor_typescript(self):
        ekp_paths = resolve_profile_knowledge(REPO_ROOT, "ekp-typescript")
        ts_paths = resolve_profile_knowledge(REPO_ROOT, "cursor-typescript")
        self.assertEqual(ekp_paths, ts_paths)

    def test_cursor_rule_count_is_74(self):
        mdc_files = sorted((self.ekp_dir / "cursor").glob("*.mdc"))
        self.assertEqual(len(mdc_files), 74)
        manifest = json.loads(
            (self.ekp_dir / "bundle-manifest.json").read_text(encoding="utf-8")
        )
        self.assertEqual(manifest["adapter"], "cursor")
        self.assertEqual(manifest["profile"], "ekp-typescript")
        self.assertEqual(manifest["rules_count"], 74)

    def test_cursor_mdc_byte_identical_to_cursor_typescript(self):
        ekp_cursor = self.ekp_dir / "cursor"
        ts_cursor = self.cursor_ts_dir / "cursor"
        ekp_names = sorted(path.name for path in ekp_cursor.glob("*.mdc"))
        ts_names = sorted(path.name for path in ts_cursor.glob("*.mdc"))
        self.assertEqual(ekp_names, ts_names)
        for name in ekp_names:
            ekp_hash = hashlib.sha256((ekp_cursor / name).read_bytes()).hexdigest()
            ts_hash = hashlib.sha256((ts_cursor / name).read_bytes()).hexdigest()
            self.assertEqual(ekp_hash, ts_hash, msg=name)

    def test_copilot_tree_includes_typescript_and_testing(self):
        github = self.ekp_dir / "copilot" / ".github"
        self.assertTrue((github / "copilot-instructions.md").is_file())
        self.assertTrue(
            (github / "instructions" / "testing.instructions.md").is_file()
        )
        ts_path = github / "instructions" / "typescript.instructions.md"
        self.assertTrue(ts_path.is_file())
        text = ts_path.read_text(encoding="utf-8")
        match = APPLY_TO_RE.search(text)
        self.assertIsNotNone(match, msg="typescript.instructions.md missing applyTo")
        self.assertEqual(match.group(1), "**/*.ts,**/*.tsx")

    def test_no_antigravity_or_claude_output(self):
        self.assertFalse((self.ekp_dir / "antigravity").exists())
        self.assertFalse((self.ekp_dir / "claude").exists())

    def test_assemble_manifest_cursor_and_copilot_only(self):
        payload = json.loads(
            (self.ekp_dir / ASSEMBLE_MANIFEST_NAME).read_text(encoding="utf-8")
        )
        self.assertEqual(payload["adapters"], ["cursor", "copilot"])
        self.assertEqual(
            [entry["manifest"] for entry in payload["outputs"]],
            ["bundle-manifest.json", "copilot/adapter-manifest.json"],
        )


if __name__ == "__main__":
    unittest.main()
