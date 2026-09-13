"""Render a knowledge unit as plain Markdown body (document-grouped).

Used by workspace-scoped Cursor/Claude/Antigravity outputs. Keeps one
canonical document per file rather than exploding to per-concept rules.
"""

from common.selected_knowledge import (
    KIND_FOUNDATION,
    KIND_ORCHESTRATOR,
    blocking_constraints,
    flow_directive_lines,
)


def _bullet(text):
    # type: (str) -> str
    stripped = text.strip()
    if stripped.startswith("- "):
        return stripped
    return "- {}".format(stripped)


def heading_for_unit(unit):
    # type: (object) -> str
    if unit.kind == KIND_ORCHESTRATOR:
        return "EKP AI orchestrator"
    if unit.kind == KIND_FOUNDATION:
        return "EKP engineering principles"
    return unit.title or unit.source_path


def flow_and_concept_lines(unit):
    # type: (object) -> list
    lines = []
    extra_directives = getattr(unit, "extra_directives", None) or []
    extra_constraints = getattr(unit, "extra_constraints", None) or []
    if extra_directives:
        lines.append("## Directives")
        lines.append("")
        for directive in extra_directives:
            lines.append(_bullet(directive))
        lines.append("")
    if extra_constraints:
        lines.append("## Constraints")
        lines.append("")
        for constraint in extra_constraints:
            lines.append(_bullet(constraint))
        lines.append("")
    if unit.flow is not None:
        directives = flow_directive_lines(unit.flow.decision_flow)
        if directives:
            heading = "Directives" if not extra_directives else "Decision flow"
            lines.append("## {}".format(heading))
            lines.append("")
            for directive in directives:
                lines.append(_bullet(directive))
            lines.append("")
        constraints = blocking_constraints(unit.flow.enforcement_rules)
        if constraints:
            heading = "Constraints" if not extra_constraints else "Enforcement"
            lines.append("## {}".format(heading))
            lines.append("")
            for constraint in constraints:
                lines.append(_bullet(constraint))
            lines.append("")
    for concept in unit.concepts:
        lines.extend(_concept_block(concept))
    return lines


def _concept_block(concept):
    # type: (object) -> list
    lines = [
        "## {} — {}".format(concept.concept_id, concept.title),
        "",
    ]
    if concept.intent:
        lines.append(_bullet(concept.intent))
        lines.append("")
    if concept.rules:
        lines.append("### Directives")
        lines.append("")
        for rule in concept.rules:
            lines.append(_bullet(rule))
        lines.append("")
    references = ["`{}` — {}".format(concept.source_document, concept.concept_id)]
    if concept.implements:
        references.append("Implements: {}".format(", ".join(concept.implements)))
    lines.append("### References")
    lines.append("")
    for reference in references:
        lines.append(_bullet(reference))
    lines.append("")
    return lines


def render_document_unit_body(unit, part_label=None):
    # type: (object, str) -> str
    """Full document-grouped Markdown body with title and Source line."""
    title = heading_for_unit(unit)
    if part_label:
        title = "{} ({})".format(title, part_label)
    lines = [
        "# {}".format(title),
        "",
        "> **Source:** `{}`".format(unit.source_path),
        "",
    ]
    lines.extend(flow_and_concept_lines(unit))
    return "\n".join(lines).rstrip() + "\n"
