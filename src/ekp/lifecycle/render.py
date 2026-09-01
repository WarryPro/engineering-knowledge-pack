"""Human-readable lifecycle output."""

from __future__ import annotations

from typing import List, Optional

from ekp.lifecycle.plan import LifecyclePlan


def render_uninstall_conflict_message(plan: LifecyclePlan) -> str:
    lines = ["Uninstall blocked.", ""]
    modified = [
        item
        for item in plan.conflicts
        if item.startswith("Managed file modified by user:")
    ]
    other = [item for item in plan.conflicts if item not in modified]

    if modified:
        lines.append("Modified managed files:")
        lines.append("")
        for item in modified[:5]:
            lines.append(
                "  {}".format(item.replace("Managed file modified by user: ", ""))
            )
        if len(modified) > 5:
            lines.append("  ... and {} more".format(len(modified) - 5))
        lines.append("")

    for item in other[:10]:
        lines.append(item)
    if len(other) > 10:
        lines.append("... and {} more conflicts".format(len(other) - 10))

    lines.append("")
    lines.append("No files were removed.")
    return "\n".join(lines)


def render_uninstall_dry_run(plan: LifecyclePlan) -> str:
    lines = [
        "EKP uninstall plan",
        "",
        "Installed version: {}".format(plan.old_version),
        "Profile:           {}".format(plan.profile),
        "Managed files:     {}".format(len(plan.operations)),
        "Delete:            {}".format(plan.delete_count),
        "Missing:           {}".format(plan.missing_count),
        "",
    ]
    if plan.directories_to_remove:
        lines.append("Directories:")
        for item in plan.directories_to_remove:
            lines.append("  {}".format(item))
        lines.append("")

    if plan.has_conflicts:
        lines.append("Conflicts: {}".format(plan.conflict_count))
        for item in plan.conflicts[:5]:
            lines.append("  - {}".format(item))
        if len(plan.conflicts) > 5:
            lines.append("  ... and {} more".format(len(plan.conflicts) - 5))
        lines.append("")

    lines.append("Dry run — no files removed.")
    return "\n".join(lines)


def render_uninstall_confirmation(plan: LifecyclePlan) -> str:
    lines = [
        "EKP uninstall",
        "",
        "Installed version: {}".format(plan.old_version),
        "Profile:           {}".format(plan.profile),
        "Managed files:     {}".format(len(plan.operations)),
        "Delete:            {}".format(plan.delete_count),
        "Missing:           {}".format(plan.missing_count),
    ]
    if plan.directories_to_remove:
        lines.append("Directories:       {}".format(", ".join(plan.directories_to_remove)))
    lines.append("")
    lines.append("Continue? [Y/n]")
    return "\n".join(lines)


def render_uninstall_success(plan: LifecyclePlan, *, warnings: Optional[List[str]] = None) -> str:
    lines = [
        "EKP uninstall complete.",
        "",
        "Profile: {}".format(plan.profile),
        "Removed: {} managed file(s)".format(plan.delete_count),
    ]
    if warnings:
        lines.append("")
        for item in warnings:
            lines.append(item)
    return "\n".join(lines)
