"""DevOps technology detector."""

from __future__ import annotations

from pathlib import Path
from typing import List, Optional

from ekp.detection.models import DetectionResult
from ekp.detection.scan import path_exists
from ekp.detection.technology.base import TechnologyDetector


class DevOpsDetector(TechnologyDetector):
    technology = "devops"

    def detect(self, root: Path, diagnostics: List[str]) -> Optional[DetectionResult]:
        evidence: List[str] = []

        if path_exists(root, "Dockerfile"):
            evidence.append("Dockerfile")
        for name in ("docker-compose.yml", "docker-compose.yaml", "compose.yml", "compose.yaml"):
            if path_exists(root, name):
                evidence.append(name)

        workflows = root / ".github" / "workflows"
        if workflows.is_dir():
            workflow_files = sorted(p.name for p in workflows.glob("*.yml")) + sorted(
                p.name for p in workflows.glob("*.yaml")
            )
            if workflow_files:
                evidence.append(".github/workflows/ ({})".format(", ".join(workflow_files[:3])))

        if not evidence:
            return None

        if path_exists(root, "Dockerfile") or workflows.is_dir():
            confidence = "medium"
        else:
            confidence = "low"

        if path_exists(root, "Dockerfile") and workflows.is_dir():
            confidence = "medium"

        return DetectionResult(technology=self.technology, confidence=confidence, evidence=evidence)
