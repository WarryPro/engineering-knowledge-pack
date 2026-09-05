"""Immutable desired managed-file contract for Consumer deployment."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class DesiredManagedFile:
    """One assistant-mapped file the shared engine should manage.

    ``relative_path`` is project-relative (POSIX). ``adapter`` is the assistant id.
    ``source_path`` points at assembled bundle bytes. ``sha256`` is the expected digest.
    """

    relative_path: str
    adapter: str
    source_path: Path
    sha256: str
