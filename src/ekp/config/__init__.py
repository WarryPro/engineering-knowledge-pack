"""Project intent configuration (.ekp/project.yaml)."""

from ekp.config.assistants import (
    ASSISTANT_DISPLAY_LABELS,
    DEFAULT_PROJECT_ASSISTANT,
    assistant_display_label,
    canonicalize_assistants,
    default_project_assistants,
)
from ekp.config.models import (
    LATEST_PROJECT_SCHEMA_VERSION,
    PROJECT_CONFIG_RELATIVE,
    PROJECT_SCHEMA_VERSION_1,
    PROJECT_SCHEMA_VERSION_2,
    SUPPORTED_PROJECT_SCHEMA_VERSION,
    SUPPORTED_PROJECT_SCHEMA_VERSIONS,
    ProjectConfig,
    ProjectConfigError,
    ProjectConfigFileSnapshot,
    ProjectConfigReplaceHandle,
    ProjectConfigRollbackError,
    ProjectConfigSnapshot,
    WorkspaceIntent,
)
from ekp.config.normalization import (
    configuration_sha256,
    normalize_project_config,
    reduce_requested_components_for_config,
)
from ekp.config.project import ProjectConfigStore, project_config_content_sha256
from ekp.config.workspaces import canonicalize_workspace_path

__all__ = [
    "ASSISTANT_DISPLAY_LABELS",
    "DEFAULT_PROJECT_ASSISTANT",
    "LATEST_PROJECT_SCHEMA_VERSION",
    "PROJECT_CONFIG_RELATIVE",
    "PROJECT_SCHEMA_VERSION_1",
    "PROJECT_SCHEMA_VERSION_2",
    "SUPPORTED_PROJECT_SCHEMA_VERSION",
    "SUPPORTED_PROJECT_SCHEMA_VERSIONS",
    "ProjectConfig",
    "ProjectConfigError",
    "ProjectConfigFileSnapshot",
    "ProjectConfigReplaceHandle",
    "ProjectConfigRollbackError",
    "ProjectConfigSnapshot",
    "ProjectConfigStore",
    "WorkspaceIntent",
    "assistant_display_label",
    "canonicalize_assistants",
    "canonicalize_workspace_path",
    "configuration_sha256",
    "default_project_assistants",
    "normalize_project_config",
    "project_config_content_sha256",
    "reduce_requested_components_for_config",
]
