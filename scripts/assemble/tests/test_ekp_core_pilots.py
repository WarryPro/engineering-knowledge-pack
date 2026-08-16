"""Integration tests for ekp-core Copilot + Antigravity pilots."""

import json
import sys
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
    ASSEMBLE_MANIFEST_NAME,
    AssembleError,
    assemble,
    verify_indexes,
)
from common.paths import get_dist_path
from common.registry import AdapterNotImplementedError, AdapterRegistry, build_default_registry
from cursor.generate import generate as cursor_generate
from cursor.manifest import build_bundle_manifest as cursor_build_manifest
from cursor.verify import verify_cursor_bundle


class EkpCorePilotAssembleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if verify_indexes(get_dist_path()):
            raise unittest.SkipTest(
                "dist indexes not available; run validate --generate-index"
            )
        assemble(profile_name="ekp-core", clean=True, verify=True)
        cls.bundle_dir = get_dist_path() / "ekp-core"

    def test_three_adapters_assembled(self):
        payload = json.loads(
            (self.bundle_dir / ASSEMBLE_MANIFEST_NAME).read_text(encoding="utf-8")
        )
        self.assertEqual(
            payload["adapters"], ["cursor", "copilot", "antigravity"]
        )
        self.assertEqual(
            [entry["manifest"] for entry in payload["outputs"]],
            [
                "bundle-manifest.json",
                "copilot/adapter-manifest.json",
                "antigravity/adapter-manifest.json",
            ],
        )

    def test_cursor_root_manifest_intact(self):
        cursor_manifest = json.loads(
            (self.bundle_dir / "bundle-manifest.json").read_text(encoding="utf-8")
        )
        self.assertEqual(cursor_manifest["adapter"], "cursor")
        self.assertEqual(cursor_manifest["profile"], "ekp-core")
        self.assertGreater(cursor_manifest["rules_count"], 0)
        self.assertFalse(
            (self.bundle_dir / "cursor" / "adapter-manifest.json").is_file()
        )

    def test_adapter_manifests_isolated(self):
        copilot = json.loads(
            (self.bundle_dir / "copilot" / "adapter-manifest.json").read_text(
                encoding="utf-8"
            )
        )
        antigravity = json.loads(
            (self.bundle_dir / "antigravity" / "adapter-manifest.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual(copilot["adapter"], "copilot")
        self.assertEqual(antigravity["adapter"], "antigravity")
        self.assertNotEqual(copilot, antigravity)

    def test_claude_still_fails_explicitly(self):
        registry = build_default_registry()
        with self.assertRaises(AdapterNotImplementedError) as context:
            registry.get("claude")
        self.assertIn("not implemented", str(context.exception).lower())

    def test_unknown_adapter_still_fails_explicitly(self):
        registry = build_default_registry()
        with self.assertRaises(AdapterNotImplementedError):
            registry.get("not-a-real-adapter")

    def test_unimplemented_output_fails_before_generation(self):
        cursor_only = AdapterRegistry()
        cursor_only.register(
            "cursor",
            generate_fn=cursor_generate,
            verify_fn=verify_cursor_bundle,
            build_manifest_fn=cursor_build_manifest,
        )
        with self.assertRaises(AssembleError) as context:
            assemble(
                profile_name="ekp-core",
                clean=False,
                verify=False,
                registry=cursor_only,
            )
        message = str(context.exception).lower()
        self.assertIn("not implemented", message)
        self.assertTrue("copilot" in message or "antigravity" in message)


if __name__ == "__main__":
    unittest.main()
