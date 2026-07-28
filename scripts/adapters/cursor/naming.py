"""Deterministic filenames for generated Cursor rules."""

import re

STOP_WORDS = {
    "a",
    "an",
    "and",
    "as",
    "at",
    "before",
    "for",
    "in",
    "of",
    "or",
    "over",
    "the",
    "to",
    "with",
}

DOCUMENT_CODES = {
    "knowledge/engineering/refactoring.md": "rf",
    "knowledge/testing/testing.md": "ts",
    "knowledge/engineering/error-handling.md": "eh",
    "knowledge/architecture/layering-and-boundaries.md": "lb",
}


def slugify_title(title, max_words=3):
    # type: (str, int) -> str
    """Convert a concept title into a short deterministic slug."""
    words = re.sub(r"[^a-zA-Z0-9\s]", "", title.lower()).split()
    filtered = [word for word in words if word not in STOP_WORDS]
    if not filtered:
        filtered = words
    return "-".join(filtered[:max_words]) or "rule"


def orchestrator_filename():
    # type: () -> str
    """Filename for the always-on AI orchestrator rule."""
    return "00-ekp-orchestrator.mdc"


def foundation_filename():
    # type: () -> str
    """Filename for the always-on engineering principles rule."""
    return "01-ekp-foundation.mdc"


def decision_flow_filename(document_path, sequence):
    # type: (str, int) -> str
    """Filename for a document-level AI Decision Flow rule."""
    code = DOCUMENT_CODES.get(document_path)
    if code is None:
        stem = document_path.split("/")[-1].replace(".md", "")
        code = re.sub(r"[^a-z0-9]+", "-", stem.lower()).strip("-")
    return "{:02d}-ekp-{}-decision-flow.mdc".format(sequence, code)


def concept_filename(concept_id, title):
    # type: (str, str) -> str
    """Filename for a concept-level rule."""
    return "concept-{}-{}.mdc".format(concept_id.lower(), slugify_title(title))
