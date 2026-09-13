"""Project intent configuration models and constants."""

from __future__ import annotations

from dataclasses import dataclass
from typing import FrozenSet, Tuple

from ekp.config.assistants import DEFAULT_PROJECT_ASSISTANT  # noqa: F401 — re-export

PROJECT_CONFIG_RELATIVE = ".ekp/project.yaml"

PROJECT_SCHEMA_VERSION_1 = 1
PROJECT_SCHEMA_VERSION_2 = 2
SUPPORTED_PROJECT_SCHEMA_VERSIONS: FrozenSet[int] = frozenset(
    {PROJECT_SCHEMA_VERSION_1, PROJECT_SCHEMA_VERSION_2}
)
# Latest workspace-capable project schema (schema1 remains first-class).
LATEST_PROJECT_SCHEMA_VERSION = PROJECT_SCHEMA_VERSION_2

# Backward-compatible name retained for schema1-oriented call sites that still
# mean "classic single-root schema". Prefer SUPPORTED_PROJECT_SCHEMA_VERSIONS
# or PROJECT_SCHEMA_VERSION_* for new code.
SUPPORTED_PROJECT_SCHEMA_VERSION = PROJECT_SCHEMA_VERSION_1


class ProjectConfigError(Exception):
    """Raised when project intent configuration is missing safety or validity."""


class ProjectConfigRollbackError(ProjectConfigError):
    """Raised when config rollback cannot safely restore prior bytes."""


@dataclass(frozen=True)
class WorkspaceIntent:
    """Explicit workspace path and requested technology components."""

    path: str
    components: Tuple[str, ...]


@dataclass(frozen=True)
class ProjectConfig:
    """Declared project intent (requested components, assistants, workspaces)."""

    schema_version: int
    components: Tuple[str, ...]
    assistants: Tuple[str, ...]
    workspaces: Tuple[WorkspaceIntent, ...] = ()


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
