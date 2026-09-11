"""Public CLI boundary for workspace / monorepo intent (AZ-E).

Host-separator normalization and flag→ProjectConfig construction live here.
Canonical lexical/filesystem validation remains in ``ekp.config.workspaces``.
"""

from __future__ import annotations

from collections import OrderedDict
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

from ekp.composition import ComponentRegistry
from ekp.config.models import (
    PROJECT_SCHEMA_VERSION_1,
    PROJECT_SCHEMA_VERSION_2,
    ProjectConfig,
    ProjectConfigError,
    WorkspaceIntent,
)
from ekp.config.normalization import configuration_sha256
from ekp.config.project import validate_project_config_payload
from ekp.config.workspaces import canonicalize_workspace_path
from ekp.install.deploy.registry import DeployRegistry, build_default_deploy_registry
from ekp.install.errors import InstallSelectionError
from ekp.install.intent import validate_composition_assistants


def normalize_cli_workspace_path(raw: str) -> str:
    """Normalize host separators at the CLI boundary, then canonicalize.

    Allowed: ``\\\\`` → ``/``.
    Not allowed: silent repair of ``.``, ``..``, trailing slashes, etc.
    """
    if not isinstance(raw, str):
        raise InstallSelectionError("workspace path must be a string")
    # Convert host-native separators only; do not rewrite path aliases.
    host_normalized = raw.replace("\\", "/")
    try:
        return canonicalize_workspace_path(host_normalized)
    except ProjectConfigError as exc:
        raise InstallSelectionError(str(exc)) from exc


def group_workspace_cli_pairs(
    pairs: Sequence[Sequence[str]],
) -> Tuple[WorkspaceIntent, ...]:
    """
    Group repeatable ``--workspace PATH COMPONENT`` into WorkspaceIntent values.

    Same normalized path merges components (first-seen order, deduped).
    """
    if not pairs:
        return ()

    grouped: "OrderedDict[str, List[str]]" = OrderedDict()
    for pair in pairs:
        if len(pair) != 2:
            raise InstallSelectionError(
                "--workspace requires PATH and COMPONENT arguments"
            )
        path_raw, component_raw = pair[0], pair[1]
        path = normalize_cli_workspace_path(str(path_raw))
        component = str(component_raw).strip()
        if not component:
            raise InstallSelectionError(
                "workspace component must not be empty for path {!r}".format(path)
            )
        bucket = grouped.setdefault(path, [])
        if component not in bucket:
            bucket.append(component)

    return tuple(
        WorkspaceIntent(path=path, components=tuple(components))
        for path, components in grouped.items()
    )


def _dedupe_ids(values: Optional[Sequence[str]]) -> Tuple[str, ...]:
    if not values:
        return ()
    unique: List[str] = []
    seen = set()
    for raw in values:
        item = str(raw).strip()
        if not item or item in seen:
            continue
        seen.add(item)
        unique.append(item)
    return tuple(unique)


def build_install_project_config_from_cli(
    *,
    project_root: Path,
    registry: ComponentRegistry,
    components: Optional[Sequence[str]],
    assistants: Optional[Sequence[str]],
    workspace_pairs: Optional[Sequence[Sequence[str]]],
    no_root_components: bool,
    no_workspaces: bool,
    profile: Optional[str],
    deploy_registry: Optional[DeployRegistry] = None,
) -> ProjectConfig:
    """Build an exact ProjectConfig for public ``ekp install`` workspace flows."""
    if no_workspaces:
        raise InstallSelectionError(
            "--no-workspaces is only valid with `ekp configure`.\n"
            "For install, omit workspaces to create a schema1 root project, "
            "or pass --workspace PATH COMPONENT for a schema2 workspace project."
        )
    if profile:
        raise InstallSelectionError(
            "Cannot combine --profile with workspace install flags.\n"
            "Legacy profile installs remain Cursor-only without --workspace "
            "or --no-root-components."
        )
    if no_root_components and components:
        raise InstallSelectionError(
            "Cannot combine --component with --no-root-components."
        )

    workspaces = group_workspace_cli_pairs(workspace_pairs or ())
    if no_root_components and not workspaces:
        raise InstallSelectionError(
            "--no-root-components requires at least one --workspace PATH COMPONENT.\n"
            "Schema1 projects must declare at least one root component."
        )
    if not workspaces:
        raise InstallSelectionError(
            "Internal error: schema2 install builder called without workspaces"
        )

    if no_root_components or components is None:
        root_components: Tuple[str, ...] = ()
    else:
        root_components = _dedupe_ids(components)
        if not root_components and not no_root_components:
            # Explicit empty --component list is invalid; treat as omission → empty root.
            root_components = ()

    deploy = deploy_registry or build_default_deploy_registry()
    selected_assistants = validate_composition_assistants(
        list(assistants) if assistants is not None else None,
        deploy_registry=deploy,
    )

    payload = {
        "schema_version": PROJECT_SCHEMA_VERSION_2,
        "components": list(root_components),
        "assistants": list(selected_assistants),
        "workspaces": [
            {"path": ws.path, "components": list(ws.components)} for ws in workspaces
        ],
    }
    try:
        validated = validate_project_config_payload(
            payload,
            registry,
            project_root=project_root,
            supported_assistants=deploy.supported_assistants(),
        )
    except ProjectConfigError as exc:
        raise InstallSelectionError(str(exc)) from exc
    return validated


