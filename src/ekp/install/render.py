"""Human-readable install output."""

from __future__ import annotations

from ekp.config.assistants import assistant_display_label
from ekp.install.plan import FileOpKind, InstallPlan


def render_conflict_message(plan: InstallPlan) -> str:
    lines = ["Installation blocked.", ""]
    unmanaged = [
        item
        for item in plan.conflicts
        if not item.startswith("Managed file modified")
        and not item.startswith("Symlink")
        and not item.startswith("Refusing")
        and not item.startswith("Unsafe")
        and not item.startswith("Path escapes")
        and not item.startswith("Internal")
    ]
    modified = [item for item in plan.conflicts if item.startswith("Managed file modified")]

    if unmanaged:
        lines.append("EKP does not own these existing files:")
        lines.append("")
        for item in unmanaged:
            if item.startswith("Managed file modified"):
                continue
            if "/" in item or item.startswith("."):
                lines.append("  {}".format(item))
            else:
                lines.append("  {}".format(item))
        lines.append("")
    if modified:
        lines.append("Modified managed files:")
        lines.append("")
        for item in modified:
            lines.append("  {}".format(item.replace("Managed file modified by user: ", "")))
        lines.append("")
    other = [
        item
        for item in plan.conflicts
        if item not in unmanaged and item not in modified
    ]
    for item in other:
        lines.append(item)
    lines.append("No files were written.")
    return "\n".join(lines)


def render_dry_run(plan: InstallPlan) -> str:
    lines = [
        "EKP installation plan",
        "",
        "Version: {}".format(plan.ekp_version),
        "Profile: {}".format(plan.profile),
        "Adapter: Cursor",
        "Rules: {}".format(plan.rules_count),
        "",
    ]
    if plan.additional_concerns:
        lines.append(
            "Note: additional concerns detected ({}) are not included in the selected profile.".format(
                ", ".join(plan.additional_concerns)
            )
        )
        lines.append("")

    creates = [
        op.relative_path
        for op in plan.operations
        if op.kind == FileOpKind.CREATE
    ]
    writes = [
        op.relative_path
        for op in plan.operations
        if op.kind in (FileOpKind.WRITE, FileOpKind.RESTORE)
    ]
    if creates:
        lines.append("Would create:")
        for item in creates[:5]:
            lines.append("  {}".format(item))
        if len(creates) > 5:
            lines.append("  ... and {} more".format(len(creates) - 5))
        lines.append("")
    if writes:
        lines.append("Would write:")
        for item in writes[:5]:
            lines.append("  {}".format(item))
        if len(writes) > 5:
            lines.append("  ... and {} more".format(len(writes) - 5))
        lines.append("")

    if plan.would_create_directories:
        lines.append("Would create directories:")
        for item in plan.would_create_directories:
            lines.append("  {}".format(item))
        lines.append("")

    if plan.is_noop:
        lines.append("Reinstall: no changes required.")
        lines.append("")

    lines.append("Would write:")
    lines.append("  .ekp/install.json")
    lines.append("")
    lines.append("Conflicts: {}".format(len(plan.conflicts)))
    if plan.conflicts:
        for item in plan.conflicts:
            lines.append("  - {}".format(item))
        lines.append("")
    lines.append("Dry run — no files written.")
    return "\n".join(lines)


def render_confirmation(plan: InstallPlan) -> str:
    lines = [
        "EKP installation",
        "",
        "Project:  {}".format(plan.project_root),
        "Version:  {}".format(plan.ekp_version),
        "Profile:  {}".format(plan.profile),
        "Adapter:  Cursor",
        "Rules:    {}".format(plan.rules_count),
        "Target:   .cursor/rules/",
    ]
    if plan.additional_concerns:
        lines.append("")
        lines.append(
            "Note: {} detected but not included in the selected profile.".format(
                ", ".join(plan.additional_concerns)
            )
        )
    lines.append("")
    lines.append("Continue? [Y/n]")
    return "\n".join(lines)


def render_success(plan: InstallPlan, *, noop: bool = False) -> str:
    if noop:
        return "EKP install complete — no changes required."
    return (
        "EKP install complete.\n\n"
        "Profile: {}\n"
        "Rules:   {}\n"
        "Target:  .cursor/rules/\n"
        "Manifest: .ekp/install.json".format(plan.profile, plan.rules_count)
    )


