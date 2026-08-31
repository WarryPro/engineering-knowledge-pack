"""Existing Cursor profile catalog."""

from __future__ import annotations

from pathlib import Path
from typing import List, Set

from ekp.paths import get_ekp_root

CURSOR_PROFILES = (
    "cursor-core",
    "cursor-php",
    "cursor-symfony",
    "cursor-typescript",
    "cursor-frontend",
    "cursor-devops",
    "cursor-nativescript",
    "cursor-flutter",
)


def list_cursor_profiles(resource_root: Path = None) -> List[str]:
    """Return validated Cursor profile names from the canonical profiles directory."""
    root = resource_root or get_ekp_root()
    profiles_dir = root / "profiles"
    available = sorted(
        path.stem
        for path in profiles_dir.glob("*.yaml")
        if path.stem in CURSOR_PROFILES
    )
    return available


def validate_profile_name(profile_name: str, resource_root: Path = None) -> bool:
    """Return True when profile_name exists in the canonical catalog."""
    return profile_name in set(list_cursor_profiles(resource_root))
