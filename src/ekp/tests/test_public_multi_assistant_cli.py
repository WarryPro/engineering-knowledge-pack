"""Public multi-assistant Consumer CLI activation tests (AX-E)."""

from __future__ import annotations

import hashlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from ekp.cli import main
from ekp.composition import ComponentRegistry
from ekp.config import PROJECT_CONFIG_RELATIVE, ProjectConfig, ProjectConfigStore
from ekp.config.project import render_project_config_yaml
from ekp.install.errors import EXIT_CONFLICT, EXIT_SELECTION, EXIT_SUCCESS
from ekp.install.intent import prompt_assistants, select_install_intent
from ekp.install.manifest import ManifestStore
from ekp.install.service import InstallRequest, InstallService
from ekp.lifecycle.uninstall import UninstallRequest, UninstallService
from ekp.lifecycle.update import UpdateRequest, UpdateService
from ekp.paths import get_ekp_root
from ekp.status.models import StatusState
from ekp.status.service import StatusRequest, StatusService
from ekp.tests.fixtures import frontend_fixture, flutter_fixture, symfony_fixture
from ekp.version import get_version


def _fingerprint(root: Path):
    items = {}
    for path in sorted(root.rglob("*")):
        if path.is_file():
            items[path.relative_to(root).as_posix()] = hashlib.sha256(
                path.read_bytes()
            ).hexdigest()
    return items


class PublicAssistantCliContractTests(unittest.TestCase):
    def test_help_lists_assistant(self):
        buf = io.StringIO()
        with mock.patch("sys.stdout", buf):
            try:
                main(["install", "--help"])
            except SystemExit as exc:
                self.assertEqual(exc.code, 0)
        text = buf.getvalue()
        self.assertIn("--assistant", text)
        self.assertIn("cursor", text)
        self.assertIn("copilot", text)
        self.assertIn("claude", text)
        self.assertIn("antigravity", text)

    def test_unknown_assistant_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            code = main(
                [
                    "install",
                    "--path",
                    tmp,
                    "--component",
                    "core",
                    "--assistant",
                    "made-up-ai",
                    "--yes",
                ]
            )
            self.assertEqual(code, EXIT_SELECTION)

    def test_duplicate_assistants_canonicalized(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            code = main(
                [
                    "install",
                    "--path",
                    str(project),
                    "--component",
                    "core",
                    "--assistant",
                    "cursor",
                    "--assistant",
                    "cursor",
                    "--assistant",
                    "copilot",
                    "--yes",
                ]
            )
            self.assertEqual(code, 0)
            manifest = ManifestStore(project).load()
            self.assertEqual(manifest.adapters, ["copilot", "cursor"])

    def test_empty_assistants_only_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            before = _fingerprint(Path(tmp))
            code = main(
                [
                    "install",
                    "--path",
                    tmp,
                    "--assistant",
                    "copilot",
                    "--yes",
                ]
            )
            self.assertEqual(code, EXIT_SELECTION)
            self.assertEqual(_fingerprint(Path(tmp)), before)
            self.assertFalse((Path(tmp) / ".ekp").exists())

    def test_flagship_empty_explicit_all_four(self):
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
                    "--assistant",
                    "cursor",
                    "--assistant",
                    "copilot",
                    "--assistant",
                    "claude",
                    "--assistant",
                    "antigravity",
                    "--yes",
                ]
            )
            self.assertEqual(code, 0)
            status = StatusService().inspect(StatusRequest(path=str(project)))
            self.assertEqual(status.state, StatusState.HEALTHY)
            self.assertEqual(status.managed_total, 137)
            self.assertEqual(
                set(status.adapters),
                {"antigravity", "claude", "copilot", "cursor"},
            )


class PublicAssistantInteractiveTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.registry = ComponentRegistry.load()

    def test_blank_assistant_choice_is_cursor(self):
        outputs = []
        selected = prompt_assistants(
            input_fn=lambda _p: "",
            output_fn=outputs.append,
        )
        self.assertEqual(selected, ("cursor",))
        self.assertIn("Select AI assistants", "\n".join(outputs))

    def test_single_non_cursor_choice(self):
        selected = prompt_assistants(input_fn=lambda _p: "copilot")
        self.assertEqual(selected, ("copilot",))

    def test_multiple_assistant_choice_by_numbers(self):
        # supported order is lexical: antigravity, claude, copilot, cursor
        selected = prompt_assistants(input_fn=lambda _p: "3,4")
        self.assertEqual(selected, ("copilot", "cursor"))

    def test_detected_project_assistant_picker(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            symfony_fixture(project)
            frontend_fixture(project)
            from ekp.detection.service import DetectionService
            from ekp.resolution.resolver import apply_resolution

            report = apply_resolution(DetectionService().detect(str(project)))
            answers = iter(["claude,copilot"])
            intent = select_install_intent(
                report,
                assume_yes=False,
                registry=self.registry,
                input_fn=lambda _p: next(answers),
                output_fn=lambda _m: None,
            )
            self.assertEqual(intent.assistants, ("claude", "copilot"))
            self.assertEqual(set(intent.components), {"frontend", "symfony"})


class PublicProjectConfigAuthorityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.registry = ComponentRegistry.load()

    def test_existing_config_copilot_claude_used_without_flags(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            store = ProjectConfigStore(project, registry=self.registry)
            store.create(
                ProjectConfig(
                    schema_version=1,
                    components=("symfony", "frontend"),
                    assistants=("claude", "copilot"),
                )
            )
            before = (project / PROJECT_CONFIG_RELATIVE).read_bytes()
            result = InstallService().install(
                InstallRequest(path=str(project), assume_yes=True)
            )
            self.assertEqual(result.exit_code, EXIT_SUCCESS, result.message)
            manifest = ManifestStore(project).load()
            self.assertEqual(manifest.adapters, ["claude", "copilot"])
            self.assertEqual(len(manifest.managed_files), 16)
            self.assertEqual((project / PROJECT_CONFIG_RELATIVE).read_bytes(), before)

    def test_matching_explicit_assistants_reuse_bytes(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            store = ProjectConfigStore(project, registry=self.registry)
            store.create(
                ProjectConfig(
                    schema_version=1,
                    components=("core",),
                    assistants=("claude", "copilot"),
                )
            )
            before = (project / PROJECT_CONFIG_RELATIVE).read_bytes()
            result = InstallService().install(
                InstallRequest(
                    path=str(project),
                    assistants=["copilot", "claude"],
                    assume_yes=True,
                )
            )
            self.assertEqual(result.exit_code, EXIT_SUCCESS, result.message)
            self.assertEqual((project / PROJECT_CONFIG_RELATIVE).read_bytes(), before)

    def test_assistant_mismatch_refuses(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            store = ProjectConfigStore(project, registry=self.registry)
            store.create(
                ProjectConfig(
                    schema_version=1,
                    components=("core",),
                    assistants=("cursor",),
                )
            )
            before = (project / PROJECT_CONFIG_RELATIVE).read_bytes()
            result = InstallService().install(
                InstallRequest(
                    path=str(project),
                    assistants=["cursor", "copilot"],
                    assume_yes=True,
                )
            )
            self.assertEqual(result.exit_code, EXIT_SELECTION)
            self.assertEqual((project / PROJECT_CONFIG_RELATIVE).read_bytes(), before)
            self.assertFalse((project / ".ekp" / "install.json").exists())

    def test_config_plus_legacy_profile_refuses(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            store = ProjectConfigStore(project, registry=self.registry)
            store.create(
                ProjectConfig(
                    schema_version=1,
                    components=("symfony",),
                    assistants=("cursor",),
                )
            )
            result = InstallService().install(
                InstallRequest(
                    path=str(project),
                    profile="cursor-symfony",
                    assume_yes=True,
                )
            )
            self.assertEqual(result.exit_code, EXIT_SELECTION)
            self.assertFalse((project / ".ekp" / "install.json").exists())

    def test_invalid_config_refuses(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            path = project / PROJECT_CONFIG_RELATIVE
            path.parent.mkdir(parents=True)
            path.write_text("not: valid: [\n", encoding="utf-8")
            result = InstallService().install(
                InstallRequest(path=str(project), assume_yes=True)
            )
            self.assertEqual(result.exit_code, EXIT_SELECTION)
            self.assertFalse((project / ".ekp" / "install.json").exists())

    def test_config_only_antigravity_without_markers(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            store = ProjectConfigStore(project, registry=self.registry)
            store.create(
                ProjectConfig(
                    schema_version=1,
                    components=("symfony",),
                    assistants=("antigravity",),
                )
            )
            result = InstallService().install(
                InstallRequest(path=str(project), assume_yes=True)
            )
            self.assertEqual(result.exit_code, EXIT_SUCCESS, result.message)
            manifest = ManifestStore(project).load()
            self.assertEqual(manifest.adapters, ["antigravity"])
            self.assertFalse((project / ".cursor").exists())


class PublicMultiAssistantLifecycleTests(unittest.TestCase):
    def _status(self, project):
        return StatusService().inspect(StatusRequest(path=str(project)))

    def test_public_copilot_only_lifecycle(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            code = main(
                [
                    "install",
                    "--path",
                    str(project),
                    "--component",
                    "core",
                    "--assistant",
                    "copilot",
                    "--yes",
                ]
            )
            self.assertEqual(code, 0)
            self.assertEqual(self._status(project).managed_total, 2)
            self.assertEqual(self._status(project).state, StatusState.HEALTHY)
            self.assertEqual(
                main(["update", "--path", str(project), "--dry-run"]), 0
            )
            self.assertEqual(main(["update", "--path", str(project), "--yes"]), 0)
            self.assertEqual(main(["uninstall", "--path", str(project), "--yes"]), 0)
            self.assertEqual(self._status(project).state, StatusState.NOT_INSTALLED)

    def test_public_claude_only_lifecycle(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            code = main(
                [
                    "install",
                    "--path",
                    str(project),
                    "--component",
                    "core",
                    "--assistant",
                    "claude",
                    "--yes",
                ]
            )
            self.assertEqual(code, 0)
            self.assertEqual(self._status(project).managed_total, 5)
            self.assertTrue((project / "CLAUDE.md").is_file())
            self.assertEqual(main(["update", "--path", str(project), "--yes"]), 0)
            self.assertEqual(main(["uninstall", "--path", str(project), "--yes"]), 0)

    def test_public_antigravity_only_lifecycle(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            code = main(
                [
                    "install",
                    "--path",
                    str(project),
                    "--component",
                    "core",
                    "--assistant",
                    "antigravity",
                    "--yes",
                ]
            )
            self.assertEqual(code, 0)
            self.assertEqual(self._status(project).managed_total, 6)
            self.assertEqual(main(["uninstall", "--path", str(project), "--yes"]), 0)

    def test_public_all_four_core_lifecycle(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            code = main(
                [
                    "install",
                    "--path",
                    str(project),
                    "--component",
                    "core",
                    "--assistant",
                    "cursor",
                    "--assistant",
                    "copilot",
                    "--assistant",
                    "claude",
                    "--assistant",
                    "antigravity",
                    "--yes",
                ]
            )
            self.assertEqual(code, 0)
            self.assertEqual(self._status(project).managed_total, 78)
            self.assertEqual(main(["update", "--path", str(project), "--yes"]), 0)
            self.assertEqual(main(["uninstall", "--path", str(project), "--yes"]), 0)
            self.assertEqual(self._status(project).state, StatusState.NOT_INSTALLED)

    def test_public_flagship_sf_fe_all_four(self):
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
                    "--assistant",
                    "cursor",
                    "--assistant",
                    "copilot",
                    "--assistant",
                    "claude",
                    "--assistant",
                    "antigravity",
                    "--yes",
                ]
            )
            self.assertEqual(code, 0)
            status = self._status(project)
            self.assertEqual(status.state, StatusState.HEALTHY)
            self.assertEqual(status.managed_total, 137)
            yaml_bytes = (project / PROJECT_CONFIG_RELATIVE).read_bytes()
            self.assertEqual(main(["update", "--path", str(project), "--dry-run"]), 0)
            self.assertEqual(main(["update", "--path", str(project), "--yes"]), 0)
            # repair
            (project / ".github" / "copilot-instructions.md").unlink()
            (project / "CLAUDE.md").unlink()
            self.assertEqual(self._status(project).state, StatusState.INCOMPLETE)
            before_manifest = (project / ".ekp" / "install.json").read_bytes()
            self.assertEqual(main(["update", "--path", str(project), "--yes"]), 0)
            self.assertEqual(self._status(project).state, StatusState.HEALTHY)
            self.assertEqual(
                (project / ".ekp" / "install.json").read_bytes(), before_manifest
            )
            self.assertEqual(main(["uninstall", "--path", str(project), "--yes"]), 0)
            self.assertEqual(self._status(project).state, StatusState.NOT_INSTALLED)
            self.assertEqual((project / PROJECT_CONFIG_RELATIVE).read_bytes(), yaml_bytes)

    def test_public_detected_all_four(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            symfony_fixture(project)
            frontend_fixture(project)
            code = main(
                [
                    "install",
                    "--path",
                    str(project),
                    "--assistant",
                    "cursor",
                    "--assistant",
                    "copilot",
                    "--assistant",
                    "claude",
                    "--assistant",
                    "antigravity",
                    "--yes",
                ]
            )
            self.assertEqual(code, 0)
            self.assertEqual(self._status(project).managed_total, 137)

    def test_public_detected_default_cursor(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            symfony_fixture(project)
            frontend_fixture(project)
            code = main(["install", "--path", str(project), "--yes"])
            self.assertEqual(code, 0)
            manifest = ManifestStore(project).load()
            self.assertEqual(manifest.adapters, ["cursor"])
            self.assertEqual(len(manifest.managed_files), 110)

    def test_public_assistant_drift_refuse(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            self.assertEqual(
                main(
                    [
                        "install",
                        "--path",
                        str(project),
                        "--component",
                        "core",
                        "--assistant",
                        "cursor",
                        "--yes",
                    ]
                ),
                0,
            )
            cfg = ProjectConfig(
                schema_version=1,
                components=("core",),
                assistants=("cursor", "copilot"),
            )
            (project / PROJECT_CONFIG_RELATIVE).write_text(
                render_project_config_yaml(cfg), encoding="utf-8"
            )
            self.assertEqual(
                self._status(project).state, StatusState.CONFIGURATION_DRIFT
            )
            self.assertEqual(
                main(["update", "--path", str(project), "--yes"]), EXIT_CONFLICT
            )
            self.assertFalse(
                (project / ".github" / "copilot-instructions.md").exists()
            )

    def test_public_no_redetect(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            symfony_fixture(project)
            self.assertEqual(
                main(
                    [
                        "install",
                        "--path",
                        str(project),
                        "--component",
                        "symfony",
                        "--assistant",
                        "copilot",
                        "--assistant",
                        "claude",
                        "--yes",
                    ]
                ),
                0,
            )
            yaml_before = (project / PROJECT_CONFIG_RELATIVE).read_bytes()
            frontend_fixture(project)
            flutter_fixture(project)
            (project / ".cursor").mkdir(exist_ok=True)
            (project / ".agents").mkdir(exist_ok=True)
            self.assertEqual(main(["update", "--path", str(project), "--yes"]), 0)
            cfg = ProjectConfigStore(
                project, registry=ComponentRegistry.load()
            ).load()
            self.assertEqual(list(cfg.components), ["symfony"])
            self.assertEqual(set(cfg.assistants), {"claude", "copilot"})
            self.assertEqual((project / PROJECT_CONFIG_RELATIVE).read_bytes(), yaml_before)

    def test_public_claude_md_collision(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            (project / "CLAUDE.md").write_text("user\n", encoding="utf-8")
            before = _fingerprint(project)
            code = main(
                [
                    "install",
                    "--path",
                    str(project),
                    "--component",
                    "core",
                    "--assistant",
                    "claude",
                    "--yes",
                ]
            )
            self.assertEqual(code, EXIT_CONFLICT)
            self.assertEqual(_fingerprint(project), before)
            self.assertFalse((project / ".ekp" / "install.json").exists())

    def test_public_dry_run_zero_writes(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            before = _fingerprint(project)
            code = main(
                [
                    "install",
                    "--path",
                    str(project),
                    "--component",
                    "core",
                    "--assistant",
                    "claude",
                    "--dry-run",
                    "--yes",
                ]
            )
            self.assertEqual(code, 0)
            self.assertEqual(_fingerprint(project), before)

    def test_legacy_installed_plus_assistant_refuses(self):
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
            before = _fingerprint(project)
            code = main(
                [
                    "install",
                    "--path",
                    str(project),
                    "--assistant",
                    "copilot",
                    "--yes",
                ]
            )
            self.assertEqual(code, EXIT_SELECTION)
            self.assertEqual(_fingerprint(project), before)


if __name__ == "__main__":
    unittest.main()
