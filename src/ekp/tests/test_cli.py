"""CLI smoke tests."""

import io
import unittest
from contextlib import redirect_stdout

from ekp.cli import main
from ekp.version import get_version


class CliTests(unittest.TestCase):
    def test_help(self):
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            try:
                main(["--help"])
            except SystemExit as exc:
                self.assertEqual(exc.code, 0)
        self.assertIn("ekp", buffer.getvalue())
        self.assertIn("version", buffer.getvalue())
        self.assertIn("detect", buffer.getvalue())
        self.assertIn("install", buffer.getvalue())
        self.assertIn("status", buffer.getvalue())
        self.assertIn("uninstall", buffer.getvalue())

    def test_version(self):
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            code = main(["version"])
        self.assertEqual(code, 0)
        output = buffer.getvalue()
        self.assertIn(get_version(), output)
        self.assertIn("resource_root:", output)
