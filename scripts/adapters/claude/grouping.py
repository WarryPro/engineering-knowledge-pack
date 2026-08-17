"""Claude file grouping — CLAUDE.md + document-grouped Skills.

Strategy
--------
1. Always-on material (orchestrator + foundation) goes to ``CLAUDE.md``.
   Official Claude Code guidance targets under ~200 lines for adherence;
   detailed procedures do **not** belong here.

2. Each remaining knowledge document becomes one Skill under
   ``.claude/skills/<skill-id>/SKILL.md``. Skills are document-grouped,
   not 1:1 Cursor concept dumps.

3. Pathless ``.claude/rules/*.md`` are intentionally **not** generated
   (they load at session start and would recreate always-on context bloat).

4. Skill IDs are deterministic. Stable aliases keep consumer-facing names
   short where document stems are long (e.g. layering-and-boundaries →
   ``ekp-layering``).
"""

from common.selected_knowledge import KIND_DOCUMENT, KIND_FOUNDATION, KIND_ORCHESTRATOR

CLAUDE_MD_RELPATH = "CLAUDE.md"
SKILLS_DIR = ".claude/skills"
SKILL_FILENAME = "SKILL.md"

# Optional short aliases for long document stems (stable Claude skill contract).
SKILL_ID_ALIASES = {
    "knowledge/architecture/layering-and-boundaries.md": "ekp-layering",
}


def document_stem(source_path):
    # type: (str) -> str
    """Deterministic filesystem stem from a knowledge path."""
    name = source_path.rsplit("/", 1)[-1]
    if name.endswith(".md"):
        name = name[:-3]
    return name.replace("_", "-")


def skill_id_for_unit(unit):
    # type: (object) -> str
    """Return the deterministic Claude skill directory id for a document unit."""
    alias = SKILL_ID_ALIASES.get(unit.source_path)
    if alias:
        return alias
    return "ekp-{}".format(document_stem(unit.source_path))


def skill_relpath(skill_id):
    # type: (str) -> str
    """Return adapter-relative path for a skill SKILL.md."""
    return "{}/{}/{}".format(SKILLS_DIR, skill_id, SKILL_FILENAME)


def partition_units(units):
    # type: (list) -> tuple
    """
    Split units into always-on vs skill documents.

    Returns (always_on_units, skill_units).
    Orchestrator and foundation are always-on. Document units become skills.
    """
    always_on = []
    skills = []
    for unit in units:
        if unit.kind in (KIND_ORCHESTRATOR, KIND_FOUNDATION):
            always_on.append(unit)
        elif unit.kind == KIND_DOCUMENT:
            skills.append(unit)
    return always_on, skills
