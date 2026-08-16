"""Copilot file grouping — adapter-owned, not a 1:1 Cursor rule dump.

Strategy
--------
1. Always-on repository instructions go to
   ``.github/copilot-instructions.md`` (no ``applyTo``).
   Includes orchestrator, foundation, and any knowledge document that is
   not assigned to a path-specific group.

2. Path-specific ``.github/instructions/<name>.instructions.md`` files are
   emitted **only** when the profile's resolved knowledge includes a
   matching domain prefix. They exist because those domains have a clear
   consumer path (tests, PHP, TypeScript, …), not to mirror Cursor's
   per-concept ``.mdc`` count.

3. Copilot skills are out of scope for AI30B.
"""

from common.selected_knowledge import KIND_DOCUMENT

COPILOT_INSTRUCTIONS_RELPATH = ".github/copilot-instructions.md"
INSTRUCTIONS_DIR = ".github/instructions"

# First matching prefix wins. Keep this list stable — filenames are part of
# the Copilot adapter contract.
PATH_GROUPS = (
    {
        "name": "php",
        "filename": "php.instructions.md",
        "prefixes": ("knowledge/php/",),
        "apply_to": "**/*.php",
    },
    {
        "name": "symfony",
        "filename": "symfony.instructions.md",
        "prefixes": ("knowledge/symfony/",),
        "apply_to": "**/*.php,**/*.twig,**/*.yaml,**/*.yml",
    },
    {
        "name": "typescript",
        "filename": "typescript.instructions.md",
        "prefixes": ("knowledge/typescript/",),
        "apply_to": "**/*.ts,**/*.tsx",
    },
    {
        "name": "frontend",
        "filename": "frontend.instructions.md",
        "prefixes": ("knowledge/frontend/",),
        "apply_to": "**/*.{js,jsx,ts,tsx,css,scss,html,vue}",
    },
    {
        "name": "devops",
        "filename": "devops.instructions.md",
        "prefixes": ("knowledge/devops/",),
        "apply_to": "**/{Dockerfile,docker-compose*.yml,docker-compose*.yaml},**/.github/workflows/**,**/*.{yml,yaml}",
    },
    {
        "name": "testing",
        "filename": "testing.instructions.md",
        "prefixes": ("knowledge/testing/",),
        "apply_to": "**/{test,tests,spec,specs}/**,**/*.{test,spec}.*",
    },
)


def matching_group(source_path):
    # type: (str) -> dict
    """Return the path group for a knowledge path, or None."""
    for group in PATH_GROUPS:
        for prefix in group["prefixes"]:
            if source_path.startswith(prefix):
                return group
    return None


def partition_units(units):
    # type: (list) -> tuple
    """
    Split units into always-on vs named path groups.

    Returns (always_on_units, {group_name: [units]}).
    Path groups with no matching units are omitted.
    """
    always_on = []
    grouped = {}
    for unit in units:
        group = None
        if unit.kind == KIND_DOCUMENT:
            group = matching_group(unit.source_path)
        if group is None:
            always_on.append(unit)
            continue
        grouped.setdefault(group["name"], []).append(unit)
    return always_on, grouped


def group_by_name(name):
    # type: (str) -> dict
    """Look up a PATH_GROUPS entry by name."""
    for group in PATH_GROUPS:
        if group["name"] == name:
            return group
    raise KeyError("Unknown Copilot path group: {}".format(name))


def instruction_relpath(filename):
    # type: (str) -> str
    """Return the adapter-relative path for a path-specific instruction file."""
    return "{}/{}".format(INSTRUCTIONS_DIR, filename)
