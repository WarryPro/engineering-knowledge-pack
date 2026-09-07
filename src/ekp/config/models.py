"""Project intent configuration models and constants."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Tuple

from ekp.config.assistants import DEFAULT_PROJECT_ASSISTANT  # noqa: F401 — re-export

PROJECT_CONFIG_RELATIVE = ".ekp/project.yaml"
SUPPORTED_PROJECT_SCHEMA_VERSION = 1


class ProjectConfigError(Exception):
    """Raised when project intent configuration is missing safety or validity."""


class ProjectConfigRollbackError(ProjectConfigError):
    """Raised when config rollback cannot safely restore prior bytes."""


@dataclass(frozen=True)
class ProjectConfig:
    """Declared project intent (requested components and assistants)."""

    schema_version: int
    components: Tuple[str, ...]
    assistants: Tuple[str, ...]


@dataclass(frozen=True)
class ProjectConfigSnapshot:
    """Loaded project config plus semantic normalization artifacts."""

    config: ProjectConfig
    normalized: dict
    configuration_sha256: str


@dataclass(frozen=True)
class ProjectConfigFileSnapshot:
    """Runtime snapshot of project.yaml semantic intent plus exact file bytes.

    Not persisted in install manifests. Used for TOCTOU and rollback only.
    """

    config: ProjectConfig
    normalized: dict
    configuration_sha256: str
    raw_bytes: bytes
    content_sha256: str


@dataclass(frozen=True)
class ProjectConfigReplaceHandle:
    """State returned by a successful project.yaml replacement for rollback."""

    old_bytes: bytes
    old_content_sha256: str
    old_configuration_sha256: str
    new_bytes: bytes
    new_content_sha256: str
    new_configuration_sha256: str
    config: ProjectConfig
