"""Unit tests for Copilot PATH_GROUPS and knowledge partitioning."""

import sys
import unittest
from pathlib import Path

ADAPTERS_DIR = Path(__file__).resolve().parents[1]

if str(ADAPTERS_DIR) not in sys.path:
    sys.path.insert(0, str(ADAPTERS_DIR))

from copilot.grouping import (
    PATH_GROUPS,
    group_by_name,
    matching_group,
    partition_units,
)
from common.selected_knowledge import KIND_DOCUMENT, KnowledgeUnit


NATIVEscript_APPLY_TO = (
    "**/*.xml,**/App_Resources/**,**/nativescript.config.{ts,js}"
)


def _document_unit(source_path):
    return KnowledgeUnit(
        source_path=source_path,
        title="Test",
        kind=KIND_DOCUMENT,
        flow=None,
        concepts=[],
    )


class CopilotGroupingTests(unittest.TestCase):
    def test_nativescript_group_is_registered(self):
        names = [group["name"] for group in PATH_GROUPS]
        self.assertIn("nativescript", names)

    def test_nativescript_group_metadata(self):
        group = group_by_name("nativescript")
        self.assertEqual(group["filename"], "nativescript.instructions.md")
        self.assertEqual(group["prefixes"], ("knowledge/nativescript/",))
        self.assertEqual(group["apply_to"], NATIVEscript_APPLY_TO)

    def test_matching_group_routes_nativescript_knowledge(self):
        group = matching_group("knowledge/nativescript/nativescript-architecture.md")
        self.assertIsNotNone(group)
        self.assertEqual(group["name"], "nativescript")

    def test_matching_group_routes_typescript_knowledge(self):
        group = matching_group("knowledge/typescript/typescript-fundamentals.md")
        self.assertIsNotNone(group)
        self.assertEqual(group["name"], "typescript")

    def test_matching_group_routes_frontend_knowledge(self):
        group = matching_group("knowledge/frontend/frontend-architecture.md")
        self.assertIsNotNone(group)
        self.assertEqual(group["name"], "frontend")

    def test_nativescript_knowledge_not_routed_to_typescript(self):
        group = matching_group("knowledge/nativescript/nativescript-architecture.md")
        self.assertNotEqual(group["name"], "typescript")

    def test_typescript_knowledge_not_routed_to_nativescript(self):
        group = matching_group("knowledge/typescript/typescript-fundamentals.md")
        self.assertNotEqual(group["name"], "nativescript")

    def test_frontend_knowledge_not_routed_to_nativescript(self):
        group = matching_group("knowledge/frontend/frontend-architecture.md")
        self.assertNotEqual(group["name"], "nativescript")

    def test_partition_units_assigns_nativescript_guide(self):
        units = [
            _document_unit("knowledge/nativescript/nativescript-architecture.md"),
            _document_unit("knowledge/typescript/typescript-fundamentals.md"),
        ]
        _always_on, grouped = partition_units(units)
        self.assertIn("nativescript", grouped)
        self.assertIn("typescript", grouped)
        self.assertEqual(len(grouped["nativescript"]), 1)
        self.assertEqual(
            grouped["nativescript"][0].source_path,
            "knowledge/nativescript/nativescript-architecture.md",
        )

    def test_apply_to_does_not_use_broad_ts_js_vue_globs(self):
        apply_to = group_by_name("nativescript")["apply_to"]
        self.assertNotIn("**/*.ts", apply_to)
        self.assertNotIn("**/*.js", apply_to)
        self.assertNotIn("**/*.vue", apply_to)
        self.assertIn("**/*.xml", apply_to)
        self.assertIn("**/App_Resources/**", apply_to)
        self.assertIn("**/nativescript.config.{ts,js}", apply_to)


if __name__ == "__main__":
    unittest.main()
