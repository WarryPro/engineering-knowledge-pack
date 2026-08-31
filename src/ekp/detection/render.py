"""Human-readable and JSON rendering for detection reports."""

from __future__ import annotations

import json
from typing import Any, Dict

from ekp.detection.models import DetectionReport


def render_human(report: DetectionReport) -> str:
    lines = ["Scanning: {}".format(report.path), "", "Technologies:"]
    if not report.technologies:
        lines.append("  (none detected)")
    else:
        for item in report.technologies:
            lines.append("  {:14} {}".format(item.technology, item.confidence))
            for evidence in item.evidence:
                lines.append("    - {}".format(evidence))

    lines.extend(["", "AI tool signals:"])
    if not report.tool_signals:
        lines.append("  (none detected)")
    else:
        for signal in report.tool_signals:
            lines.append(
                "  {:14} {} ({})".format(
                    signal.tool, signal.confidence, signal.signal_type
                )
            )
            for evidence in signal.evidence:
                lines.append("    - {}".format(evidence))

    lines.extend(["", "Recommendation:"])
    if report.recommended_profile:
        lines.append("  {}".format(report.recommended_profile))
    elif report.ambiguous:
        lines.append("  (ambiguous)")
        for candidate in report.candidate_profiles:
            lines.append("  candidate: {}".format(candidate))
        if report.reason:
            lines.append("  reason: {}".format(report.reason))
    else:
        lines.append("  (none — interactive selection required)")

    if report.additional_concerns:
        lines.extend(["", "Additional concerns:"])
        for concern in report.additional_concerns:
            lines.append("  {}".format(concern))

    if report.diagnostics:
        lines.extend(["", "Diagnostics:"])
        for message in report.diagnostics:
            lines.append("  - {}".format(message))

    return "\n".join(lines)


def report_to_dict(report: DetectionReport) -> Dict[str, Any]:
    return {
        "path": report.path,
        "technologies": [
            {
                "technology": item.technology,
                "confidence": item.confidence,
                "evidence": list(item.evidence),
            }
            for item in report.technologies
        ],
        "tool_signals": [
            {
                "tool": signal.tool,
                "confidence": signal.confidence,
                "signal_type": signal.signal_type,
                "evidence": list(signal.evidence),
            }
            for signal in report.tool_signals
        ],
        "recommended_profile": report.recommended_profile,
        "candidate_profiles": list(report.candidate_profiles),
        "additional_concerns": list(report.additional_concerns),
        "ambiguous": report.ambiguous,
        "reason": report.reason,
        "diagnostics": list(report.diagnostics),
    }


def render_json(report: DetectionReport) -> str:
    return json.dumps(report_to_dict(report), indent=2, sort_keys=True) + "\n"
