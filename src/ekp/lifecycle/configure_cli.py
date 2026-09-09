"""Public ``ekp configure`` orchestration (CLI-facing; uses ConfigureService)."""

from __future__ import annotations

from typing import Callable, List, Optional, Sequence

from ekp.composition import ComponentRegistry
from ekp.install.deploy.registry import build_default_deploy_registry
from ekp.install.errors import EXIT_SELECTION, EXIT_SUCCESS, InstallSelectionError
from ekp.lifecycle.configure import (
    ConfigurePreparedOperation,
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

    if noninteractive:
        if not cli_components or not cli_assistants:
            return ConfigureResult(
                exit_code=EXIT_SELECTION,
                message=(
                    "With --yes or --dry-run, both component and assistant sets "
                    "must be supplied.\n"
                    "Provide at least one --component and one --assistant "
                    "(exact desired-state sets)."
                ),
            )

    try:
        return _run_configure(
            configure=configure,
            registry=registry,
            deploy_registry=deploy_registry,
            path=path,
            cli_components=cli_components,
            cli_assistants=cli_assistants,
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

    if noninteractive:
        desired_components = list(cli_components or [])
        desired_assistants = list(cli_assistants or [])
    else:
        if cli_components is not None:
            desired_components = list(cli_components)
        else:
            desired_components = list(
                prompt_configure_components(
                    inspected.current_config.components,
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
                    inspected.current_config.assistants,
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
