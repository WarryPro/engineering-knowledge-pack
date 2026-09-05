"""Human-readable and JSON rendering for status results."""

from __future__ import annotations

import json
from typing import Any, Dict

from ekp.install.manifest import INSTALL_MODE_COMPOSITION
from ekp.status.models import StatusResult, StatusState


def render_human(result: StatusResult) -> str:
    if result.state == StatusState.NOT_INSTALLED:
        return "EKP is not installed in this project."

    if result.state == StatusState.INVALID:
        lines = ["EKP installation", ""]
        if result.mode:
            lines.append("Mode: {}".format(result.mode))
            lines.append("")
        lines.append("State: INVALID")
        lines.append("")
        if result.error_message:
            lines.append(result.error_message)
        return "\n".join(lines)

    lines = [
        "EKP installation",
        "",
        "Installed version: {}".format(result.installed_version),
        "Running CLI:       {}".format(result.running_version),
        "Mode:              {}".format(result.mode or "legacy-profile"),
        "Profile:           {}".format(result.profile),
        "Adapters:          {}".format(", ".join(result.adapters)),
        "",
    ]

    if result.mode == INSTALL_MODE_COMPOSITION:
        lines.append("Requested components:")
        for item in result.requested_components:
            lines.append("  {}".format(item))
        lines.append("")
        lines.append("Resolved components:")
        for item in result.resolved_components:
            lines.append("  {}".format(item))
        lines.append("")
        lines.append("Assistants:")
        for item in result.assistants:
            lines.append("  {}".format(item))
        lines.append("")
        if result.configuration_drift:
            lines.append("Configuration:     DRIFT")
        else:
            lines.append("Configuration:     matched")
        lines.append("")

    lines.extend(
        [
            "Managed files:     {}".format(result.managed_total),
            "Intact:            {}".format(result.intact_count),
            "Modified:          {}".format(len(result.modified_paths)),
            "Missing:           {}".format(len(result.missing_paths)),
            "",
            "State: {}".format(result.state.name),
        ]
    )

    if result.state == StatusState.VERSION_MISMATCH:
        lines.extend(
            [
                "",
                "This CLI does not modify the installation.",
            ]
        )

    if result.state == StatusState.CONFIGURATION_DRIFT:
        lines.extend(
            [
                "",
                "Project configuration has changed since EKP was installed.",
                "Automatic reconfiguration is not supported in v0.18.",
            ]
        )

    if result.modified_paths:
        lines.extend(["", "Modified managed files:"])
        for path in result.modified_paths[:10]:
            lines.append("  {}".format(path))
        if len(result.modified_paths) > 10:
            lines.append("  ... and {} more".format(len(result.modified_paths) - 10))

    if result.missing_paths:
        lines.extend(["", "Missing managed files:"])
        for path in result.missing_paths[:10]:
            lines.append("  {}".format(path))
        if len(result.missing_paths) > 10:
            lines.append("  ... and {} more".format(len(result.missing_paths) - 10))

    return "\n".join(lines)


def result_to_dict(result: StatusResult) -> Dict[str, Any]:
    payload: Dict[str, Any] = {
        "installed": result.installed,
        "state": result.state.value,
        "project_root": result.project_root,
        "running_version": result.running_version,
    }
    if result.state == StatusState.NOT_INSTALLED:
        return payload

    if result.mode is not None:
        payload["mode"] = result.mode

    if result.state == StatusState.INVALID:
        payload["error"] = result.error_message
        if result.installed_version:
            payload["installed_version"] = result.installed_version
        if result.profile:
            payload["profile"] = result.profile
        return payload

    payload.update(
        {
            "schema_version": result.schema_version,
            "installed_version": result.installed_version,
            "profile": result.profile,
            "adapters": list(result.adapters),
            "install_root": result.install_root,
            "installed_at": result.installed_at,
            "managed_files": {
                "total": result.managed_total,
                "intact": result.intact_count,
                "modified": list(result.modified_paths),
                "missing": list(result.missing_paths),
            },
        }
    )
    if result.unsafe_paths:
        payload["unsafe_paths"] = list(result.unsafe_paths)

    if result.mode == INSTALL_MODE_COMPOSITION:
        payload["requested_components"] = list(result.requested_components)
        payload["resolved_components"] = list(result.resolved_components)
        payload["assistants"] = list(result.assistants)
        payload["configuration_sha256"] = result.configuration_sha256
        payload["current_configuration_sha256"] = result.current_configuration_sha256
        payload["configuration_drift"] = bool(result.configuration_drift)

    return payload


def render_json(result: StatusResult) -> str:
    return json.dumps(result_to_dict(result), indent=2, sort_keys=True) + "\n"
