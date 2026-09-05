"""Tests for reusable resolved-profile assembly core (AW-C)."""

import json
import sys
import tempfile
import unittest
from pathlib import Path

ASSEMBLE_DIR = Path(__file__).resolve().parents[1]
REPO_ROOT = ASSEMBLE_DIR.parents[1]
ADAPTERS_DIR = REPO_ROOT / "scripts" / "adapters"
SRC_DIR = REPO_ROOT / "src"

if str(ASSEMBLE_DIR) not in sys.path:
    sys.path.insert(0, str(ASSEMBLE_DIR))
if str(ADAPTERS_DIR) not in sys.path:
    sys.path.insert(0, str(ADAPTERS_DIR))
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from assemble import AssembleError, assemble, assemble_resolved_profile, verify_indexes
from common.profile_loader import load_profile_by_name
from common.paths import get_dist_path

from ekp.composition import (
    PROJECT_COMPOSITION_PROFILE,
    ComponentRegistry,
    build_ephemeral_composition_profile,
    resolve_composition,
)
from ekp.paths import get_ekp_root


class AssembleResolvedProfileCoreTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if verify_indexes(get_dist_path()):
            raise unittest.SkipTest(
                "dist indexes not available; run validate --generate-index"
            )

    def test_named_assemble_uses_resolved_core_unchanged(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp)
            named = assemble(
                profile_name="cursor-core",
                clean=True,
                verify=True,
                dist_dir=get_dist_path(),
                bundle_root=output,
            )
            profile = load_profile_by_name("cursor-core")
            resolved = assemble_resolved_profile(
                profile_name="cursor-core",
                profile=profile,
                clean=True,
                verify=True,
                dist_dir=get_dist_path(),
                bundle_root=output,
            )
            self.assertEqual(named["rules_count"], resolved["rules_count"])
            self.assertEqual(named["profile"], "cursor-core")
            self.assertEqual(resolved["profile"], "cursor-core")

    def test_in_memory_profile_contract_assembles(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp)
            registry = ComponentRegistry.load(get_ekp_root())
            composition = resolve_composition(["core"], registry)
            ephemeral = build_ephemeral_composition_profile(composition, ["cursor"])
            manifest = assemble_resolved_profile(
                profile_name=PROJECT_COMPOSITION_PROFILE,
                profile=ephemeral,
                clean=True,
                verify=True,
                dist_dir=get_dist_path(),
                bundle_root=output,
            )
            self.assertEqual(manifest["profile"], PROJECT_COMPOSITION_PROFILE)
            self.assertEqual(manifest["rules_count"], 65)
            assemble_manifest = json.loads(
                (
                    output / PROJECT_COMPOSITION_PROFILE / "assemble-manifest.json"
                ).read_text(encoding="utf-8")
            )
            self.assertEqual(assemble_manifest["profile"], PROJECT_COMPOSITION_PROFILE)

    def test_empty_outputs_rejected(self):
        profile = load_profile_by_name("cursor-core")
        profile = dict(profile)
        profile["outputs"] = []
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(AssembleError) as ctx:
                assemble_resolved_profile(
                    profile_name="cursor-core",
                    profile=profile,
                    clean=True,
                    verify=False,
                    dist_dir=get_dist_path(),
                    bundle_root=Path(tmp),
                )
            self.assertIn("no adapter outputs", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
