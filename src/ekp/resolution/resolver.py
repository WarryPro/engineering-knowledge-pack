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

# Display-only candidate ordering for legacy single-profile recommendation.
# Not composition identity / dependency SoT (ComponentRegistry owns that).
_LEGACY_PRIMARY_DISPLAY_ORDER = (
    "nativescript",
    "flutter",
    "symfony",
    "frontend",
    "typescript",
    "php",
    "devops",
)

MIN_PRIMARY_CONFIDENCE = {"high", "medium"}


def resolve_profile(
    technologies: Iterable[DetectionResult],
    registry: Optional[ComponentRegistry] = None,
) -> Tuple[
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

    Dependency collapse uses ComponentRegistry.requires (not a duplicated table).
    """
    loaded = registry
    if loaded is None:
        loaded = ComponentRegistry.load(get_ekp_root())

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

    # Collapse implied dependencies using the component graph.
    for tech in list(active):
        if not loaded.has(tech):
            continue
        for required in loaded.get(tech).requires:
            active.discard(required)

    additional: List[str] = []
    if "devops" in active and len(active) > 1:
        # Legacy display: devops co-presence is an additional concern, not a
        # competing primary profile. Composition treats devops as first-class.
        active.remove("devops")
        additional.append("devops")

    ordered_active = [
        tech for tech in _LEGACY_PRIMARY_DISPLAY_ORDER if tech in active
    ]
    for tech in sorted(active):
        if tech not in ordered_active:
            ordered_active.append(tech)

    if len(ordered_active) == 0:
        return None, [], additional, False, None

    if len(ordered_active) == 1:
        profile = _legacy_profile_for_technology(ordered_active[0], loaded)
        return profile, [profile], additional, False, None

    candidates = [
        _legacy_profile_for_technology(tech, loaded) for tech in ordered_active
    ]
    reason = "multiple independent primary stacks"
    return None, candidates, additional, True, reason


def apply_resolution(
    report: DetectionReport,
    registry: Optional[ComponentRegistry] = None,
) -> DetectionReport:
    """Populate legacy profile fields and composition-aware proposal fields."""
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
            (
                report.recommended_profile,
                report.candidate_profiles,
                report.additional_concerns,
                report.ambiguous,
                report.reason,
            ) = None, [], [], False, None
            return report

    (
        report.recommended_profile,
        report.candidate_profiles,
        report.additional_concerns,
        report.ambiguous,
        report.reason,
    ) = resolve_profile(report.technologies, loaded)

    composition, proposal_diagnostics = resolve_detected_components(
        report.technologies, loaded
    )
    report.diagnostics.extend(proposal_diagnostics)
    proposed, resolved = proposed_and_resolved_lists(composition)
    report.proposed_components = proposed
    report.resolved_components = resolved
    return report


def _legacy_profile_for_technology(
    technology: str, registry: ComponentRegistry
) -> str:
    """Map a technology id to a cursor-* profile via Component.legacy_profile."""
    if not registry.has(technology):
        raise KeyError(technology)
    profile = registry.get(technology).legacy_profile
    if not profile:
        raise KeyError(technology)
    return profile


def _confidence_rank(confidence: str) -> int:
    return {"high": 3, "medium": 2, "low": 1}.get(confidence, 0)


# Backward-compatible names for any external imports (no longer SoT tables).
def __getattr__(name: str):
    if name in ("TECHNOLOGY_TO_PROFILE", "SPECIALIZATIONS", "PRIMARY_ORDER"):
        raise AttributeError(
            "ekp.resolution.resolver.{} was removed; use ComponentRegistry "
            "(legacy_profile / requires) as the composition source of truth. "
            "Legacy profile recommendation uses resolve_profile().".format(name)
        )
    raise AttributeError("module {!r} has no attribute {!r}".format(__name__, name))
