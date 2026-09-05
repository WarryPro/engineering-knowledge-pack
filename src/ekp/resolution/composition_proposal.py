"""Propose requested components from technology detections."""

from __future__ import annotations

from typing import Iterable, List, Optional, Sequence, Tuple

from ekp.composition import (
    ComponentRegistry,
    CompositionError,
    ResolvedComposition,
    resolve_composition,
)
from ekp.detection.models import DetectionResult

MIN_PROPOSAL_CONFIDENCE = frozenset({"high", "medium"})


def resolve_detected_components(
    technologies: Iterable[DetectionResult],
    registry: ComponentRegistry,
) -> Tuple[Optional[ResolvedComposition], List[str]]:
    """
    Derive a canonical composition from medium/high technology detections.

    Technology ids map to component ids by identity. Unknown ids are excluded
    from the proposal and reported as diagnostics. Composition identity does
    not depend on detector display order — reduction + closure are canonical.

    Returns:
        (ResolvedComposition or None when no proposal, diagnostics)
    """
    diagnostics: List[str] = []
    by_tech = {}
    for item in technologies:
        existing = by_tech.get(item.technology)
        if existing is None or _confidence_rank(item.confidence) > _confidence_rank(
            existing.confidence
        ):
            by_tech[item.technology] = item

    candidates: List[str] = []
    for tech, result in by_tech.items():
        if result.confidence not in MIN_PROPOSAL_CONFIDENCE:
            continue
        if not registry.has(tech):
            diagnostics.append(
                "unknown technology {!r} excluded from composition proposal".format(tech)
            )
            continue
        component = registry.get(tech)
        if not component.selectable:
            diagnostics.append(
                "non-selectable component {!r} excluded from composition proposal".format(
                    tech
                )
            )
            continue
        candidates.append(tech)

    if not candidates:
        return None, diagnostics

    try:
        composition = resolve_composition(candidates, registry)
    except CompositionError as exc:
        diagnostics.append("composition proposal failed: {}".format(exc))
        return None, diagnostics

    return composition, diagnostics


def proposed_and_resolved_lists(
    composition: Optional[ResolvedComposition],
) -> Tuple[List[str], List[str]]:
    """Convert an optional composition into report list fields."""
    if composition is None:
        return [], []
    return list(composition.requested_components), list(composition.resolved_components)


def _confidence_rank(confidence: str) -> int:
    return {"high": 3, "medium": 2, "low": 1}.get(confidence, 0)
