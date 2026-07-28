"""Markdown extraction for EKP knowledge documents."""

import re
from typing import Dict, List, Optional

from .models import ConceptRule, DocumentFlow

CONCEPT_HEADING_RE = re.compile(
    r"^### (EKP-(?:[A-Z]{2}\d{2}|P(?:0[1-9]|10))):\s*(.+)$",
    re.MULTILINE,
)
DOCUMENT_TITLE_RE = re.compile(r"^# (.+)$", re.MULTILINE)
DECISION_FLOW_HEADING_RE = re.compile(
    r"^## (AI Decision Flow|Decision Flow)\s*$",
    re.MULTILINE,
)
ENFORCEMENT_HEADING_RE = re.compile(
    r"^(?:## Adapter enforcement table|\*\*Adapter enforcement:\*\*)\s*$",
    re.MULTILINE,
)
FIELD_RE = re.compile(
    r"^\*\*(Implements|Intent|Rules|Good|Bad|Review signals):\*\*\s*(.*)$",
    re.MULTILINE,
)
PRINCIPLE_ID_RE = re.compile(r"EKP-P(?:0[1-9]|10)")


def _normalize_enforcement_row(row):
    # type: (Dict[str, str]) -> Dict[str, str]
    """Normalize markdown table headers to stable keys."""
    normalized = {}
    for key, value in row.items():
        lowered = key.strip().lower().replace(" ", "_").replace("-", "_")
        normalized[lowered] = value.strip()
    return normalized


def _parse_markdown_table(lines):
    # type: (List[str]) -> List[Dict[str, str]]
    """Parse a markdown pipe table into a list of row dicts."""
    rows = []
    headers = None
    table_started = False

    for line in lines:
        stripped = line.strip()
        if not stripped:
            if not table_started:
                continue
            break

        if not stripped.startswith("|"):
            if not table_started:
                continue
            break

        table_started = True
        cells = [cell.strip() for cell in stripped.strip("|").split("|")]
        if headers is None:
            headers = cells
            continue

        if all(set(cell) <= set("-: ") for cell in cells):
            continue

        if len(cells) != len(headers):
            continue

        rows.append(_normalize_enforcement_row(dict(zip(headers, cells))))

    return rows


def _section_lines(markdown, start_index):
    # type: (str, int) -> List[str]
    """Return lines belonging to a section starting at start_index."""
    lines = markdown[start_index:].splitlines()
    section = []

    for line in lines:
        if line.startswith("## ") and not line.startswith("### "):
            break
        section.append(line)

    return section


def _parse_implements(value):
    # type: (str) -> List[str]
    """Extract EKP-P principle IDs from an Implements field value."""
    if not value:
        return []
    return sorted(set(PRINCIPLE_ID_RE.findall(value)))


def _parse_rules_block(body, rules_marker_end):
    # type: (str, int) -> List[str]
    """Parse bullet rules following a **Rules:** marker."""
    rules = []
    for line in body[rules_marker_end:].splitlines():
        stripped = line.strip()
        if stripped.startswith("- "):
            rules.append(stripped[2:].strip())
            continue
        if stripped == "" and rules:
            continue
        if stripped.startswith("**") and rules:
            break
        if stripped.startswith("---"):
            break
        if rules and not stripped.startswith("- "):
            break
    return rules


def _parse_concept_body(body):
    # type: (str) -> Dict[str, object]
    """Parse labeled fields from a concept section body."""
    parsed = {
        "implements": [],
        "intent": "",
        "rules": [],
        "good_examples": None,
        "bad_examples": None,
        "review_signals": None,
    }

    for match in FIELD_RE.finditer(body):
        label = match.group(1)
        inline_value = match.group(2).strip()
        start = match.end()

        if label == "Implements":
            value = inline_value
            if not value:
                next_line = body[start:].splitlines()
                value = next_line[0].strip() if next_line else ""
            parsed["implements"] = _parse_implements(value)
        elif label == "Intent":
            parsed["intent"] = inline_value
        elif label == "Rules":
            parsed["rules"] = _parse_rules_block(body, start)
        elif label == "Good":
            parsed["good_examples"] = inline_value or None
        elif label == "Bad":
            parsed["bad_examples"] = inline_value or None
        elif label == "Review signals":
            parsed["review_signals"] = inline_value or None

    return parsed


