"""AI tool signal tests."""

import tempfile
import unittest
from pathlib import Path

from ekp.detection.service import DetectionService
from ekp.detection.tools import detect_tool_signals
from ekp.tests.fixtures import symfony_fixture


class ToolSignalTests(unittest.TestCase):
    def test_cursor_signal(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / ".cursor" / "rules").mkdir(parents=True)
            signals = detect_tool_signals(root)
            self.assertEqual(signals[0].tool, "cursor")

    def test_copilot_signal(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / ".github").mkdir()
            (root / ".github" / "copilot-instructions.md").write_text("x", encoding="utf-8")
            signals = detect_tool_signals(root)
            self.assertEqual(signals[0].tool, "copilot")

    def test_antigravity_signal(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / ".agents" / "rules").mkdir(parents=True)
            signals = detect_tool_signals(root)
            self.assertEqual(signals[0].tool, "antigravity")

    def test_claude_signal(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "CLAUDE.md").write_text("# project", encoding="utf-8")
            signals = detect_tool_signals(root)
            self.assertEqual(signals[0].tool, "claude")

    def test_tool_signals_do_not_change_recommendation(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            symfony_fixture(root)
            (root / ".cursor" / "rules").mkdir(parents=True)
            report = DetectionService().detect(str(root))
            self.assertEqual(report.recommended_profile, "cursor-symfony")
            self.assertTrue(any(signal.tool == "cursor" for signal in report.tool_signals))
