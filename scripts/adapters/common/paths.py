"""Repository path helpers for EKP adapters."""

from pathlib import Path


def get_repo_root():
    # type: () -> Path
    """Return the EKP repository root directory."""
    return Path(__file__).resolve().parents[3]


def get_knowledge_path():
    # type: () -> Path
    """Return the knowledge/ source directory."""
    return get_repo_root() / "knowledge"


def get_dist_path():
    # type: () -> Path
    """Return the dist/ directory for generated indexes and bundles."""
    return get_repo_root() / "dist"
