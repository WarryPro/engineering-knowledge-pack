"""Tests for profile includes composition (EKP-AI24)."""

import shutil
import sys
import tempfile
import unittest
from pathlib import Path

import yaml

VALIDATE_DIR = Path(__file__).resolve().parents[1]
VALIDATE_MODULES = VALIDATE_DIR / "modules"
REPO_ROOT = VALIDATE_DIR.parents[1]
ADAPTERS_COMMON = REPO_ROOT / "scripts" / "adapters" / "common"
ASSEMBLE_DIR = REPO_ROOT / "scripts" / "assemble"

if str(VALIDATE_MODULES) not in sys.path:
    sys.path.insert(0, str(VALIDATE_MODULES))
if str(ADAPTERS_COMMON) not in sys.path:
    sys.path.insert(0, str(ADAPTERS_COMMON))
if str(ASSEMBLE_DIR) not in sys.path:
    sys.path.insert(0, str(ASSEMBLE_DIR))

from profile_resolve import ProfileResolveError, resolve_profile_knowledge
from profile_validate import validate_profiles


def _write_profile(profiles_dir, name, knowledge, includes=None):
    data = {"name": name, "knowledge": knowledge}
    if includes is not None:
        data["includes"] = includes
    path = profiles_dir / "{}.yaml".format(name)
    path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")
    return path


def _touch_knowledge(repo_root, rel_path):
    doc = repo_root / rel_path
    doc.parent.mkdir(parents=True, exist_ok=True)
    doc.write_text("# fixture\n", encoding="utf-8")


class ProfileIncludesResolutionTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.repo_root = Path(self.tmp)
        self.profiles_dir = self.repo_root / "profiles"
        self.profiles_dir.mkdir(parents=True)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_simple_include(self):
        _touch_knowledge(self.repo_root, "knowledge/b.md")
        _touch_knowledge(self.repo_root, "knowledge/a.md")
        _write_profile(self.profiles_dir, "profile-b", ["knowledge/b.md"])
        _write_profile(
            self.profiles_dir, "profile-a", ["knowledge/a.md"], includes=["profile-b"]
        )

        resolved = resolve_profile_knowledge(self.repo_root, "profile-a")
        self.assertEqual(resolved, ["knowledge/b.md", "knowledge/a.md"])

    def test_dedupe_preserves_first_occurrence(self):
        _touch_knowledge(self.repo_root, "knowledge/x.md")
        _touch_knowledge(self.repo_root, "knowledge/y.md")
        _write_profile(self.profiles_dir, "profile-b", ["knowledge/x.md"])
        _write_profile(
            self.profiles_dir,
            "profile-a",
            ["knowledge/x.md", "knowledge/y.md"],
            includes=["profile-b"],
        )

        resolved = resolve_profile_knowledge(self.repo_root, "profile-a")
        self.assertEqual(resolved, ["knowledge/x.md", "knowledge/y.md"])

    def test_nested_includes_depth_first(self):
        for path in ("knowledge/c.md", "knowledge/b-local.md", "knowledge/a-local.md"):
            _touch_knowledge(self.repo_root, path)
        _write_profile(self.profiles_dir, "profile-c", ["knowledge/c.md"])
        _write_profile(
            self.profiles_dir,
            "profile-b",
            ["knowledge/b-local.md"],
            includes=["profile-c"],
        )
        _write_profile(
            self.profiles_dir,
            "profile-a",
            ["knowledge/a-local.md"],
            includes=["profile-b"],
        )

        resolved = resolve_profile_knowledge(self.repo_root, "profile-a")
        self.assertEqual(
            resolved,
            [
                "knowledge/c.md",
                "knowledge/b-local.md",
                "knowledge/a-local.md",
            ],
        )

    def test_circular_include_fails(self):
        _touch_knowledge(self.repo_root, "knowledge/a.md")
        _touch_knowledge(self.repo_root, "knowledge/b.md")
        _write_profile(
            self.profiles_dir, "profile-a", ["knowledge/a.md"], includes=["profile-b"]
        )
        _write_profile(
            self.profiles_dir, "profile-b", ["knowledge/b.md"], includes=["profile-a"]
        )

        with self.assertRaises(ProfileResolveError) as context:
            resolve_profile_knowledge(self.repo_root, "profile-a")
        self.assertIn("circular profile include", str(context.exception))

    def test_unknown_include_fails_validation(self):
        _write_profile(self.profiles_dir, "profile-a", ["knowledge/a.md"], includes=["missing"])

        errors = validate_profiles(self.repo_root, self.profiles_dir)
        self.assertTrue(any("unknown include" in err for err in errors))

    def test_multiple_includes_merge_deterministically(self):
        for path in ("knowledge/b.md", "knowledge/c.md", "knowledge/shared.md", "knowledge/a.md"):
            _touch_knowledge(self.repo_root, path)
        _write_profile(self.profiles_dir, "profile-b", ["knowledge/b.md", "knowledge/shared.md"])
        _write_profile(self.profiles_dir, "profile-c", ["knowledge/c.md", "knowledge/shared.md"])
        _write_profile(
            self.profiles_dir,
            "profile-a",
            ["knowledge/a.md"],
            includes=["profile-b", "profile-c"],
        )

        resolved = resolve_profile_knowledge(self.repo_root, "profile-a")
        self.assertEqual(
            resolved,
            [
                "knowledge/b.md",
                "knowledge/shared.md",
                "knowledge/c.md",
                "knowledge/a.md",
            ],
        )


class ProfileIncludesRegressionTests(unittest.TestCase):
    EXPECTED_RULE_COUNTS = {
        "cursor-core": 65,
        "cursor-php": 74,
        "cursor-symfony": 83,
        "cursor-typescript": 74,
        "cursor-frontend": 83,
        "cursor-devops": 74,
    }

    @classmethod
    def setUpClass(cls):
        from assemble import verify_indexes
        from common.paths import get_dist_path

        if verify_indexes(get_dist_path()):
            raise unittest.SkipTest(
                "dist indexes not available; run validate --generate-index"
            )

    def test_all_profiles_preserve_rule_counts(self):
        import assemble as assemble_module

        for profile_name, expected in self.EXPECTED_RULE_COUNTS.items():
            manifest = assemble_module.assemble(
                profile_name=profile_name, clean=True, verify=True
            )
            self.assertEqual(
                manifest["rules_count"],
                expected,
                msg="{} rule count drift".format(profile_name),
            )

    def test_cursor_core_has_no_includes_and_is_unchanged(self):
        core_path = REPO_ROOT / "profiles" / "cursor-core.yaml"
        text = core_path.read_text(encoding="utf-8")
        self.assertNotIn("includes:", text)
        self.assertIn("name: cursor-core", text)


if __name__ == "__main__":
    unittest.main()
