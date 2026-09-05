"""Install CLI tests."""

import io
import json
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

from ekp.cli import main
from ekp.install.manifest import ManifestStore
from ekp.tests.fixtures import symfony_fixture


class InstallCliTests(unittest.TestCase):
    def test_help_includes_install(self):
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            try:
                main(["--help"])
            except SystemExit as exc:
                self.assertEqual(exc.code, 0)
        self.assertIn("install", buffer.getvalue())

    def test_symfony_install_json_manifest(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            symfony_fixture(root)
            buffer = io.StringIO()
            stderr = io.StringIO()
            with redirect_stdout(buffer), redirect_stderr(stderr):
                code = main(["install", "--path", str(root), "--yes"])
            self.assertEqual(code, 0)
            manifest = ManifestStore(root).load()
            self.assertEqual(manifest.profile, "project-composition")
            self.assertEqual(manifest.mode, "composition")
            self.assertEqual(len(manifest.managed_files), 83)
            self.assertTrue((root / ".ekp" / "project.yaml").is_file())

    def test_dry_run_stdout(self):
        with tempfile.TemporaryDirectory() as tmp:
            buffer = io.StringIO()
            with redirect_stdout(buffer):
                code = main(
                    ["install", "--path", tmp, "--profile", "cursor-flutter", "--dry-run"]
                )
            self.assertEqual(code, 0)
            output = buffer.getvalue()
            self.assertIn("Dry run", output)
            self.assertIn("cursor-flutter", output)
            self.assertEqual(list(Path(tmp).rglob("*")), [])

    def test_invalid_profile_exit_code(self):
        with tempfile.TemporaryDirectory() as tmp:
            stderr = io.StringIO()
            with redirect_stderr(stderr):
                code = main(
                    ["install", "--path", tmp, "--profile", "cursor-react", "--yes"]
                )
            self.assertEqual(code, 2)
            self.assertIn("Unknown or unsupported", stderr.getvalue())
