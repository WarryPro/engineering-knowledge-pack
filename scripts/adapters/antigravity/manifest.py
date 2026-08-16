"""Antigravity adapter-manifest generation."""

from datetime import datetime
from pathlib import Path

ADAPTER_NAME = "antigravity"
MANIFEST_NAME = "adapter-manifest.json"

SKIP_NAMES = {MANIFEST_NAME}


def _relative_files(adapter_dir):
    # type: (Path) -> list
    files = []
    if not adapter_dir.is_dir():
        return files
    for path in sorted(adapter_dir.rglob("*")):
        if not path.is_file():
            continue
        if path.name in SKIP_NAMES:
            continue
        files.append(path)
    return files


def _sources_from_content(content):
    # type: (str) -> list
    sources = []
    for line in content.splitlines():
        marker = "> **Source:** `"
        if marker not in line:
            continue
        start = line.find(marker) + len(marker)
        end = line.find("`", start)
        if end == -1:
            continue
        source = line[start:end]
        if source not in sources:
            sources.append(source)
    return sources


def build_adapter_manifest(profile_name, adapter_dir, generated_at=None):
    # type: (str, Path, str) -> dict
    """Build an Antigravity adapter manifest from generated rule files."""
    files = []
    for path in _relative_files(adapter_dir):
        content = path.read_text(encoding="utf-8")
        files.append(
            {
                "path": path.relative_to(adapter_dir).as_posix(),
                "char_count": len(content),
                "sources": _sources_from_content(content),
            }
        )

    timestamp = generated_at
    if timestamp is None:
        timestamp = datetime.utcnow().replace(microsecond=0).isoformat() + "Z"

    return {
        "profile": profile_name,
        "adapter": ADAPTER_NAME,
        "generated_at": timestamp,
        "files_count": len(files),
        "files": files,
    }


build_manifest = build_adapter_manifest
