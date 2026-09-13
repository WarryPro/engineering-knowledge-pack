"""Public CLI workspace UX tests (AZ-E)."""

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
    group_workspace_cli_pairs,
    normalize_cli_workspace_path,
)
from ekp.composition import ComponentRegistry
from ekp.config.models import ProjectConfig, WorkspaceIntent
from ekp.config.project import ProjectConfigStore
from ekp.install.errors import EXIT_SELECTION, EXIT_SUCCESS, InstallSelectionError
from ekp.lifecycle.configure_cli import run_configure_cli
from ekp.paths import get_ekp_root
from ekp.status.models import StatusState
from ekp.status.service import StatusRequest, StatusService
from ekp.tests.fixtures import frontend_fixture, symfony_fixture

WORKSPACE_DIRS = (
    "apps/api",
    "apps/mobile",
    "apps/web",
    "packages/shared",
)

GOLDEN_A = "09cf2e9312aa182a2fc6438080bc4a9c687838077e4e7aeffe56c448e8655b14"
GOLDEN_B = "e62a4fedaae9b849e684cab7ad01ed7f9e2eee0278b5e2d4515cb3d40b41308b"


def _make_monorepo(tmp: str) -> Path:
    project = Path(tmp) / "project"
    project.mkdir()
    for relative in WORKSPACE_DIRS:
        (project / relative).mkdir(parents=True, exist_ok=True)
    return project


class WorkspaceCliHelpers(unittest.TestCase):
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
        )


class NormalizeAndGroupTests(unittest.TestCase):
    def test_normalize_backslash_and_refuse_dot_segment(self):
        self.assertEqual(normalize_cli_workspace_path(r"apps\api"), "apps/api")
        with self.assertRaises(InstallSelectionError):
            normalize_cli_workspace_path("apps/./api")

    def test_group_workspace_cli_pairs_merges_same_path(self):
        grouped = group_workspace_cli_pairs(
            [
                ("apps/api", "symfony"),
                (r"apps\api", "frontend"),
                ("apps/web", "frontend"),
                ("apps/api", "symfony"),
            ]
        )
        self.assertEqual(
            grouped,
            (
                WorkspaceIntent("apps/api", ("symfony", "frontend")),
                WorkspaceIntent("apps/web", ("frontend",)),
            ),
        )


