"""Profile resolution utilities."""

from ekp.resolution.catalog import CURSOR_PROFILES, list_cursor_profiles, validate_profile_name
from ekp.resolution.resolver import apply_resolution, resolve_profile

__all__ = [
    "CURSOR_PROFILES",
    "apply_resolution",
    "list_cursor_profiles",
    "resolve_detected_components",
    "resolve_profile",
    "validate_profile_name",
]


def __getattr__(name):
    if name == "resolve_detected_components":
        from ekp.resolution.composition_proposal import resolve_detected_components

        return resolve_detected_components
    raise AttributeError("module {!r} has no attribute {!r}".format(__name__, name))
