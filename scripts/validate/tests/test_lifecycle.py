"""Tests for knowledge document lifecycle status (EKP-AI16)."""

import sys
import unittest
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parents[1]
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from modules.lifecycle_validate import (
    DEFAULT_STATUS,
    VALID_STATUSES,
    resolve_status,
    validate_lifecycle,
)
from modules.models import DocumentNode
from modules.schema_validate import validate_schema

FIXTURES = Path(__file__).resolve().parent / "fixtures"
REPO_ROOT = FIXTURES


def load_fixture(rel_path):
    node, errors = DocumentNode.from_path(REPO_ROOT / rel_path, REPO_ROOT)
    if errors:
        raise AssertionError(errors)
    return node


class LifecycleStatusTests(unittest.TestCase):
    def test_missing_status_defaults_to_published(self):
        node = load_fixture("knowledge/engineering/engineering-principles.md")
        self.assertEqual(resolve_status(node.frontmatter), DEFAULT_STATUS)
        self.assertEqual(DEFAULT_STATUS, "published")

    def test_all_valid_statuses_accepted(self):
        for status in sorted(VALID_STATUSES):
            fm = {
                "title": "T",
                "domain": "engineering",
                "tags": ["test"],
                "severity": "recommended",
                "applies_to": ["backend"],
                "role": "practice",
                "type": "guide",
                "depends_on": ["knowledge/engineering/engineering-principles.md"],
                "implements": ["EKP-P04"],
                "concept_ids": ["EKP-CC01"],
                "status": status,
            }
            errors = validate_schema(fm, "knowledge/engineering/test-status.md")
            self.assertEqual(errors, [], msg="status={}".format(status))
            node = DocumentNode(
                path="knowledge/engineering/test-status.md",
                frontmatter=fm,
                body="",
                role="practice",
            )
            errors, warnings = validate_lifecycle([node])
            self.assertEqual(errors, [])
            self.assertEqual(warnings, [])

    def test_invalid_status_fails_validation(self):
        fm = {
            "title": "T",
            "domain": "engineering",
            "tags": ["test"],
            "severity": "recommended",
            "applies_to": ["backend"],
            "role": "practice",
            "type": "guide",
            "depends_on": ["knowledge/engineering/engineering-principles.md"],
            "implements": ["EKP-P04"],
            "concept_ids": ["EKP-CC01"],
            "status": "archived",
        }
        schema_errors = validate_schema(fm, "knowledge/engineering/bad-status.md")
        self.assertTrue(schema_errors)

        fm["status"] = "published"
        node = DocumentNode(
            path="knowledge/engineering/bad-status.md",
            frontmatter=dict(fm, status="not-a-status"),
            body="",
        )
        errors, warnings = validate_lifecycle([node])
        self.assertTrue(any("invalid status" in e for e in errors))

    def test_existing_guides_without_status_validate(self):
        """Regression: fixture guides without status pass lifecycle checks."""
        guides = [
            "knowledge/engineering/engineering-principles.md",
            "knowledge/engineering/valid-practice.md",
        ]
        for rel in guides:
            path = REPO_ROOT / rel
            if not path.is_file():
                continue
            node = load_fixture(rel)
            self.assertEqual(resolve_status(node.frontmatter), "published")
            errors, warnings = validate_lifecycle([node])
            self.assertEqual(errors, [], msg=rel)


if __name__ == "__main__":
    unittest.main()
