"""Semantic normalization and configuration hashing for project intent."""

from __future__ import annotations

import hashlib
import json
from typing import Any, Dict, List, Sequence

from ekp.composition import ComponentRegistry, reduce_requested_components
from ekp.config.models import (
    PROJECT_SCHEMA_VERSION_1,
    PROJECT_SCHEMA_VERSION_2,
    SUPPORTED_PROJECT_SCHEMA_VERSIONS,
    ProjectConfig,
    ProjectConfigError,
    WorkspaceIntent,
)


def reduce_requested_components_for_config(
    requested: Sequence[str],
    registry: ComponentRegistry,
) -> List[str]:
    """Reduce requested components using the composition dependency graph."""
    try:
        return reduce_requested_components(requested, registry)
    except Exception as exc:
        raise ProjectConfigError(str(exc)) from exc


def _normalize_schema1(
    config: ProjectConfig,
    registry: ComponentRegistry,
) -> Dict[str, Any]:
    """Exact v0.20 schema1 semantic representation (frozen)."""
    components = reduce_requested_components_for_config(config.components, registry)
    assistants = sorted(set(str(item) for item in config.assistants))
    return {
        "schema_version": int(config.schema_version),
        "components": components,
        "assistants": assistants,
    }


def _normalize_schema2(
    config: ProjectConfig,
    registry: ComponentRegistry,
) -> Dict[str, Any]:
    """Deterministic schema2 semantic representation (requested intent only)."""
    root_components = reduce_requested_components_for_config(
        config.components, registry
    )
    assistants = sorted(set(str(item) for item in config.assistants))
    workspaces = []
    for workspace in sorted(config.workspaces, key=lambda item: item.path):
        workspaces.append(
            {
                "components": reduce_requested_components_for_config(
                    workspace.components, registry
                ),
                "path": workspace.path,
            }
        )
    return {
        "assistants": assistants,
        "components": root_components,
        "schema_version": int(config.schema_version),
        "workspaces": workspaces,
    }


def normalize_project_config(
    config: ProjectConfig,
    registry: ComponentRegistry,
) -> Dict[str, Any]:
    """
    Build deterministic semantic representation for hashing.

    Schema1 preserves the exact v0.20 normalizer. Schema2 is a separate branch.
    """
    if config.schema_version not in SUPPORTED_PROJECT_SCHEMA_VERSIONS:
        raise ProjectConfigError(
            "unsupported project config schema_version: {}".format(config.schema_version)
        )

    if config.schema_version == PROJECT_SCHEMA_VERSION_1:
        if config.workspaces:
            raise ProjectConfigError(
                "schema_version 1 project config must not declare workspaces"
            )
        return _normalize_schema1(config, registry)

    if config.schema_version == PROJECT_SCHEMA_VERSION_2:
        if not config.workspaces:
            raise ProjectConfigError(
                "schema_version 2 project config requires at least one workspace"
            )
        return _normalize_schema2(config, registry)

    raise ProjectConfigError(
        "unsupported project config schema_version: {}".format(config.schema_version)
    )


def configuration_sha256(
    config: ProjectConfig,
    registry: ComponentRegistry,
) -> str:
    """SHA-256 of canonical semantic JSON for the project configuration."""
    normalized = normalize_project_config(config, registry)
    payload = json.dumps(
        normalized,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()
