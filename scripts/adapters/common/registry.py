"""Adapter registry and dispatch metadata."""

from common.profile_loader import IMPLEMENTED_ADAPTERS, KNOWN_ADAPTERS

# Future adapters are registered for architecture stability; not implemented.
FUTURE_ADAPTERS = tuple(
    name for name in KNOWN_ADAPTERS if name not in IMPLEMENTED_ADAPTERS
)


class AdapterNotImplementedError(Exception):
    """Raised when a profile requests an adapter that is not yet available."""


class AdapterRegistry(object):
    """Maps adapter names to generate/verify implementations."""

    def __init__(self):
        self._adapters = {}

    def register(self, name, generate_fn, verify_fn, build_manifest_fn):
        # type: (str, object, object, object) -> None
        if name not in KNOWN_ADAPTERS:
            raise ValueError("Unknown adapter name: {}".format(name))
        self._adapters[name] = {
            "name": name,
            "generate": generate_fn,
            "verify": verify_fn,
            "build_manifest": build_manifest_fn,
            "implemented": True,
        }

    def get(self, name):
        # type: (str) -> dict
        if name not in KNOWN_ADAPTERS:
            raise AdapterNotImplementedError(
                "Unknown adapter '{}'. Known adapters: {}".format(
                    name, ", ".join(KNOWN_ADAPTERS)
                )
            )
        if name not in self._adapters:
            raise AdapterNotImplementedError(
                "Adapter '{}' is not implemented yet.".format(name)
            )
        return self._adapters[name]

    def is_implemented(self, name):
        # type: (str) -> bool
        return name in self._adapters

    def known_adapters(self):
        # type: () -> tuple
        return KNOWN_ADAPTERS

    def future_adapters(self):
        # type: () -> tuple
        return FUTURE_ADAPTERS


def build_default_registry():
    # type: () -> AdapterRegistry
    """Construct the default adapter registry with operational adapters."""
    from cursor.generate import generate as cursor_generate
    from cursor.manifest import build_bundle_manifest as cursor_build_manifest
    from cursor.verify import verify_cursor_bundle

    registry = AdapterRegistry()
    registry.register(
        "cursor",
        generate_fn=cursor_generate,
        verify_fn=verify_cursor_bundle,
        build_manifest_fn=cursor_build_manifest,
    )
    return registry
