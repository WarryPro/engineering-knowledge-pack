"""Composition lifecycle Consumer activation tests (AW-E2)."""

from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from ekp.cli import main
from ekp.composition import PROJECT_COMPOSITION_PROFILE
from ekp.config import PROJECT_CONFIG_RELATIVE, ProjectConfig, ProjectConfigStore
from ekp.config.project import render_project_config_yaml
from ekp.install.errors import EXIT_CONFLICT, EXIT_SELECTION
from ekp.install.manifest import INSTALL_MODE_COMPOSITION, ManifestStore
from ekp.install.service import InstallRequest, InstallService
from ekp.lifecycle.update import UpdateRequest, UpdateService
from ekp.lifecycle.uninstall import UninstallRequest, UninstallService
from ekp.status.models import StatusState
from ekp.status.service import StatusRequest, StatusService
from ekp.tests.fixtures import devops_fixture, frontend_fixture, flutter_fixture, symfony_fixture
from ekp.version import get_version


def _fingerprint(root: Path):
    items = {}
    for path in sorted(root.rglob("*")):
        if path.is_file():
            items[path.relative_to(root).as_posix()] = hashlib.sha256(
                path.read_bytes()
            ).hexdigest()
    return items


def _rule_count(project: Path) -> int:
    rules = project / ".cursor" / "rules"
    return len(list(rules.glob("*.mdc"))) if rules.is_dir() else 0


