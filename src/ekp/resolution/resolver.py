"""Profile recommendation from technology detections."""

from __future__ import annotations

from typing import Dict, Iterable, List, Optional, Set, Tuple

from ekp.composition import ComponentRegistry
from ekp.detection.models import DetectionResult, DetectionReport
from ekp.paths import get_ekp_root
from ekp.resolution.composition_proposal import (
    proposed_and_resolved_lists,
    resolve_detected_components,
)

# Temporary legacy-profile shim for v0.17-compatible install selection.
# Composition proposal does NOT use these tables — ComponentRegistry owns
# composition facts via reduce_requested_components / resolve_composition.
TECHNOLOGY_TO_PROFILE = {
    "nativescript": "cursor-nativescript",
    "flutter": "cursor-flutter",
    "symfony": "cursor-symfony",
    "frontend": "cursor-frontend",
    "typescript": "cursor-typescript",
    "php": "cursor-php",
    "devops": "cursor-devops",
}

# Legacy single-profile specialization collapse only (not composition identity).
SPECIALIZATIONS = {
    "symfony": {"php"},
    "frontend": {"typescript"},
    "nativescript": {"typescript"},
}

# Display / legacy candidate ordering only — not composition identity.
PRIMARY_ORDER = (
    "nativescript",
    "flutter",
    "symfony",
    "frontend",
    "typescript",
    "php",
    "devops",
)

MIN_PRIMARY_CONFIDENCE = {"high", "medium"}


def resolve_profile(technologies: Iterable[DetectionResult]) -> Tuple[
    Optional[str],
    List[str],
    List[str],
    bool,
    Optional[str],
]:
    """
    Resolve detections to a recommended Cursor profile (legacy compatibility).

    Returns:
        recommended_profile, candidate_profiles, additional_concerns,
        ambiguous, reason

    Multi-primary stacks remain ambiguous for legacy single-profile install.
    Composition fields are populated separately and treat multi-stack as valid.
    """
    by_tech: Dict[str, DetectionResult] = {}
    for item in technologies:
        existing = by_tech.get(item.technology)
        if existing is None or _confidence_rank(item.confidence) > _confidence_rank(
            existing.confidence
        ):
            by_tech[item.technology] = item

    active: Set[str] = {
        tech
        for tech, result in by_tech.items()
        if result.confidence in MIN_PRIMARY_CONFIDENCE
    }

    if not active:
        return None, [], [], False, None

    for primary, subsumed in SPECIALIZATIONS.items():
        if primary in active:
            active -= subsumed

    additional: List[str] = []
    if "devops" in active and len(active) > 1:
        active.remove("devops")
        additional.append("devops")

    ordered_active = [tech for tech in PRIMARY_ORDER if tech in active]

    if len(ordered_active) == 0:
        return None, [], additional, False, None

    if len(ordered_active) == 1:
        profile = _legacy_profile_for_technology(ordered_active[0])
        return profile, [profile], additional, False, None

    candidates = [_legacy_profile_for_technology(tech) for tech in ordered_active]
    reason = "multiple independent primary stacks"
    return None, candidates, additional, True, reason


def apply_resolution(
    report: DetectionReport,
    registry: Optional[ComponentRegistry] = None,
) -> DetectionReport:
    """Populate legacy profile fields and composition-aware proposal fields."""
    (
        report.recommended_profile,
        report.candidate_profiles,
        report.additional_concerns,
        report.ambiguous,
        report.reason,
    ) = resolve_profile(report.technologies)

    loaded = registry
    if loaded is None:
        try:
            loaded = ComponentRegistry.load(get_ekp_root())
        except Exception as exc:  # pragma: no cover - resource integrity
            report.diagnostics.append(
                "component registry unavailable for composition proposal: {}".format(exc)
            )
            report.proposed_components = []
            report.resolved_components = []
            return report

    composition, proposal_diagnostics = resolve_detected_components(
        report.technologies, loaded
    )
    report.diagnostics.extend(proposal_diagnostics)
    proposed, resolved = proposed_and_resolved_lists(composition)
    report.proposed_components = proposed
    report.resolved_components = resolved
    return report


def _legacy_profile_for_technology(technology: str) -> str:
    """Map a technology id to a cursor-* profile for legacy install compatibility."""
    # Prefer TECHNOLOGY_TO_PROFILE shim (mirrors Component.legacy_profile today).
    return TECHNOLOGY_TO_PROFILE[technology]


def _confidence_rank(confidence: str) -> int:
    return {"high": 3, "medium": 2, "low": 1}.get(confidence, 0)
