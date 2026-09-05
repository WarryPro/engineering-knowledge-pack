"""Detection result models."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional

CONFIDENCE_LEVELS = ("high", "medium", "low")


@dataclass
class DetectionResult:
    """Technology signal detected in a consumer project."""

    technology: str
    confidence: str
    evidence: List[str] = field(default_factory=list)

    def __post_init__(self):
        if self.confidence not in CONFIDENCE_LEVELS:
            raise ValueError("Invalid confidence: {}".format(self.confidence))


@dataclass
class ToolSignal:
    """Weak local signal that an AI tool may be configured."""

    tool: str
    confidence: str
    evidence: List[str] = field(default_factory=list)
    signal_type: str = "detected signal"


@dataclass
class DetectionReport:
    """Complete read-only detection output."""

    path: str
    technologies: List[DetectionResult] = field(default_factory=list)
    tool_signals: List[ToolSignal] = field(default_factory=list)
    recommended_profile: Optional[str] = None
    candidate_profiles: List[str] = field(default_factory=list)
    additional_concerns: List[str] = field(default_factory=list)
    diagnostics: List[str] = field(default_factory=list)
    ambiguous: bool = False
    reason: Optional[str] = None
    # Composition-aware additive fields (AW-D). Empty when no medium/high proposal.
    proposed_components: List[str] = field(default_factory=list)
    resolved_components: List[str] = field(default_factory=list)
