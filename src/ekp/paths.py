"""EKP resource root resolution for development checkouts and installed packages."""

from pathlib import Path

_PACKAGE_DIR = Path(__file__).resolve().parent
_BUNDLED_ROOT = _PACKAGE_DIR / "_resources"


def get_ekp_root():
    # type: () -> Path
    """
    Return the read-only EKP resource root.

    The root contains ``knowledge/``, ``profiles/``, ``components/``, ``schema/``, and
    ``scripts/`` — the same layout as a development repository checkout.
    """
    if (_BUNDLED_ROOT / "knowledge").is_dir() and (_BUNDLED_ROOT / "profiles").is_dir():
        return _BUNDLED_ROOT

    for parent in _PACKAGE_DIR.parents:
        if (parent / "pyproject.toml").is_file() and (parent / "knowledge").is_dir():
            if (parent / "profiles").is_dir():
                return parent

    raise RuntimeError("Cannot locate EKP resource root")
