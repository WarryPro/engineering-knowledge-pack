"""Tests for EKP assemble pipeline."""

import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

ASSEMBLE_DIR = Path(__file__).resolve().parents[1]
REPO_ROOT = ASSEMBLE_DIR.parents[1]
ADAPTERS_DIR = REPO_ROOT / "scripts" / "adapters"

if str(ASSEMBLE_DIR) not in sys.path:
    sys.path.insert(0, str(ASSEMBLE_DIR))
if str(ADAPTERS_DIR) not in sys.path:
    sys.path.insert(0, str(ADAPTERS_DIR))

from assemble import (
    AssembleError,
    assemble,
    build_bundle_manifest,
    verify_bundle,
    verify_indexes,
)
from common.paths import get_dist_path, get_repo_root
from cursor.naming import orchestrator_filename


class VerifyIndexesTests(unittest.TestCase):
    def test_missing_indexes_fails_correctly(self):
        with tempfile.TemporaryDirectory() as tmp:
            fake_root = Path(tmp)
            (fake_root / "profiles").mkdir(parents=True)
            shutil.copy2(
                REPO_ROOT / "profiles" / "cursor-core.yaml",
                fake_root / "profiles" / "cursor-core.yaml",
            )
            (fake_root / "dist").mkdir()

            missing = verify_indexes(fake_root / "dist")
            self.assertEqual(
                missing,
                [
                    "concept-index.json",
                    "knowledge-graph.json",
                    "adapter-manifest.json",
                ],
            )

            with self.assertRaises(AssembleError) as context:
                assemble(
                    profile_name="cursor-core",
                    repo_root=fake_root,
                )

            self.assertIn("Missing required indexes", str(context.exception))
            self.assertIn("--generate-index", str(context.exception))


class AssembleBundleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if verify_indexes(get_dist_path()):
            raise unittest.SkipTest(
                "dist indexes not available; run validate --generate-index"
            )

    def test_cursor_core_profile_generates_bundle(self):
        manifest = assemble(profile_name="cursor-core", clean=True, verify=False)

        cursor_dir = get_dist_path() / "cursor-core" / "cursor"
        self.assertTrue(cursor_dir.is_dir())
        self.assertGreater(len(list(cursor_dir.glob("*.mdc"))), 0)
        self.assertEqual(manifest["profile"], "cursor-core")
        self.assertEqual(manifest["adapter"], "cursor")

    def test_manifest_created(self):
        assemble(profile_name="cursor-core", clean=True, verify=False)

        manifest_path = get_dist_path() / "cursor-core" / "bundle-manifest.json"
        self.assertTrue(manifest_path.is_file())

        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        self.assertIn("generated_at", manifest)
        self.assertIn("rules", manifest)
        self.assertEqual(manifest["rules_count"], len(manifest["rules"]))

    def test_verify_passes(self):
        assemble(profile_name="cursor-core", clean=True, verify=True)
        verify_bundle(get_dist_path() / "cursor-core")

    def test_deterministic_output_except_timestamp(self):
        first = assemble(profile_name="cursor-core", clean=True, verify=False)
        second = assemble(profile_name="cursor-core", clean=False, verify=False)

        first_compare = dict(first)
        second_compare = dict(second)
        first_compare.pop("generated_at")
        second_compare.pop("generated_at")
        self.assertEqual(first_compare, second_compare)

        cursor_dir = get_dist_path() / "cursor-core" / "cursor"
        fixed_time = "2026-01-01T00:00:00Z"
        manifest_one = build_bundle_manifest(
            "cursor-core", cursor_dir, generated_at=fixed_time
        )
        manifest_two = build_bundle_manifest(
            "cursor-core", cursor_dir, generated_at=fixed_time
        )
        self.assertEqual(manifest_one, manifest_two)


class BundleContentTests(unittest.TestCase):
    def test_orchestrator_in_bundle(self):
        if verify_indexes(get_dist_path()):
            self.skipTest("dist indexes not available")

        assemble(profile_name="cursor-core", clean=True, verify=False)
        orchestrator = (
            get_dist_path() / "cursor-core" / "cursor" / orchestrator_filename()
        )
        self.assertTrue(orchestrator.is_file())


if __name__ == "__main__":
    unittest.main()
