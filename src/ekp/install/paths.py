"""Project path safety helpers for install."""

from __future__ import annotations

from pathlib import Path
from typing import Optional


def resolve_project_root(path: str) -> Path:
    """Resolve and validate a consumer project root directory."""
    candidate = Path(path).expanduser()
    if not candidate.exists():
        raise FileNotFoundError("Project path does not exist: {}".format(path))
    if not candidate.is_dir():
        raise NotADirectoryError("Project path is not a directory: {}".format(path))
    return candidate.resolve()


def relative_posix_path(relative: str) -> str:
    """Normalize a relative path to forward-slash POSIX form."""
    parts = Path(relative).parts
    if not parts or any(part in (".", "..") for part in parts):
        raise ValueError("Unsafe relative path: {}".format(relative))
    return "/".join(parts)


def resolve_under_root(project_root: Path, relative: str) -> Path:
    """Resolve a relative consumer path and ensure it stays inside project_root."""
    normalized = relative_posix_path(relative)
    target = (project_root / normalized).resolve()
    root = project_root.resolve()
    try:
        target.relative_to(root)
    except ValueError as exc:
        raise ValueError(
            "Path escapes project root: {} -> {}".format(relative, target)
        ) from exc
    return target


def check_symlink_boundary(project_root: Path, relative: str) -> Optional[str]:
    """
    Reject symlinked deployment path components that resolve outside project_root.

    Returns an error message when unsafe, otherwise None.
    """
    root = project_root.resolve()
    current = root
    for part in Path(relative).parts:
        if part in (".", ".."):
            return "Unsafe path component in {}: {}".format(relative, part)
        current = current / part
        if current.is_symlink():
            resolved = current.resolve()
            try:
                resolved.relative_to(root)
            except ValueError:
                return "Symlink escapes project root: {}".format(relative)
            current = resolved
        elif not current.exists():
            break
    return None
