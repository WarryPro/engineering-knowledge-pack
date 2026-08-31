"""NativeScript technology detector."""

from __future__ import annotations

from pathlib import Path
from typing import List, Optional

from ekp.detection.models import DetectionResult
from ekp.detection.scan import dependency_names, path_exists, read_json_file
from ekp.detection.technology.base import TechnologyDetector


class NativeScriptDetector(TechnologyDetector):
    technology = "nativescript"

    def detect(self, root: Path, diagnostics: List[str]) -> Optional[DetectionResult]:
        evidence: List[str] = []
        package = read_json_file(root / "package.json", diagnostics)
        deps = dependency_names(package)

        for dep in sorted(deps):
            if dep.startswith("@nativescript/") or dep == "nativescript":
                evidence.append("package.json: {}".format(dep))

        for config_name in ("nativescript.config.ts", "nativescript.config.js"):
            if path_exists(root, config_name):
                evidence.append(config_name)

        if path_exists(root, "App_Resources"):
            evidence.append("App_Resources/")

        if not evidence:
            return None

        if any("nativescript.config" in item for item in evidence) or any(
            item.startswith("package.json: @nativescript/") for item in evidence
        ):
            confidence = "high"
        else:
            confidence = "medium"

        return DetectionResult(technology=self.technology, confidence=confidence, evidence=evidence)
