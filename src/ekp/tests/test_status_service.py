"""Status service tests."""

import json
import tempfile
import unittest
from pathlib import Path

from ekp.install.service import InstallRequest, InstallService
from ekp.status.models import StatusState
from ekp.status.service import StatusRequest, StatusService
from ekp.tests.fixtures import symfony_fixture


class StatusServiceTests(unittest.TestCase):
    def setUp(self):
        self.service = StatusService()

    def test_not_installed(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = self.service.inspect(StatusRequest(path=tmp))
            self.assertFalse(result.installed)
            self.assertEqual(result.state, StatusState.NOT_INSTALLED)
            self.assertEqual(result.exit_code, 0)

    def test_healthy_after_install(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            symfony_fixture(root)
            InstallService().install(InstallRequest(path=str(root), assume_yes=True))
            result = self.service.inspect(StatusRequest(path=str(root)))
            self.assertTrue(result.installed)
            self.assertEqual(result.state, StatusState.HEALTHY)
            self.assertEqual(result.managed_total, 83)
            self.assertEqual(result.intact_count, 83)
            self.assertEqual(result.modified_paths, [])
            self.assertEqual(result.missing_paths, [])

    def test_modified_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            symfony_fixture(root)
            InstallService().install(InstallRequest(path=str(root), assume_yes=True))
            target = next((root / ".cursor" / "rules").glob("*.mdc"))
            target.write_text("modified\n", encoding="utf-8")
            result = self.service.inspect(StatusRequest(path=str(root)))
            self.assertEqual(result.state, StatusState.MODIFIED)
            self.assertEqual(len(result.modified_paths), 1)
            self.assertEqual(result.exit_code, 0)

    def test_missing_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            symfony_fixture(root)
            InstallService().install(InstallRequest(path=str(root), assume_yes=True))
            target = next((root / ".cursor" / "rules").glob("*.mdc"))
            rel = target.relative_to(root).as_posix()
            target.unlink()
            result = self.service.inspect(StatusRequest(path=str(root)))
            self.assertEqual(result.state, StatusState.INCOMPLETE)
            self.assertIn(rel, result.missing_paths)
            self.assertEqual(result.exit_code, 0)

    def test_version_mismatch(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            symfony_fixture(root)
            InstallService().install(InstallRequest(path=str(root), assume_yes=True))
            manifest_path = root / ".ekp" / "install.json"
            payload = json.loads(manifest_path.read_text(encoding="utf-8"))
            payload["ekp_version"] = "0.14.0"
            manifest_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
            result = self.service.inspect(StatusRequest(path=str(root)))
            self.assertEqual(result.state, StatusState.VERSION_MISMATCH)
            self.assertEqual(result.installed_version, "0.14.0")
            self.assertEqual(result.exit_code, 0)

    def test_invalid_manifest_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manifest = root / ".ekp" / "install.json"
            manifest.parent.mkdir(parents=True)
            manifest.write_text("{bad", encoding="utf-8")
            result = self.service.inspect(StatusRequest(path=str(root)))
            self.assertEqual(result.state, StatusState.INVALID)
            self.assertEqual(result.exit_code, 3)

    def test_unsafe_manifest_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            symfony_fixture(root)
            InstallService().install(InstallRequest(path=str(root), assume_yes=True))
            manifest_path = root / ".ekp" / "install.json"
            payload = json.loads(manifest_path.read_text(encoding="utf-8"))
            payload["managed_files"][0]["relative_path"] = "../outside.mdc"
            manifest_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
            result = self.service.inspect(StatusRequest(path=str(root)))
            self.assertEqual(result.state, StatusState.INVALID)
            self.assertEqual(result.exit_code, 3)

    def test_does_not_modify_project(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            symfony_fixture(root)
            InstallService().install(InstallRequest(path=str(root), assume_yes=True))
            before = {
                str(path.relative_to(root)): path.stat().st_mtime_ns
                for path in root.rglob("*")
                if path.is_file()
            }
            self.service.inspect(StatusRequest(path=str(root)))
            after = {
                str(path.relative_to(root)): path.stat().st_mtime_ns
                for path in root.rglob("*")
                if path.is_file()
            }
            self.assertEqual(before, after)
