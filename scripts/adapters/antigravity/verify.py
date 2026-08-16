"""Antigravity bundle verification.

File generation does **not** prove Antigravity activation. Official docs
did not establish a file-based Always On / Manual / Model Decision / Glob
frontmatter contract. A human must run the empirical activation check
documented in ``docs/adapter-architecture.md``.
"""

import json
from pathlib import Path

from antigravity.grouping import (
    FOUNDATION_FILENAME,
    MAX_RULE_CHARS,
    ORCHESTRATOR_FILENAME,
    RULES_DIR,
)
from antigravity.manifest import MANIFEST_NAME

ADAPTER_NAME = "antigravity"
CURSOR_LEAKAGE = ("alwaysApply:", "always_apply:")


class AntigravityVerifyError(Exception):
    """Raised when Antigravity bundle verification fails."""


def _relative_files(adapter_dir):
    # type: (Path) -> list
    files = []
    if not adapter_dir.is_dir():
        return files
    for path in sorted(adapter_dir.rglob("*")):
        if path.is_file():
            files.append(path)
    return files


def verify_antigravity_bundle(bundle_dir):
    # type: (Path) -> None
    """Verify generated Antigravity output under ``bundle_dir/antigravity/``."""
    errors = []
    adapter_dir = Path(bundle_dir) / ADAPTER_NAME
    rules_dir = adapter_dir / RULES_DIR
    if not rules_dir.is_dir():
        raise AntigravityVerifyError(
            "Missing Antigravity rules directory: {}".format(rules_dir)
        )

    orchestrator = rules_dir / ORCHESTRATOR_FILENAME
    if not orchestrator.is_file():
        errors.append("Missing orchestrator rule: {}".format(ORCHESTRATOR_FILENAME))

    foundation = rules_dir / FOUNDATION_FILENAME
    if not foundation.is_file():
        errors.append("Missing foundation rule: {}".format(FOUNDATION_FILENAME))

    generated = []
    for path in _relative_files(adapter_dir):
        rel = path.relative_to(adapter_dir).as_posix()
        if rel == MANIFEST_NAME:
            continue
        generated.append(rel)
        content = path.read_text(encoding="utf-8")

        if not rel.startswith("{}/".format(RULES_DIR)):
            errors.append("{}: unexpected Antigravity path".format(rel))
            continue
        if not path.name.endswith(".md"):
            errors.append("{}: rule files must use .md".format(rel))

        if len(content) >= MAX_RULE_CHARS:
            errors.append(
                "{}: {} characters exceeds {} limit".format(
                    rel, len(content), MAX_RULE_CHARS
                )
            )

        if content.lstrip().startswith("---"):
            errors.append(
                "{}: invented YAML frontmatter is not allowed".format(rel)
            )

        for leak in CURSOR_LEAKAGE:
            if leak in content:
                errors.append("{}: Cursor metadata leakage ({})".format(rel, leak))

        if "> **Source:**" not in content:
            errors.append("{}: missing Source reference".format(rel))

    if not generated:
        errors.append("No Antigravity rule files generated in {}".format(rules_dir))

    manifest_path = adapter_dir / MANIFEST_NAME
    if not manifest_path.is_file():
        errors.append("Missing adapter manifest: {}".format(manifest_path))
    else:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if manifest.get("adapter") != ADAPTER_NAME:
            errors.append(
                "Manifest adapter must be 'antigravity', got {!r}".format(
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

    if errors:
        raise AntigravityVerifyError("\n".join(errors))
