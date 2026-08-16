"""Antigravity file grouping — adapter-owned, not a 1:1 Cursor rule dump.

Strategy
--------
1. One Markdown file per selected knowledge document under
   ``.agents/rules/``. Orchestrator and foundation keep stable names;
   remaining documents use a deterministic numeric prefix plus the
   document stem.

2. Files are plain Markdown. This adapter does **not** invent YAML
   activation frontmatter (no Always On / Manual / Model Decision / Glob
   contract has been established in official Antigravity file format
   docs). Activation must be checked empirically in a real workspace.

3. Each file must stay under ``MAX_RULE_CHARS`` (12,000). If a document
   would exceed the split threshold, it is split on concept boundaries
   into ``<stem>-partN.md``.

4. Skills and workflows are out of scope for AI30B.
"""

from common.selected_knowledge import KIND_FOUNDATION, KIND_ORCHESTRATOR

RULES_DIR = ".agents/rules"
MAX_RULE_CHARS = 12000
SPLIT_THRESHOLD_CHARS = 11000

ORCHESTRATOR_FILENAME = "00-orchestrator.md"
FOUNDATION_FILENAME = "01-foundation.md"
DOCUMENT_SEQUENCE_START = 10


def document_stem(source_path):
    # type: (str) -> str
    """Deterministic filesystem stem from a knowledge path."""
    name = source_path.rsplit("/", 1)[-1]
    if name.endswith(".md"):
        name = name[:-3]
    return name.replace("_", "-")


def filename_for_unit(unit, document_sequence):
    # type: (object, int) -> str
    """Return the base filename for a knowledge unit (before part splits)."""
    if unit.kind == KIND_ORCHESTRATOR:
        return ORCHESTRATOR_FILENAME
    if unit.kind == KIND_FOUNDATION:
        return FOUNDATION_FILENAME
    return "{:02d}-{}.md".format(document_sequence, document_stem(unit.source_path))


def part_filename(base_filename, part_index):
    # type: (str, int) -> str
    """Return a split-part filename. Part indexes are 1-based."""
    if not base_filename.endswith(".md"):
        raise ValueError("Antigravity rule filename must end with .md")
    stem = base_filename[:-3]
    return "{}-part{}.md".format(stem, part_index)


def assign_filenames(units):
    # type: (list) -> list
    """
    Pair units with deterministic base filenames.

    Returns a list of (unit, base_filename).
    """
    assigned = []
    sequence = DOCUMENT_SEQUENCE_START
    for unit in units:
        name = filename_for_unit(unit, sequence)
        if unit.kind not in (KIND_ORCHESTRATOR, KIND_FOUNDATION):
            sequence += 1
        assigned.append((unit, name))
    return assigned
