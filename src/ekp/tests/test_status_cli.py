"""Status CLI tests."""

import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from ekp.cli import main
from ekp.install.service import InstallRequest, InstallService
from ekp.tests.fixtures import symfony_fixture


class StatusCliTests(unittest.TestCase):
    def test_help_includes_status(self):
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            try:
                main(["--help"])
            except SystemExit as exc:
                self.assertEqual(exc.code, 0)
        self.assertIn("status", buffer.getvalue())

    def test_not_installed_human(self):
        with tempfile.TemporaryDirectory() as tmp:
            buffer = io.StringIO()
            with redirect_stdout(buffer):
                code = main(["status", "--path", tmp])
            self.assertEqual(code, 0)
            self.assertIn("not installed", buffer.getvalue().lower())

    def test_not_installed_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            buffer = io.StringIO()
            with redirect_stdout(buffer):
                code = main(["status", "--path", tmp, "--json"])
            self.assertEqual(code, 0)
            payload = json.loads(buffer.getvalue())
            self.assertFalse(payload["installed"])
            self.assertEqual(payload["state"], "not_installed")

    def test_healthy_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            symfony_fixture(root)
            main(["install", "--path", str(root), "--yes"])
            buffer = io.StringIO()
            with redirect_stdout(buffer):
                code = main(["status", "--path", str(root), "--json"])
            self.assertEqual(code, 0)
            payload = json.loads(buffer.getvalue())
            self.assertTrue(payload["installed"])
            self.assertEqual(payload["state"], "healthy")
            self.assertEqual(payload["managed_files"]["total"], 83)
            self.assertEqual(payload["managed_files"]["intact"], 83)

    def test_invalid_manifest_exit_code(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manifest = root / ".ekp" / "install.json"
            manifest.parent.mkdir(parents=True)
            manifest.write_text("{bad", encoding="utf-8")
            buffer = io.StringIO()
            with redirect_stdout(buffer):
                code = main(["status", "--path", str(root)])
            self.assertEqual(code, 3)
