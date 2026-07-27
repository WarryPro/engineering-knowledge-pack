"""Additional v2.1 validation tests."""

import json
import sys
import tempfile
import unittest
from pathlib import Path

import yaml

SCRIPT_DIR = Path(__file__).resolve().parents[1]
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from modules.graph_rules import load_graph_rules
from modules.graph_validate import (
    compute_dependency_depth,
    validate_dependency_depth,
    validate_dependency_directions,
)
from modules.models import DocumentNode
from modules.principle_validate import (
    format_principle_report,
    validate_foundation_related,
    validate_principle_coverage,
)
from modules.profile_validate import validate_profiles
from modules.readme_validate import validate_readmes

FIXTURES = Path(__file__).resolve().parent / "fixtures"
REPO_ROOT = FIXTURES


def load_fixture(rel_path):
    node, errors = DocumentNode.from_path(REPO_ROOT / rel_path, REPO_ROOT)
    if errors:
        raise AssertionError(errors)
    return node


def make_node(path, role, depends_on, implements=None, related=None):
    # type: (str, str, list, list, list) -> DocumentNode
    return DocumentNode(
        path=path,
        frontmatter={"role": role},
        body="",
        role=role,
        depends_on=depends_on,
        implements=implements or [],
        related=related or [],
        concept_ids=["EKP-CC01"],
    )


class GraphRulesTests(unittest.TestCase):
    def test_invalid_practice_to_practice_dependency(self):
        rules = load_graph_rules()
        foundation = load_fixture("knowledge/engineering/engineering-principles.md")
        practice = load_fixture("knowledge/engineering/valid-practice.md")
        invalid = load_fixture("knowledge/engineering/invalid-practice-dep.md")

        errors = validate_dependency_directions([foundation, practice, invalid], rules)
        self.assertTrue(
            any("invalid-practice-dep.md" in error and "valid-practice.md" in error for error in errors)
        )

    def test_valid_pattern_to_practice_exception(self):
        rules = load_graph_rules()
        # Add fixture exception for tests (production exception is design-patterns -> solid)
        rules["exceptions"].append(
            {
                "source": "knowledge/engineering/valid-pattern-dep.md",
                "allowed_dependency": "knowledge/engineering/valid-practice.md",
            }
        )
        foundation = load_fixture("knowledge/engineering/engineering-principles.md")
        practice = load_fixture("knowledge/engineering/valid-practice.md")
        pattern = load_fixture("knowledge/engineering/valid-pattern-dep.md")

        errors = validate_dependency_directions(
            [foundation, practice, pattern], rules
        )
        self.assertEqual(errors, [])

    def test_depth_warning(self):
        rules = {"depth": {"warn_at": 3, "error_at": 4}}
        by_path = {
            "knowledge/engineering/engineering-principles.md": make_node(
                "knowledge/engineering/engineering-principles.md",
                "foundation",
                [],
            ),
            "knowledge/engineering/a.md": make_node(
                "knowledge/engineering/a.md", "practice", ["knowledge/engineering/engineering-principles.md"]
            ),
            "knowledge/engineering/b.md": make_node(
                "knowledge/engineering/b.md", "practice", ["knowledge/engineering/a.md"]
            ),
            "knowledge/engineering/c.md": make_node(
                "knowledge/engineering/c.md", "practice", ["knowledge/engineering/b.md"]
            ),
        }
        nodes = list(by_path.values())

        depth = compute_dependency_depth(by_path["knowledge/engineering/c.md"], by_path)
        self.assertEqual(depth, 3)

        errors, warnings = validate_dependency_depth(nodes, rules)
        self.assertEqual(errors, [])
        self.assertTrue(any("dependency depth is 3" in warning for warning in warnings))

    def test_depth_error(self):
        rules = {"depth": {"warn_at": 3, "error_at": 4}}
        by_path = {
            "knowledge/engineering/engineering-principles.md": make_node(
                "knowledge/engineering/engineering-principles.md",
                "foundation",
                [],
            ),
            "knowledge/engineering/a.md": make_node(
                "knowledge/engineering/a.md", "practice", ["knowledge/engineering/engineering-principles.md"]
            ),
            "knowledge/engineering/b.md": make_node(
                "knowledge/engineering/b.md", "practice", ["knowledge/engineering/a.md"]
            ),
            "knowledge/engineering/c.md": make_node(
                "knowledge/engineering/c.md", "practice", ["knowledge/engineering/b.md"]
            ),
            "knowledge/engineering/d.md": make_node(
                "knowledge/engineering/d.md", "practice", ["knowledge/engineering/c.md"]
            ),
        }
        nodes = list(by_path.values())

        errors, warnings = validate_dependency_depth(nodes, rules)
        self.assertTrue(any("dependency depth is 4" in error for error in errors))


