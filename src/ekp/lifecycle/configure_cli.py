"""Public ``ekp configure`` orchestration (CLI-facing; uses ConfigureService)."""

from __future__ import annotations

from typing import Callable, List, Optional, Sequence, Tuple

from ekp.cli_workspace import (
    build_configure_project_config_from_cli,
    group_workspace_cli_pairs,
)
from ekp.composition import ComponentRegistry
from ekp.config.models import (
    PROJECT_SCHEMA_VERSION_1,
    PROJECT_SCHEMA_VERSION_2,
    ProjectConfig,
    ProjectConfigError,
    WorkspaceIntent,
)
from ekp.config.project import validate_project_config_payload
from ekp.install.deploy.registry import build_default_deploy_registry
from ekp.install.errors import EXIT_SELECTION, EXIT_SUCCESS, InstallSelectionError
from ekp.install.intent import validate_composition_assistants
from ekp.install.paths import resolve_project_root
from ekp.lifecycle.configure import (
    ConfigureProjectRequest,
    ConfigureRequest,
    ConfigureResult,
    ConfigureService,
)
from ekp.lifecycle.configure_render import (
    render_configure_cancelled,
    render_configure_noop,
    render_configure_plan,
    render_configure_success,
)
from ekp.lifecycle.configure_select import (
    prompt_configure_assistants,
    prompt_configure_components,
    prompt_configure_workspaces,
)


class ConfigureCancelled(Exception):
    """User declined configure confirmation."""

    exit_code = EXIT_SUCCESS


def run_configure_cli(
    *,
    path: str,
    components: Optional[Sequence[str]],
    assistants: Optional[Sequence[str]],
    assume_yes: bool,
    dry_run: bool,
    workspaces: Optional[Sequence[Sequence[str]]] = None,
    no_root_components: bool = False,
    no_workspaces: bool = False,
    input_fn: Callable[[str], str] = input,
    output_fn: Callable[[str], None] = print,
    service: Optional[ConfigureService] = None,
) -> ConfigureResult:
    """Public configure workflow: inspect → select → prepare → render → apply."""
    configure = service or ConfigureService()
    registry = configure._registry_or_load()
    deploy_registry = configure._deploy_registry_or_default()

    noninteractive = bool(assume_yes or dry_run)
    cli_components = list(components) if components else None
    cli_assistants = list(assistants) if assistants else None
    cli_workspaces = list(workspaces) if workspaces else None

    try:
        return _run_configure(
            configure=configure,
            registry=registry,
            deploy_registry=deploy_registry,
            path=path,
            cli_components=cli_components,
            cli_assistants=cli_assistants,
            cli_workspaces=cli_workspaces,
            no_root_components=no_root_components,
            no_workspaces=no_workspaces,
            assume_yes=assume_yes,
            dry_run=dry_run,
            noninteractive=noninteractive,
            input_fn=input_fn,
            output_fn=output_fn,
        )
    except ConfigureCancelled:
        return ConfigureResult(
            exit_code=EXIT_SUCCESS, message=render_configure_cancelled()
        )
    except InstallSelectionError as exc:
        return ConfigureResult(exit_code=exc.exit_code, message=exc.message)


def _run_configure(
    *,
    configure: ConfigureService,
    registry: ComponentRegistry,
    deploy_registry,
    path: str,
    cli_components: Optional[List[str]],
    cli_assistants: Optional[List[str]],
    cli_workspaces: Optional[List[Sequence[str]]],
    no_root_components: bool,
    no_workspaces: bool,
    assume_yes: bool,
    dry_run: bool,
    noninteractive: bool,
    input_fn: Callable[[str], str],
    output_fn: Callable[[str], None],
) -> ConfigureResult:
    inspected = configure.inspect(path)
    if not inspected.eligible:
        return ConfigureResult(
            exit_code=inspected.exit_code,
            message=inspected.message,
        )

    assert inspected.current_config is not None
    current = inspected.current_config
    project_root = resolve_project_root(path)

    workspace_flags_used = bool(
        cli_workspaces or no_workspaces or no_root_components
    )

    if noninteractive:
        desired = build_configure_project_config_from_cli(
            project_root=project_root,
            current=current,
            registry=registry,
            components=cli_components,
            assistants=cli_assistants,
            workspace_pairs=cli_workspaces,
            no_root_components=no_root_components,
            no_workspaces=no_workspaces,
            deploy_registry=deploy_registry,
        )
    elif workspace_flags_used or current.schema_version == PROJECT_SCHEMA_VERSION_2:
        desired = _interactive_desired_config(
            project_root=project_root,
            current=current,
            registry=registry,
            deploy_registry=deploy_registry,
            cli_components=cli_components,
            cli_assistants=cli_assistants,
            cli_workspaces=cli_workspaces,
            no_root_components=no_root_components,
            no_workspaces=no_workspaces,
            input_fn=input_fn,
            output_fn=output_fn,
        )
    else:
        # Historical schema1 interactive / flag path (no workspace UX).
        if cli_components is not None:
            desired_components = list(cli_components)
        else:
            desired_components = list(
                prompt_configure_components(
                    current.components,
                    registry,
                    input_fn=input_fn,
                    output_fn=output_fn,
                )
            )
        if cli_assistants is not None:
            desired_assistants = list(cli_assistants)
        else:
            desired_assistants = list(
                prompt_configure_assistants(
                    current.assistants,
                    deploy_registry=deploy_registry,
                    input_fn=input_fn,
                    output_fn=output_fn,
                )
            )
        prepared_result = configure.prepare(
            ConfigureRequest(
                path=path,
                components=desired_components,
                assistants=desired_assistants,
                dry_run=dry_run,
            )
        )
        return _finish_prepared(
            configure=configure,
            prepared_result=prepared_result,
            registry=registry,
            assume_yes=assume_yes,
            dry_run=dry_run,
            input_fn=input_fn,
            output_fn=output_fn,
        )

    prepared_result = configure.prepare_project(
        ConfigureProjectRequest(
            path=path,
            desired_config=desired,
            dry_run=dry_run,
        )
    )
    return _finish_prepared(
        configure=configure,
        prepared_result=prepared_result,
        registry=registry,
        assume_yes=assume_yes,
        dry_run=dry_run,
        input_fn=input_fn,
        output_fn=output_fn,
    )


