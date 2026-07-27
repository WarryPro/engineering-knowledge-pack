"""Validator v2.3 performance tests for scale targets."""

import string
import sys
import time
import unittest
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parents[1]
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from modules.concept_validate import validate_concepts
from modules.graph_validate import validate_graph
from modules.models import FOUNDATION_PATH, DocumentNode
from modules.namespace_validate import validate_namespaces
from modules.schema_validate import validate_schema

FOUNDATION = FOUNDATION_PATH
MAX_SECONDS_AT_500 = 5.0


def _namespace_code(index):
    # type: (int) -> str
    first = string.ascii_uppercase[index // 26]
    second = string.ascii_uppercase[index % 26]
    return first + second


def build_synthetic_nodes(count):
    # type: (int) -> tuple
    """Build a star graph with unique namespace ownership per document."""
    registry = {
        "EKP-P": {
            "owner": FOUNDATION,
            "format": "^EKP-P(0[1-9]|10)$",
        }
    }
    nodes = [
        DocumentNode(
            path=FOUNDATION,
            frontmatter={
                "title": "Foundation",
                "domain": "engineering",
                "tags": ["test"],
                "severity": "required",
                "applies_to": ["backend"],
                "role": "foundation",
                "concept_ids": ["EKP-P01"],
            },
            body="# Foundation\n",
            title="Foundation",
            domain="engineering",
            role="foundation",
            depends_on=[],
            concept_ids=["EKP-P01"],
        )
    ]

    for index in range(1, count):
        code = _namespace_code(index)
        namespace = "EKP-{}".format(code)
        concept_id = "{}01".format(namespace)
        path = "knowledge/engineering/synth-{:04d}.md".format(index)
        registry[namespace] = {
            "owner": path,
            "format": "^{}[0-9]{{2}}$".format(namespace),
        }
        frontmatter = {
            "title": "Synthetic {}".format(index),
            "domain": "engineering",
            "tags": ["test"],
            "severity": "recommended",
            "applies_to": ["backend"],
            "role": "practice",
            "depends_on": [FOUNDATION],
            "implements": ["EKP-P01"],
            "concept_ids": [concept_id],
            "adapter_priority": "medium",
        }
        nodes.append(
            DocumentNode(
                path=path,
                frontmatter=frontmatter,
                body="### {} Synthetic\n".format(concept_id),
                title=frontmatter["title"],
                domain="engineering",
                role="practice",
                depends_on=[FOUNDATION],
                implements=["EKP-P01"],
                concept_ids=[concept_id],
            )
        )

    return nodes, registry


def run_validation_pipeline(nodes, registry):
    # type: (list, dict) -> None
    for node in nodes:
        validate_schema(node.frontmatter, node.path)
    validate_graph(nodes, Path("."))
    validate_concepts(nodes)
    validate_namespaces(nodes, registry=registry)


class PerformanceTests(unittest.TestCase):
    def _assert_under_budget(self, count):
        nodes, registry = build_synthetic_nodes(count)
        start = time.time()
        run_validation_pipeline(nodes, registry)
        elapsed = time.time() - start
        self.assertLess(
            elapsed,
            MAX_SECONDS_AT_500,
            "Validation for {} docs took {:.2f}s".format(count, elapsed),
        )

    def test_validation_100_documents(self):
        self._assert_under_budget(100)

    def test_validation_250_documents(self):
        self._assert_under_budget(250)

    def test_validation_500_documents(self):
        self._assert_under_budget(500)


if __name__ == "__main__":
    unittest.main()
