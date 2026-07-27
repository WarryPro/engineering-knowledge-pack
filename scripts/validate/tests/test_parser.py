"""Tests for YAML frontmatter parsing."""

import sys
import unittest
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parents[1]
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from modules.models import DocumentNode
from modules.parse import parse_document

FIXTURES = Path(__file__).resolve().parent / "fixtures"
REPO_ROOT = FIXTURES


class ParserTests(unittest.TestCase):
    def test_multiline_depends_on_and_implements(self):
        path = FIXTURES / "knowledge/engineering/valid-practice.md"
        frontmatter, body, errors = parse_document(path)

        self.assertEqual(errors, [])
        self.assertIn("Fixture Practice", body)
        self.assertEqual(
            frontmatter["depends_on"],
            ["knowledge/engineering/engineering-principles.md"],
        )
        self.assertEqual(frontmatter["implements"], ["EKP-P01"])

    def test_scalar_fields(self):
        path = FIXTURES / "knowledge/engineering/engineering-principles.md"
        frontmatter, body, errors = parse_document(path)

        self.assertEqual(errors, [])
        self.assertEqual(frontmatter["title"], "Fixture Foundation")
        self.assertEqual(frontmatter["role"], "foundation")
        self.assertEqual(frontmatter["depends_on"], [])

    def test_invalid_yaml(self):
        invalid = FIXTURES / "invalid.yaml.md"
        invalid.write_text("---\ntitle: [unclosed\n---\n", encoding="utf-8")
        try:
            frontmatter, body, errors = parse_document(invalid)
            self.assertIsNone(frontmatter)
            self.assertTrue(any("invalid YAML" in error for error in errors))
        finally:
            if invalid.exists():
                invalid.unlink()

    def test_document_node_normalizes_lists(self):
        path = FIXTURES / "knowledge/engineering/valid-practice.md"
        node, errors = DocumentNode.from_path(path, REPO_ROOT)
        self.assertEqual(errors, [])
        self.assertEqual(node.depends_on, ["knowledge/engineering/engineering-principles.md"])
        self.assertEqual(node.related, [])
        self.assertEqual(node.implements, ["EKP-P01"])


if __name__ == "__main__":
    unittest.main()
