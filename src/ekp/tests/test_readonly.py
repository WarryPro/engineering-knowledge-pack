"""Read-only filesystem audit for ekp detect."""

import os
import tempfile
import unittest
from pathlib import Path

from ekp.cli import main
from ekp.tests.fixtures import symfony_fixture


class ReadOnlyDetectTests(unittest.TestCase):
    def test_detect_does_not_modify_fixture_tree(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            symfony_fixture(root)
            before = {
                str(path.relative_to(root)): (
                    path.stat().st_mtime_ns,
                    path.stat().st_size,
                )
                for path in root.rglob("*")
                if path.is_file()
            }

            code = main(["detect", "--path", str(root)])
            self.assertEqual(code, 0)

            after = {
                str(path.relative_to(root)): (
                    path.stat().st_mtime_ns,
                    path.stat().st_size,
                )
                for path in root.rglob("*")
                if path.is_file()
            }

            self.assertEqual(before, after)
            self.assertFalse((root / ".ekp").exists())
            self.assertFalse((root / "dist").exists())
