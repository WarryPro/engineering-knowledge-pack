"""Claude bundle verification.

File generation does **not** prove Claude Code skill auto-invocation or
runtime loading. Verification covers packaging structure, provenance,
determinism inputs, and cross-adapter leakage only.
"""

import json
import re
from pathlib import Path

from claude.grouping import CLAUDE_MD_RELPATH, SKILLS_DIR
from claude.manifest import MANIFEST_NAME

ADAPTER_NAME = "claude"
FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)
NAME_RE = re.compile(r"^name:\s*(.+)\s*$", re.MULTILINE)
DESCRIPTION_RE = re.compile(r"^description:\s*(.+)\s*$", re.MULTILINE)

LEAKAGE = (
    "alwaysApply:",
    "always_apply:",
    "applyTo:",
)


class ClaudeVerifyError(Exception):
    """Raised when Claude bundle verification fails."""


def _relative_files(adapter_dir):
    # type: (Path) -> list
    files = []
    if not adapter_dir.is_dir():
        return files
    for path in sorted(adapter_dir.rglob("*")):
        if path.is_file():
            files.append(path)
    return files


def verify_claude_bundle(bundle_dir):
    # type: (Path) -> None
    """Verify generated Claude output under ``bundle_dir/claude/``."""
    errors = []
    adapter_dir = Path(bundle_dir) / ADAPTER_NAME
    if not adapter_dir.is_dir():
        raise ClaudeVerifyError(
            "Missing claude output directory: {}".format(adapter_dir)
        )

    claude_md = adapter_dir / CLAUDE_MD_RELPATH
    if not claude_md.is_file():
        errors.append("Missing CLAUDE.md")
    else:
        content = claude_md.read_text(encoding="utf-8")
        line_count = len(content.splitlines())
        if line_count > 250:
            errors.append(
                "CLAUDE.md has {} lines; expected a compact always-on file".format(
                    line_count
                )
            )
        if content.lstrip().startswith("---"):
            errors.append("CLAUDE.md must not use YAML frontmatter")
        if "> **Source:**" not in content:
            errors.append("CLAUDE.md: missing Source reference")
        for leak in LEAKAGE:
            if leak in content:
                errors.append("CLAUDE.md: cross-adapter leakage ({})".format(leak))

    skills_root = adapter_dir / SKILLS_DIR
    if not skills_root.is_dir():
        errors.append("Missing skills directory: {}".format(SKILLS_DIR))

    # Pathless rules are forbidden for Claude v1.
    rules_dir = adapter_dir / ".claude" / "rules"
    if rules_dir.exists():
        errors.append(
            "Claude v1 must not generate pathless .claude/rules/ (found {})".format(
                rules_dir
            )
        )

    generated = []
    skill_files = []
    for path in _relative_files(adapter_dir):
        rel = path.relative_to(adapter_dir).as_posix()
        if rel == MANIFEST_NAME:
            continue
        generated.append(rel)
        content = path.read_text(encoding="utf-8")

        for leak in LEAKAGE:
            if leak in content and rel != CLAUDE_MD_RELPATH:
                errors.append("{}: cross-adapter leakage ({})".format(rel, leak))

        if rel == CLAUDE_MD_RELPATH:
            continue

        if not rel.startswith(SKILLS_DIR + "/"):
            errors.append("{}: unexpected Claude path".format(rel))
            continue

        if not rel.endswith("/SKILL.md"):
            errors.append("{}: skill files must be named SKILL.md".format(rel))
            continue

        skill_files.append(rel)
        match = FRONTMATTER_RE.match(content)
        if not match:
            errors.append("{}: missing YAML frontmatter".format(rel))
            continue
        front = match.group(1)
        if not NAME_RE.search(front):
            errors.append("{}: frontmatter missing name".format(rel))
        desc = DESCRIPTION_RE.search(front)
        if not desc or not desc.group(1).strip().strip('"'):
            errors.append("{}: frontmatter missing usable description".format(rel))
        if "alwaysApply" in front or "applyTo" in front:
            errors.append("{}: forbidden adapter metadata in frontmatter".format(rel))
        if "> **Source:**" not in content:
            errors.append("{}: missing Source reference".format(rel))

    if not skill_files:
        errors.append("No Claude skills generated under {}".format(SKILLS_DIR))

    manifest_path = adapter_dir / MANIFEST_NAME
    if not manifest_path.is_file():
        errors.append("Missing adapter manifest: {}".format(manifest_path))
    else:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if manifest.get("adapter") != ADAPTER_NAME:
            errors.append(
                "Manifest adapter must be 'claude', got {!r}".format(
                    manifest.get("adapter")
                )
            )
        manifest_paths = sorted(
            entry.get("path", "") for entry in manifest.get("files", [])
        )
        disk_paths = sorted(generated)
        if manifest_paths != disk_paths:
            errors.append("Manifest file list does not match generated files.")
        if manifest.get("files_count") != len(disk_paths):
            errors.append("Manifest files_count does not match generated file count.")
        for entry in manifest.get("files", []):
            if not entry.get("sources"):
                errors.append(
                    "{}: manifest entry missing sources".format(
                        entry.get("path", "?")
                    )
                )
            kind = entry.get("kind")
            path = entry.get("path", "")
            if path == CLAUDE_MD_RELPATH and kind != "memory":
                errors.append("CLAUDE.md manifest kind must be 'memory'")
            if path.startswith(SKILLS_DIR + "/") and kind != "skill":
                errors.append("{}: skill manifest kind must be 'skill'".format(path))

    if errors:
        raise ClaudeVerifyError("\n".join(errors))
