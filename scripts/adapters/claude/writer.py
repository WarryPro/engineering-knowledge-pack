"""Render selected knowledge as Claude Code CLAUDE.md and Skills."""

from common.selected_knowledge import (
    KIND_FOUNDATION,
    KIND_ORCHESTRATOR,
    blocking_constraints,
    flow_directive_lines,
)

from claude.grouping import CLAUDE_MD_RELPATH, skill_id_for_unit, skill_relpath


def _bullet(text):
    # type: (str) -> str
    stripped = text.strip()
    if stripped.startswith("- "):
        return stripped
    return "- {}".format(stripped)


def _yaml_escape(value):
    # type: (str) -> str
    """Quote YAML scalar values when needed for Skill frontmatter."""
    if not value:
        return '""'
    if any(char in value for char in ':{}[]&*#?|-<>=!%@\\"\n'):
        escaped = value.replace("\\", "\\\\").replace('"', '\\"')
        return '"{}"'.format(escaped)
    return value


def _append_bullets(lines, items):
    # type: (list, list) -> None
    for item in items:
        lines.append(_bullet(item))
    if items:
        lines.append("")


def _concept_lines(concept):
    # type: (object) -> list
    lines = [
        "### {} — {}".format(concept.concept_id, concept.title),
        "",
    ]
    if concept.intent:
        lines.append(_bullet(concept.intent))
        lines.append("")
    if concept.rules:
        for rule in concept.rules:
            lines.append(_bullet(rule))
        lines.append("")
    return lines


def _compact_unit_section(unit, heading):
    # type: (object, str) -> list
    """Compact always-on section for CLAUDE.md (no full concept dump)."""
    lines = [
        "## {}".format(heading),
        "",
        "> **Source:** `{}`".format(unit.source_path),
        "",
    ]
    extra_directives = getattr(unit, "extra_directives", None) or []
    extra_constraints = getattr(unit, "extra_constraints", None) or []
    if extra_directives:
        lines.append("### Directives")
        lines.append("")
        _append_bullets(lines, extra_directives)
    if extra_constraints:
        lines.append("### Constraints")
        lines.append("")
        _append_bullets(lines, extra_constraints)
    if unit.flow is not None:
        directives = flow_directive_lines(unit.flow.decision_flow)
        if directives:
            lines.append("### Directives")
            lines.append("")
            _append_bullets(lines, directives)
        constraints = blocking_constraints(unit.flow.enforcement_rules)
        if constraints:
            lines.append("### Constraints")
            lines.append("")
            _append_bullets(lines, constraints)
    return lines


def render_claude_md(always_on_units, skill_units):
    # type: (list, list) -> str
    """Render compact always-on CLAUDE.md."""
    lines = [
        "# EKP engineering instructions",
        "",
        "These Claude Code project instructions are generated from EKP knowledge.",
        "Keep this file as always-on context. Detailed procedures live in Skills",
        "under `.claude/skills/` — invoke them with `/skill-name` or let Claude",
        "load them when the skill description matches the task.",
        "",
        "Do not treat this file as a full dump of every EKP concept.",
        "",
    ]

    if skill_units:
        lines.append("## Available EKP skills")
        lines.append("")
        for unit in skill_units:
            skill_id = skill_id_for_unit(unit)
            title = unit.title or unit.source_path
            lines.append(
                "- `/{}` — {} (`{}`)".format(skill_id, title, unit.source_path)
            )
        lines.append("")

    for unit in always_on_units:
        if unit.kind == KIND_ORCHESTRATOR:
            lines.extend(_compact_unit_section(unit, "AI orchestrator"))
        elif unit.kind == KIND_FOUNDATION:
            lines.extend(_compact_unit_section(unit, "Engineering principles"))

    lines.append("## References")
    lines.append("")
    seen = []
    for unit in always_on_units:
        ref = "`{}`".format(unit.source_path)
        if ref not in seen:
            seen.append(ref)
            lines.append(_bullet(ref))
    lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def _skill_description(unit):
    # type: (object) -> str
    """Build a usable Skill description for Claude discovery."""
    title = unit.title or skill_id_for_unit(unit)
    if unit.flow is not None:
        return (
            "EKP decision flow for {}. Use when the task involves {} guidance "
            "from EKP knowledge document `{}`.".format(
                title, title.lower(), unit.source_path
            )
        )
    return (
        "EKP guidance for {}. Use when implementing or reviewing work related "
        "to `{}`.".format(title, unit.source_path)
    )


def render_skill(unit):
    # type: (object) -> str
    """Render one document-grouped SKILL.md with official frontmatter fields."""
    skill_id = skill_id_for_unit(unit)
    description = _skill_description(unit)
    title = unit.title or skill_id
    lines = [
        "---",
        "name: {}".format(skill_id),
        "description: {}".format(_yaml_escape(description)),
        "---",
        "",
        "# {}".format(title),
        "",
        "> **Source:** `{}`".format(unit.source_path),
        "",
        "Generated EKP skill for Claude Code. Follow the directives and",
        "constraints below when this skill is active.",
        "",
    ]

    if unit.flow is not None:
        directives = flow_directive_lines(unit.flow.decision_flow)
        if directives:
            lines.append("## Directives")
            lines.append("")
            _append_bullets(lines, directives)
        constraints = blocking_constraints(unit.flow.enforcement_rules)
        if constraints:
            lines.append("## Constraints")
            lines.append("")
            _append_bullets(lines, constraints)

    if unit.concepts:
        lines.append("## Concepts")
        lines.append("")
        for concept in unit.concepts:
            lines.extend(_concept_lines(concept))

    lines.append("## References")
    lines.append("")
    lines.append(_bullet("`{}`".format(unit.source_path)))
    for concept in unit.concepts:
        lines.append(
            _bullet(
                "`{}` — {}".format(concept.source_document, concept.concept_id)
            )
        )
    lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def planned_files(always_on_units, skill_units):
    # type: (list, list) -> list
    """
    Return deterministic (relative_path, content, sources, kind) tuples.
    """
    planned = []
    if always_on_units:
        planned.append(
            (
                CLAUDE_MD_RELPATH,
                render_claude_md(always_on_units, skill_units),
                [unit.source_path for unit in always_on_units],
                "memory",
            )
        )
    for unit in skill_units:
        skill_id = skill_id_for_unit(unit)
        planned.append(
            (
                skill_relpath(skill_id),
                render_skill(unit),
                [unit.source_path],
                "skill",
            )
        )
    return planned
