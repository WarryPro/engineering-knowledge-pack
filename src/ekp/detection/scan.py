"""Filesystem scan helpers for deterministic local detection."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable, List, Optional, Set

IGNORED_DIR_NAMES = frozenset(
    {
        ".git",
        "vendor",
        "node_modules",
        "dist",
        "build",
        "coverage",
        ".cache",
        ".pytest_cache",
        "__pycache__",
        ".venv",
        "venv",
        ".dart_tool",
        ".gradle",
        "ios",
        "android",
        "build",
        ".ekp",
    }
)

SOURCE_DIR_NAMES = ("src", "app", "lib", "tests", "test", "spec")


def resolve_scan_root(path: Optional[str]) -> Path:
    """Resolve and validate the project directory to scan."""
    target = Path(path or ".").resolve()
    if not target.exists():
        raise FileNotFoundError("Path does not exist: {}".format(target))
    if not target.is_dir():
        raise NotADirectoryError("Path is not a directory: {}".format(target))
    return target


def read_json_file(path: Path, diagnostics: List[str]) -> Optional[dict]:
    """Read JSON metadata safely."""
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        diagnostics.append("{}: {}".format(path.name, exc))
        return None


def read_text_lines(path: Path, diagnostics: List[str]) -> Optional[str]:
    """Read a small text file safely."""
    if not path.is_file():
        return None
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        diagnostics.append("{}: {}".format(path.name, exc))
        return None


def path_exists(root: Path, *parts: str) -> bool:
    return (root.joinpath(*parts)).exists()


def count_limited_files(root: Path, suffix: str, limit: int = 20) -> int:
    """Count files with suffix under conventional dirs without deep walks."""
    count = 0
    for base in _scan_bases(root):
        if not base.is_dir():
            continue
        for path in base.rglob("*{}".format(suffix)):
            if any(part in IGNORED_DIR_NAMES for part in path.parts):
                continue
            if path.is_file():
                count += 1
                if count >= limit:
                    return count
    return count


def _scan_bases(root: Path) -> Iterable[Path]:
    yield root
    for name in SOURCE_DIR_NAMES:
        candidate = root / name
        if candidate.is_dir():
            yield candidate


def dependency_names(package_data: Optional[dict]) -> Set[str]:
    names: Set[str] = set()
    if not isinstance(package_data, dict):
        return names
    for section in ("dependencies", "devDependencies", "peerDependencies"):
        deps = package_data.get(section)
        if isinstance(deps, dict):
            names.update(str(key).lower() for key in deps)
    return names


def composer_require_names(composer_data: Optional[dict]) -> Set[str]:
    names: Set[str] = set()
    if not isinstance(composer_data, dict):
        return names
    for section in ("require", "require-dev"):
        deps = composer_data.get(section)
        if isinstance(deps, dict):
            names.update(str(key).lower() for key in deps)
    return names