def _finish_prepared(
    *,
    configure: ConfigureService,
    prepared_result: ConfigureResult,
    registry: ComponentRegistry,
    assume_yes: bool,
    dry_run: bool,
    input_fn: Callable[[str], str],
    output_fn: Callable[[str], None],
) -> ConfigureResult:
    if prepared_result.exit_code != EXIT_SUCCESS:
        if prepared_result.prepared is not None:
            prepared_result.prepared.close()
        return prepared_result

    prepared = prepared_result.prepared
    assert prepared is not None

    if prepared.noop:
        prepared.close()
        return ConfigureResult(
            exit_code=EXIT_SUCCESS,
            message=render_configure_noop(prepared),
            plan=prepared.plan,
            noop=True,
            desired_configuration_sha256=prepared.desired_semantic_hash,
            old_configuration_sha256=prepared.old_file_snapshot.configuration_sha256,
        )

    if dry_run:
        message = render_configure_plan(
            prepared, registry=registry, dry_run=True
        )
        prepared.close()
        return ConfigureResult(
            exit_code=EXIT_SUCCESS,
            message=message,
            plan=prepared.plan,
            noop=False,
            desired_configuration_sha256=prepared.desired_semantic_hash,
            old_configuration_sha256=prepared.old_file_snapshot.configuration_sha256,
        )

    if not assume_yes:
        output_fn(render_configure_plan(prepared, registry=registry, dry_run=False))
        answer = input_fn("").strip().lower()
        if answer not in ("", "y", "yes"):
            prepared.close()
            raise ConfigureCancelled()

    apply_result = configure.apply(prepared)
    if apply_result.exit_code != EXIT_SUCCESS:
        return apply_result

    plan = apply_result.plan or prepared.plan
    managed_total = (
        len(plan.new_manifest.managed_files)
        if plan is not None and plan.new_manifest is not None
        else 0
    )

    return ConfigureResult(
        exit_code=EXIT_SUCCESS,
        message=render_configure_success(
            prepared, managed_total=managed_total, registry=registry
        ),
        plan=plan,
        noop=False,
        desired_configuration_sha256=prepared.desired_semantic_hash,
        old_configuration_sha256=prepared.old_file_snapshot.configuration_sha256,
    )


def _interactive_desired_config(
    *,
    project_root,
    current: ProjectConfig,
    registry: ComponentRegistry,
    deploy_registry,
    cli_components: Optional[List[str]],
    cli_assistants: Optional[List[str]],
    cli_workspaces: Optional[List[Sequence[str]]],
    no_root_components: bool,
    no_workspaces: bool,
    input_fn: Callable[[str], str],
    output_fn: Callable[[str], None],
) -> ProjectConfig:
    """Build complete desired ProjectConfig for interactive / mixed workspace UX."""
    if no_root_components and cli_components:
        raise InstallSelectionError(
            "Cannot combine --component with --no-root-components."
        )
    if no_workspaces and cli_workspaces:
        raise InstallSelectionError(
            "Cannot combine --workspace with --no-workspaces."
        )
    if no_workspaces and no_root_components:
        raise InstallSelectionError(
            "Cannot combine --no-workspaces with --no-root-components.\n"
            "Schema1 projects require at least one root component."
        )

    # Root components
    if no_root_components:
        root_components: Tuple[str, ...] = ()
    elif cli_components is not None:
        root_components = tuple(cli_components)
    else:
        root_components = prompt_configure_components(
            current.components,
            registry,
            allow_empty=True,
            input_fn=input_fn,
            output_fn=output_fn,
        )

    # Assistants
    if cli_assistants is not None:
        assistants = validate_composition_assistants(
            cli_assistants, deploy_registry=deploy_registry
        )
    else:
        assistants = prompt_configure_assistants(
            current.assistants,
            deploy_registry=deploy_registry,
            input_fn=input_fn,
            output_fn=output_fn,
        )

    # Workspaces
    if no_workspaces:
        workspaces: Tuple[WorkspaceIntent, ...] = ()
    elif cli_workspaces is not None:
        workspaces = group_workspace_cli_pairs(cli_workspaces)
    else:
        workspaces = prompt_configure_workspaces(
            current.workspaces,
            registry=registry,
            project_root=project_root,
            input_fn=input_fn,
            output_fn=output_fn,
        )

    if not workspaces and not root_components:
        raise InstallSelectionError(
            "Desired configuration cannot have empty root components and no "
            "workspaces.\n"
            "Select at least one root component, or keep/add workspaces."
        )

    schema_version = (
        PROJECT_SCHEMA_VERSION_2 if workspaces else PROJECT_SCHEMA_VERSION_1
    )
    payload = {
        "schema_version": schema_version,
        "components": list(root_components),
        "assistants": list(assistants),
    }
    if schema_version == PROJECT_SCHEMA_VERSION_2:
        payload["workspaces"] = [
            {"path": ws.path, "components": list(ws.components)} for ws in workspaces
        ]
    try:
        validated = validate_project_config_payload(
            payload,
            registry,
            project_root=project_root,
            supported_assistants=deploy_registry.supported_assistants(),
        )
    except ProjectConfigError as exc:
        raise InstallSelectionError(str(exc)) from exc
    return validated
