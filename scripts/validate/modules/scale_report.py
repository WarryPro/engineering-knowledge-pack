"""Scale and readiness reporting."""

from .adapter_validate import OPERATIONAL_ROLES
from .graph_validate import get_max_depth
from .namespace_validate import load_namespace_registry


def _estimate_phase(doc_count, concept_count):
    # type: (int, int) -> str
    if doc_count < 15:
        return "Phase 2"
    if doc_count < 50:
        return "Phase 3"
    if doc_count < 150:
        return "Phase 4"
    return "Phase 5"


def format_scale_report(nodes, warnings):
    # type: (list, list) -> str
    registry = load_namespace_registry()
    total_concepts = sum(len(node.concept_ids) for node in nodes)
    adapter_ready = 0
    operational_concepts = 0

    for node in nodes:
        if node.role not in OPERATIONAL_ROLES:
            continue
        priority = node.frontmatter.get("adapter_priority")
        count = len(node.concept_ids)
        operational_concepts += count
        if priority in ("high", "medium", "low"):
            adapter_ready += count

    readiness_pct = 0
    if operational_concepts:
        readiness_pct = int(round(100.0 * adapter_ready / operational_concepts))

    lines = [
        "EKP Scale Report",
        "",
        "Documents:",
        " {}".format(len(nodes)),
        "",
        "Concepts:",
        " {}".format(total_concepts),
        "",
        "Namespaces:",
        " {}".format(len(registry)),
        "",
        "Max graph depth:",
        " {}".format(get_max_depth(nodes)),
        "",
        "Adapter ready concepts:",
        " {}%".format(readiness_pct),
        "",
        "Warnings:",
        " {}".format(len(warnings)),
        "",
        "Estimated readiness:",
        " {}".format(_estimate_phase(len(nodes), total_concepts)),
    ]
    return "\n".join(lines)


def print_scale_report(nodes, warnings):
    # type: (list, list) -> None
    print(format_scale_report(nodes, warnings))
