"""Integration tests for ekp-nativescript (Cursor + Copilot stack profile MVP)."""

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

NATIVEscript_APPLY_TO = (
    "**/*.xml,**/App_Resources/**,**/nativescript.config.{ts,js}"
)


class EkpNativescriptProfileTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if verify_indexes(get_dist_path()):
            raise unittest.SkipTest(
                "dist indexes not available; run validate --generate-index"
            )
        assemble(profile_name="cursor-nativescript", clean=True, verify=True)
        assemble(profile_name="ekp-nativescript", clean=True, verify=True)
        cls.ekp_dir = get_dist_path() / "ekp-nativescript"
        cls.cursor_nativescript_dir = get_dist_path() / "cursor-nativescript"

    def test_ekp_nativescript_loads_successfully(self):
        profile = load_profile_by_name("ekp-nativescript", repo_root=REPO_ROOT)
        self.assertEqual(profile["name"], "ekp-nativescript")
        self.assertTrue(profile["knowledge"])

    def test_ekp_nativescript_includes_cursor_nativescript_only(self):
        profile_path = REPO_ROOT / "profiles" / "ekp-nativescript.yaml"
        data = yaml.safe_load(profile_path.read_text(encoding="utf-8"))
        self.assertEqual(data["includes"], ["cursor-nativescript"])

    def test_ekp_nativescript_outputs_cursor_and_copilot(self):
        profile = load_profile_by_name("ekp-nativescript", repo_root=REPO_ROOT)
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

    def test_resolved_knowledge_matches_cursor_nativescript(self):
        ekp_paths = resolve_profile_knowledge(REPO_ROOT, "ekp-nativescript")
        nativescript_paths = resolve_profile_knowledge(
            REPO_ROOT, "cursor-nativescript"
        )
        self.assertEqual(ekp_paths, nativescript_paths)

    def test_cursor_rule_count_is_84(self):
        mdc_files = sorted((self.ekp_dir / "cursor").glob("*.mdc"))
        self.assertEqual(len(mdc_files), 84)
        manifest = json.loads(
            (self.ekp_dir / "bundle-manifest.json").read_text(encoding="utf-8")
        )
        self.assertEqual(manifest["adapter"], "cursor")
        self.assertEqual(manifest["profile"], "ekp-nativescript")
        self.assertEqual(manifest["rules_count"], 84)

    def test_cursor_mdc_byte_identical_to_cursor_nativescript(self):
        ekp_cursor = self.ekp_dir / "cursor"
        nativescript_cursor = self.cursor_nativescript_dir / "cursor"
        ekp_names = sorted(path.name for path in ekp_cursor.glob("*.mdc"))
        nativescript_names = sorted(
            path.name for path in nativescript_cursor.glob("*.mdc")
        )
        self.assertEqual(ekp_names, nativescript_names)
        mismatches = []
        for name in ekp_names:
            ekp_hash = hashlib.sha256((ekp_cursor / name).read_bytes()).hexdigest()
            nativescript_hash = hashlib.sha256(
                (nativescript_cursor / name).read_bytes()
            ).hexdigest()
            if ekp_hash != nativescript_hash:
                mismatches.append(name)
        self.assertEqual(mismatches, [])

    def test_copilot_tree_includes_nativescript_typescript_and_testing(self):
        github = self.ekp_dir / "copilot" / ".github"
        self.assertTrue((github / "copilot-instructions.md").is_file())
        self.assertTrue(
            (github / "instructions" / "testing.instructions.md").is_file()
        )
        ts_path = github / "instructions" / "typescript.instructions.md"
        self.assertTrue(ts_path.is_file())
        ts_match = APPLY_TO_RE.search(ts_path.read_text(encoding="utf-8"))
        self.assertIsNotNone(
            ts_match, msg="typescript.instructions.md missing applyTo"
        )
        self.assertEqual(ts_match.group(1), "**/*.ts,**/*.tsx")
        ns_path = github / "instructions" / "nativescript.instructions.md"
        self.assertTrue(ns_path.is_file())
        ns_match = APPLY_TO_RE.search(ns_path.read_text(encoding="utf-8"))
        self.assertIsNotNone(
            ns_match, msg="nativescript.instructions.md missing applyTo"
        )
        self.assertEqual(ns_match.group(1), NATIVEscript_APPLY_TO)

    def test_copilot_no_php_symfony_frontend_or_devops_instructions(self):
        instructions_dir = self.ekp_dir / "copilot" / ".github" / "instructions"
        self.assertFalse((instructions_dir / "php.instructions.md").exists())
        self.assertFalse((instructions_dir / "symfony.instructions.md").exists())
        self.assertFalse((instructions_dir / "frontend.instructions.md").exists())
        self.assertFalse((instructions_dir / "devops.instructions.md").exists())

    def test_copilot_no_unexpected_instruction_groups(self):
        instructions_dir = self.ekp_dir / "copilot" / ".github" / "instructions"
        emitted = sorted(path.name for path in instructions_dir.glob("*.instructions.md"))
        self.assertEqual(
            emitted,
            [
                "nativescript.instructions.md",
                "testing.instructions.md",
                "typescript.instructions.md",
            ],
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
