"""CLI detect command tests."""

import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from ekp.cli import main
from ekp.tests.fixtures import flutter_fixture, symfony_fixture


class DetectCliTests(unittest.TestCase):
    def test_detect_human_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            symfony_fixture(Path(tmp))
            buffer = io.StringIO()
            with redirect_stdout(buffer):
                code = main(["detect", "--path", tmp])
            self.assertEqual(code, 0)
            output = buffer.getvalue()
            self.assertIn("symfony", output)
            self.assertIn("cursor-symfony", output)

    def test_detect_json_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            flutter_fixture(Path(tmp))
            buffer = io.StringIO()
            with redirect_stdout(buffer):
                code = main(["detect", "--json", "--path", tmp])
            self.assertEqual(code, 0)
            payload = json.loads(buffer.getvalue())
            self.assertEqual(payload["recommended_profile"], "cursor-flutter")
            self.assertIn("technologies", payload)
            self.assertIn("tool_signals", payload)

    def test_detect_empty_directory_exit_zero(self):
        with tempfile.TemporaryDirectory() as tmp:
            code = main(["detect", "--path", tmp])
            self.assertEqual(code, 0)

    def test_detect_invalid_path(self):
        code = main(["detect", "--path", "/nonexistent/ekp-detect-path"])
        self.assertEqual(code, 2)

    def test_detect_ambiguous_project(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            symfony_fixture(root)
            from ekp.tests.fixtures import frontend_fixture

            frontend_fixture(root)
            buffer = io.StringIO()
            with redirect_stdout(buffer):
                code = main(["detect", "--path", str(root)])
            self.assertEqual(code, 0)
            output = buffer.getvalue()
            self.assertIn("ambiguous", output)
            self.assertIn("cursor-symfony", output)
            self.assertIn("cursor-frontend", output)

    def test_help_lists_detect(self):
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            try:
                main(["--help"])
            except SystemExit as exc:
                self.assertEqual(exc.code, 0)
        self.assertIn("detect", buffer.getvalue())
