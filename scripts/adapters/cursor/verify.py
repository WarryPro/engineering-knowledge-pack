"""Cursor bundle verification."""

import json
import re
from pathlib import Path

from cursor.naming import orchestrator_filename

FRONTMATTER_RE = re.compile(r"^---\s*\n.*?\n---\s*\n", re.DOTALL)


class CursorVerifyError(Exception):
    """Raised when Cursor bundle verification fails."""


def verify_cursor_bundle(bundle_dir):
    # type: (Path) -> None
    """
    Verify generated Cursor bundle integrity.

    Expects ``bundle_dir/cursor/*.mdc`` and ``bundle_dir/bundle-manifest.json``.
    """
    errors = []
    cursor_dir = bundle_dir / "cursor"
    manifest_path = bundle_dir / "bundle-manifest.json"

    if not cursor_dir.is_dir():
        errors.append("Missing cursor output directory: {}".format(cursor_dir))
        raise CursorVerifyError("\n".join(errors))

    mdc_files = sorted(cursor_dir.glob("*.mdc"))
    if not mdc_files:
        errors.append("No .mdc files generated in {}".format(cursor_dir))

    orchestrator = cursor_dir / orchestrator_filename()
    if not orchestrator.is_file():
        errors.append(
            "Missing orchestrator rule: {}".format(orchestrator.name)
        )

    for mdc_path in mdc_files:
        content = mdc_path.read_text(encoding="utf-8")
        if not FRONTMATTER_RE.match(content):
            errors.append("{}: missing YAML frontmatter".format(mdc_path.name))
        if "> **Source:**" not in content:
            errors.append("{}: missing Source reference".format(mdc_path.name))

    if not manifest_path.is_file():
        errors.append("Missing bundle manifest: {}".format(manifest_path))
    else:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest_names = sorted(
            rule["filename"] for rule in manifest.get("rules", [])
        )
        disk_names = sorted(path.name for path in mdc_files)

        if manifest_names != disk_names:
            errors.append("Manifest filenames do not match generated files.")

        if manifest.get("rules_count") != len(disk_names):
            errors.append(
                "Manifest rules_count does not match generated file count."
            )

        if manifest.get("adapter") != "cursor":
            errors.append(
                "Manifest adapter must be 'cursor', got {!r}".format(
                    manifest.get("adapter")
                )
            )

        for rule in manifest.get("rules", []):
            if not rule.get("source"):
                errors.append(
                    "{}: manifest entry missing source".format(
                        rule.get("filename", "?")
                    )
                )

    if errors:
        raise CursorVerifyError("\n".join(errors))
