"""Tests for EKP knowledge markdown extraction."""

import sys
import unittest
from pathlib import Path

ADAPTERS_DIR = Path(__file__).resolve().parents[1]
if str(ADAPTERS_DIR) not in sys.path:
    sys.path.insert(0, str(ADAPTERS_DIR))

from common.extract import (
    extract_adapter_enforcement,
    extract_concepts,
    extract_decision_flow,
)
from common.paths import get_dist_path, get_knowledge_path, get_repo_root

AI_DOC = get_knowledge_path() / "ai" / "ai-assisted-development.md"
SOURCE_PATH = "knowledge/ai/ai-assisted-development.md"


class ExtractConceptTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.markdown = AI_DOC.read_text(encoding="utf-8")

    def test_extract_ekp_ai01_concept(self):
        concepts = extract_concepts(self.markdown, SOURCE_PATH)
        ai01 = next(item for item in concepts if item.concept_id == "EKP-AI01")

        self.assertEqual(ai01.title, "Scope to the stated task")
        self.assertEqual(ai01.implements, ["EKP-P01"])
        self.assertIn("what was asked", ai01.intent)
        self.assertGreaterEqual(len(ai01.rules), 3)
        self.assertIn("email validation", ai01.good_examples)
        self.assertIn("entire form module", ai01.bad_examples)
        self.assertIn("unrelated to the ticket", ai01.review_signals)
        self.assertEqual(ai01.source_document, SOURCE_PATH)

    def test_extract_multiple_concepts(self):
        concepts = extract_concepts(self.markdown, SOURCE_PATH)
        concept_ids = [item.concept_id for item in concepts]

        self.assertEqual(len(concepts), 12)
        self.assertEqual(concept_ids[0], "EKP-AI01")
        self.assertEqual(concept_ids[-1], "EKP-AI12")
        self.assertIn("EKP-AI05", concept_ids)
        self.assertTrue(all(item.rules for item in concepts))


class ExtractDecisionFlowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.markdown = AI_DOC.read_text(encoding="utf-8")

    def test_extract_ai_decision_flow(self):
        flow = extract_decision_flow(self.markdown, SOURCE_PATH)

        self.assertIsNotNone(flow)
        self.assertEqual(flow.title, "AI-Assisted Development")
        self.assertEqual(flow.document_path, SOURCE_PATH)
        self.assertIn("Scope verification", flow.decision_flow)
        self.assertIn("Completion verification", flow.decision_flow)
        self.assertIn("EKP-AI01", flow.decision_flow)
        self.assertGreaterEqual(len(flow.enforcement_rules), 8)

    def test_extract_adapter_enforcement_table(self):
        rows = extract_adapter_enforcement(self.markdown)

        self.assertGreaterEqual(len(rows), 8)
        self.assertIn("step", rows[0])
        self.assertIn("auto_apply", rows[0])
        self.assertIn("notes", rows[0])
        self.assertIn("Scope", rows[0]["step"])
        self.assertIn("Block", rows[0]["auto_apply"])
        self.assertIn("EKP-AI01", rows[0]["notes"])


class ExtractInvalidMarkdownTests(unittest.TestCase):
    def test_invalid_markdown_returns_empty_results(self):
        invalid = "# Not an EKP document\n\nNo concepts here.\n"

        self.assertEqual(extract_concepts(invalid, "knowledge/example.md"), [])
        self.assertIsNone(extract_decision_flow(invalid, "knowledge/example.md"))
        self.assertEqual(extract_adapter_enforcement(invalid), [])
        self.assertEqual(extract_concepts("", SOURCE_PATH), [])
        self.assertIsNone(extract_decision_flow("", SOURCE_PATH))


class PathHelperTests(unittest.TestCase):
    def test_repo_paths_resolve(self):
        root = get_repo_root()
        self.assertTrue((root / "knowledge" / "ai" / "ai-assisted-development.md").is_file())
        self.assertEqual(get_knowledge_path(), root / "knowledge")
        self.assertEqual(get_dist_path(), root / "dist")


if __name__ == "__main__":
    unittest.main()
