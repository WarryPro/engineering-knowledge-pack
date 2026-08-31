"""Detection orchestration service."""

from __future__ import annotations

from pathlib import Path
from typing import Iterable, List, Optional

from ekp.detection.models import DetectionReport, DetectionResult
from ekp.detection.technology import DEFAULT_DETECTORS, TechnologyDetector
from ekp.detection.tools import detect_tool_signals
from ekp.detection.scan import resolve_scan_root
from ekp.resolution.resolver import apply_resolution


class DetectionService:
    """Run local technology and tool detection for a consumer project."""

    def __init__(self, detectors: Optional[Iterable[TechnologyDetector]] = None):
        self._detectors = tuple(detectors or DEFAULT_DETECTORS)

    def detect(self, path: Optional[str] = None) -> DetectionReport:
        root = resolve_scan_root(path)
        diagnostics: List[str] = []
        technologies: List[DetectionResult] = []

        for detector in self._detectors:
            try:
                result = detector.detect(root, diagnostics)
            except OSError as exc:
                diagnostics.append("{} detector: {}".format(detector.technology, exc))
                continue
            if result is not None:
                technologies.append(result)

        technologies.sort(
            key=lambda item: (
                _technology_order(item.technology),
                -_confidence_rank(item.confidence),
            )
        )

        report = DetectionReport(
            path=str(root),
            technologies=technologies,
            tool_signals=detect_tool_signals(root),
            diagnostics=diagnostics,
        )
        return apply_resolution(report)


def _technology_order(technology: str) -> int:
    order = [
        "symfony",
        "php",
        "typescript",
        "frontend",
        "nativescript",
        "flutter",
        "devops",
    ]
    try:
        return order.index(technology)
    except ValueError:
        return len(order)


def _confidence_rank(confidence: str) -> int:
    return {"high": 3, "medium": 2, "low": 1}.get(confidence, 0)
