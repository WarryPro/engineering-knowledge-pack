"""ADR index validation."""

import re
from pathlib import Path

ADR_INDEX_PATH = "knowledge/architecture/decisions/README.md"
ADR_LINK_RE = re.compile(r"\]\((adr-[^)]+\.md)\)")


def validate_adr_index(repo_root):
    # type: (Path) -> list
    """Every adr-*.md must appear in decisions/README.md index."""
    errors = []
    decisions_dir = repo_root / "knowledge" / "architecture" / "decisions"
    index_path = repo_root / ADR_INDEX_PATH

    if not decisions_dir.is_dir():
        return errors

    adr_files = sorted(
        path.name
        for path in decisions_dir.glob("adr-*.md")
    )

    if not index_path.is_file():
        for adr_name in adr_files:
            errors.append("[ADR] ADR missing from index: {}".format(adr_name))
        return errors

    index_content = index_path.read_text(encoding="utf-8")
    indexed = set(ADR_LINK_RE.findall(index_content))

    for adr_name in adr_files:
        if adr_name not in indexed:
            errors.append("[ADR] ADR missing from index: {}".format(adr_name))

    return errors
