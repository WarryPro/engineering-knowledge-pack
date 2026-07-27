"""Tests for knowledge graph validation."""

import sys
import unittest
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parents[1]
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from modules.concept_validate import validate_concepts
from modules.graph_validate import (
    detect_cycles,
    validate_depends_on_paths,
    validate_foundation_singleton,
    validate_graph,
    validate_reachability,
)
from modules.models import DocumentNode, FOUNDATION_PATH

FIXTURES = Path(__file__).resolve().parent / "fixtures"
REPO_ROOT = FIXTURES


def load_fixture(rel_path):
    node, errors = DocumentNode.from_path(REPO_ROOT / rel_path, REPO_ROOT)
    if errors:
        raise AssertionError(errors)
    return node


class GraphTests(unittest.TestCase):
    def test_valid_dependency_tree(self):
        foundation = load_fixture("knowledge/engineering/engineering-principles.md")
        practice = load_fixture("knowledge/engineering/valid-practice.md")

        errors, warnings = validate_graph([foundation, practice], REPO_ROOT)
        self.assertEqual(errors, [])
        self.assertEqual(warnings, [])

    def test_cycle_detection(self):
        node_a = load_fixture("knowledge/engineering/cycle-a.md")
        node_b = load_fixture("knowledge/engineering/cycle-b.md")

        errors = detect_cycles([node_a, node_b])
        self.assertTrue(any("dependency cycle detected" in error for error in errors))

    def test_missing_dependency(self):
        node = load_fixture("knowledge/security/unreachable.md")
        errors = validate_depends_on_paths([node], REPO_ROOT)
        self.assertTrue(
            any(
                "depends_on 'knowledge/security/missing-parent.md' does not exist" in error
                for error in errors
            )
        )

    def test_unreachable_document(self):
        foundation = load_fixture("knowledge/engineering/engineering-principles.md")
        orphan = load_fixture("knowledge/security/unreachable.md")
        orphan.depends_on = ["knowledge/engineering/engineering-principles.md"]

        errors = validate_reachability([foundation, orphan])
        self.assertEqual(errors, [])

        orphan.depends_on = ["knowledge/security/missing-parent.md"]
        errors = validate_reachability([foundation, orphan])
        self.assertTrue(any("not reachable" in error for error in errors))

    def test_multiple_foundations(self):
        foundation = load_fixture("knowledge/engineering/engineering-principles.md")
        second = load_fixture("knowledge/engineering/valid-practice.md")
        second.role = "foundation"
        second.path = "knowledge/engineering/second-foundation.md"

        errors = validate_foundation_singleton([foundation, second])
        self.assertTrue(any("multiple foundation documents" in error for error in errors))

    def test_duplicate_concept_ids(self):
        foundation = load_fixture("knowledge/engineering/engineering-principles.md")
        practice = load_fixture("knowledge/engineering/valid-practice.md")
        duplicate = load_fixture("knowledge/engineering/valid-practice.md")
        duplicate.path = "knowledge/engineering/duplicate.md"
        duplicate.concept_ids = ["EKP-CC01"]

        errors = validate_concepts([foundation, practice, duplicate])
        self.assertTrue(any("EKP-CC01 defined in multiple documents" in error for error in errors))

    def test_mixed_namespaces(self):
        node = load_fixture("knowledge/engineering/mixed-namespace.md")
        errors = validate_concepts([node])
        self.assertTrue(any("mixed concept_id namespaces" in error for error in errors))

    def test_foundation_path_constant(self):
        self.assertEqual(
            FOUNDATION_PATH,
            "knowledge/engineering/engineering-principles.md",
        )


if __name__ == "__main__":
    unittest.main()
