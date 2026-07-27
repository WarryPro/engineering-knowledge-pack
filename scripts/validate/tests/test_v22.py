"""Validator v2.2 tests: registry, body sync, adapter, related, ADR, reports."""

import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parents[1]
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from modules.adapter_validate import validate_adapter_metadata
from modules.adr_validate import validate_adr_index
from modules.concept_body_validate import validate_concept_body
from modules.models import DocumentNode
from modules.namespace_validate import validate_namespaces
from modules.related_validate import validate_related_paths
from modules.reports import format_adapters_report, format_concepts_report

FIXTURES = Path(__file__).resolve().parent / "fixtures"
REPO_ROOT = FIXTURES

TEST_REGISTRY = {
    "EKP-P": {
        "owner": "knowledge/engineering/engineering-principles.md",
        "format": "^EKP-P(0[1-9]|10)$",
    },
    "EKP-CC": {
        "owner": "knowledge/engineering/valid-practice.md",
        "format": "^EKP-CC[0-9]{2}$",
    },
    "EKP-DP": {
        "owner": "knowledge/engineering/valid-pattern-dep.md",
        "format": "^EKP-DP[0-9]{2}$",
    },
}


def load_fixture(rel_path):
    node, errors = DocumentNode.from_path(REPO_ROOT / rel_path, REPO_ROOT)
    if errors:
        raise AssertionError(errors)
    return node


def make_node(path, role, concept_ids, body="", adapter_priority=None):
    frontmatter = {"role": role, "concept_ids": concept_ids}
    if adapter_priority is not None:
        frontmatter["adapter_priority"] = adapter_priority
    return DocumentNode(
        path=path,
        frontmatter=frontmatter,
        body=body,
        role=role,
        concept_ids=concept_ids,
    )


class NamespaceTests(unittest.TestCase):
    def test_unknown_namespace(self):
        node = make_node(
            "knowledge/engineering/valid-practice.md",
            "practice",
            ["EKP-XYZ01"],
        )
        errors, warnings = validate_namespaces([node], TEST_REGISTRY)
        self.assertTrue(any("unknown namespace" in error for error in errors))

    def test_wrong_owner(self):
        node = make_node(
            "knowledge/engineering/invalid-practice-dep.md",
            "practice",
            ["EKP-CC01"],
        )
        errors, warnings = validate_namespaces([node], TEST_REGISTRY)
        self.assertTrue(any("may not own" in error for error in errors))

    def test_duplicate_concept_id_in_document(self):
        node = make_node(
            "knowledge/engineering/valid-practice.md",
            "practice",
            ["EKP-CC01", "EKP-CC01"],
        )
        errors, warnings = validate_namespaces([node], TEST_REGISTRY)
        self.assertTrue(any("duplicate concept_id" in error for error in errors))

    def test_numbering_gap_warning(self):
        node = make_node(
            "knowledge/engineering/valid-practice.md",
            "practice",
            ["EKP-CC01", "EKP-CC03"],
        )
        errors, warnings = validate_namespaces([node], TEST_REGISTRY)
        self.assertTrue(any("numbering gap" in warning for warning in warnings))


class BodySyncTests(unittest.TestCase):
    def test_missing_heading_in_body(self):
        node = make_node(
            "knowledge/testing/testing.md",
            "practice",
            ["EKP-TS01"],
            body="# Test\n\nNo concept headings here.\n",
        )
        warnings = validate_concept_body([node])
        self.assertTrue(any("not found in document body" in warning for warning in warnings))

    def test_missing_metadata_for_heading(self):
        node = make_node(
            "knowledge/testing/testing.md",
            "practice",
            ["EKP-TS01"],
            body="### EKP-TS01 Example\n\n### EKP-TS02 Missing metadata\n",
        )
        warnings = validate_concept_body([node])
        self.assertTrue(any("EKP-TS02" in warning for warning in warnings))


class AdapterTests(unittest.TestCase):
    def test_missing_priority_warning(self):
        node = make_node("knowledge/engineering/clean-code.md", "practice", ["EKP-CC01"])
        errors, warnings = validate_adapter_metadata([node])
        self.assertEqual(errors, [])
        self.assertTrue(any("should define adapter_priority" in warning for warning in warnings))

    def test_foundation_priority_error(self):
        node = make_node(
            "knowledge/engineering/engineering-principles.md",
            "foundation",
            ["EKP-P01"],
            adapter_priority="high",
        )
        errors, warnings = validate_adapter_metadata([node])
        self.assertTrue(any("cannot define adapter_priority" in error for error in errors))


class RelatedTests(unittest.TestCase):
    def test_missing_related_target(self):
        node = DocumentNode(
            path="knowledge/engineering/valid-practice.md",
            frontmatter={},
            body="",
            related=["knowledge/engineering/missing-related.md"],
        )
        errors = validate_related_paths([node], REPO_ROOT)
        self.assertTrue(any("RELATED target missing" in error for error in errors))


class AdrTests(unittest.TestCase):
    def test_missing_adr_index_entry(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            decisions = root / "knowledge" / "architecture" / "decisions"
            decisions.mkdir(parents=True)
            (decisions / "adr-0004-example.md").write_text("# ADR", encoding="utf-8")
            (decisions / "adr-0005-example.md").write_text("# ADR", encoding="utf-8")
            (decisions / "README.md").write_text(
                "| ADR |\n|-----|\n| [adr-0004](adr-0004-example.md) |\n",
                encoding="utf-8",
            )

            errors = validate_adr_index(root)
            self.assertTrue(any("adr-0005-example.md" in error for error in errors))


class ReportTests(unittest.TestCase):
    def test_concepts_report(self):
        foundation = load_fixture("knowledge/engineering/engineering-principles.md")
        report = format_concepts_report([foundation], TEST_REGISTRY)
        self.assertIn("Concept Registry", report)
        self.assertIn("EKP-P", report)
        self.assertIn("Total concepts:", report)

    def test_adapters_report(self):
        high = make_node(
            "knowledge/testing/testing.md",
            "practice",
            ["EKP-TS01"],
            adapter_priority="high",
        )
        missing = make_node(
            "knowledge/engineering/clean-code.md",
            "practice",
            ["EKP-CC01"],
        )
        report = format_adapters_report([high, missing])
        self.assertIn("Adapter readiness:", report)
        self.assertIn("testing.md", report)
        self.assertIn("clean-code.md", report)


if __name__ == "__main__":
    unittest.main()
