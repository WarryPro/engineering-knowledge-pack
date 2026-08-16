"""Render selected knowledge as plain Antigravity Markdown rule files."""

from common.selected_knowledge import (
    KIND_FOUNDATION,
    KIND_ORCHESTRATOR,
    blocking_constraints,
    flow_directive_lines,
)

from antigravity.grouping import (
    SPLIT_THRESHOLD_CHARS,
    part_filename,
)


def _bullet(text):
    # type: (str) -> str
    stripped = text.strip()
    if stripped.startswith("- "):
        return stripped
    return "- {}".format(stripped)


def _heading_for_unit(unit):
    # type: (object) -> str
    if unit.kind == KIND_ORCHESTRATOR:
        return "EKP AI orchestrator"
    if unit.kind == KIND_FOUNDATION:
        return "EKP engineering principles"
    return unit.title or unit.source_path


def _header_lines(unit, part_label=None):
    # type: (object, str) -> list
    title = _heading_for_unit(unit)
    if part_label:
        title = "{} ({})".format(title, part_label)
    return [
        "# {}".format(title),
        "",
        "> **Source:** `{}`".format(unit.source_path),
        "",
        "This file is generated EKP knowledge for Antigravity workspace rules.",
        "It is plain Markdown. It does not declare Always On, Manual,",
        "Model Decision, or Glob activation — those semantics are not an",
        "established file-based contract and must be validated empirically.",
        "",
    ]


def _flow_blocks(unit):
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
    if unit.flow is None:
        return lines
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


def _join(lines):
    # type: (list) -> str
    return "\n".join(lines).rstrip() + "\n"


def render_unit_files(unit, base_filename):
    # type: (object, str) -> list
    """
    Render one knowledge unit to one or more (filename, content) pairs.

    Splits on concept boundaries when content would exceed the comfortable
    character threshold. Flow content stays with part 1.
    """
    header = _header_lines(unit)
    flow = _flow_blocks(unit)
    concept_blocks = [_concept_block(concept) for concept in unit.concepts]

    combined = header + flow
    for block in concept_blocks:
        combined.extend(block)
    combined_text = _join(combined)
    if len(combined_text) <= SPLIT_THRESHOLD_CHARS:
        return [(base_filename, combined_text)]

    parts = []
    current = header + flow
    part_index = 1

    def flush():
        filename = part_filename(base_filename, part_index)
        labeled_header = _header_lines(
            unit, part_label="part {}".format(part_index)
        )
        body = current[len(header):]
        parts.append((filename, _join(labeled_header + body)))

    for block in concept_blocks:
        candidate = current + block
        if len(_join(candidate)) > SPLIT_THRESHOLD_CHARS and current != header + flow:
            flush()
            part_index += 1
            current = header + block
        else:
            current = candidate

    flush()
    return parts
