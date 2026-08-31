"""Frontend technology detector."""

from __future__ import annotations

from pathlib import Path
from typing import List, Optional

from ekp.detection.models import DetectionResult
from ekp.detection.scan import dependency_names, path_exists, read_json_file
from ekp.detection.technology.base import TechnologyDetector

UI_FRAMEWORKS = (
    "react",
    "react-dom",
    "vue",
    "nuxt",
    "angular",
    "@angular/core",
    "svelte",
    "@sveltejs/kit",
    "next",
    "vite",
    "@vitejs/plugin-react",
    "@vitejs/plugin-vue",
)

FRONTEND_PATHS = (
    ("src", "components"),
    ("src", "views"),
    ("src", "pages"),
    ("app", "components"),
)


class FrontendDetector(TechnologyDetector):
    technology = "frontend"

    def detect(self, root: Path, diagnostics: List[str]) -> Optional[DetectionResult]:
        evidence: List[str] = []
        package = read_json_file(root / "package.json", diagnostics)
        deps = dependency_names(package)

        for dep in UI_FRAMEWORKS:
            if dep in deps:
                evidence.append("package.json: {}".format(dep))

        for config_name in (
            "vite.config.ts",
            "vite.config.js",
            "webpack.config.js",
            "angular.json",
        ):
            if path_exists(root, config_name):
                evidence.append(config_name)

        for parts in FRONTEND_PATHS:
            if path_exists(root, *parts):
                evidence.append("/".join(parts) + "/")

        if path_exists(root, "index.html") and path_exists(root, "package.json"):
            evidence.append("browser application structure (index.html + package.json)")

        if not evidence:
            return None

        framework_hits = [item for item in evidence if item.startswith("package.json:")]
        if framework_hits or any(
            name in evidence
            for name in ("vite.config.ts", "vite.config.js", "webpack.config.js", "angular.json")
        ):
            confidence = "high"
        elif any(item.endswith("/") for item in evidence):
            confidence = "medium"
        else:
            confidence = "medium"

        return DetectionResult(technology=self.technology, confidence=confidence, evidence=evidence)
