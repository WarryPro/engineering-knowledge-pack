"""Integration tests for cursor-nativescript (Cursor-only NativeScript vertical)."""

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
    "knowledge/typescript/typescript-fundamentals.md",
    "knowledge/nativescript/nativescript-architecture.md",
]


class CursorNativescriptProfileTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if verify_indexes(get_dist_path()):
            raise unittest.SkipTest(
                "dist indexes not available; run validate --generate-index"
            )
        assemble(profile_name="cursor-nativescript", clean=True, verify=True)
        cls.bundle_dir = get_dist_path() / "cursor-nativescript"

    def test_profile_loads_successfully(self):
        profile = load_profile_by_name("cursor-nativescript", repo_root=REPO_ROOT)
        self.assertEqual(profile["name"], "cursor-nativescript")
        self.assertEqual(profile["knowledge"], EXPECTED_PATHS)
        raw = yaml.safe_load(
            (REPO_ROOT / "profiles" / "cursor-nativescript.yaml").read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual(raw["includes"], ["cursor-typescript"])
        self.assertEqual(
            raw["knowledge"],
            ["knowledge/nativescript/nativescript-architecture.md"],
        )

    def test_outputs_cursor_only(self):
        profile = load_profile_by_name("cursor-nativescript", repo_root=REPO_ROOT)
        self.assertEqual(resolve_profile_outputs(profile), ["cursor"])
        self.assertEqual(profile["outputs"], ["cursor"])

    def test_resolved_knowledge_paths(self):
        paths = resolve_profile_knowledge(REPO_ROOT, "cursor-nativescript")
        self.assertEqual(paths, EXPECTED_PATHS)

    def test_includes_typescript_and_core_knowledge(self):
        paths = resolve_profile_knowledge(REPO_ROOT, "cursor-nativescript")
        self.assertIn("knowledge/typescript/typescript-fundamentals.md", paths)
        self.assertIn(
            "knowledge/engineering/engineering-principles.md", paths
        )
        self.assertIn(
            "knowledge/nativescript/nativescript-architecture.md", paths
        )

    def test_no_frontend_flutter_symfony_or_devops_knowledge(self):
        paths = resolve_profile_knowledge(REPO_ROOT, "cursor-nativescript")
        joined = "\n".join(paths)
        self.assertNotIn("knowledge/frontend/", joined)
        self.assertNotIn("knowledge/flutter/", joined)
        self.assertNotIn("knowledge/symfony/", joined)
        self.assertNotIn("knowledge/php/", joined)
        self.assertNotIn("knowledge/devops/", joined)

    def test_resolved_superset_of_cursor_typescript(self):
        ns_paths = resolve_profile_knowledge(REPO_ROOT, "cursor-nativescript")
        ts_paths = resolve_profile_knowledge(REPO_ROOT, "cursor-typescript")
        self.assertEqual(ns_paths[:-1], ts_paths)
        self.assertEqual(
            ns_paths[-1],
            "knowledge/nativescript/nativescript-architecture.md",
        )

    def test_assemble_cursor_only_tree(self):
        cursor_dir = self.bundle_dir / "cursor"
        self.assertTrue(cursor_dir.is_dir())
        self.assertFalse((self.bundle_dir / "copilot").exists())
        self.assertFalse((self.bundle_dir / "antigravity").exists())
        self.assertFalse((self.bundle_dir / "claude").exists())
        mdc_files = sorted(cursor_dir.glob("*.mdc"))
        self.assertGreater(len(mdc_files), 0)
        manifest = json.loads(
            (self.bundle_dir / "bundle-manifest.json").read_text(encoding="utf-8")
        )
        self.assertEqual(manifest["adapter"], "cursor")
        self.assertEqual(manifest["profile"], "cursor-nativescript")
        self.assertEqual(manifest["rules_count"], len(mdc_files))

    def test_profile_yaml_does_not_include_frontend(self):
        path = REPO_ROOT / "profiles" / "cursor-nativescript.yaml"
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        self.assertEqual(data["includes"], ["cursor-typescript"])
        self.assertNotIn("cursor-frontend", data["includes"])


if __name__ == "__main__":
    unittest.main()
