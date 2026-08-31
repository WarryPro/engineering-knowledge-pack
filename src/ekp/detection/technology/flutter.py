"""Flutter technology detector."""

from __future__ import annotations

import re
from pathlib import Path
from typing import List, Optional

from ekp.detection.models import DetectionResult
from ekp.detection.scan import path_exists, read_text_lines
from ekp.detection.technology.base import TechnologyDetector


class FlutterDetector(TechnologyDetector):
    technology = "flutter"

    def detect(self, root: Path, diagnostics: List[str]) -> Optional[DetectionResult]:
        evidence: List[str] = []
        pubspec_path = root / "pubspec.yaml"
        pubspec_text = read_text_lines(pubspec_path, diagnostics)

        has_flutter_sdk = False
        if pubspec_text:
            evidence.append("pubspec.yaml")
            if re.search(r"^\s*flutter\s*:", pubspec_text, re.MULTILINE):
                has_flutter_sdk = True
                evidence.append("pubspec.yaml: flutter SDK")

        if path_exists(root, "lib", "main.dart"):
            evidence.append("lib/main.dart")
        elif path_exists(root, "lib"):
            evidence.append("lib/")

        if not evidence or not has_flutter_sdk:
            return None

        if has_flutter_sdk and path_exists(root, "lib", "main.dart"):
            confidence = "high"
        else:
            confidence = "medium"

        return DetectionResult(technology=self.technology, confidence=confidence, evidence=evidence)