def _concept_section_end(markdown, start):
    # type: (str, int) -> int
    """Find the end index of a concept section."""
    lines = markdown[start:].splitlines()
    offset = 0

    for index, line in enumerate(lines):
        if index == 0:
            offset += len(line) + 1
            continue
        if line.startswith("### EKP-"):
            return start + offset - len(line) - 1
        if line.startswith("## ") and not line.startswith("### "):
            return start + offset - len(line) - 1
        offset += len(line) + 1

    return len(markdown)


def extract_concepts(markdown, source_path):
    # type: (str, str) -> List[ConceptRule]
    """
    Extract EKP concept sections from markdown.

    Detects headings of the form ``### EKP-XX##: Title`` and parses
    Implements, Intent, Rules, Good, Bad, and Review signals fields.
    """
    if not markdown or not markdown.strip():
        return []

    concepts = []
    matches = list(CONCEPT_HEADING_RE.finditer(markdown))

    for match in matches:
        concept_id = match.group(1)
        title = match.group(2).strip()
        body_start = match.end()
        body_end = _concept_section_end(markdown, body_start)
        body = markdown[body_start:body_end]
        fields = _parse_concept_body(body)

        concepts.append(
            ConceptRule(
                concept_id=concept_id,
                title=title,
                implements=fields["implements"],
                intent=fields["intent"],
                rules=fields["rules"],
                good_examples=fields["good_examples"],
                bad_examples=fields["bad_examples"],
                review_signals=fields["review_signals"],
                source_document=source_path,
            )
        )

    return concepts


def _extract_fenced_or_numbered_flow(section_lines):
    # type: (List[str]) -> str
    """Extract decision flow text from a fenced block or numbered list."""
    in_fence = False
    fence_lines = []
    numbered_lines = []

    for line in section_lines:
        stripped = line.strip()
        if stripped.startswith("```"):
            if in_fence:
                in_fence = False
                if fence_lines:
                    return "\n".join(fence_lines).strip()
                fence_lines = []
                continue
            in_fence = True
            continue

        if in_fence:
            fence_lines.append(line)
            continue

        if re.match(r"^\d+\.\s", stripped):
            numbered_lines.append(stripped)
            continue

        if numbered_lines and stripped.startswith("→"):
            numbered_lines.append(stripped)
            continue

        if numbered_lines and stripped == "":
            continue

        if numbered_lines and stripped.startswith("**"):
            break

    if fence_lines:
        return "\n".join(fence_lines).strip()
    if numbered_lines:
        return "\n".join(numbered_lines).strip()
    return ""


def _document_title(markdown):
    # type: (str) -> str
    """Extract the top-level document title from markdown."""
    match = DOCUMENT_TITLE_RE.search(markdown)
    return match.group(1).strip() if match else ""


def extract_adapter_enforcement(markdown):
    # type: (str) -> List[Dict[str, str]]
    """
    Extract adapter enforcement rows from markdown.

    Supports ``## Adapter enforcement table`` and ``**Adapter enforcement:**``
    headings followed by a pipe table with Step, Auto-apply, and Notes columns.
    """
    if not markdown or not markdown.strip():
        return []

    match = ENFORCEMENT_HEADING_RE.search(markdown)
    if not match:
        return []

    section = _section_lines(markdown, match.end())
    return _parse_markdown_table(section)


def extract_decision_flow(markdown, source_path):
    # type: (str, str) -> Optional[DocumentFlow]
    """
    Extract an AI Decision Flow section from markdown.

    Detects ``## AI Decision Flow`` or ``## Decision Flow`` headings and
    extracts fenced code blocks or numbered lists. Adapter enforcement rows
    are parsed from the same document when present.
    """
    if not markdown or not markdown.strip():
        return None

    match = DECISION_FLOW_HEADING_RE.search(markdown)
    if not match:
        return None

    section = _section_lines(markdown, match.end())
    decision_flow = _extract_fenced_or_numbered_flow(section)
    if not decision_flow:
        return None

    return DocumentFlow(
        document_path=source_path,
        title=_document_title(markdown),
        decision_flow=decision_flow,
        enforcement_rules=extract_adapter_enforcement(markdown),
        source_document=source_path,
    )
