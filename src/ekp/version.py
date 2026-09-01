"""Canonical runtime version for the installed EKP distribution."""

import re

from importlib.metadata import PackageNotFoundError, version

from ekp.paths import get_ekp_root

_PROJECT_VERSION_RE = re.compile(
    r'^version\s*=\s*["\']([^"\']+)["\']\s*(?:#.*)?$'
)


def _read_project_version(pyproject_path):
    # type: (...) -> str | None
    """Read ``[project].version`` from a static PEP 621 ``pyproject.toml``."""
    in_project = False
    for line in pyproject_path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if stripped.startswith("[") and stripped.endswith("]"):
            in_project = stripped == "[project]"
            continue
        if not in_project:
            continue
        match = _PROJECT_VERSION_RE.match(stripped)
        if match:
            return match.group(1)
    return None


def _read_source_version():
    # type: () -> str
    """Return the canonical version from the development checkout."""
    try:
        root = get_ekp_root()
    except RuntimeError as exc:
        raise RuntimeError("Cannot determine EKP version") from exc

    pyproject = root / "pyproject.toml"
    if not pyproject.is_file():
        raise RuntimeError("Cannot determine EKP version")

    project_version = _read_project_version(pyproject)
    if not project_version:
        raise RuntimeError("Cannot determine EKP version")
    return project_version


def get_version():
    # type: () -> str
    """Return the installed distribution version from package metadata."""
    try:
        return version("engineering-knowledge-pack")
    except PackageNotFoundError:
        return _read_source_version()
