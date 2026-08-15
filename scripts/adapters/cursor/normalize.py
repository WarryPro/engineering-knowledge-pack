"""Normalize extracted knowledge into Cursor GeneratedRule objects."""

import re

from common.extract import CONCEPT_HEADING_RE
from common.models import GeneratedRule

from cursor.naming import (
    concept_filename,
    decision_flow_filename,
    foundation_filename,
    orchestrator_filename,
)

BLOCKING_AUTO_APPLY = ("block", "hard block")


def _extract_section(markdown, heading):
    # type: (str, str) -> str
    """Extract a level-2 markdown section body."""
    match = re.search(
        r"^## " + re.escape(heading) + r"\s*$", markdown, re.MULTILINE
    )
    if not match:
        return ""

    start = match.end()
    next_heading = re.search(r"^## ", markdown[start:], re.MULTILINE)
    end = start + next_heading.start() if next_heading else len(markdown)
    return markdown[start:end].strip()


def _enforcement_constraints(enforcement_rules):
    # type: (list) -> list
    """Convert adapter enforcement rows into constraint directives."""
    constraints = []
    for row in enforcement_rules:
        auto_apply = row.get("auto_apply", "").lower()
        if not any(token in auto_apply for token in BLOCKING_AUTO_APPLY):
            continue
        step = row.get("step", "Step")
        notes = row.get("notes", "")
        if notes:
            constraints.append(
                "Step {} — {}. {}".format(step, auto_apply, notes)
            )
        else:
            constraints.append("Step {} — {}.".format(step, auto_apply))
    return constraints


def _flow_directives(flow_text):
    # type: (str) -> list
    """Split a decision flow into directive lines."""
    directives = []
    for line in flow_text.splitlines():
        stripped = line.strip()
        if stripped:
            directives.append(stripped)
    return directives


def build_orchestrator_rule(flow):
    # type: (object) -> GeneratedRule
    """Build the always-on orchestrator GeneratedRule."""
    directives = _flow_directives(flow.decision_flow)
    constraints = _enforcement_constraints(flow.enforcement_rules)

    return GeneratedRule(
        name=orchestrator_filename(),
        description="EKP master AI decision flow — apply before any implementation",
        always_apply=True,
        directives=directives,
        constraints=constraints,
        references=[
            "`{}` — AI Decision Flow".format(flow.source_document),
            "`{}` — EKP-AI01 through EKP-AI12".format(flow.source_document),
        ],
    )


def build_foundation_rule(markdown, source_path):
    # type: (str, str) -> GeneratedRule
    """Build the always-on engineering principles GeneratedRule."""
    summary = _extract_section(markdown, "Summary")
    summary_lines = [
        line.strip()
        for line in summary.splitlines()
        if line.strip() and not line.strip().startswith("|")
    ]

    directives = []
    if summary_lines:
        directives.append(summary_lines[0])

    for match in CONCEPT_HEADING_RE.finditer(markdown):
        concept_id = match.group(1)
        if not concept_id.startswith("EKP-P"):
            continue

        title = match.group(2).strip()
        body_start = match.end()
        next_match = CONCEPT_HEADING_RE.search(markdown, body_start)
        body_end = next_match.start() if next_match else len(markdown)
        body = markdown[body_start:body_end].strip()

        first_paragraph = ""
        for line in body.splitlines():
            stripped = line.strip()
            if not stripped:
                continue
            if stripped.startswith("- ") or stripped.startswith("**"):
                break
            first_paragraph = stripped
            break

        directive = "{} — {}".format(concept_id, title)
        if first_paragraph:
            directive = "{} — {}".format(directive, first_paragraph)
        directives.append(directive)

    return GeneratedRule(
        name=foundation_filename(),
        description="EKP engineering principles — required decision framework",
        always_apply=True,
        directives=directives,
        constraints=[
            "Every technical decision must consider EKP-P01 through EKP-P10.",
            "Deviation requires documented rationale.",
        ],
        references=[
            "`{}` — Engineering Principles".format(source_path),
        ],
    )


def build_decision_flow_rule(flow, sequence):
    # type: (object, int) -> GeneratedRule
    """Build a document-level decision flow GeneratedRule."""
    directives = _flow_directives(flow.decision_flow)
    constraints = _enforcement_constraints(flow.enforcement_rules)

    return GeneratedRule(
        name=decision_flow_filename(flow.document_path, sequence),
        description="EKP decision flow — {}".format(flow.title),
        always_apply=False,
        directives=directives,
        constraints=constraints,
        references=["`{}` — AI Decision Flow".format(flow.source_document)],
    )


def build_concept_rule(concept, concept_index_entry):
    # type: (object, dict) -> tuple
    """Build a concept-level GeneratedRule and optional preferences."""
    concept_id = concept.concept_id
    title = concept.title
    description = "{} — {}".format(concept_id, title)

    directives = []
    if concept.intent:
        directives.append(concept.intent)
    directives.extend(concept.rules)

    constraints = []
    preferences = []

    if concept.good_examples:
        preferences.append("Good: {}".format(concept.good_examples))
    if concept.bad_examples:
        preferences.append("Bad: {}".format(concept.bad_examples))

    if concept_id == "EKP-AI08":
        constraints = list(concept.rules)
        directives = [concept.intent] if concept.intent else []

    references = ["`{}` — {}".format(concept.source_document, concept_id)]
    if concept.implements:
        references.append("Implements: {}".format(", ".join(concept.implements)))

    severity = concept_index_entry.get("severity")
    if severity:
        references.append("Severity: {}".format(severity))

    rule = GeneratedRule(
        name=concept_filename(concept_id, title),
        description=description,
        always_apply=False,
        directives=directives,
        constraints=constraints,
        references=references,
    )
    return rule, preferences
