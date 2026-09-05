"""Consumer install workflow."""

from ekp.install.errors import (
    EXIT_ASSEMBLY,
    EXIT_CONFLICT,
    EXIT_FILESYSTEM,
    EXIT_SELECTION,
    EXIT_SUCCESS,
    InstallError,
)

__all__ = [
    "EXIT_ASSEMBLY",
    "EXIT_CONFLICT",
    "EXIT_FILESYSTEM",
    "EXIT_SELECTION",
    "EXIT_SUCCESS",
    "InstallError",
    "InstallRequest",
    "InstallResult",
    "InstallService",
]


def __getattr__(name):
    if name in ("InstallRequest", "InstallResult", "InstallService"):
        from ekp.install.service import InstallRequest, InstallResult, InstallService

        mapping = {
            "InstallRequest": InstallRequest,
            "InstallResult": InstallResult,
            "InstallService": InstallService,
        }
        return mapping[name]
    raise AttributeError("module {!r} has no attribute {!r}".format(__name__, name))