class PrincipleTests(unittest.TestCase):
    def test_missing_owner_warning(self):
        foundation = load_fixture("knowledge/engineering/engineering-principles.md")
        practice = load_fixture("knowledge/engineering/valid-practice.md")
        practice.implements = ["EKP-P01"]

        warnings = validate_principle_coverage([foundation, practice])
        self.assertTrue(any("EKP-P09" in warning for warning in warnings))

    def test_exception_handling(self):
        foundation = load_fixture("knowledge/engineering/engineering-principles.md")
        warnings = validate_principle_coverage([foundation])
        self.assertFalse(any("EKP-P01" in warning for warning in warnings))
        self.assertFalse(any("EKP-P08" in warning for warning in warnings))

    def test_coverage_report(self):
        foundation = load_fixture("knowledge/engineering/engineering-principles.md")
        report = format_principle_report([foundation])
        self.assertIn("EKP Principle Coverage", report)
        self.assertIn("P01:", report)
        self.assertIn("exception: foundation-only principle", report)

    def test_foundation_related_warning(self):
        foundation = load_fixture("knowledge/engineering/engineering-principles.md")
        practice = load_fixture("knowledge/engineering/valid-practice.md")
        foundation.related = []

        warnings = validate_foundation_related([foundation, practice])
        self.assertTrue(any("missing from" in warning for warning in warnings))


class ReadmeTests(unittest.TestCase):
    def test_broken_published_link(self):
        errors, warnings = validate_readmes(
            REPO_ROOT,
            ["knowledge/engineering/valid-practice.md"],
            navigation_readmes=["knowledge/engineering/README-broken.md"],
        )
        self.assertTrue(
            any("missing target: knowledge/engineering/missing-doc.md" in error for error in errors)
        )

    def test_missing_published_entry_warning(self):
        errors, warnings = validate_readmes(
            REPO_ROOT,
            [
                "knowledge/engineering/valid-practice.md",
                "knowledge/engineering/not-indexed.md",
            ],
            navigation_readmes=["knowledge/engineering/README.md"],
        )
        self.assertEqual(errors, [])
        self.assertTrue(
            any("not indexed in domain README" in warning for warning in warnings)
        )


class ProfileTests(unittest.TestCase):
    def test_invalid_yaml(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            profiles = root / "profiles"
            profiles.mkdir()
            profile = profiles / "bad.yaml"
            profile.write_text("name: [\n", encoding="utf-8")

            errors = validate_profiles(root, profiles)
            self.assertTrue(any("invalid YAML" in error for error in errors))

    def test_invalid_schema(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            profiles = root / "profiles"
            profiles.mkdir()
            profile = profiles / "bad.yaml"
            profile.write_text(
                yaml.dump({"name": "INVALID NAME", "description": "x", "knowledge": []}),
                encoding="utf-8",
            )

            errors = validate_profiles(root, profiles)
            self.assertTrue(any("does not match" in error or "is too short" in error for error in errors))

    def test_missing_knowledge_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            profiles = root / "profiles"
            profiles.mkdir()
            profile = profiles / "bad.yaml"
            profile.write_text(
                yaml.dump(
                    {
                        "name": "test-profile",
                        "description": "test",
                        "knowledge": ["knowledge/engineering/missing.md"],
                    }
                ),
                encoding="utf-8",
            )

            errors = validate_profiles(root, profiles)
            self.assertTrue(any("missing document" in error for error in errors))


if __name__ == "__main__":
    unittest.main()
