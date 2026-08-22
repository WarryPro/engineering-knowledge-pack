"""Integration tests for ekp-symfony (Cursor + Copilot stack profile MVP)."""

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


class EkpSymfonyProfileTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if verify_indexes(get_dist_path()):
            raise unittest.SkipTest(
                "dist indexes not available; run validate --generate-index"
            )
        assemble(profile_name="cursor-symfony", clean=True, verify=True)
        assemble(profile_name="ekp-symfony", clean=True, verify=True)
        cls.ekp_dir = get_dist_path() / "ekp-symfony"
        cls.cursor_symfony_dir = get_dist_path() / "cursor-symfony"

    def test_ekp_symfony_loads_successfully(self):
        profile = load_profile_by_name("ekp-symfony", repo_root=REPO_ROOT)
        self.assertEqual(profile["name"], "ekp-symfony")
        self.assertTrue(profile["knowledge"])

    def test_ekp_symfony_outputs_cursor_and_copilot(self):
        profile = load_profile_by_name("ekp-symfony", repo_root=REPO_ROOT)
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

    def test_resolved_knowledge_matches_cursor_symfony(self):
        ekp_paths = resolve_profile_knowledge(REPO_ROOT, "ekp-symfony")
        symfony_paths = resolve_profile_knowledge(REPO_ROOT, "cursor-symfony")
        self.assertEqual(ekp_paths, symfony_paths)

    def test_cursor_rule_count_is_83(self):
        mdc_files = sorted((self.ekp_dir / "cursor").glob("*.mdc"))
        self.assertEqual(len(mdc_files), 83)
        manifest = json.loads(
            (self.ekp_dir / "bundle-manifest.json").read_text(encoding="utf-8")
        )
        self.assertEqual(manifest["adapter"], "cursor")
        self.assertEqual(manifest["profile"], "ekp-symfony")
        self.assertEqual(manifest["rules_count"], 83)

    def test_cursor_mdc_byte_identical_to_cursor_symfony(self):
        ekp_cursor = self.ekp_dir / "cursor"
        symfony_cursor = self.cursor_symfony_dir / "cursor"
        ekp_names = sorted(path.name for path in ekp_cursor.glob("*.mdc"))
        symfony_names = sorted(path.name for path in symfony_cursor.glob("*.mdc"))
        self.assertEqual(ekp_names, symfony_names)
        for name in ekp_names:
            ekp_hash = hashlib.sha256((ekp_cursor / name).read_bytes()).hexdigest()
            symfony_hash = hashlib.sha256(
                (symfony_cursor / name).read_bytes()
            ).hexdigest()
            self.assertEqual(ekp_hash, symfony_hash, msg=name)

    def test_copilot_tree_includes_php_symfony_and_testing(self):
        github = self.ekp_dir / "copilot" / ".github"
        self.assertTrue((github / "copilot-instructions.md").is_file())
        self.assertTrue(
            (github / "instructions" / "testing.instructions.md").is_file()
        )
        php_path = github / "instructions" / "php.instructions.md"
        self.assertTrue(php_path.is_file())
        php_text = php_path.read_text(encoding="utf-8")
        php_match = APPLY_TO_RE.search(php_text)
        self.assertIsNotNone(php_match, msg="php.instructions.md missing applyTo")
        self.assertEqual(php_match.group(1), "**/*.php")
        symfony_path = github / "instructions" / "symfony.instructions.md"
        self.assertTrue(symfony_path.is_file())
        symfony_text = symfony_path.read_text(encoding="utf-8")
        symfony_match = APPLY_TO_RE.search(symfony_text)
        self.assertIsNotNone(
            symfony_match, msg="symfony.instructions.md missing applyTo"
        )
        self.assertEqual(
            symfony_match.group(1), "**/*.php,**/*.twig,**/*.yaml,**/*.yml"
        )

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
