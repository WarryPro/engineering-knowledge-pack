"""Project intent configuration models and constants."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Tuple

from ekp.config.assistants import DEFAULT_PROJECT_ASSISTANT  # noqa: F401 — re-export

PROJECT_CONFIG_RELATIVE = ".ekp/project.yaml"
SUPPORTED_PROJECT_SCHEMA_VERSION = 1


class ProjectConfigError(Exception):
    """Raised when project intent configuration is missing safety or validity."""


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
