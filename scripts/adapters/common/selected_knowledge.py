"""Selected knowledge units for non-Cursor adapters.

Reuses extract + selection. Filenames, grouping, and activation metadata
remain adapter-owned — this module does not invent tool frontmatter.
"""

import re

from common.extract import CONCEPT_HEADING_RE, extract_concepts, extract_decision_flow
from common.selection import (
    load_generation_indexes,
    markdown_cache_for_profile,
    select_manifest_rules,
)

ORCHESTRATOR_PATH = "knowledge/ai/ai-assisted-development.md"
FOUNDATION_PATH = "knowledge/engineering/engineering-principles.md"

KIND_ORCHESTRATOR = "orchestrator"
KIND_FOUNDATION = "foundation"
KIND_DOCUMENT = "document"

BLOCKING_AUTO_APPLY = ("block", "hard block")


class KnowledgeUnit(object):
    """One profile knowledge document with selected concepts and optional flow."""

    def __init__(
        self,
        source_path,
        title,
        kind,
        flow,
        concepts,
        extra_directives=None,
        extra_constraints=None,
    ):
        self.source_path = source_path
        self.title = title
        self.kind = kind
        self.flow = flow
        self.concepts = list(concepts or [])
        self.extra_directives = list(extra_directives or [])
        self.extra_constraints = list(extra_constraints or [])


def document_kind(source_path):
    # type: (str) -> str
    """Classify a knowledge path for adapter grouping."""
    if source_path == ORCHESTRATOR_PATH:
        return KIND_ORCHESTRATOR
    if source_path == FOUNDATION_PATH:
        return KIND_FOUNDATION
    return KIND_DOCUMENT


def blocking_constraints(enforcement_rules):
    # type: (list) -> list
    """Convert blocking adapter-enforcement rows into constraint strings."""
    constraints = []
    for row in enforcement_rules or []:
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


def flow_directive_lines(flow_text):
    # type: (str) -> list
    """Split a decision-flow body into non-empty directive lines."""
    directives = []
    for line in (flow_text or "").splitlines():
        stripped = line.strip()
        if stripped:
            directives.append(stripped)
    return directives


def collect_selected_units(profile, repo_root):
    # type: (dict, object) -> list
    """
    Build deterministic knowledge units for a loaded profile.

    High-priority concepts follow shared adapter-manifest selection.
    Decision flows are included whenever present on a profile document.
    """
    from common.paths import get_repo_root

    root = repo_root or get_repo_root()
    knowledge_paths = list(profile.get("knowledge") or [])
    if not knowledge_paths:
        raise ValueError("Profile has no resolved knowledge paths.")

    knowledge_set = set(knowledge_paths)
    if ORCHESTRATOR_PATH not in knowledge_set:
        raise ValueError("Profile must include orchestrator document.")

    concept_index, manifest = load_generation_indexes(root / "dist")
    get_markdown = markdown_cache_for_profile(root, knowledge_paths)
    manifest_rules = select_manifest_rules(
        manifest,
        knowledge_paths,
        profile.get("adapter_priorities") or ["high"],
    )

    selected_ids_by_source = {}
    for entry in manifest_rules:
        source_path = entry.get("source")
        concept_id = entry.get("concept")
        if not source_path or not concept_id:
            continue
        selected_ids_by_source.setdefault(source_path, []).append(concept_id)

    units = []
    for source_path in knowledge_paths:
        markdown = get_markdown(source_path)
        flow = extract_decision_flow(markdown, source_path)
        extracted = extract_concepts(markdown, source_path)
        by_id = {item.concept_id: item for item in extracted}
        concepts = []
        for concept_id in selected_ids_by_source.get(source_path, []):
            concept = by_id.get(concept_id)
            if concept is not None:
                concepts.append(concept)

        kind = document_kind(source_path)
        title = ""
        if flow is not None:
            title = flow.title
        if not title:
            title = _first_heading(markdown) or source_path

        if kind == KIND_ORCHESTRATOR and flow is None:
            raise ValueError("Orchestrator document missing AI Decision Flow.")

        if kind == KIND_DOCUMENT and flow is None and not concepts:
            continue

        extra_directives = []
        extra_constraints = []
        if kind == KIND_FOUNDATION:
            extra_directives, extra_constraints = foundation_content(markdown)

        units.append(
            KnowledgeUnit(
                source_path=source_path,
                title=title,
                kind=kind,
                flow=flow,
                concepts=concepts,
                extra_directives=extra_directives,
                extra_constraints=extra_constraints,
            )
        )

    # concept_index is loaded so generation fails closed if indexes are missing.
    _ = concept_index
    return units


def foundation_content(markdown):
    # type: (str) -> tuple
    """
    Extract compact engineering-principle directives.

    Cursor emits these via a dedicated foundation rule rather than adapter-
    manifest concept rows. Non-Cursor adapters reuse the same content here
    so foundation knowledge is not dropped.
    """
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

    constraints = [
        "Every technical decision must consider EKP-P01 through EKP-P10.",
        "Deviation requires documented rationale.",
    ]
    return directives, constraints


def _extract_section(markdown, heading):
    # type: (str, str) -> str
    """Extract a level-2 markdown section body."""
    match = re.search(
        r"^## " + re.escape(heading) + r"\s*$",
        markdown,
        re.MULTILINE,
    )
    if not match:
        return ""
    start = match.end()
    next_heading = re.search(r"^## ", markdown[start:], re.MULTILINE)
    end = start + next_heading.start() if next_heading else len(markdown)
    return markdown[start:end].strip()


def _first_heading(markdown):
    # type: (str) -> str
    """Return the first level-1 heading, if any."""
    for line in markdown.splitlines():
        stripped = line.strip()
        if stripped.startswith("# "):
            return stripped[2:].strip()
    return ""
