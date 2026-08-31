"""Canonical runtime version for the installed EKP distribution."""

from importlib.metadata import PackageNotFoundError, version


def get_version():
    # type: () -> str
    """Return the installed distribution version from package metadata."""
    try:
        return version("engineering-knowledge-pack")
    except PackageNotFoundError:
        return "0.15.0.dev0"
