"""Cursor bundle manifest generation."""

import re
from datetime import datetime
from pathlib import Path

SOURCE_RE = re.compile(
    r">\s*\*\*Source:\*\*\s*`(knowledge/[^`]+\.md)`"
)
CONCEPT_FILENAME_RE = re.compile(
    r"^concept-(ekp-(?:p(?:0[1-9]|10)|[a-z]{2}\d{2}))",
    re.IGNORECASE,
)

ADAPTER_NAME = "cursor"


def _concept_ids_from_rule(filename, content):
    # type: (str, str) -> list
    """Derive concept IDs for a generated rule file."""
    match = CONCEPT_FILENAME_RE.match(filename)
    if match:
        return [match.group(1).upper()]
    return []


def _source_from_rule(content):
    # type: (str) -> str
    """Extract the knowledge source path from a generated rule file."""
    match = SOURCE_RE.search(content)
    return match.group(1) if match else ""


def build_bundle_manifest(profile_name, cursor_dir, generated_at=None):
    # type: (str, Path, str) -> dict
    """Build a deterministic bundle manifest from generated .mdc files."""
    rules = []

    for mdc_path in sorted(cursor_dir.glob("*.mdc")):
        content = mdc_path.read_text(encoding="utf-8")
        rules.append(
            {
                "filename": mdc_path.name,
                "source": _source_from_rule(content),
                "concept_ids": _concept_ids_from_rule(mdc_path.name, content),
            }
        )

    timestamp = generated_at
    if timestamp is None:
        timestamp = datetime.utcnow().replace(microsecond=0).isoformat() + "Z"

    return {
        "profile": profile_name,
        "adapter": ADAPTER_NAME,
        "generated_at": timestamp,
        "rules_count": len(rules),
        "rules": rules,
    }
