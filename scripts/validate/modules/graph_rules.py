"""Load graph dependency rules from schema/graph-rules.yaml."""

from pathlib import Path

import yaml

RULES_PATH = Path(__file__).resolve().parents[3] / "schema" / "graph-rules.yaml"


def load_graph_rules():
    # type: () -> dict
    with RULES_PATH.open(encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def get_allowed_exceptions(rules):
    # type: (dict) -> set
    """Return set of (source_path, dependency_path) tuples explicitly allowed."""
    pairs = set()
    for entry in rules.get("exceptions", []):
        source = entry.get("source")
        dep = entry.get("allowed_dependency")
        if source and dep:
            pairs.add((source, dep))
    return pairs


def get_role_rules(rules, role):
    # type: (dict, str) -> dict
    return rules.get("roles", {}).get(role, {})