class BuildInstallConfigTests(WorkspaceCliHelpers):
    def test_option_order_independence_same_golden_b(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = _make_monorepo(tmp)
            kwargs = dict(
                project_root=project,
                registry=self.registry,
                components=["devops"],
                assistants=["cursor", "claude"],
                no_root_components=False,
                no_workspaces=False,
                profile=None,
            )
            forward = build_install_project_config_from_cli(
                workspace_pairs=[
                    ("apps/api", "symfony"),
                    ("apps/web", "frontend"),
                ],
                **kwargs,
            )
            reverse = build_install_project_config_from_cli(
                workspace_pairs=[
                    ("apps/web", "frontend"),
                    ("apps/api", "symfony"),
                ],
                **kwargs,
            )
            self.assertEqual(configuration_hash_for(forward, self.registry), GOLDEN_B)
            self.assertEqual(
                configuration_hash_for(forward, self.registry),
                configuration_hash_for(reverse, self.registry),
            )

    def test_no_workspaces_flag_refused_on_install_builder(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = _make_monorepo(tmp)
            with self.assertRaises(InstallSelectionError) as raised:
                build_install_project_config_from_cli(
                    project_root=project,
                    registry=self.registry,
                    components=None,
                    assistants=["cursor"],
                    workspace_pairs=[("apps/api", "symfony")],
                    no_root_components=True,
                    no_workspaces=True,
                    profile=None,
                )
            self.assertIn("--no-workspaces", str(raised.exception.message))

    def test_scale_fifty_workspaces_deterministic_hash(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            project.mkdir()
            pairs = []
            for index in range(50):
                relative = "apps/ws{:02d}".format(index)
                (project / relative).mkdir(parents=True, exist_ok=True)
                pairs.append((relative, "core"))
            config = build_install_project_config_from_cli(
                project_root=project,
                registry=self.registry,
                components=None,
                assistants=["cursor"],
                workspace_pairs=pairs,
                no_root_components=True,
                no_workspaces=False,
                profile=None,
            )
            self.assertEqual(len(config.workspaces), 50)
            digest = configuration_hash_for(config, self.registry)
            again = build_install_project_config_from_cli(
                project_root=project,
                registry=self.registry,
                components=None,
                assistants=["cursor"],
                workspace_pairs=list(reversed(pairs)),
                no_root_components=True,
                no_workspaces=False,
                profile=None,
            )
            self.assertEqual(configuration_hash_for(again, self.registry), digest)


class PublicInstallWorkspaceCliTests(WorkspaceCliHelpers):
    def test_empty_root_install_golden_a_healthy(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = _make_monorepo(tmp)
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
            self.assertEqual(code, EXIT_SUCCESS)
            status = self._status(project)
            self.assertEqual(status.state, StatusState.HEALTHY)
            self.assertEqual(status.configuration_sha256, GOLDEN_A)
            self.assertEqual(status.requested_components, [])
            self.assertFalse((project / "CLAUDE.md").exists())

    def test_schema1_install_still_works(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            project.mkdir()
            code = main(
                [
                    "install",
                    "--path",
                    str(project),
                    "--component",
                    "frontend",
                    "--assistant",
                    "cursor",
                    "--yes",
                ]
            )
            self.assertEqual(code, EXIT_SUCCESS)
            status = self._status(project)
            self.assertEqual(status.state, StatusState.HEALTHY)
            self.assertEqual(status.requested_components, ["frontend"])

    def test_workspace_install_skips_root_symfony_detection(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            project.mkdir()
            (project / "apps" / "web").mkdir(parents=True)
            symfony_fixture(project)
            frontend_fixture(project / "apps" / "web")
            code = main(
                [
                    "install",
                    "--path",
                    str(project),
                    "--workspace",
                    "apps/web",
                    "frontend",
                    "--assistant",
                    "cursor",
                    "--yes",
                ]
            )
            self.assertEqual(code, EXIT_SUCCESS)
            cfg = ProjectConfigStore(project, registry=self.registry).load()
            self.assertEqual(cfg.components, ())
            self.assertEqual(
                [ws.path for ws in cfg.workspaces],
                ["apps/web"],
            )
            self.assertEqual(list(cfg.workspaces[0].components), ["frontend"])
            expected = configuration_hash_for(
                ProjectConfig(
                    2,
                    (),
                    ("cursor",),
                    (WorkspaceIntent("apps/web", ("frontend",)),),
                ),
                self.registry,
            )
            self.assertEqual(self._status(project).configuration_sha256, expected)
            self.assertNotEqual(expected, GOLDEN_A)

    def test_invalid_install_flag_combinations_and_paths(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = _make_monorepo(tmp)
            combo = main(
                [
                    "install",
                    "--path",
                    str(project),
                    "--component",
                    "core",
                    "--no-root-components",
                    "--workspace",
                    "apps/api",
                    "symfony",
                    "--assistant",
                    "cursor",
                    "--yes",
                ]
            )
            self.assertEqual(combo, EXIT_SELECTION)

            bare = main(
                [
                    "install",
                    "--path",
                    str(project),
                    "--no-root-components",
                    "--assistant",
                    "cursor",
                    "--yes",
                ]
            )
            self.assertEqual(bare, EXIT_SELECTION)

            missing = main(
                [
                    "install",
                    "--path",
                    str(project),
                    "--workspace",
                    "apps/missing",
                    "symfony",
                    "--assistant",
                    "cursor",
                    "--yes",
                ]
            )
            self.assertEqual(missing, EXIT_SELECTION)

            unknown = main(
                [
                    "install",
                    "--path",
                    str(project),
                    "--workspace",
                    "apps/api",
                    "not-a-real-component",
                    "--assistant",
                    "cursor",
                    "--yes",
                ]
            )
            self.assertEqual(unknown, EXIT_SELECTION)

            dot = main(
                [
                    "install",
                    "--path",
                    str(project),
                    "--workspace",
                    ".",
                    "symfony",
                    "--assistant",
                    "cursor",
                    "--yes",
                ]
            )
            self.assertEqual(dot, EXIT_SELECTION)

            bad_assistant = main(
                [
                    "install",
                    "--path",
                    str(project),
                    "--workspace",
                    "apps/api",
                    "symfony",
                    "--assistant",
                    "not-a-real-assistant",
                    "--yes",
                ]
            )
            self.assertEqual(bad_assistant, EXIT_SELECTION)

            profile_ws = main(
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
            self.assertEqual(profile_ws, EXIT_SELECTION)


class PublicConfigureWorkspaceCliTests(WorkspaceCliHelpers):
    def test_noninteractive_configure_refuses_without_assistant(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = _make_monorepo(tmp)
            self.assertEqual(
                main(
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
                ),
                EXIT_SUCCESS,
            )
            result = self._run_configure(
                project,
                no_root_components=True,
                workspaces=[("apps/api", "symfony")],
                assume_yes=True,
            )
            self.assertEqual(result.exit_code, EXIT_SELECTION)
            self.assertRegex(result.message.lower(), r"assistant")

    def test_schema1_to_schema2_configure(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = _make_monorepo(tmp)
            self.assertEqual(
                main(
                    [
                        "install",
                        "--path",
                        str(project),
                        "--component",
                        "frontend",
                        "--assistant",
                        "cursor",
                        "--yes",
                    ]
                ),
                EXIT_SUCCESS,
            )
            result = self._run_configure(
                project,
                components=None,
                assistants=["cursor", "claude"],
                workspaces=[("apps/api", "symfony")],
                no_root_components=True,
                assume_yes=True,
            )
            self.assertEqual(result.exit_code, EXIT_SUCCESS, result.message)
            self.assertFalse(result.noop)
            status = self._status(project)
            self.assertEqual(status.state, StatusState.HEALTHY)
            self.assertEqual(status.requested_components, [])
            self.assertEqual(
                [ws.path for ws in status.workspaces],
                ["apps/api"],
            )
            self.assertEqual(set(status.assistants), {"claude", "cursor"})

    def test_interactive_preserve_noop_after_schema2_install(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = _make_monorepo(tmp)
            self.assertEqual(
                main(
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
                ),
                EXIT_SUCCESS,
            )
            outputs = []
            result = self._run_configure(
                project,
                answers=["", "", "n"],
                outputs=outputs,
            )
            self.assertEqual(result.exit_code, EXIT_SUCCESS, result.message)
            self.assertTrue(result.noop)
            joined = "\n".join(outputs)
            self.assertNotIn("Continue?", joined)
            self.assertEqual(self._status(project).configuration_sha256, GOLDEN_A)


class WorkspaceCliHelpTests(unittest.TestCase):
    def test_install_and_configure_help_list_workspace(self):
        for argv in (["install", "--help"], ["configure", "--help"]):
            buf = io.StringIO()
            with mock.patch("sys.stdout", buf):
                with self.assertRaises(SystemExit) as raised:
                    main(argv)
            self.assertEqual(raised.exception.code, 0)
            self.assertIn("--workspace", buf.getvalue())


if __name__ == "__main__":
    unittest.main()
