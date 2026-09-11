"""Deterministic workspace identity helpers (D76).

Pure path→filename primitives shared by adapters and status diagnostics.
"""

from __future__ import annotations

import hashlib
import re

_UNSAFE_RE = re.compile(r"[^a-zA-Z0-9._-]+")


def workspace_path_hash(workspace_path: str) -> str:
    """First 10 lowercase hex chars of SHA-256(normalized workspace path)."""
    digest = hashlib.sha256(workspace_path.encode("utf-8")).hexdigest()
    return digest[:10]


def slugify_segment(value: str) -> str:
    """Portable filename segment from an arbitrary string."""
    text = str(value).strip().replace("/", "-").replace("\\", "-")
    text = _UNSAFE_RE.sub("-", text)
    text = re.sub(r"-{2,}", "-", text).strip("-._")
    return text.lower() or "unit"


def document_unit_from_source(source_path: str) -> str:
    """Logical unit stem from a canonical knowledge source path."""
    stem = source_path.rsplit("/", 1)[-1]
    if stem.endswith(".md"):
        stem = stem[:-3]
    return slugify_segment(stem)


def workspace_scoped_filename(
    workspace_path: str, source_path: str, extension: str
) -> str:
    """Build ``<slug>-<hash>-<logical-unit>.<ext>``."""
    slug = slugify_segment(workspace_path)
    path_hash = workspace_path_hash(workspace_path)
    unit = document_unit_from_source(source_path)
    ext = extension.lstrip(".")
    return "{}-{}-{}.{}".format(slug, path_hash, unit, ext)


def workspace_filename_prefix(workspace_path: str) -> str:
    """Prefix that identifies managed files for a workspace path (D76)."""
    return "{}-{}-".format(
        slugify_segment(workspace_path), workspace_path_hash(workspace_path)
    )
