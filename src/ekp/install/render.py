"""Human-readable install output."""

from __future__ import annotations

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
