"""Public CLI workspace consumer proofs (AZ-E)."""

from __future__ import annotations

import io
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from ekp.cli import main
from ekp.cli_workspace import (
    build_install_project_config_from_cli,
    configuration_hash_for,
)
from ekp.composition import ComponentRegistry
from ekp.config.models import PROJECT_CONFIG_RELATIVE
from ekp.config.project import ProjectConfigStore
from ekp.install.errors import EXIT_SELECTION, EXIT_SUCCESS
from ekp.install.manifest import ManifestStore
from ekp.lifecycle.configure import ConfigureService
from ekp.lifecycle.configure_cli import run_configure_cli
from ekp.paths import get_ekp_root
from ekp.status.models import StatusState
from ekp.status.service import StatusRequest, StatusService

GOLDEN_A = "09cf2e9312aa182a2fc6438080bc4a9c687838077e4e7aeffe56c448e8655b14"
GOLDEN_C = "2320ef8549f08599beb643f9bb1d04de9304cda1531ec11d44d033fb44dae1de"
REF_CURSOR, REF_COPILOT, REF_CLAUDE, REF_ANTIGRAVITY = 105, 16, 37, 38

WORKSPACE_DIRS = (
    "apps/api",
    "apps/mobile",
    "apps/web",
    "packages/shared",
)

REFERENCE_WORKSPACES = [
    ("apps/api", "symfony"),
    ("apps/mobile", "flutter"),
    ("apps/web", "frontend"),
    ("packages/shared", "typescript"),
]

ALL_ASSISTANTS = ("cursor", "copilot", "claude", "antigravity")


def _make_reference_monorepo(tmp: str) -> Path:
    project = Path(tmp) / "project"
    project.mkdir()
    for relative in WORKSPACE_DIRS:
        path = project / relative
        path.mkdir(parents=True, exist_ok=True)
        (path / "SENTINEL").write_text("ok\n", encoding="utf-8")
    return project


def _adapter_counts(project: Path) -> dict:
    counts = {}
    for item in ManifestStore(project).load().managed_files:
        counts[item.adapter] = counts.get(item.adapter, 0) + 1
    return counts


