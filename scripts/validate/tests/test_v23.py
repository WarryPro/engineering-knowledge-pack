"""Validator v2.3 tests: incremental validation, tiers, indexes, strict adapters."""

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

SCRIPT_DIR = Path(__file__).resolve().parents[1]
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import validate
from modules.adapter_validate import validate_adapter_metadata
from modules.git_changes import (
    changed_knowledge_guides,
    get_all_changed_paths,
    requires_full_graph_validation,
)
from modules.index_generate import (
    generate_adapter_manifest,
    generate_concept_index,
    generate_knowledge_graph,
    write_indexes,
)
from modules.models import DocumentNode
from modules.scale_report import format_scale_report

FIXTURES = Path(__file__).resolve().parent / "fixtures"
REPO_ROOT = FIXTURES
PROFILES_DIR = REPO_ROOT / "profiles"

FOUNDATION = "knowledge/engineering/engineering-principles.md"


def make_node(path, role="practice", concept_ids=None, depends_on=None, **extra):
    frontmatter = {
        "title": "Test",
        "domain": "engineering",
        "tags": ["test"],
        "severity": "recommended",
        "applies_to": ["backend"],
        "role": role,
        "concept_ids": concept_ids or ["EKP-CC01"],
        "depends_on": depends_on or [FOUNDATION],
        "implements": ["EKP-P01"],
    }
    frontmatter.update(extra)
    return DocumentNode(
        path=path,
        frontmatter=frontmatter,
        body="### EKP-CC01 Example\n",
        title="Test",
        domain="engineering",
        role=role,
        depends_on=depends_on or [FOUNDATION],
        implements=["EKP-P01"],
        concept_ids=concept_ids or ["EKP-CC01"],
    )


class GitChangesTests(unittest.TestCase):
    def test_modified_file_detection(self):
        change_set = {
            "added": [],
            "modified": ["knowledge/testing/testing.md"],
            "deleted": [],
        }
        guides = changed_knowledge_guides(change_set)
        self.assertIn("knowledge/testing/testing.md", guides)
        self.assertNotIn("knowledge/testing/README.md", guides)

    def test_graph_invalidation_on_schema_change(self):
        change_set = {
            "added": [],
            "modified": ["schema/graph-rules.yaml"],
            "deleted": [],
        }
        self.assertTrue(requires_full_graph_validation(change_set))

    def test_no_graph_invalidation_for_knowledge_doc_only(self):
        change_set = {
            "added": ["knowledge/engineering/new-doc.md"],
            "modified": [],
            "deleted": [],
        }
        self.assertFalse(requires_full_graph_validation(change_set))

    def test_no_graph_invalidation_for_profile_only(self):
        change_set = {
            "added": [],
            "modified": ["profiles/backend.yaml"],
            "deleted": [],
        }
        self.assertFalse(requires_full_graph_validation(change_set))
        self.assertEqual(changed_knowledge_guides(change_set), set())

    def test_deleted_guide_detected(self):
        change_set = {
            "added": [],
            "modified": [],
            "deleted": ["knowledge/testing/testing.md"],
        }
        guides = changed_knowledge_guides(change_set)
        self.assertIn("knowledge/testing/testing.md", guides)

    def test_get_all_changed_paths(self):
        change_set = {
            "added": ["a.md"],
            "modified": ["b.md"],
            "deleted": ["c.md"],
        }
        paths = get_all_changed_paths(change_set)
        self.assertEqual(paths, {"a.md", "b.md", "c.md"})


class ChangedOnlyTests(unittest.TestCase):
    @patch.object(validate, "get_changed_files")
    def test_changed_only_skips_unchanged_profile(self, mock_changes):
        mock_changes.return_value = {
            "added": [],
            "modified": ["profiles/backend.yaml"],
            "deleted": [],
        }
        with patch.object(validate, "REPO_ROOT", REPO_ROOT):
            with patch.object(validate, "KNOWLEDGE_DIR", REPO_ROOT / "knowledge"):
                with patch.object(validate, "PROFILES_DIR", PROFILES_DIR):
                    code = validate.run_validation(changed_only=True, tier="all")
        self.assertEqual(code, 0)

    @patch.object(validate, "get_changed_files")
    @patch.object(validate, "validate_graph")
    def test_changed_only_skips_graph_without_invalidation(
        self, mock_graph, mock_changes
    ):
        mock_changes.return_value = {
            "added": [],
            "modified": ["knowledge/engineering/clean-code.md"],
            "deleted": [],
        }
        mock_graph.return_value = ([], [])
        with patch.object(validate, "REPO_ROOT", REPO_ROOT):
            with patch.object(validate, "KNOWLEDGE_DIR", REPO_ROOT / "knowledge"):
                with patch.object(validate, "PROFILES_DIR", PROFILES_DIR):
                    validate.run_validation(changed_only=True, tier="all")
        mock_graph.assert_not_called()

    @patch.object(validate, "get_changed_files")
    @patch.object(validate, "validate_graph")
    def test_changed_only_runs_full_graph_on_schema_change(
        self, mock_graph, mock_changes
    ):
        mock_changes.return_value = {
            "added": [],
            "modified": ["schema/graph-rules.yaml"],
            "deleted": [],
        }
        mock_graph.return_value = ([], [])
        with patch.object(validate, "REPO_ROOT", REPO_ROOT):
            with patch.object(validate, "KNOWLEDGE_DIR", REPO_ROOT / "knowledge"):
                with patch.object(validate, "PROFILES_DIR", PROFILES_DIR):
                    validate.run_validation(changed_only=True, tier="all")
        mock_graph.assert_called_once()


