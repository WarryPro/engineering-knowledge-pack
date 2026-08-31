"""Repository path helpers for EKP adapters."""

from pathlib import Path

_path_context = {
    "repo_root": None,
    "dist_dir": None,
}


def set_path_context(repo_root=None, dist_dir=None):
    # type: (Path, Path) -> None
    """Override repo/dist resolution for the current assembly workspace."""
    _path_context["repo_root"] = repo_root
    _path_context["dist_dir"] = dist_dir


def clear_path_context():
    # type: () -> None
    """Clear path overrides set by :func:`set_path_context`."""
    set_path_context(None, None)


def _detect_resource_root():
    # type: () -> Path
    """Locate the EKP resource root from this module's filesystem location."""
    path = Path(__file__).resolve()
    for parent in path.parents:
        if (parent / "knowledge").is_dir() and (parent / "profiles").is_dir():
            return parent
    return path.parents[3]


def get_repo_root():
    # type: () -> Path
    """Return the EKP resource root directory."""
    if _path_context["repo_root"] is not None:
        return _path_context["repo_root"]
    return _detect_resource_root()


def get_knowledge_path():
    # type: () -> Path
    """Return the knowledge/ source directory."""
    return get_repo_root() / "knowledge"


def get_dist_path():
    # type: () -> Path
    """Return the dist/ directory for generated indexes and bundles."""
    if _path_context["dist_dir"] is not None:
        return _path_context["dist_dir"]
    return get_repo_root() / "dist"