def build_configure_project_config_from_cli(
    *,
    project_root: Path,
    current: ProjectConfig,
    registry: ComponentRegistry,
    components: Optional[Sequence[str]],
    assistants: Optional[Sequence[str]],
    workspace_pairs: Optional[Sequence[Sequence[str]]],
    no_root_components: bool,
    no_workspaces: bool,
    deploy_registry: Optional[DeployRegistry] = None,
) -> ProjectConfig:
    """
    Resolve noninteractive configure flags into a complete desired ProjectConfig.

    All omission/flag semantics are resolved here before the lifecycle service.
    """
    if no_root_components and components:
        raise InstallSelectionError(
            "Cannot combine --component with --no-root-components."
        )
    if no_workspaces and workspace_pairs:
        raise InstallSelectionError(
            "Cannot combine --workspace with --no-workspaces."
        )
    if no_workspaces and no_root_components:
        raise InstallSelectionError(
            "Cannot combine --no-workspaces with --no-root-components.\n"
            "Schema1 projects require at least one root component."
        )

    assistants_missing = assistants is None or not list(assistants)
    components_omitted = components is None and not no_root_components

    workspace_flag_present = bool(workspace_pairs)
    if no_workspaces:
        desired_workspaces: Tuple[WorkspaceIntent, ...] = ()
    elif workspace_flag_present:
        desired_workspaces = group_workspace_cli_pairs(workspace_pairs or ())
    else:
        # Omitted workspace dimension.
        if current.schema_version == PROJECT_SCHEMA_VERSION_2 and current.workspaces:
            raise InstallSelectionError(
                "This project currently uses workspaces.\n"
                "For non-interactive configure, specify the complete desired "
                "workspace set with --workspace, or use --no-workspaces to "
                "remove all workspaces."
            )
        desired_workspaces = ()

    # Prefer a combined message when schema1-style both dimensions are omitted.
    if assistants_missing and components_omitted and not desired_workspaces:
        raise InstallSelectionError(
            "With --yes or --dry-run, both component and assistant sets must "
            "be supplied.\n"
            "Provide at least one --component and one --assistant "
            "(exact desired-state sets)."
        )
    if assistants_missing:
        raise InstallSelectionError(
            "With --yes or --dry-run, specify one or more --assistant values.\n"
            "Configure does not default assistants from Cursor or tool signals."
        )

    deploy = deploy_registry or build_default_deploy_registry()
    selected_assistants = validate_composition_assistants(
        list(assistants), deploy_registry=deploy
    )

    if no_root_components:
        root_components: Tuple[str, ...] = ()
    elif components is not None:
        root_components = _dedupe_ids(components)
        if not root_components:
            raise InstallSelectionError(
                "Provide at least one --component, or use --no-root-components."
            )
    else:
        # Root dimension omitted.
        if desired_workspaces:
            raise InstallSelectionError(
                "Specify at least one --component, or use --no-root-components."
            )
        raise InstallSelectionError(
            "With --yes or --dry-run, both component and assistant sets must "
            "be supplied.\n"
            "Provide at least one --component and one --assistant "
            "(exact desired-state sets)."
        )

    if desired_workspaces:
        schema_version = PROJECT_SCHEMA_VERSION_2
        if no_root_components is False and components is None:
            # unreachable due to raise above
            pass
    else:
        schema_version = PROJECT_SCHEMA_VERSION_1
        if not root_components:
            raise InstallSelectionError(
                "Schema1 projects require at least one root component.\n"
                "Provide --component, or keep workspaces with --workspace / "
                "--no-root-components."
            )
        if no_root_components:
            raise InstallSelectionError(
                "Cannot use --no-root-components without workspaces."
            )

    # schema1→schema1 cannot use --no-workspaces as a no-op marker when already schema1
    if (
        current.schema_version == PROJECT_SCHEMA_VERSION_1
        and no_workspaces
        and not desired_workspaces
        and schema_version == PROJECT_SCHEMA_VERSION_1
    ):
        raise InstallSelectionError(
            "--no-workspaces is not valid for schema1→schema1 configure.\n"
            "Omit workspace flags when staying on a root-only project."
        )

    payload: Dict = {
        "schema_version": schema_version,
        "components": list(root_components),
        "assistants": list(selected_assistants),
    }
    if schema_version == PROJECT_SCHEMA_VERSION_2:
        payload["workspaces"] = [
            {"path": ws.path, "components": list(ws.components)}
            for ws in desired_workspaces
        ]

    try:
        validated = validate_project_config_payload(
            payload,
            registry,
            project_root=project_root,
            supported_assistants=deploy.supported_assistants(),
        )
    except ProjectConfigError as exc:
        raise InstallSelectionError(str(exc)) from exc
    return validated


def configuration_hash_for(
    config: ProjectConfig, registry: ComponentRegistry
) -> str:
    """Semantic configuration hash for CLI/tests."""
    return configuration_sha256(config, registry)
