"""CursorDeployer unit tests."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from ekp.install.deploy.cursor import CURSOR_ADAPTER, CursorDeployer
from ekp.install.deploy.engine import SharedDeploymentEngine
from ekp.install.deploy.hashing import sha256_file
from ekp.install.errors import InstallAssemblyError


class CursorDeployerTests(unittest.TestCase):
    def setUp(self):
        self.deployer = CursorDeployer()
        self.engine = SharedDeploymentEngine()

    def _write_mdc(self, cursor_dir: Path, name: str, body: str) -> Path:
        path = cursor_dir / name
        path.write_text(body, encoding="utf-8")
        return path

    def test_valid_cursor_bundle_mapping(self):
        with tempfile.TemporaryDirectory() as tmp:
            bundle = Path(tmp) / "bundle"
            cursor_dir = bundle / "cursor"
            cursor_dir.mkdir(parents=True)
            a = self._write_mdc(cursor_dir, "alpha.mdc", "alpha\n")
            b = self._write_mdc(cursor_dir, "beta.mdc", "beta\n")

            desired = self.engine.normalize_desired_files(
                self.deployer.collect_desired_files(bundle)
            )
            self.assertEqual(self.deployer.assistant_id, CURSOR_ADAPTER)
            self.assertEqual(
                [item.relative_path for item in desired],
                [".cursor/rules/alpha.mdc", ".cursor/rules/beta.mdc"],
            )
            self.assertEqual([item.adapter for item in desired], [CURSOR_ADAPTER, CURSOR_ADAPTER])
            self.assertEqual(desired[0].source_path, a)
            self.assertEqual(desired[1].source_path, b)
            self.assertEqual(desired[0].sha256, sha256_file(a))
            self.assertEqual(desired[1].sha256, sha256_file(b))

    def test_missing_cursor_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            bundle = Path(tmp) / "bundle"
            bundle.mkdir()
            with self.assertRaises(InstallAssemblyError):
                self.deployer.collect_desired_files(bundle)

    def test_unsafe_generated_filename(self):
        with tempfile.TemporaryDirectory() as tmp:
            bundle = Path(tmp) / "bundle"
            cursor_dir = bundle / "cursor"
            cursor_dir.mkdir(parents=True)
            # Simulate a name that would escape if accepted as a path segment.
            bad = cursor_dir / "..evil.mdc"
            # On most filesystems ".." in the filename is just a weird name; deployer
            # rejects names containing ".." as a substring.
            bad.write_text("x\n", encoding="utf-8")
            # Rename to include ".." if the filesystem allowed writing with that name
            # via open; Path.write_text on "..evil.mdc" creates a file named "..evil.mdc".
            with self.assertRaises(InstallAssemblyError):
                self.deployer.collect_desired_files(bundle)

    def test_deterministic_inventory_ignores_discovery_order(self):
        with tempfile.TemporaryDirectory() as tmp:
            bundle = Path(tmp) / "bundle"
            cursor_dir = bundle / "cursor"
            cursor_dir.mkdir(parents=True)
            # Write out of lexical order
            self._write_mdc(cursor_dir, "z.mdc", "z\n")
            self._write_mdc(cursor_dir, "a.mdc", "a\n")
            self._write_mdc(cursor_dir, "m.mdc", "m\n")
            desired = self.engine.normalize_desired_files(
                self.deployer.collect_desired_files(bundle)
            )
            self.assertEqual(
                [item.relative_path for item in desired],
                [
                    ".cursor/rules/a.mdc",
                    ".cursor/rules/m.mdc",
                    ".cursor/rules/z.mdc",
                ],
            )


if __name__ == "__main__":
    unittest.main()
