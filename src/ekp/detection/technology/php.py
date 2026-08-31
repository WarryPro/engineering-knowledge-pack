"""PHP technology detector."""

from __future__ import annotations

from pathlib import Path
from typing import List, Optional

from ekp.detection.models import DetectionResult
from ekp.detection.scan import (
    composer_require_names,
    count_limited_files,
    path_exists,
    read_json_file,
)
from ekp.detection.technology.base import TechnologyDetector


class PHPDetector(TechnologyDetector):
    technology = "php"

    def detect(self, root: Path, diagnostics: List[str]) -> Optional[DetectionResult]:
        evidence: List[str] = []
        composer_path = root / "composer.json"
        composer = read_json_file(composer_path, diagnostics)
        requires = composer_require_names(composer)

        if "php" in requires:
            evidence.append("composer.json: php requirement")
        if composer is not None and composer_path.is_file():
            evidence.append("composer.json")

        php_count = count_limited_files(root, ".php")
        if php_count:
            evidence.append(".php source files ({})".format(php_count))

        if not evidence:
            return None

        if "php" in requires and composer is not None:
            confidence = "high"
        elif composer is not None and php_count >= 3:
            confidence = "medium"
        elif php_count >= 1:
            confidence = "low"
        else:
            confidence = "medium"

        if path_exists(root, "src") and composer is not None:
            if confidence == "medium":
                confidence = "high"

        return DetectionResult(technology=self.technology, confidence=confidence, evidence=evidence)
