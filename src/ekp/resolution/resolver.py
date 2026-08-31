"""Profile recommendation from technology detections."""

from __future__ import annotations

from typing import Dict, Iterable, List, Optional, Set, Tuple

from ekp.detection.models import DetectionResult, DetectionReport

TECHNOLOGY_TO_PROFILE = {
    "nativescript": "cursor-nativescript",
    "flutter": "cursor-flutter",
    "symfony": "cursor-symfony",
    "frontend": "cursor-frontend",
    "typescript": "cursor-typescript",
    "php": "cursor-php",
    "devops": "cursor-devops",
}

SPECIALIZATIONS = {
    "symfony": {"php"},
    "frontend": {"typescript"},
    "nativescript": {"typescript"},
}

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
    Resolve detections to a recommended Cursor profile.

    Returns:
        recommended_profile, candidate_profiles, additional_concerns,
        ambiguous, reason
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
        profile = TECHNOLOGY_TO_PROFILE[ordered_active[0]]
        return profile, [profile], additional, False, None

    candidates = [TECHNOLOGY_TO_PROFILE[tech] for tech in ordered_active]
    reason = "multiple independent primary stacks"
    return None, candidates, additional, True, reason


def apply_resolution(report: DetectionReport) -> DetectionReport:
    """Populate recommendation fields on a detection report."""
    (
        report.recommended_profile,
        report.candidate_profiles,
        report.additional_concerns,
        report.ambiguous,
        report.reason,
    ) = resolve_profile(report.technologies)
    return report


def _confidence_rank(confidence: str) -> int:
    return {"high": 3, "medium": 2, "low": 1}.get(confidence, 0)
