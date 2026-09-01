"""Version metadata tests."""

import tempfile
import unittest
from importlib.metadata import PackageNotFoundError
from pathlib import Path
from unittest import mock

from ekp.version import _read_project_version, _read_source_version, get_version


class VersionTests(unittest.TestCase):
    def test_version_is_non_empty(self):
        version_value = get_version()
        self.assertTrue(version_value)
        self.assertEqual(version_value, "0.15.0")

    def test_get_version_uses_installed_metadata(self):
        with mock.patch("ekp.version.version", return_value="9.9.9") as metadata_version:
            self.assertEqual(get_version(), "9.9.9")
        metadata_version.assert_called_once_with("engineering-knowledge-pack")

    def test_get_version_falls_back_to_pyproject_on_package_not_found(self):
        with mock.patch(
            "ekp.version.version",
            side_effect=PackageNotFoundError("engineering-knowledge-pack"),
        ):
            self.assertEqual(get_version(), "0.15.0")

    def test_read_source_version_reads_pyproject(self):
        with mock.patch(
            "ekp.version.version",
            side_effect=PackageNotFoundError("engineering-knowledge-pack"),
        ):
            self.assertEqual(_read_source_version(), "0.15.0")

    def test_install_uses_same_version_as_get_version(self):
        with mock.patch(
            "ekp.version.version",
            side_effect=PackageNotFoundError("engineering-knowledge-pack"),
        ):
            resolved = get_version()
        self.assertEqual(resolved, "0.15.0")
        self.assertNotEqual(resolved, "0.15.0.dev0")

    def test_read_project_version_parses_static_pep621_metadata(self):
        with tempfile.TemporaryDirectory() as tmp:
            pyproject = Path(tmp) / "pyproject.toml"
            pyproject.write_text(
                '[build-system]\nrequires = ["hatchling"]\n\n'
                '[project]\n'
                'name = "engineering-knowledge-pack"\n'
                'version = "1.2.3"\n',
                encoding="utf-8",
            )
            self.assertEqual(_read_project_version(pyproject), "1.2.3")

    def test_read_source_version_raises_when_pyproject_missing(self):
        with mock.patch("ekp.version.get_ekp_root", return_value=Path("/missing/root")):
            with self.assertRaisesRegex(RuntimeError, "Cannot determine EKP version"):
                _read_source_version()

    def test_read_source_version_raises_when_version_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "pyproject.toml").write_text(
                "[project]\nname = \"engineering-knowledge-pack\"\n",
                encoding="utf-8",
            )
            with mock.patch("ekp.version.get_ekp_root", return_value=root):
                with self.assertRaisesRegex(RuntimeError, "Cannot determine EKP version"):
                    _read_source_version()

    def test_read_source_version_raises_when_version_malformed(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "pyproject.toml").write_text(
                "[project]\nversion = unquoted\n",
                encoding="utf-8",
            )
            with mock.patch("ekp.version.get_ekp_root", return_value=root):
                with self.assertRaisesRegex(RuntimeError, "Cannot determine EKP version"):
                    _read_source_version()
