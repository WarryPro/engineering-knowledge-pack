"""TypeScript technology detector."""

from __future__ import annotations

from pathlib import Path
from typing import List, Optional

from ekp.detection.models import DetectionResult
from ekp.detection.scan import (
    count_limited_files,
    dependency_names,
    path_exists,
    read_json_file,
)
from ekp.detection.technology.base import TechnologyDetector


class TypeScriptDetector(TechnologyDetector):
    technology = "typescript"

    def detect(self, root: Path, diagnostics: List[str]) -> Optional[DetectionResult]:
        evidence: List[str] = []
        has_tsconfig = path_exists(root, "tsconfig.json")
        package = read_json_file(root / "package.json", diagnostics)
        deps = dependency_names(package)

        if has_tsconfig:
            evidence.append("tsconfig.json")
        if "typescript" in deps:
            evidence.append("package.json: typescript")

        ts_count = count_limited_files(root, ".ts") + count_limited_files(root, ".tsx")
        if ts_count:
            evidence.append(".ts/.tsx source files ({})".format(ts_count))

        if not evidence:
            return None

        if has_tsconfig and "typescript" in deps:
            confidence = "high"
        elif has_tsconfig or ("typescript" in deps and ts_count >= 2):
            confidence = "medium"
        else:
            confidence = "low"

        return DetectionResult(technology=self.technology, confidence=confidence, evidence=evidence)
