"""Install workflow errors and exit codes."""

from __future__ import annotations

EXIT_SUCCESS = 0
EXIT_SELECTION = 2
EXIT_CONFLICT = 3
EXIT_ASSEMBLY = 4
EXIT_FILESYSTEM = 5


class InstallError(Exception):
    """Base install error with an exit code."""

    exit_code = EXIT_SELECTION

    def __init__(self, message: str):
        super().__init__(message)
        self.message = message


class InstallSelectionError(InstallError):
    """Profile or configuration selection failure."""

    exit_code = EXIT_SELECTION


class InstallConflictError(InstallError):
    """Ownership or deployment conflict."""

    exit_code = EXIT_CONFLICT


class InstallAssemblyError(InstallError):
    """Assembly or bundle validation failure."""

    exit_code = EXIT_ASSEMBLY


class InstallFilesystemError(InstallError):
    """Unexpected filesystem failure."""

    exit_code = EXIT_FILESYSTEM


class InstallCancelled(Exception):
    """User declined confirmation."""

    exit_code = EXIT_SUCCESS
