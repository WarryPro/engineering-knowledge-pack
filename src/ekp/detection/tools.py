"""AI tool signal detection (informational only)."""

from __future__ import annotations

from pathlib import Path
from typing import List

from ekp.detection.models import ToolSignal
from ekp.detection.scan import path_exists


def detect_tool_signals(root: Path) -> List[ToolSignal]:
    """Detect weak local signals for supported AI tools."""
    signals: List[ToolSignal] = []

    if path_exists(root, ".cursor"):
        evidence = [".cursor/"]
        if path_exists(root, ".cursor", "rules"):
            evidence.append(".cursor/rules/")
        signals.append(
            ToolSignal(tool="cursor", confidence="medium", evidence=evidence)
        )

    if path_exists(root, ".github", "copilot-instructions.md"):
        signals.append(
            ToolSignal(
                tool="copilot",
                confidence="medium",
                evidence=[".github/copilot-instructions.md"],
            )
        )
    elif path_exists(root, ".github", "instructions"):
        signals.append(
            ToolSignal(
                tool="copilot",
                confidence="low",
                evidence=[".github/instructions/"],
            )
        )

    if path_exists(root, ".agents", "rules"):
        signals.append(
            ToolSignal(
                tool="antigravity",
                confidence="medium",
                evidence=[".agents/rules/"],
            )
        )

    if path_exists(root, "CLAUDE.md"):
        evidence = ["CLAUDE.md"]
        if path_exists(root, ".claude"):
            evidence.append(".claude/")
        signals.append(
            ToolSignal(tool="claude", confidence="medium", evidence=evidence)
        )
    elif path_exists(root, ".claude"):
        signals.append(
            ToolSignal(tool="claude", confidence="low", evidence=[".claude/"])
        )

    return signals