class CompositionCliInstallTests(unittest.TestCase):
    def test_help_exposes_component(self):
        with mock.patch("sys.stdout"), mock.patch("sys.stderr"):
            # argparse writes help to stdout
            pass
        import io
        import sys

        buf = io.StringIO()
        with mock.patch.object(sys, "stdout", buf):
            try:
                main(["install", "--help"])
            except SystemExit as exc:
                self.assertEqual(exc.code, 0)
        text = buf.getvalue()
        self.assertIn("--component", text)
        self.assertIn("--profile", text)

    def test_component_and_profile_mutual_exclusion(self):
        with tempfile.TemporaryDirectory() as tmp:
            code = main(
                [
                    "install",
                    "--path",
                    tmp,
                    "--profile",
                    "cursor-symfony",
                    "--component",
                    "frontend",
                    "--yes",
                ]
            )
            self.assertEqual(code, EXIT_SELECTION)

    def test_unknown_component_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            code = main(
                [
                    "install",
                    "--path",
                    tmp,
                    "--component",
                    "made-up-framework",
                    "--yes",
                ]
            )
            self.assertEqual(code, EXIT_SELECTION)

    def test_empty_yes_without_component_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            code = main(["install", "--path", tmp, "--yes"])
            self.assertEqual(code, EXIT_SELECTION)

    def test_empty_explicit_components_yes(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            code = main(
                [
                    "install",
                    "--path",
                    str(project),
                    "--component",
                    "symfony",
                    "--component",
                    "frontend",
                    "--yes",
                ]
            )
            self.assertEqual(code, 0)
            self.assertEqual(_rule_count(project), 110)
            status = StatusService().inspect(StatusRequest(path=str(project)))
            self.assertEqual(status.state, StatusState.HEALTHY)
            self.assertEqual(status.mode, INSTALL_MODE_COMPOSITION)

    def test_detected_symfony_yes_composition(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            symfony_fixture(project)
            code = main(["install", "--path", str(project), "--yes"])
            self.assertEqual(code, 0)
            self.assertEqual(_rule_count(project), 83)
            raw = json.loads((project / ".ekp" / "install.json").read_text(encoding="utf-8"))
            self.assertEqual(raw["profile"], PROJECT_COMPOSITION_PROFILE)
            self.assertEqual(raw["mode"], INSTALL_MODE_COMPOSITION)
            status = StatusService().inspect(StatusRequest(path=str(project)))
            self.assertEqual(status.state, StatusState.HEALTHY)
            self.assertEqual(status.requested_components, ["symfony"])

    def test_detected_multi_stack_yes(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            symfony_fixture(project)
            frontend_fixture(project)
            code = main(["install", "--path", str(project), "--yes"])
            self.assertEqual(code, 0)
            self.assertEqual(_rule_count(project), 110)
            status = StatusService().inspect(StatusRequest(path=str(project)))
            self.assertEqual(status.state, StatusState.HEALTHY)
            self.assertEqual(status.requested_components, ["frontend", "symfony"])

    def test_detected_with_devops_yes(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            symfony_fixture(project)
            frontend_fixture(project)
            devops_fixture(project)
            code = main(["install", "--path", str(project), "--yes"])
            self.assertEqual(code, 0)
            self.assertEqual(_rule_count(project), 119)

    def test_explicit_legacy_profile(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            symfony_fixture(project)
            code = main(
                [
                    "install",
                    "--path",
                    str(project),
                    "--profile",
                    "cursor-symfony",
                    "--yes",
                ]
            )
            self.assertEqual(code, 0)
            self.assertEqual(_rule_count(project), 83)
            raw = json.loads((project / ".ekp" / "install.json").read_text(encoding="utf-8"))
            self.assertEqual(raw["profile"], "cursor-symfony")
            self.assertNotIn("mode", raw)
            self.assertFalse((project / PROJECT_CONFIG_RELATIVE).exists())
            status = StatusService().inspect(StatusRequest(path=str(project)))
            self.assertEqual(status.state, StatusState.HEALTHY)
            self.assertEqual(status.mode, "legacy-profile")

    def test_composition_dry_run_zero_writes(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            before = _fingerprint(project)
            code = main(
                [
                    "install",
                    "--path",
                    str(project),
                    "--component",
                    "symfony",
                    "--component",
                    "frontend",
                    "--dry-run",
                ]
            )
            self.assertEqual(code, 0)
            self.assertEqual(_fingerprint(project), before)

    def test_legacy_install_refuses_component(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            symfony_fixture(project)
            self.assertEqual(
                main(
                    [
                        "install",
                        "--path",
                        str(project),
                        "--profile",
                        "cursor-symfony",
                        "--yes",
                    ]
                ),
                0,
            )
            code = main(
                [
                    "install",
                    "--path",
                    str(project),
                    "--component",
                    "frontend",
                    "--yes",
                ]
            )
            self.assertEqual(code, EXIT_SELECTION)

    def test_composition_reinstall_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            symfony_fixture(project)
            self.assertEqual(main(["install", "--path", str(project), "--yes"]), 0)
            code = main(["install", "--path", str(project), "--yes"])
            self.assertEqual(code, EXIT_SELECTION)


class CompositionStatusTests(unittest.TestCase):
    def _compose_symfony(self, project: Path):
        symfony_fixture(project)
        self.assertEqual(main(["install", "--path", str(project), "--yes"]), 0)

    def test_healthy_composition(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            self._compose_symfony(project)
            result = StatusService().inspect(StatusRequest(path=str(project)))
            self.assertEqual(result.state, StatusState.HEALTHY)
            self.assertEqual(result.mode, INSTALL_MODE_COMPOSITION)
            self.assertFalse(result.configuration_drift)
            payload = json.loads(
                __import__("ekp.status.render", fromlist=["render_json"]).render_json(result)
            )
            self.assertEqual(payload["mode"], INSTALL_MODE_COMPOSITION)
            self.assertIn("requested_components", payload)

    def test_configuration_drift(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            self._compose_symfony(project)
            path = project / PROJECT_CONFIG_RELATIVE
            path.write_text(
                render_project_config_yaml(
                    ProjectConfig(
                        schema_version=1,
                        components=("symfony", "frontend"),
                        assistants=("cursor",),
                    )
                ),
                encoding="utf-8",
            )
            result = StatusService().inspect(StatusRequest(path=str(project)))
            self.assertEqual(result.state, StatusState.CONFIGURATION_DRIFT)
            self.assertTrue(result.configuration_drift)
            self.assertEqual(_rule_count(project), 83)

    def test_semantic_equivalent_healthy(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            self._compose_symfony(project)
            path = project / PROJECT_CONFIG_RELATIVE
            path.write_text(
                "# equivalent\n"
                "schema_version: 1\n"
                "assistants:\n"
                "  - cursor\n"
                "components:\n"
                "  - core\n"
                "  - php\n"
                "  - symfony\n",
                encoding="utf-8",
            )
            result = StatusService().inspect(StatusRequest(path=str(project)))
            self.assertEqual(result.state, StatusState.HEALTHY)
            self.assertFalse(result.configuration_drift)

    def test_missing_config_invalid(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            self._compose_symfony(project)
            (project / PROJECT_CONFIG_RELATIVE).unlink()
            result = StatusService().inspect(StatusRequest(path=str(project)))
            self.assertEqual(result.state, StatusState.INVALID)

    def test_invalid_config_invalid(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            self._compose_symfony(project)
            (project / PROJECT_CONFIG_RELATIVE).write_text("not: valid: yaml: [\n", encoding="utf-8")
            result = StatusService().inspect(StatusRequest(path=str(project)))
            self.assertEqual(result.state, StatusState.INVALID)

    def test_incomplete(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            self._compose_symfony(project)
            rules = list((project / ".cursor" / "rules").glob("*.mdc"))
            rules[0].unlink()
            result = StatusService().inspect(StatusRequest(path=str(project)))
            self.assertEqual(result.state, StatusState.INCOMPLETE)

    def test_modified(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            self._compose_symfony(project)
            rules = list((project / ".cursor" / "rules").glob("*.mdc"))
            rules[0].write_text("mutated\n", encoding="utf-8")
            result = StatusService().inspect(StatusRequest(path=str(project)))
            self.assertEqual(result.state, StatusState.MODIFIED)

    def test_version_mismatch(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            self._compose_symfony(project)
            store = ManifestStore(project)
            manifest = store.load()
            manifest.ekp_version = "0.0.0"
            store.save(manifest)
            result = StatusService().inspect(StatusRequest(path=str(project)))
            self.assertEqual(result.state, StatusState.VERSION_MISMATCH)

    def test_config_only_not_installed(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            ProjectConfigStore(project).create(
                ProjectConfig(
                    schema_version=1,
                    components=("symfony",),
                    assistants=("cursor",),
                )
            )
            result = StatusService().inspect(StatusRequest(path=str(project)))
            self.assertEqual(result.state, StatusState.NOT_INSTALLED)

    def test_legacy_plus_stray_config(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            symfony_fixture(project)
            self.assertEqual(
                main(
                    [
                        "install",
                        "--path",
                        str(project),
                        "--profile",
                        "cursor-symfony",
                        "--yes",
                    ]
                ),
                0,
            )
            ProjectConfigStore(project).create(
                ProjectConfig(
                    schema_version=1,
                    components=("frontend",),
                    assistants=("cursor",),
                )
            )
            result = StatusService().inspect(StatusRequest(path=str(project)))
            self.assertEqual(result.mode, "legacy-profile")
            self.assertEqual(result.state, StatusState.HEALTHY)
            self.assertIsNone(result.configuration_drift)


class CompositionUpdateTests(unittest.TestCase):
    def test_same_version_noop(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            symfony_fixture(project)
            self.assertEqual(main(["install", "--path", str(project), "--yes"]), 0)
            before = (project / ".ekp" / "install.json").read_bytes()
            result = UpdateService().update(
                UpdateRequest(path=str(project), assume_yes=True)
            )
            self.assertEqual(result.exit_code, 0, result.message)
            self.assertEqual((project / ".ekp" / "install.json").read_bytes(), before)

    def test_same_version_repair(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            symfony_fixture(project)
            self.assertEqual(main(["install", "--path", str(project), "--yes"]), 0)
            before = (project / ".ekp" / "install.json").read_bytes()
            rules = list((project / ".cursor" / "rules").glob("*.mdc"))
            rules[0].unlink()
            self.assertEqual(
                StatusService().inspect(StatusRequest(path=str(project))).state,
                StatusState.INCOMPLETE,
            )
            result = UpdateService().update(
                UpdateRequest(path=str(project), assume_yes=True)
            )
            self.assertEqual(result.exit_code, 0, result.message)
            self.assertEqual(_rule_count(project), 83)
            self.assertEqual((project / ".ekp" / "install.json").read_bytes(), before)
            self.assertEqual(
                StatusService().inspect(StatusRequest(path=str(project))).state,
                StatusState.HEALTHY,
            )

    def test_drift_refusal(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            symfony_fixture(project)
            self.assertEqual(main(["install", "--path", str(project), "--yes"]), 0)
            before = _fingerprint(project)
            (project / PROJECT_CONFIG_RELATIVE).write_text(
                render_project_config_yaml(
                    ProjectConfig(
                        schema_version=1,
                        components=("symfony", "frontend"),
                        assistants=("cursor",),
                    )
                ),
                encoding="utf-8",
            )
            after_edit = _fingerprint(project)
            result = UpdateService().update(
                UpdateRequest(path=str(project), assume_yes=True)
            )
            self.assertEqual(result.exit_code, EXIT_CONFLICT, result.message)
            self.assertEqual(_fingerprint(project), after_edit)
            self.assertIn("configuration has changed", result.message.lower())

    def test_no_redetect(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            symfony_fixture(project)
            self.assertEqual(main(["install", "--path", str(project), "--yes"]), 0)
            config_before = (project / PROJECT_CONFIG_RELATIVE).read_bytes()
            frontend_fixture(project)
            devops_fixture(project)
            flutter_fixture(project)
            result = UpdateService().update(
                UpdateRequest(path=str(project), assume_yes=True)
            )
            self.assertEqual(result.exit_code, 0, result.message)
            self.assertEqual(_rule_count(project), 83)
            self.assertEqual((project / PROJECT_CONFIG_RELATIVE).read_bytes(), config_before)

    def test_missing_config_refusal(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            symfony_fixture(project)
            self.assertEqual(main(["install", "--path", str(project), "--yes"]), 0)
            (project / PROJECT_CONFIG_RELATIVE).unlink()
            result = UpdateService().update(
                UpdateRequest(path=str(project), assume_yes=True)
            )
            self.assertEqual(result.exit_code, EXIT_SELECTION)

    def test_invalid_config_refusal(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            symfony_fixture(project)
            self.assertEqual(main(["install", "--path", str(project), "--yes"]), 0)
            (project / PROJECT_CONFIG_RELATIVE).write_text("{bad", encoding="utf-8")
            result = UpdateService().update(
                UpdateRequest(path=str(project), assume_yes=True)
            )
            self.assertEqual(result.exit_code, EXIT_SELECTION)

    def test_modified_managed_conflict(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            symfony_fixture(project)
            self.assertEqual(main(["install", "--path", str(project), "--yes"]), 0)
            rules = list((project / ".cursor" / "rules").glob("*.mdc"))
            rules[0].write_text("user-edit\n", encoding="utf-8")
            # Force cross-version so update tries WRITE/compare path meaningfully:
            # same-version with modified file that still matches inventory hash mismatch
            # classification yields conflict when disk != old.
            store = ManifestStore(project)
            manifest = store.load()
            manifest.ekp_version = "0.0.0"
            store.save(manifest)
            result = UpdateService().update(
                UpdateRequest(path=str(project), assume_yes=True)
            )
            self.assertEqual(result.exit_code, EXIT_CONFLICT, result.message)

    def test_config_toctou_during_apply(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            symfony_fixture(project)
            self.assertEqual(main(["install", "--path", str(project), "--yes"]), 0)
            # Delete one rule so same-version repair performs writes.
            rules = list((project / ".cursor" / "rules").glob("*.mdc"))
            rules[0].unlink()
            original_apply = UpdateService().applier.apply_update

            def mutate_then_apply(plan):
                (project / PROJECT_CONFIG_RELATIVE).write_text(
                    render_project_config_yaml(
                        ProjectConfig(
                            schema_version=1,
                            components=("symfony", "frontend"),
                            assistants=("cursor",),
                        )
                    ),
                    encoding="utf-8",
                )
                return original_apply(plan)

            service = UpdateService()
            service.applier.apply_update = mutate_then_apply
            result = service.update(UpdateRequest(path=str(project), assume_yes=True))
            self.assertEqual(result.exit_code, EXIT_CONFLICT, result.message)
            # Bound hash must remain the original symfony-only hash.
            raw = json.loads((project / ".ekp" / "install.json").read_text(encoding="utf-8"))
            self.assertEqual(raw["mode"], INSTALL_MODE_COMPOSITION)
            status = StatusService().inspect(StatusRequest(path=str(project)))
            self.assertEqual(status.state, StatusState.CONFIGURATION_DRIFT)

    def test_legacy_update_with_stray_config(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            symfony_fixture(project)
            self.assertEqual(
                main(
                    [
                        "install",
                        "--path",
                        str(project),
                        "--profile",
                        "cursor-symfony",
                        "--yes",
                    ]
                ),
                0,
            )
            ProjectConfigStore(project).create(
                ProjectConfig(
                    schema_version=1,
                    components=("frontend",),
                    assistants=("cursor",),
                )
            )
            config_bytes = (project / PROJECT_CONFIG_RELATIVE).read_bytes()
            result = UpdateService().update(
                UpdateRequest(path=str(project), assume_yes=True)
            )
            self.assertEqual(result.exit_code, 0, result.message)
            raw = json.loads((project / ".ekp" / "install.json").read_text(encoding="utf-8"))
            self.assertEqual(raw["profile"], "cursor-symfony")
            self.assertNotIn("mode", raw)
            self.assertEqual((project / PROJECT_CONFIG_RELATIVE).read_bytes(), config_bytes)


class CompositionUninstallTests(unittest.TestCase):
    def test_healthy_uninstall_preserves_config(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            symfony_fixture(project)
            frontend_fixture(project)
            self.assertEqual(main(["install", "--path", str(project), "--yes"]), 0)
            config_bytes = (project / PROJECT_CONFIG_RELATIVE).read_bytes()
            result = UninstallService().uninstall(
                UninstallRequest(path=str(project), assume_yes=True)
            )
            self.assertEqual(result.exit_code, 0, result.message)
            self.assertFalse((project / ".ekp" / "install.json").exists())
            self.assertEqual((project / PROJECT_CONFIG_RELATIVE).read_bytes(), config_bytes)
            self.assertEqual(_rule_count(project), 0)
            status = StatusService().inspect(StatusRequest(path=str(project)))
            self.assertEqual(status.state, StatusState.NOT_INSTALLED)

    def test_drifted_config_uninstall(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            symfony_fixture(project)
            self.assertEqual(main(["install", "--path", str(project), "--yes"]), 0)
            drifted = render_project_config_yaml(
                ProjectConfig(
                    schema_version=1,
                    components=("symfony", "frontend"),
                    assistants=("cursor",),
                )
            ).encode("utf-8")
            (project / PROJECT_CONFIG_RELATIVE).write_bytes(drifted)
            result = UninstallService().uninstall(
                UninstallRequest(path=str(project), assume_yes=True)
            )
            self.assertEqual(result.exit_code, 0, result.message)
            self.assertEqual((project / PROJECT_CONFIG_RELATIVE).read_bytes(), drifted)

    def test_invalid_config_uninstall(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            symfony_fixture(project)
            self.assertEqual(main(["install", "--path", str(project), "--yes"]), 0)
            bad = b"{not-yaml"
            (project / PROJECT_CONFIG_RELATIVE).write_bytes(bad)
            result = UninstallService().uninstall(
                UninstallRequest(path=str(project), assume_yes=True)
            )
            self.assertEqual(result.exit_code, 0, result.message)
            self.assertEqual((project / PROJECT_CONFIG_RELATIVE).read_bytes(), bad)

    def test_missing_config_uninstall(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            symfony_fixture(project)
            self.assertEqual(main(["install", "--path", str(project), "--yes"]), 0)
            (project / PROJECT_CONFIG_RELATIVE).unlink()
            result = UninstallService().uninstall(
                UninstallRequest(path=str(project), assume_yes=True)
            )
            self.assertEqual(result.exit_code, 0, result.message)
            self.assertFalse((project / ".ekp" / "install.json").exists())
            self.assertEqual(_rule_count(project), 0)


if __name__ == "__main__":
    unittest.main()