class WorkspaceConsumerHelpers(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.registry = ComponentRegistry.load(get_ekp_root())

    def _status(self, project: Path):
        return StatusService().inspect(StatusRequest(path=str(project)))

    def _run_configure(
        self,
        project: Path,
        *,
        components=None,
        assistants=None,
        workspaces=None,
        no_root_components=False,
        no_workspaces=False,
        assume_yes=False,
        dry_run=False,
        answers=None,
        outputs=None,
        service=None,
    ):
        answers = list(answers or [])
        outputs = outputs if outputs is not None else []

        def input_fn(_prompt=""):
            if not answers:
                return ""
            return answers.pop(0)

        def output_fn(text):
            outputs.append(text)

        return run_configure_cli(
            path=str(project),
            components=components,
            assistants=assistants,
            workspaces=workspaces,
            no_root_components=no_root_components,
            no_workspaces=no_workspaces,
            assume_yes=assume_yes,
            dry_run=dry_run,
            input_fn=input_fn,
            output_fn=output_fn,
            service=service,
        )

    def _install_reference(self, project: Path) -> int:
        argv = [
            "install",
            "--path",
            str(project),
            "--component",
            "devops",
        ]
        for path, component in REFERENCE_WORKSPACES:
            argv.extend(["--workspace", path, component])
        for assistant in ALL_ASSISTANTS:
            argv.extend(["--assistant", assistant])
        argv.append("--yes")
        return main(argv)

    def _install_empty_root(self, project: Path) -> int:
        return main(
            [
                "install",
                "--path",
                str(project),
                "--workspace",
                "apps/api",
                "symfony",
                "--assistant",
                "cursor",
                "--yes",
            ]
        )


class ReferenceInstallStatusUpdateTests(WorkspaceConsumerHelpers):
    def test_reference_cli_install_status_update(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = _make_reference_monorepo(tmp)
            self.assertEqual(self._install_reference(project), EXIT_SUCCESS)
            status = self._status(project)
            self.assertEqual(status.state, StatusState.HEALTHY)
            self.assertEqual(status.configuration_sha256, GOLDEN_C)
            counts = _adapter_counts(project)
            self.assertEqual(counts.get("cursor"), REF_CURSOR)
            self.assertEqual(counts.get("copilot"), REF_COPILOT)
            self.assertEqual(counts.get("claude"), REF_CLAUDE)
            self.assertEqual(counts.get("antigravity"), REF_ANTIGRAVITY)

            buf = io.StringIO()
            with mock.patch("sys.stdout", buf):
                code = main(["status", "--path", str(project)])
            self.assertEqual(code, EXIT_SUCCESS)
            human = buf.getvalue()
            self.assertIn("Workspaces", human)
            for relative in WORKSPACE_DIRS:
                self.assertIn(relative, human)

            yaml_path = project / PROJECT_CONFIG_RELATIVE
            before = yaml_path.read_bytes()
            self.assertEqual(
                main(["update", "--path", str(project), "--yes"]),
                EXIT_SUCCESS,
            )
            self.assertEqual(self._status(project).state, StatusState.HEALTHY)
            self.assertEqual(yaml_path.read_bytes(), before)

    def test_adapter_workspace_output_smokes(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = _make_reference_monorepo(tmp)
            self.assertEqual(self._install_reference(project), EXIT_SUCCESS)

            cursor_hits = []
            for path in (project / ".cursor" / "rules").glob("*.mdc"):
                text = path.read_text(encoding="utf-8")
                if "globs: apps/api/**" in text and "alwaysApply: false" in text:
                    cursor_hits.append(path)
            self.assertGreater(len(cursor_hits), 0)

            instructions = list(
                (project / ".github" / "instructions").glob("*.instructions.md")
            )
            self.assertGreater(len(instructions), 0)
            self.assertTrue(
                any(
                    "applyTo" in p.read_text(encoding="utf-8")
                    and "apps/api" in p.read_text(encoding="utf-8")
                    for p in instructions
                )
            )
            root_copilot = project / ".github" / "copilot-instructions.md"
            self.assertTrue(root_copilot.is_file())

            claude_hits = []
            for path in (project / ".claude" / "rules").glob("*.md"):
                text = path.read_text(encoding="utf-8")
                if "paths:" in text and "apps/api/**" in text:
                    claude_hits.append(path)
            self.assertGreater(len(claude_hits), 0)
            self.assertFalse((project / "apps" / "api" / "CLAUDE.md").exists())

            anti_hits = []
            for path in (project / ".agents" / "rules").glob("*.md"):
                text = path.read_text(encoding="utf-8")
                if "trigger: glob" in text and "globs: apps/api/**" in text:
                    anti_hits.append(path)
            self.assertGreater(len(anti_hits), 0)


class ConfigureTransitionTests(WorkspaceConsumerHelpers):
    def test_configure_schema2_to_schema2(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = _make_reference_monorepo(tmp)
            self.assertEqual(self._install_reference(project), EXIT_SUCCESS)
            result = self._run_configure(
                project,
                components=["devops"],
                assistants=list(ALL_ASSISTANTS),
                workspaces=[
                    ("apps/api", "symfony"),
                    ("apps/mobile", "flutter"),
                    ("apps/web", "frontend"),
                    ("packages/shared", "frontend"),
                ],
                assume_yes=True,
            )
            self.assertEqual(result.exit_code, EXIT_SUCCESS, result.message)
            status = self._status(project)
            self.assertEqual(status.state, StatusState.HEALTHY)
            cfg = ProjectConfigStore(project, registry=self.registry).load()
            shared = [ws for ws in cfg.workspaces if ws.path == "packages/shared"]
            self.assertEqual(len(shared), 1)
            self.assertEqual(list(shared[0].components), ["frontend"])

    def test_configure_schema2_to_schema1(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = _make_reference_monorepo(tmp)
            self.assertEqual(self._install_reference(project), EXIT_SUCCESS)
            result = self._run_configure(
                project,
                components=["devops"],
                assistants=list(ALL_ASSISTANTS),
                no_workspaces=True,
                assume_yes=True,
            )
            self.assertEqual(result.exit_code, EXIT_SUCCESS, result.message)
            status = self._status(project)
            self.assertEqual(status.state, StatusState.HEALTHY)
            cfg = ProjectConfigStore(project, registry=self.registry).load()
            self.assertEqual(cfg.schema_version, 1)
            self.assertEqual(status.workspaces, [])
            for relative in WORKSPACE_DIRS:
                self.assertTrue((project / relative / "SENTINEL").is_file())
            for path in (project / ".cursor" / "rules").glob("*.mdc"):
                self.assertNotIn(
                    "globs: apps/api/**",
                    path.read_text(encoding="utf-8"),
                )

    def test_configure_dry_run_matches_yes_intent(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = _make_reference_monorepo(tmp)
            self.assertEqual(self._install_empty_root(project), EXIT_SUCCESS)
            yaml_path = project / PROJECT_CONFIG_RELATIVE
            before = yaml_path.read_bytes()
            result = self._run_configure(
                project,
                no_root_components=True,
                assistants=["cursor"],
                workspaces=[("apps/web", "frontend")],
                dry_run=True,
            )
            self.assertEqual(result.exit_code, EXIT_SUCCESS, result.message)
            self.assertEqual(yaml_path.read_bytes(), before)
            self.assertIn("Dry", result.message)
            self.assertEqual(self._status(project).configuration_sha256, GOLDEN_A)


class InstallDryRunAndScaleTests(WorkspaceConsumerHelpers):
    def test_install_dry_run_workspace(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = _make_reference_monorepo(tmp)
            code = main(
                [
                    "install",
                    "--path",
                    str(project),
                    "--workspace",
                    "apps/api",
                    "symfony",
                    "--assistant",
                    "cursor",
                    "--dry-run",
                ]
            )
            self.assertEqual(code, EXIT_SUCCESS)
            self.assertFalse((project / PROJECT_CONFIG_RELATIVE).exists())

    def test_scale_four_and_ten_workspaces(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            project.mkdir()
            for count in (4, 10):
                pairs = []
                for index in range(count):
                    relative = "apps/ws{:02d}".format(index)
                    (project / relative).mkdir(parents=True, exist_ok=True)
                    pairs.append((relative, "core"))
                forward = build_install_project_config_from_cli(
                    project_root=project,
                    registry=self.registry,
                    components=None,
                    assistants=["cursor"],
                    workspace_pairs=pairs,
                    no_root_components=True,
                    no_workspaces=False,
                    profile=None,
                )
                reverse = build_install_project_config_from_cli(
                    project_root=project,
                    registry=self.registry,
                    components=None,
                    assistants=["cursor"],
                    workspace_pairs=list(reversed(pairs)),
                    no_root_components=True,
                    no_workspaces=False,
                    profile=None,
                )
                self.assertEqual(len(forward.workspaces), count)
                digest = configuration_hash_for(forward, self.registry)
                self.assertEqual(
                    configuration_hash_for(reverse, self.registry), digest
                )


class InvalidConfigureMatrixTests(WorkspaceConsumerHelpers):
    def test_invalid_configure_matrix(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = _make_reference_monorepo(tmp)
            self.assertEqual(self._install_reference(project), EXIT_SUCCESS)

            combo = self._run_configure(
                project,
                workspaces=[("apps/api", "symfony")],
                no_workspaces=True,
                assistants=["cursor"],
                assume_yes=True,
            )
            self.assertEqual(combo.exit_code, EXIT_SELECTION)
            self.assertIn("--workspace", combo.message)
            self.assertIn("--no-workspaces", combo.message)

            empty = self._run_configure(
                project,
                no_workspaces=True,
                no_root_components=True,
                assistants=["cursor"],
                assume_yes=True,
            )
            self.assertEqual(empty.exit_code, EXIT_SELECTION)
            self.assertIn("--no-workspaces", empty.message)
            self.assertIn("--no-root-components", empty.message)

            omitted = self._run_configure(
                project,
                components=["devops"],
                assistants=["cursor"],
                assume_yes=True,
            )
            self.assertEqual(omitted.exit_code, EXIT_SELECTION)
            self.assertRegex(omitted.message.lower(), r"workspace")

        with tempfile.TemporaryDirectory() as tmp:
            project = _make_reference_monorepo(tmp)
            self.assertEqual(
                main(
                    [
                        "install",
                        "--path",
                        str(project),
                        "--component",
                        "devops",
                        "--assistant",
                        "cursor",
                        "--yes",
                    ]
                ),
                EXIT_SUCCESS,
            )
            missing_root = self._run_configure(
                project,
                workspaces=[("apps/api", "symfony")],
                assistants=["cursor"],
                assume_yes=True,
            )
            self.assertEqual(missing_root.exit_code, EXIT_SELECTION)
            self.assertRegex(
                missing_root.message.lower(),
                r"component|no-root-components",
            )


class InteractiveConfigureTests(WorkspaceConsumerHelpers):
    def test_interactive_workspace_replacement_and_remove_all(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = _make_reference_monorepo(tmp)
            self.assertEqual(self._install_empty_root(project), EXIT_SUCCESS)
            result = self._run_configure(
                project,
                answers=["", "", "y", "apps/web", "frontend", "", "y"],
            )
            self.assertEqual(result.exit_code, EXIT_SUCCESS, result.message)
            cfg = ProjectConfigStore(project, registry=self.registry).load()
            self.assertEqual(cfg.schema_version, 2)
            self.assertEqual([ws.path for ws in cfg.workspaces], ["apps/web"])
            self.assertEqual(list(cfg.workspaces[0].components), ["frontend"])

        with tempfile.TemporaryDirectory() as tmp:
            project = _make_reference_monorepo(tmp)
            self.assertEqual(
                main(
                    [
                        "install",
                        "--path",
                        str(project),
                        "--component",
                        "devops",
                        "--workspace",
                        "apps/api",
                        "symfony",
                        "--assistant",
                        "cursor",
                        "--yes",
                    ]
                ),
                EXIT_SUCCESS,
            )
            result = self._run_configure(
                project,
                answers=["", "", "y", "", "y"],
            )
            self.assertEqual(result.exit_code, EXIT_SUCCESS, result.message)
            cfg = ProjectConfigStore(project, registry=self.registry).load()
            self.assertEqual(cfg.schema_version, 1)
            self.assertEqual(list(cfg.components), ["devops"])
            self.assertEqual(cfg.workspaces, ())

    def test_interactive_empty_root_zero_workspaces_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = _make_reference_monorepo(tmp)
            self.assertEqual(self._install_empty_root(project), EXIT_SUCCESS)
            result = self._run_configure(
                project,
                answers=["-", "", "y", ""],
            )
            self.assertEqual(result.exit_code, EXIT_SELECTION)
            self.assertRegex(result.message.lower(), r"empty|workspace|component")

    def test_prepare_once(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = _make_reference_monorepo(tmp)
            self.assertEqual(self._install_empty_root(project), EXIT_SUCCESS)
            service = ConfigureService(
                registry=self.registry,
                resource_root=get_ekp_root(),
            )
            prepared_results = []
            real_prepare = service.prepare_project

            def tracking_prepare(*args, **kwargs):
                result = real_prepare(*args, **kwargs)
                prepared_results.append(result)
                return result

            with mock.patch.object(
                service, "prepare_project", side_effect=tracking_prepare
            ), mock.patch.object(
                service, "apply", wraps=service.apply
            ) as apply_mock:
                result = self._run_configure(
                    project,
                    answers=["", "", "y", "apps/web", "frontend", "", "y"],
                    service=service,
                )
            self.assertEqual(result.exit_code, EXIT_SUCCESS, result.message)
            self.assertEqual(len(prepared_results), 1)
            self.assertEqual(apply_mock.call_count, 1)
            self.assertIs(
                apply_mock.call_args[0][0],
                prepared_results[0].prepared,
            )


class RefusalAndStatusTests(WorkspaceConsumerHelpers):
    def test_legacy_profile_refuses_workspace(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = _make_reference_monorepo(tmp)
            err = io.StringIO()
            with mock.patch("sys.stderr", err):
                code = main(
                    [
                        "install",
                        "--path",
                        str(project),
                        "--profile",
                        "cursor-core",
                        "--workspace",
                        "apps/api",
                        "symfony",
                        "--yes",
                    ]
                )
            self.assertEqual(code, EXIT_SELECTION)
            self.assertIn("--profile", err.getvalue())

    def test_reinstall_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = _make_reference_monorepo(tmp)
            self.assertEqual(self._install_empty_root(project), EXIT_SUCCESS)
            err = io.StringIO()
            with mock.patch("sys.stderr", err):
                code = main(
                    [
                        "install",
                        "--path",
                        str(project),
                        "--workspace",
                        "apps/api",
                        "symfony",
                        "--assistant",
                        "cursor",
                        "--yes",
                    ]
                )
            self.assertNotEqual(code, EXIT_SUCCESS)
            lowered = err.getvalue().lower()
            self.assertIn("status", lowered)
            self.assertIn("update", lowered)

    def test_status_shows_empty_root(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = _make_reference_monorepo(tmp)
            self.assertEqual(self._install_empty_root(project), EXIT_SUCCESS)
            buf = io.StringIO()
            with mock.patch("sys.stdout", buf):
                code = main(["status", "--path", str(project)])
            self.assertEqual(code, EXIT_SUCCESS)
            self.assertIn("Root components: none", buf.getvalue())


if __name__ == "__main__":
    unittest.main()
