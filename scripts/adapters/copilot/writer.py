"""Render selected knowledge as GitHub Copilot instruction markdown."""

from common.selected_knowledge import (
    KIND_FOUNDATION,
    KIND_ORCHESTRATOR,
    blocking_constraints,
    flow_directive_lines,
)

from copilot.grouping import COPILOT_INSTRUCTIONS_RELPATH, instruction_relpath


def _bullet(text):
    # type: (str) -> str
    stripped = text.strip()
    if stripped.startswith("- "):
        return stripped
    return "- {}".format(stripped)


def _append_section(lines, heading, items):
    # type: (list, str, list) -> None
    if not items:
        return
    lines.append("## {}".format(heading))
    lines.append("")
    for item in items:
        lines.append(_bullet(item))
    lines.append("")


def _concept_lines(concept):
    # type: (object) -> list
    """Compact concept block: intent, rules, no Cursor frontmatter."""
    lines = [
        "### {} — {}".format(concept.concept_id, concept.title),
        "",
    ]
    if concept.intent:
        lines.append(_bullet(concept.intent))
        lines.append("")
    if concept.rules:
        lines.append("Directives:")
        lines.append("")
        for rule in concept.rules:
            lines.append(_bullet(rule))
        lines.append("")
    return lines


def _unit_body(unit):
    # type: (object) -> list
    lines = []
    heading = unit.title or unit.source_path
    if unit.kind == KIND_ORCHESTRATOR:
        heading = "AI orchestrator"
    elif unit.kind == KIND_FOUNDATION:
        heading = "Engineering principles"
    lines.append("## {}".format(heading))
    lines.append("")
    lines.append("> **Source:** `{}`".format(unit.source_path))
    lines.append("")

    extra_directives = getattr(unit, "extra_directives", None) or []
    extra_constraints = getattr(unit, "extra_constraints", None) or []
    if extra_directives:
        lines.append("### Directives")
        lines.append("")
        for directive in extra_directives:
            lines.append(_bullet(directive))
        lines.append("")
    if extra_constraints:
        lines.append("### Constraints")
        lines.append("")
        for constraint in extra_constraints:
            lines.append(_bullet(constraint))
        lines.append("")

    if unit.flow is not None:
        directives = flow_directive_lines(unit.flow.decision_flow)
        if directives:
            lines.append("### Directives")
            lines.append("")
            for directive in directives:
                lines.append(_bullet(directive))
            lines.append("")
        constraints = blocking_constraints(unit.flow.enforcement_rules)
        if constraints:
            lines.append("### Constraints")
            lines.append("")
            for constraint in constraints:
                lines.append(_bullet(constraint))
            lines.append("")

    for concept in unit.concepts:
        lines.extend(_concept_lines(concept))

    return lines


def _reference_lines(units):
    # type: (list) -> list
    seen = []
    for unit in units:
        ref = "`{}`".format(unit.source_path)
        if ref not in seen:
            seen.append(ref)
        for concept in unit.concepts:
            concept_ref = "`{}` — {}".format(
                concept.source_document, concept.concept_id
            )
            if concept_ref not in seen:
                seen.append(concept_ref)
    return seen


def render_always_on(units):
    # type: (list) -> str
    """Render repository-wide ``copilot-instructions.md``."""
    lines = [
        "# EKP engineering instructions",
        "",
        "These repository-wide GitHub Copilot instructions are generated from EKP",
        "knowledge. Apply them on every Copilot task in this repository.",
        "",
        "Copilot skills are out of scope for this bundle.",
        "",
    ]
    for unit in units:
        lines.extend(_unit_body(unit))

    references = _reference_lines(units)
    _append_section(lines, "References", references)
    return "\n".join(lines).rstrip() + "\n"


def render_path_instructions(group, units):
    # type: (dict, list) -> str
    """Render a path-specific ``*.instructions.md`` file with ``applyTo``."""
    lines = [
        "---",
        'applyTo: "{}"'.format(group["apply_to"]),
        "---",
        "",
        "# EKP {} instructions".format(group["name"]),
        "",
        "Path-specific GitHub Copilot instructions generated from EKP knowledge.",
        "These apply only to files matching ``applyTo``.",
        "",
    ]
    for unit in units:
        lines.extend(_unit_body(unit))
    references = _reference_lines(units)
    _append_section(lines, "References", references)
    return "\n".join(lines).rstrip() + "\n"


def planned_files(always_on_units, grouped_units, group_lookup):
    # type: (list, dict, object) -> list
    """
    Return deterministic (relative_path, content, sources) tuples.

    ``group_lookup(name) -> group dict``.
    """
    planned = []
    if always_on_units:
        planned.append(
            (
                COPILOT_INSTRUCTIONS_RELPATH,
                render_always_on(always_on_units),
                [unit.source_path for unit in always_on_units],
            )
        )
    for name in sorted(grouped_units.keys()):
        group = group_lookup(name)
        units = grouped_units[name]
        planned.append(
            (
                instruction_relpath(group["filename"]),
                render_path_instructions(group, units),
                [unit.source_path for unit in units],
            )
        )
    return planned