class TierTests(unittest.TestCase):
    @patch.object(validate, "validate_graph")
    @patch.object(validate, "validate_concepts")
    def test_structural_only(self, mock_concepts, mock_graph):
        with patch.object(validate, "REPO_ROOT", REPO_ROOT):
            with patch.object(validate, "KNOWLEDGE_DIR", REPO_ROOT / "knowledge"):
                with patch.object(validate, "PROFILES_DIR", PROFILES_DIR):
                    validate.run_validation(tier="structural")
        mock_graph.assert_not_called()
        mock_concepts.assert_not_called()

    @patch.object(validate, "validate_legacy_fields", return_value=[])
    @patch.object(validate, "validate_schema", return_value=[])
    @patch.object(validate, "validate_markdown_links", return_value=[])
    @patch.object(validate, "validate_graph")
    def test_graph_only(self, mock_graph, *_ignored):
        mock_graph.return_value = ([], [])
        with patch.object(validate, "REPO_ROOT", REPO_ROOT):
            with patch.object(validate, "KNOWLEDGE_DIR", REPO_ROOT / "knowledge"):
                with patch.object(validate, "PROFILES_DIR", PROFILES_DIR):
                    validate.run_validation(tier="graph")
        mock_graph.assert_called_once()

    @patch.object(validate, "validate_graph")
    @patch.object(validate, "validate_concepts")
    def test_registry_only(self, mock_concepts, mock_graph):
        mock_concepts.return_value = []
        with patch.object(validate, "REPO_ROOT", REPO_ROOT):
            with patch.object(validate, "KNOWLEDGE_DIR", REPO_ROOT / "knowledge"):
                with patch.object(validate, "PROFILES_DIR", PROFILES_DIR):
                    validate.run_validation(tier="registry")
        mock_graph.assert_not_called()
        mock_concepts.assert_called_once()


class IndexGenerationTests(unittest.TestCase):
    def test_concept_index_output(self):
        node = make_node(
            "knowledge/testing/testing.md",
            concept_ids=["EKP-TS01"],
            adapter_priority="high",
        )
        node.body = "### EKP-TS01: Unit Testing\n"
        index = generate_concept_index([node])
        self.assertIn("EKP-TS01", index)
        self.assertEqual(index["EKP-TS01"]["title"], "Unit Testing")
        self.assertEqual(index["EKP-TS01"]["adapter_priority"], "high")

    def test_knowledge_graph_output(self):
        node = make_node(
            "knowledge/engineering/clean-code.md",
            depends_on=[FOUNDATION],
        )
        node.related = ["knowledge/engineering/solid.md"]
        graph = generate_knowledge_graph([node])
        self.assertTrue(any(edge["type"] == "depends_on" for edge in graph["edges"]))
        self.assertTrue(any(edge["type"] == "related" for edge in graph["edges"]))
        self.assertEqual(graph["nodes"][0]["id"], node.path)

    def test_adapter_manifest_output(self):
        node = make_node(
            "knowledge/testing/testing.md",
            concept_ids=["EKP-TS01"],
            adapter_priority="high",
        )
        manifest = generate_adapter_manifest([node])
        self.assertIn("EKP-P01", manifest["principles"])
        self.assertEqual(manifest["rules"][0]["concept"], "EKP-TS01")
        self.assertEqual(manifest["rules"][0]["priority"], "high")

    def test_write_indexes(self):
        node = make_node("knowledge/testing/testing.md", concept_ids=["EKP-TS01"])
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp)
            written = write_indexes([node], output)
            self.assertTrue((output / "concept-index.json").exists())
            self.assertTrue((output / "knowledge-graph.json").exists())
            self.assertTrue((output / "adapter-manifest.json").exists())
            concept_data = json.loads((output / "concept-index.json").read_text())
            self.assertIn("EKP-TS01", concept_data)
            self.assertIn("concept_index", written)


class StrictAdapterTests(unittest.TestCase):
    def test_missing_priority_warning(self):
        node = make_node("knowledge/engineering/clean-code.md")
        errors, warnings = validate_adapter_metadata([node])
        self.assertEqual(errors, [])
        self.assertTrue(any("adapter_priority" in warning for warning in warnings))

    def test_strict_failure(self):
        node = make_node("knowledge/engineering/clean-code.md")
        errors, warnings = validate_adapter_metadata([node], strict_adapters=True)
        self.assertTrue(any("adapter_priority" in error for error in errors))
        self.assertEqual(warnings, [])


class ScaleReportTests(unittest.TestCase):
    def test_scale_report_format(self):
        node = make_node(
            "knowledge/testing/testing.md",
            concept_ids=["EKP-TS01"],
            adapter_priority="high",
        )
        report = format_scale_report([node], ["sample warning"])
        self.assertIn("EKP Scale Report", report)
        self.assertIn("Documents:", report)
        self.assertIn("Phase", report)


if __name__ == "__main__":
    unittest.main()
