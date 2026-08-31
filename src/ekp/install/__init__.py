"""Consumer install workflow."""

from ekp.install.errors import (
    EXIT_ASSEMBLY,
    EXIT_CONFLICT,
    EXIT_FILESYSTEM,
    EXIT_SELECTION,
    EXIT_SUCCESS,
    InstallError,
)
from ekp.install.service import InstallRequest, InstallResult, InstallService

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
