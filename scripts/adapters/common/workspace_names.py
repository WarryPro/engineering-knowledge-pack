"""Deterministic portable filenames for workspace-scoped adapter outputs (D76)."""

from __future__ import annotations

from ekp.workspace_identity import (  # noqa: F401 — re-export adapter contract
    document_unit_from_source,
    slugify_segment,
    workspace_path_hash,
    workspace_scoped_filename,
)


def prefix_apply_to_patterns(apply_to, workspace_path):
    # type: (str, str) -> str
    """Prefix each comma-separated Copilot applyTo pattern with workspace path."""
    parts = []
    for raw in apply_to.split(","):
        pattern = raw.strip()
        if not pattern:
            continue
        parts.append("{}/{}".format(workspace_path, pattern))
    return ",".join(parts)