def _managed_files_block(plan) -> list:
    assistants = plan.assistants
    lines = ["Managed files:"]
    if len(assistants) == 1 and assistants[0] == "cursor":
        lines.append("  Cursor rules  {}".format(plan.rules_count))
        lines.append("  Total         {}".format(plan.managed_file_count))
        return lines

    width = max(len(assistant_display_label(a)) for a in assistants)
    for assistant_id in assistants:
        label = assistant_display_label(assistant_id)
        count = plan.assistant_counts.get(assistant_id, 0)
        lines.append(
            "  {}  {}".format(label.ljust(width), count)
        )
    lines.append(
        "  {}  {}".format("Total".ljust(width), plan.managed_file_count)
    )
    return lines


def _composition_from_plan(plan):
    if getattr(plan, "lifecycle_intent", None) is not None:
        return plan.lifecycle_intent.composition
    if plan.intent is not None:
        return plan.intent.composition
    return None


def _composition_intent_lines(plan) -> list:
    config = plan.project_config
    composition = _composition_from_plan(plan)
    lines = [
        "Schema:              {}".format(config.schema_version),
        "",
    ]
    if config.components:
        lines.append("Root components:")
        for item in config.components:
            lines.append("  {}".format(item))
    else:
        lines.append("Root components:     none")
    lines.append("")
    if composition is not None and composition.resolved_components:
        lines.append("Resolved root components:")
        for item in composition.resolved_components:
            lines.append("  {}".format(item))
        lines.append("")
    if getattr(config, "workspaces", None):
        lines.append("Workspaces:")
        for ws in config.workspaces:
            lines.append(
                "  {} - {}".format(ws.path, ", ".join(ws.components))
            )
        lines.append("")
    lines.append("Assistants:")
    for item in plan.assistants:
        lines.append("  {}".format(assistant_display_label(item)))
    lines.append("")
    return lines


def render_composition_dry_run(plan) -> str:
    from ekp.composition import PROJECT_COMPOSITION_PROFILE
    from ekp.install.intent import MODE_COMPOSITION

    lines = [
        "EKP composition installation plan",
        "",
        "Mode:                {}".format(MODE_COMPOSITION),
        "Profile:             {}".format(PROJECT_COMPOSITION_PROFILE),
        "Configuration:       {}".format(plan.config_action),
        "configuration_sha256: {}".format(plan.configuration_sha256),
        "",
    ]
    lines.extend(_composition_intent_lines(plan))
    lines.extend(_managed_files_block(plan))
    lines.append("")
    lines.append(
        "Would write:  .ekp/project.yaml"
        if plan.config_action == "create"
        else "Would reuse:  .ekp/project.yaml"
    )
    lines.append("Would write:  .ekp/install.json")
    lines.append("")
    lines.append(
        "Conflicts: {}".format(len(plan.conflicts) + len(plan.cursor_plan.conflicts))
    )
    lines.append("Dry run — no files written.")
    return "\n".join(lines)


def render_composition_confirmation(plan) -> str:
    lines = [
        "EKP composition installation",
        "",
    ]
    lines.extend(_composition_intent_lines(plan))
    lines.extend(_managed_files_block(plan))
    lines.append("Config:       {}".format(plan.config_action))
    lines.append("")
    lines.append("Continue? [Y/n]")
    return "\n".join(lines)


def render_composition_success(plan) -> str:
    config = plan.project_config
    lines = [
        "EKP installation complete.",
        "",
        "Mode: composition",
        "Schema: {}".format(config.schema_version),
    ]
    if config.components:
        lines.append("Root components: {}".format(", ".join(config.components)))
    else:
        lines.append("Root components: none")
    if getattr(config, "workspaces", None):
        lines.append("Workspaces:")
        for ws in config.workspaces:
            lines.append(
                "  {} - {}".format(ws.path, ", ".join(ws.components))
            )
    lines.extend(
        [
            "Assistants: {}".format(", ".join(plan.assistants)),
            "Managed files: {}".format(plan.managed_file_count),
            "Config: {}".format(plan.config_action),
            "Manifest: .ekp/install.json",
        ]
    )
    return "\n".join(lines)
