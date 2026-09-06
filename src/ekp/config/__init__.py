"""Project intent configuration (.ekp/project.yaml)."""

from ekp.config.assistants import (
    ASSISTANT_DISPLAY_LABELS,
    DEFAULT_PROJECT_ASSISTANT,
    assistant_display_label,
    canonicalize_assistants,
    default_project_assistants,
)
from ekp.config.models import (
    PROJECT_CONFIG_RELATIVE,
    ProjectConfig,
    ProjectConfigError,
    ProjectConfigSnapshot,
)
from ekp.config.normalization import (
    configuration_sha256,
    normalize_project_config,
    reduce_requested_components_for_config,
)
from ekp.config.project import ProjectConfigStore

__all__ = [
    "ASSISTANT_DISPLAY_LABELS",
    "DEFAULT_PROJECT_ASSISTANT",
    "PROJECT_CONFIG_RELATIVE",
    "ProjectConfig",
    "ProjectConfigError",
    "ProjectConfigSnapshot",
    "ProjectConfigStore",
    "assistant_display_label",
    "canonicalize_assistants",
    "configuration_sha256",
    "default_project_assistants",
    "normalize_project_config",
    "reduce_requested_components_for_config",
]
