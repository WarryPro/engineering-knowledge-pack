"""Technology detector contract."""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import List, Optional

from ekp.detection.models import DetectionResult


class TechnologyDetector(ABC):
    """Detect one EKP technology vertical from local project evidence."""

    technology: str

    @abstractmethod
    def detect(self, root: Path, diagnostics: List[str]) -> Optional[DetectionResult]:
        """Return a detection result or None when no signal is found."""
