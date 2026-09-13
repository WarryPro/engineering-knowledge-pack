"""Human-readable configure plan / success / NOOP rendering."""

from __future__ import annotations

from typing import Dict, List, Optional, Sequence

from ekp.composition import ComponentRegistry, resolve_composition, resolve_project_composition
from ekp.config.assistants import assistant_display_label
from ekp.config.models import PROJECT_SCHEMA_VERSION_2, ProjectConfig
from ekp.lifecycle.configure import ConfigurePreparedOperation
from ekp.lifecycle.plan import LifecyclePlan
from ekp.paths import get_ekp_root


def _fmt_list(items: Sequence[str]) -> List[str]:
    if not items:
        return ["  (none)"]
    return ["  {}".format(item) for item in items]


def _resolved_components(
    config: ProjectConfig, registry: Optional[ComponentRegistry] = None
) -> List[str]:
    loaded = registry or ComponentRegistry.load(get_ekp_root())
    if config.schema_version == PROJECT_SCHEMA_VERSION_2:
        resolution = resolve_project_composition(config, loaded)
        if resolution.root is None:
            return []
        return list(resolution.root.resolved_components)
    if not config.components:
        return []
    composition = resolve_composition(list(config.components), loaded)
    return list(composition.resolved_components)


def _fmt_workspaces(config: ProjectConfig) -> List[str]:
    if config.schema_version != PROJECT_SCHEMA_VERSION_2 or not config.workspaces:
        return ["  (none)"]
    lines: List[str] = []
    for ws in config.workspaces:
        comps = ", ".join(ws.components) if ws.components else "(none)"
        lines.append("  {} — {}".format(ws.path, comps))
    return lines


def _assistant_counts(plan: LifecyclePlan) -> Dict[str, int]:
    counts: Dict[str, int] = {}
    if plan.new_manifest is None:
        return counts
    for item in plan.new_manifest.managed_files:
        counts[item.adapter] = counts.get(item.adapter, 0) + 1
    return counts


def render_configure_plan(
    prepared: ConfigurePreparedOperation,
    *,
    registry: Optional[ComponentRegistry] = None,
    dry_run: bool = False,
) -> str:
    """Render prepare outcome for dry-run or pre-confirmation."""
    plan = prepared.plan
    current = prepared.old_file_snapshot.config
    desired = prepared.desired_config
    loaded = registry or ComponentRegistry.load(get_ekp_root())

    lines = [
        "EKP configure plan",
        "",
        "Schema: {} → {}".format(current.schema_version, desired.schema_version),
        "",
        "Current root components:",
    ]
    lines.extend(_fmt_list(list(current.components)))
    lines.append("")
    lines.append("Desired root components:")
    lines.extend(_fmt_list(list(desired.components)))
    lines.append("")
    lines.append("Resolved desired root components:")
    lines.extend(_fmt_list(_resolved_components(desired, loaded)))
    lines.append("")
    lines.append("Current workspaces:")
    lines.extend(_fmt_workspaces(current))
    lines.append("")
    lines.append("Desired workspaces:")
    lines.extend(_fmt_workspaces(desired))
    lines.append("")
    lines.append("Current assistants:")
    lines.extend(_fmt_list(sorted(current.assistants)))
    lines.append("")
    lines.append("Desired assistants:")
    lines.extend(_fmt_list(sorted(desired.assistants)))
    lines.append("")
    lines.append("Configuration:")
    lines.append(
        "  current semantic hash: {}".format(
            prepared.old_file_snapshot.configuration_sha256
        )
    )
    lines.append(
        "  desired semantic hash: {}".format(prepared.desired_semantic_hash)
    )
    action = "NOOP" if prepared.noop else "UPDATE"
    lines.append("  Configuration action: {}".format(action))
    lines.append("")

    if prepared.noop:
        lines.append("Configuration already matches the requested state.")
        lines.append("No changes are required.")
        if dry_run:
            lines.append("")
            lines.append("Dry run — no files changed.")
        return "\n".join(lines)

    lines.append("Managed files:")
    lines.append("  CREATE: {}".format(plan.create_count))
    lines.append("  WRITE:  {}".format(plan.write_count))
    lines.append("  DELETE: {}".format(plan.delete_count))
    lines.append("  NOOP:   {}".format(plan.noop_count))
    if plan.new_manifest is not None:
        total = len(plan.new_manifest.managed_files)
        lines.append("  total desired: {}".format(total))
        counts = _assistant_counts(plan)
        if counts:
            lines.append("")
            lines.append("Desired managed files by assistant:")
            for assistant_id in sorted(counts):
                lines.append(
                    "  {}: {}".format(
                        assistant_display_label(assistant_id), counts[assistant_id]
                    )
                )
            lines.append("  Total: {}".format(total))
    lines.append("")

    if plan.has_conflicts:
        lines.append("Conflicts: {}".format(plan.conflict_count))
        for item in plan.conflicts[:10]:
            lines.append("  - {}".format(item))
        if len(plan.conflicts) > 10:
            lines.append("  ... and {} more".format(len(plan.conflicts) - 10))
        lines.append("")

    if dry_run:
        lines.append("Dry run — no files changed.")
    else:
        lines.append("Continue? [Y/n]")
    return "\n".join(lines)


def render_configure_noop(prepared: ConfigurePreparedOperation) -> str:
    current = prepared.old_file_snapshot.config
    root = ", ".join(current.components) if current.components else "(none)"
    lines = [
        "Configuration already matches the requested state.",
        "No changes are required.",
        "",
        "Root components: {}".format(root),
        "Assistants: {}".format(
            ", ".join(assistant_display_label(a) for a in sorted(current.assistants))
        ),
    ]
    if current.schema_version == PROJECT_SCHEMA_VERSION_2 and current.workspaces:
        lines.append(
            "Workspaces: {}".format(
                ", ".join(ws.path for ws in current.workspaces)
            )
        )
    return "\n".join(lines)


def render_configure_success(
    prepared: ConfigurePreparedOperation,
    *,
    managed_total: int,
    registry: Optional[ComponentRegistry] = None,
) -> str:
    desired = prepared.desired_config
    loaded = registry or ComponentRegistry.load(get_ekp_root())
    root = ", ".join(desired.components) if desired.components else "(none)"
    resolved = _resolved_components(desired, loaded)
    lines = [
        "EKP configuration updated.",
        "",
        "Schema: {}".format(desired.schema_version),
        "Root components: {}".format(root),
        "Resolved root components: {}".format(
            ", ".join(resolved) if resolved else "(none)"
        ),
    ]
    if desired.schema_version == PROJECT_SCHEMA_VERSION_2:
        if desired.workspaces:
            lines.append("Workspaces:")
            for ws in desired.workspaces:
                lines.append(
                    "  {} — {}".format(ws.path, ", ".join(ws.components))
                )
        else:
            lines.append("Workspaces: (none)")
    lines.extend(
        [
            "Assistants: {}".format(
                ", ".join(
                    assistant_display_label(a) for a in sorted(desired.assistants)
                )
            ),
            "Managed files: {}".format(managed_total),
            "State: HEALTHY",
        ]
    )
    return "\n".join(lines)


def render_configure_cancelled() -> str:
    return "Configuration cancelled."
