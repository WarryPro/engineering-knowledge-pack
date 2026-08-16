"""Tests for multi-adapter packaging (EKP-AI30A)."""

import json
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
    ASSEMBLE_MANIFEST_NAME,
    AssembleError,
    assemble,
    build_assemble_manifest,
    verify_indexes,
)
from common.paths import get_dist_path
from common.profile_loader import load_profile_by_name
from common.registry import AdapterNotImplementedError, build_default_registry


def _dummy_adapter(name):
    def generate(profile_name, output_dir, profile, repo_root):
        output_dir.mkdir(parents=True, exist_ok=True)
        marker = output_dir / "placeholder.txt"
        marker.write_text("{}:{}\n".format(name, profile_name), encoding="utf-8")

    def build_manifest(profile_name, adapter_dir):
        files = sorted(path.name for path in adapter_dir.iterdir() if path.is_file())
        return {
            "profile": profile_name,
            "adapter": name,
            "files": files,
        }

    def verify(bundle_dir):
        adapter_dir = bundle_dir / name
        if not (adapter_dir / "placeholder.txt").is_file():
            raise AssembleError("missing {} placeholder".format(name))

    return generate, verify, build_manifest


def _registry_with_dummies(*names):
    registry = build_default_registry()
    for name in names:
        generate_fn, verify_fn, manifest_fn = _dummy_adapter(name)
        registry.register(
            name,
            generate_fn=generate_fn,
            verify_fn=verify_fn,
            build_manifest_fn=manifest_fn,
        )
    return registry


class EkpCoreProfileTests(unittest.TestCase):
    def test_ekp_core_includes_cursor_core_knowledge(self):
        core = load_profile_by_name("cursor-core", repo_root=REPO_ROOT)
        pilot = load_profile_by_name("ekp-core", repo_root=REPO_ROOT)
        self.assertEqual(pilot["knowledge"], core["knowledge"])
        self.assertEqual(pilot["outputs"], ["cursor", "copilot", "antigravity"])
        self.assertEqual(pilot["adapter_priorities"], ["high"])

    def test_assemble_ekp_core_succeeds_for_three_adapters(self):
        if verify_indexes(get_dist_path()):
            self.skipTest("dist indexes not available")

        assemble(profile_name="ekp-core", clean=True, verify=True)
        bundle_dir = get_dist_path() / "ekp-core"
        self.assertTrue(bundle_dir.is_dir())
        self.assertTrue((bundle_dir / "cursor" / "00-ekp-orchestrator.mdc").is_file())
        self.assertTrue(
            (bundle_dir / "copilot" / ".github" / "copilot-instructions.md").is_file()
        )
        self.assertTrue(
            (bundle_dir / "antigravity" / ".agents" / "rules" / "00-orchestrator.md").is_file()
        )


class AssembleManifestTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if verify_indexes(get_dist_path()):
            raise unittest.SkipTest(
                "dist indexes not available; run validate --generate-index"
            )

    def test_cursor_core_writes_assemble_manifest(self):
        assemble(profile_name="cursor-core", clean=True, verify=True)
        bundle_dir = get_dist_path() / "cursor-core"
        assemble_path = bundle_dir / ASSEMBLE_MANIFEST_NAME
        self.assertTrue(assemble_path.is_file())

        payload = json.loads(assemble_path.read_text(encoding="utf-8"))
        self.assertNotIn("generated_at", payload)
        self.assertEqual(payload["profile"], "cursor-core")
        self.assertEqual(payload["adapters"], ["cursor"])
        self.assertEqual(
            payload["outputs"],
            [
                {
                    "adapter": "cursor",
                    "directory": "cursor",
                    "manifest": "bundle-manifest.json",
                    "status": "assembled",
                }
            ],
        )

        cursor_manifest = json.loads(
            (bundle_dir / "bundle-manifest.json").read_text(encoding="utf-8")
        )
        self.assertEqual(cursor_manifest["adapter"], "cursor")
        self.assertFalse((bundle_dir / "cursor" / "adapter-manifest.json").is_file())

    def test_assemble_manifest_is_deterministic(self):
        first = build_assemble_manifest("demo", ["cursor", "copilot"])
        second = build_assemble_manifest("demo", ["cursor", "copilot"])
        self.assertEqual(first, second)
        self.assertEqual(first["adapters"], ["cursor", "copilot"])


class MultiAdapterIsolationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if verify_indexes(get_dist_path()):
            raise unittest.SkipTest(
                "dist indexes not available; run validate --generate-index"
            )

    def test_cursor_manifest_not_overwritten_by_dummy_adapters(self):
        registry = _registry_with_dummies("copilot", "antigravity")
        returned = assemble(
            profile_name="ekp-core",
            clean=True,
            verify=True,
            registry=registry,
        )

        bundle_dir = get_dist_path() / "ekp-core"
        cursor_manifest = json.loads(
            (bundle_dir / "bundle-manifest.json").read_text(encoding="utf-8")
        )
        self.assertEqual(returned["adapter"], "cursor")
        self.assertEqual(cursor_manifest["adapter"], "cursor")
        self.assertEqual(cursor_manifest["profile"], "ekp-core")
        self.assertGreater(cursor_manifest["rules_count"], 0)

        copilot_manifest = json.loads(
            (bundle_dir / "copilot" / "adapter-manifest.json").read_text(
                encoding="utf-8"
            )
        )
        antigravity_manifest = json.loads(
            (bundle_dir / "antigravity" / "adapter-manifest.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual(copilot_manifest["adapter"], "copilot")
        self.assertEqual(antigravity_manifest["adapter"], "antigravity")

        assemble_payload = json.loads(
            (bundle_dir / ASSEMBLE_MANIFEST_NAME).read_text(encoding="utf-8")
        )
        self.assertEqual(
            assemble_payload["adapters"],
            ["cursor", "copilot", "antigravity"],
        )
        self.assertEqual(
            [entry["manifest"] for entry in assemble_payload["outputs"]],
            [
                "bundle-manifest.json",
                "copilot/adapter-manifest.json",
                "antigravity/adapter-manifest.json",
            ],
        )

        self.assertTrue((bundle_dir / "copilot" / "placeholder.txt").is_file())
        self.assertTrue((bundle_dir / "antigravity" / "placeholder.txt").is_file())
        self.assertTrue((bundle_dir / "cursor" / "00-ekp-orchestrator.mdc").is_file())

    def test_assemble_manifest_stable_across_runs(self):
        registry = _registry_with_dummies("copilot", "antigravity")
        assemble(
            profile_name="ekp-core",
            clean=True,
            verify=False,
            registry=registry,
        )
        first = json.loads(
            (get_dist_path() / "ekp-core" / ASSEMBLE_MANIFEST_NAME).read_text(
                encoding="utf-8"
            )
        )
        assemble(
            profile_name="ekp-core",
            clean=False,
            verify=False,
            registry=registry,
        )
        second = json.loads(
            (get_dist_path() / "ekp-core" / ASSEMBLE_MANIFEST_NAME).read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual(first, second)


class UnimplementedAdapterAssembleTests(unittest.TestCase):
    def test_default_registry_still_rejects_claude(self):
        registry = build_default_registry()
        self.assertFalse(registry.is_implemented("claude"))
        with self.assertRaises(AdapterNotImplementedError):
            registry.get("claude")
