"""Tests for adapter dispatch architecture (EKP-AI28)."""

import hashlib
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

import yaml

ADAPTERS_DIR = Path(__file__).resolve().parents[1]
REPO_ROOT = ADAPTERS_DIR.parents[1]
ASSEMBLE_DIR = REPO_ROOT / "scripts" / "assemble"

if str(ADAPTERS_DIR) not in sys.path:
    sys.path.insert(0, str(ADAPTERS_DIR))
if str(ASSEMBLE_DIR) not in sys.path:
    sys.path.insert(0, str(ASSEMBLE_DIR))

from common.profile_loader import load_profile_by_name, resolve_profile_outputs
from common.registry import AdapterNotImplementedError, build_default_registry
from common.selection import select_manifest_rules
from cursor.generate import generate


class ProfileOutputsTests(unittest.TestCase):
    def test_outputs_canonical_over_target(self):
        data = {
            "outputs": ["cursor"],
            "adapter": {"target": ["copilot"]},
        }
        self.assertEqual(resolve_profile_outputs(data), ["cursor"])

    def test_target_fallback_when_outputs_missing(self):
        data = {"adapter": {"target": ["cursor"]}}
        self.assertEqual(resolve_profile_outputs(data), ["cursor"])

    def test_default_cursor_when_unspecified(self):
        self.assertEqual(resolve_profile_outputs({}), ["cursor"])

    def test_operational_profiles_declare_cursor_outputs(self):
        profiles_dir = REPO_ROOT / "profiles"
        for profile_path in sorted(profiles_dir.glob("cursor-*.yaml")):
            data = yaml.safe_load(profile_path.read_text(encoding="utf-8"))
            outputs = resolve_profile_outputs(data)
            self.assertEqual(outputs, ["cursor"], msg=profile_path.name)


class AdapterRegistryTests(unittest.TestCase):
    def test_cursor_is_implemented(self):
        registry = build_default_registry()
        self.assertTrue(registry.is_implemented("cursor"))
        adapter = registry.get("cursor")
        self.assertEqual(adapter["name"], "cursor")

    def test_copilot_antigravity_and_claude_are_implemented(self):
        registry = build_default_registry()
        for name in ("copilot", "antigravity", "claude"):
            self.assertTrue(registry.is_implemented(name), msg=name)
            self.assertEqual(registry.get(name)["name"], name)

    def test_unknown_adapter_rejected(self):
        registry = build_default_registry()
        with self.assertRaises(AdapterNotImplementedError):
            registry.get("unknown-tool")


class SelectionTests(unittest.TestCase):
    def test_select_manifest_rules_filters_priority_and_source(self):
        manifest = {
            "rules": [
                {"concept": "EKP-AI01", "source": "knowledge/a.md", "priority": "high"},
                {"concept": "EKP-AI02", "source": "knowledge/b.md", "priority": "high"},
                {"concept": "EKP-AI03", "source": "knowledge/a.md", "priority": "low"},
            ]
        }
        selected = select_manifest_rules(
            manifest, ["knowledge/a.md"], ["high"]
        )
        self.assertEqual(len(selected), 1)
        self.assertEqual(selected[0]["concept"], "EKP-AI01")


class CursorRegressionTests(unittest.TestCase):
    EXPECTED_RULE_COUNTS = {
        "cursor-core": 65,
        "cursor-php": 74,
        "cursor-symfony": 83,
        "cursor-typescript": 74,
        "cursor-frontend": 83,
        "cursor-devops": 74,
    }

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_cursor_core_byte_identical_across_runs(self):
        first_dir = Path(self.temp_dir) / "first"
        second_dir = Path(self.temp_dir) / "second"

        generate(profile_name="cursor-core", output_dir=first_dir)
        generate(profile_name="cursor-core", output_dir=second_dir)

        first_files = sorted(path.name for path in first_dir.glob("*.mdc"))
        second_files = sorted(path.name for path in second_dir.glob("*.mdc"))
        self.assertEqual(first_files, second_files)

        for name in first_files:
            first_hash = hashlib.sha256((first_dir / name).read_bytes()).hexdigest()
            second_hash = hashlib.sha256((second_dir / name).read_bytes()).hexdigest()
            self.assertEqual(first_hash, second_hash)

    def test_all_profiles_rule_counts_via_generate(self):
        from assemble import verify_indexes
        from common.paths import get_dist_path

        if verify_indexes(get_dist_path()):
            self.skipTest("dist indexes not available")

        for profile_name, expected in self.EXPECTED_RULE_COUNTS.items():
            output_dir = Path(self.temp_dir) / profile_name
            written = generate(profile_name=profile_name, output_dir=output_dir)
            self.assertEqual(
                len(written),
                expected,
                msg="{} rule count drift".format(profile_name),
            )


class AssembleDispatchTests(unittest.TestCase):
    def test_load_profile_includes_outputs(self):
        profile = load_profile_by_name("cursor-core", repo_root=REPO_ROOT)
        self.assertIn("outputs", profile)
        self.assertEqual(profile["outputs"], ["cursor"])

    def test_ekp_core_outputs_include_implemented_pilots(self):
        profile = load_profile_by_name("ekp-core", repo_root=REPO_ROOT)
        self.assertEqual(
            profile["outputs"], ["cursor", "copilot", "antigravity", "claude"]
        )
        registry = build_default_registry()
        self.assertTrue(registry.is_implemented("cursor"))
        self.assertTrue(registry.is_implemented("copilot"))
        self.assertTrue(registry.is_implemented("antigravity"))
        self.assertTrue(registry.is_implemented("claude"))


if __name__ == "__main__":
    unittest.main()
