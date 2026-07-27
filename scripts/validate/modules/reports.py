"""Formatted reports for --report CLI commands."""

from pathlib import Path

from .adapter_validate import OPERATIONAL_ROLES
from .graph_validate import get_direct_dependents, get_max_depth
from .models import FOUNDATION_PATH
from .namespace_validate import load_namespace_registry
from .principle_validate import format_principle_report


def format_graph_report(nodes):
    # type: (list) -> str
    lines = [
        "Knowledge Graph",
        "",
        "Foundation:",
        " {}".format(Path(FOUNDATION_PATH).name),
        "",
        "Depth:",
        " max: {}".format(get_max_depth(nodes)),
        "",
        "Edges:",
        " {}".format(Path(FOUNDATION_PATH).stem),
    ]

    children = get_direct_dependents(nodes, FOUNDATION_PATH)
    for child in children:
        lines.append(" |")
        lines.append(" + {}".format(Path(child).name))

    return "\n".join(lines)


def format_concepts_report(nodes, registry=None):
    # type: (list, dict) -> str
    if registry is None:
        registry = load_namespace_registry()

    total = sum(len(node.concept_ids) for node in nodes)
    lines = [
        "Concept Registry",
        "",
        "Namespaces:",
    ]

    for ns_key in sorted(registry.keys()):
        entry = registry[ns_key]
        lines.append("")
        lines.append(ns_key)
        lines.append(" owner:")
        lines.append("  {}".format(Path(entry["owner"]).name))

    lines.extend(["", "Total concepts:", " {}".format(total)])
    return "\n".join(lines)


def format_adapters_report(nodes):
    # type: (list) -> str
    high_priority = []
    missing_priority = []

    for node in nodes:
        if node.role not in OPERATIONAL_ROLES:
            continue
        priority = node.frontmatter.get("adapter_priority")
        name = Path(node.path).name
        if priority == "high":
            high_priority.append(name)
        elif priority is None:
            missing_priority.append(name)

    lines = [
        "Adapter readiness:",
        "",
        "High priority:",
    ]
    if high_priority:
        lines.extend("- {}".format(name) for name in sorted(high_priority))
    else:
        lines.append("- (none)")

    lines.append("")
    lines.append("Missing priority:")
    if missing_priority:
        lines.extend("- {}".format(name) for name in sorted(missing_priority))
    else:
        lines.append("- (none)")

    return "\n".join(lines)


def print_principle_report(nodes):
    # type: (list) -> None
    print(format_principle_report(nodes))


def print_graph_report(nodes):
    # type: (list) -> None
    print(format_graph_report(nodes))


def print_concepts_report(nodes):
    # type: (list) -> None
    print(format_concepts_report(nodes))


def print_adapters_report(nodes):
    # type: (list) -> None
    print(format_adapters_report(nodes))
