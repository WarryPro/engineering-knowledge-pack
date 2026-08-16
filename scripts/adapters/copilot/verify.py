"""Copilot bundle verification."""

import json
import re
from pathlib import Path

from copilot.grouping import COPILOT_INSTRUCTIONS_RELPATH
from copilot.manifest import MANIFEST_NAME

ADAPTER_NAME = "copilot"
FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)
APPLY_TO_RE = re.compile(r"^applyTo:\s*\"([^\"]+)\"\s*$", re.MULTILINE)
INSTRUCTIONS_SUFFIX = ".instructions.md"
CURSOR_LEAKAGE = ("alwaysApply:", "always_apply:")


class CopilotVerifyError(Exception):
    """Raised when Copilot bundle verification fails."""


def _relative_files(adapter_dir):
    # type: (Path) -> list
    files = []
    if not adapter_dir.is_dir():
        return files
    for path in sorted(adapter_dir.rglob("*")):
        if path.is_file():
            files.append(path)
    return files


def verify_copilot_bundle(bundle_dir):
    # type: (Path) -> None
    """
    Verify generated Copilot output under ``bundle_dir/copilot/``.

    Does not claim Copilot product behavior — only generated tree integrity.
    """
    errors = []
    adapter_dir = Path(bundle_dir) / ADAPTER_NAME
    if not adapter_dir.is_dir():
        raise CopilotVerifyError(
            "Missing copilot output directory: {}".format(adapter_dir)
        )

    always_on = adapter_dir / COPILOT_INSTRUCTIONS_RELPATH
    if not always_on.is_file():
        errors.append(
            "Missing repository-wide instructions: {}".format(
                COPILOT_INSTRUCTIONS_RELPATH
            )
        )

    generated = []
    for path in _relative_files(adapter_dir):
        rel = path.relative_to(adapter_dir).as_posix()
        if rel == MANIFEST_NAME:
            continue
        generated.append(rel)

        content = path.read_text(encoding="utf-8")
        for leak in CURSOR_LEAKAGE:
            if leak in content:
                errors.append("{}: Cursor metadata leakage ({})".format(rel, leak))

        if "> **Source:**" not in content and "knowledge/" not in content:
            errors.append("{}: missing Source reference".format(rel))

        if rel == COPILOT_INSTRUCTIONS_RELPATH:
            if content.startswith("---"):
                errors.append(
                    "{}: repository-wide instructions must not use frontmatter".format(
                        rel
                    )
                )
            continue

        if not rel.startswith(".github/instructions/"):
            errors.append("{}: unexpected Copilot path".format(rel))
            continue

        if not path.name.endswith(INSTRUCTIONS_SUFFIX):
            errors.append(
                "{}: path-specific files must use {}".format(rel, INSTRUCTIONS_SUFFIX)
            )
            continue

        match = FRONTMATTER_RE.match(content)
        if not match:
            errors.append("{}: missing YAML frontmatter".format(rel))
            continue
        if not APPLY_TO_RE.search(match.group(1)):
            errors.append("{}: frontmatter missing applyTo".format(rel))
        if "alwaysApply" in match.group(1):
            errors.append("{}: Cursor alwaysApply must not appear".format(rel))

    if not generated:
        errors.append("No Copilot instruction files generated in {}".format(adapter_dir))

    manifest_path = adapter_dir / MANIFEST_NAME
    if not manifest_path.is_file():
        errors.append("Missing adapter manifest: {}".format(manifest_path))
    else:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if manifest.get("adapter") != ADAPTER_NAME:
            errors.append(
                "Manifest adapter must be 'copilot', got {!r}".format(
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

    expected_prefixes = (".github/",)
    for rel in generated:
        if rel != COPILOT_INSTRUCTIONS_RELPATH and not any(
            rel.startswith(prefix) for prefix in expected_prefixes
        ):
            errors.append("{}: unexpected file".format(rel))

    if errors:
        raise CopilotVerifyError("\n".join(errors))
