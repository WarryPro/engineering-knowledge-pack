"""Symfony technology detector."""

from __future__ import annotations

from pathlib import Path
from typing import List, Optional

from ekp.detection.models import DetectionResult
from ekp.detection.scan import composer_require_names, path_exists, read_json_file
from ekp.detection.technology.base import TechnologyDetector

SYMFONY_PACKAGES = (
    "symfony/framework-bundle",
    "symfony/symfony",
    "symfony/flex",
)


class SymfonyDetector(TechnologyDetector):
    technology = "symfony"

    def detect(self, root: Path, diagnostics: List[str]) -> Optional[DetectionResult]:
        evidence: List[str] = []

        if path_exists(root, "symfony.lock"):
            evidence.append("symfony.lock")

        composer = read_json_file(root / "composer.json", diagnostics)
        requires = composer_require_names(composer)
        for package in SYMFONY_PACKAGES:
            if package in requires:
                evidence.append("composer.json: {}".format(package))

        if path_exists(root, "config", "bundles.php"):
            evidence.append("config/bundles.php")
        if path_exists(root, "bin", "console"):
            evidence.append("bin/console")

        if not evidence:
            return None

        if path_exists(root, "symfony.lock") or any(
            pkg in requires for pkg in SYMFONY_PACKAGES
        ):
            confidence = "high"
        elif path_exists(root, "config", "bundles.php") and path_exists(root, "bin", "console"):
            confidence = "medium"
        else:
            confidence = "medium"

        return DetectionResult(technology=self.technology, confidence=confidence, evidence=evidence)
