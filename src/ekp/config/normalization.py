"""Semantic normalization and configuration hashing for project intent."""

from __future__ import annotations

import hashlib
import json
from typing import Any, Dict, List, Sequence

from ekp.composition import ComponentRegistry, reduce_requested_components
from ekp.config.models import (
    SUPPORTED_PROJECT_ASSISTANTS,
    SUPPORTED_PROJECT_SCHEMA_VERSION,
    ProjectConfig,
    ProjectConfigError,
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


def normalize_project_config(
    config: ProjectConfig,
    registry: ComponentRegistry,
) -> Dict[str, Any]:
    """
    Build deterministic semantic representation for hashing.

    Redundant dependency components are removed; remaining ids are sorted.
    """
    if config.schema_version != SUPPORTED_PROJECT_SCHEMA_VERSION:
        raise ProjectConfigError(
            "unsupported project config schema_version: {}".format(config.schema_version)
        )

    components = reduce_requested_components_for_config(config.components, registry)
    assistants = sorted(set(str(item) for item in config.assistants))
    return {
        "schema_version": int(config.schema_version),
        "components": components,
        "assistants": assistants,
    }


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
