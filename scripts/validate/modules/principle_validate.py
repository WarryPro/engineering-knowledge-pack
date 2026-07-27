"""Principle ownership and delegation validation."""

import json
from pathlib import Path

from .models import FOUNDATION_PATH, DocumentNode

EXCEPTIONS_PATH = Path(__file__).resolve().parents[3] / "schema" / "principle-exceptions.json"
ALL_PRINCIPLES = ["EKP-P{:02d}".format(n) for n in range(1, 11)]


def load_principle_exceptions():
    # type: () -> dict
    with EXCEPTIONS_PATH.open(encoding="utf-8") as handle:
        return json.load(handle)


def build_principle_owners(nodes):
    # type: (list) -> dict
    """Map each EKP-P** principle to documents that implement it."""
    owners = {pid: [] for pid in ALL_PRINCIPLES}
    for node in nodes:
        for principle_id in node.implements:
            if principle_id in owners:
                owners[principle_id].append(node.path)
    return owners


def validate_principle_coverage(nodes):
    # type: (list) -> list
    """R-P2: warn when a principle has no owner and no documented exception."""
    warnings = []
    exceptions = load_principle_exceptions()
    owners = build_principle_owners(nodes)

    for principle_id in ALL_PRINCIPLES:
        if owners[principle_id]:
            continue
        if principle_id in exceptions:
            continue
        warnings.append(
            "[PRINCIPLE] {} has no implementing document and no exception".format(
                principle_id
            )
        )

    return warnings


def validate_foundation_related(nodes):
    # type: (list) -> list
    """R-P3: downstream documents should appear in foundation related (warning)."""
    warnings = []
    by_path = {node.path: node for node in nodes}
    foundation = by_path.get(FOUNDATION_PATH)
    if foundation is None:
        return warnings

    related = set(foundation.related)
    for node in nodes:
        if node.is_foundation:
            continue
        if FOUNDATION_PATH not in node.depends_on:
            continue
        if node.path not in related:
            warnings.append(
                "[PRINCIPLE] {} depends on foundation but is missing from "
                "{} related".format(node.path, FOUNDATION_PATH)
            )

    return warnings


def validate_principles(nodes):
    # type: (list) -> tuple
    """Run principle governance checks. Returns (errors, warnings)."""
    warnings = []
    warnings.extend(validate_principle_coverage(nodes))
    warnings.extend(validate_foundation_related(nodes))
    return [], warnings


def format_principle_report(nodes):
    # type: (list) -> str
    """Build human-readable principle coverage report."""
    exceptions = load_principle_exceptions()
    owners = build_principle_owners(nodes)
    lines = ["EKP Principle Coverage", ""]

    for principle_id in ALL_PRINCIPLES:
        short = principle_id.replace("EKP-P", "P")
        lines.append("{}:".format(short))

        doc_owners = owners[principle_id]
        if doc_owners:
            for owner in sorted(doc_owners):
                lines.append("  {}".format(Path(owner).name))
        elif principle_id in exceptions:
            lines.append("  exception: {}".format(exceptions[principle_id]["reason"]))
        else:
            lines.append("  (no owner)")

        lines.append("")

    return "\n".join(lines).rstrip()
