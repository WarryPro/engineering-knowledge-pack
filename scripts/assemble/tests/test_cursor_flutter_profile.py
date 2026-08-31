"""Integration tests for cursor-flutter (Cursor-only Flutter vertical)."""

import hashlib
import json
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

from assemble import assemble, verify_indexes
from common.paths import get_dist_path
from common.profile_loader import load_profile_by_name, resolve_profile_outputs
from common.profile_resolve import resolve_profile_knowledge

EXPECTED_PATHS = [
    "knowledge/engineering/engineering-principles.md",
    "knowledge/ai/ai-assisted-development.md",
    "knowledge/engineering/refactoring.md",
    "knowledge/testing/testing.md",
    "knowledge/engineering/error-handling.md",
    "knowledge/architecture/layering-and-boundaries.md",
    "knowledge/flutter/flutter-architecture.md",
]

EXPECTED_RULE_COUNT = 75


class CursorFlutterProfileTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if verify_indexes(get_dist_path()):
            raise unittest.SkipTest(
                "dist indexes not available; run validate --generate-index"
            )
        assemble(profile_name="cursor-core", clean=True, verify=True)
        assemble(profile_name="cursor-flutter", clean=True, verify=True)
        cls.bundle_dir = get_dist_path() / "cursor-flutter"
        cls.core_dir = get_dist_path() / "cursor-core"

    def test_profile_loads_successfully(self):
        profile = load_profile_by_name("cursor-flutter", repo_root=REPO_ROOT)
        self.assertEqual(profile["name"], "cursor-flutter")
        self.assertEqual(profile["knowledge"], EXPECTED_PATHS)
        raw = yaml.safe_load(
            (REPO_ROOT / "profiles" / "cursor-flutter.yaml").read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual(raw["includes"], ["cursor-core"])
        self.assertEqual(
            raw["knowledge"],
            ["knowledge/flutter/flutter-architecture.md"],
        )

    def test_outputs_cursor_only(self):
        profile = load_profile_by_name("cursor-flutter", repo_root=REPO_ROOT)
        self.assertEqual(resolve_profile_outputs(profile), ["cursor"])
        self.assertEqual(profile["outputs"], ["cursor"])

    def test_resolved_knowledge_paths(self):
        paths = resolve_profile_knowledge(REPO_ROOT, "cursor-flutter")
        self.assertEqual(paths, EXPECTED_PATHS)
        self.assertEqual(len(paths), 7)

    def test_includes_core_knowledge_only(self):
        paths = resolve_profile_knowledge(REPO_ROOT, "cursor-flutter")
        self.assertIn(
            "knowledge/engineering/engineering-principles.md", paths
        )
        self.assertIn("knowledge/flutter/flutter-architecture.md", paths)

    def test_no_typescript_frontend_nativescript_or_other_stack_knowledge(self):
        paths = resolve_profile_knowledge(REPO_ROOT, "cursor-flutter")
        joined = "\n".join(paths)
        self.assertNotIn("knowledge/typescript/", joined)
        self.assertNotIn("knowledge/frontend/", joined)
        self.assertNotIn("knowledge/nativescript/", joined)
        self.assertNotIn("knowledge/devops/", joined)
        self.assertNotIn("knowledge/php/", joined)
        self.assertNotIn("knowledge/symfony/", joined)

    def test_resolved_superset_of_cursor_core(self):
        flutter_paths = resolve_profile_knowledge(REPO_ROOT, "cursor-flutter")
        core_paths = resolve_profile_knowledge(REPO_ROOT, "cursor-core")
        self.assertEqual(flutter_paths[:-1], core_paths)
        self.assertEqual(
            flutter_paths[-1],
            "knowledge/flutter/flutter-architecture.md",
        )

    def test_assemble_cursor_only_tree(self):
        cursor_dir = self.bundle_dir / "cursor"
        self.assertTrue(cursor_dir.is_dir())
        self.assertFalse((self.bundle_dir / "copilot").exists())
        self.assertFalse((self.bundle_dir / "antigravity").exists())
        self.assertFalse((self.bundle_dir / "claude").exists())
        mdc_files = sorted(cursor_dir.glob("*.mdc"))
        self.assertEqual(len(mdc_files), EXPECTED_RULE_COUNT)
        manifest = json.loads(
            (self.bundle_dir / "bundle-manifest.json").read_text(encoding="utf-8")
        )
        self.assertEqual(manifest["adapter"], "cursor")
        self.assertEqual(manifest["profile"], "cursor-flutter")
        self.assertEqual(manifest["rules_count"], EXPECTED_RULE_COUNT)

    def test_cursor_core_mdc_files_byte_identical_in_flutter_bundle(self):
        core_mdc = {p.name: p for p in (self.core_dir / "cursor").glob("*.mdc")}
        flutter_mdc = {
            p.name: p for p in (self.bundle_dir / "cursor").glob("*.mdc")
        }
        self.assertEqual(set(core_mdc), set(flutter_mdc) - self._flutter_only_names())
        for name, core_path in core_mdc.items():
            core_hash = hashlib.sha256(core_path.read_bytes()).hexdigest()
            flutter_hash = hashlib.sha256(flutter_mdc[name].read_bytes()).hexdigest()
            self.assertEqual(core_hash, flutter_hash, msg=name)

    def test_flutter_bundle_has_additive_rules_beyond_core(self):
        core_count = len(list((self.core_dir / "cursor").glob("*.mdc")))
        flutter_count = len(list((self.bundle_dir / "cursor").glob("*.mdc")))
        self.assertEqual(core_count, 65)
        self.assertEqual(flutter_count, EXPECTED_RULE_COUNT)
        self.assertEqual(flutter_count - core_count, EXPECTED_RULE_COUNT - 65)

    def test_profile_yaml_does_not_include_typescript_or_frontend(self):
        path = REPO_ROOT / "profiles" / "cursor-flutter.yaml"
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        self.assertEqual(data["includes"], ["cursor-core"])
        self.assertNotIn("cursor-typescript", data["includes"])
        self.assertNotIn("cursor-frontend", data["includes"])
        self.assertNotIn("cursor-nativescript", data["includes"])
        self.assertNotIn("cursor-devops", data["includes"])

    @staticmethod
    def _flutter_only_names():
        core_names = {
            p.name
            for p in (get_dist_path() / "cursor-core" / "cursor").glob("*.mdc")
        }
        flutter_names = {
            p.name
            for p in (get_dist_path() / "cursor-flutter" / "cursor").glob("*.mdc")
        }
        return flutter_names - core_names


if __name__ == "__main__":
    unittest.main()
