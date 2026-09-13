"""AZ-D workspace / schema2 status inspection tests."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from ekp.composition import ComponentRegistry
from ekp.config.models import ProjectConfig, WorkspaceIntent
from ekp.config.project import render_project_config_yaml
from ekp.install.composition_install import CompositionInstallService
from ekp.install.errors import EXIT_SUCCESS
from ekp.install.manifest import ManifestStore
from ekp.paths import get_ekp_root
from ekp.status.models import StatusState
from ekp.status.service import StatusRequest, StatusService

WORKSPACE_DIRS = (
    "apps/api",
    "apps/mobile",
    "apps/web",
    "packages/shared",
)


def _reference_cursor_only():
    return ProjectConfig(
        2,
        ("devops",),
        ("cursor",),
        (
            WorkspaceIntent("apps/api", ("symfony",)),
            WorkspaceIntent("apps/mobile", ("flutter",)),
            WorkspaceIntent("apps/web", ("frontend",)),
            WorkspaceIntent("packages/shared", ("typescript",)),
        ),
    )


def _empty_root_symfony():
    return ProjectConfig(
        2,
        (),
        ("cursor",),
        (WorkspaceIntent("apps/api", ("symfony",)),),
    )


def _make_monorepo(tmp: str) -> Path:
    project = Path(tmp) / "project"
    project.mkdir()
    for relative in WORKSPACE_DIRS:
        (project / relative).mkdir(parents=True, exist_ok=True)
    return project


class WorkspaceStatusHelpers(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.resource_root = get_ekp_root()
        cls.registry = ComponentRegistry.load(cls.resource_root)

    def _install(self, project: Path, config: ProjectConfig):
        result = CompositionInstallService(
            registry=self.registry,
            resource_root=self.resource_root,
        ).install_project_config(project, config, dry_run=False)
        self.assertEqual(result.exit_code, EXIT_SUCCESS, result.message)

    def _status(self, project: Path):
        return StatusService().inspect(StatusRequest(path=str(project)))


class WorkspaceStatusTests(WorkspaceStatusHelpers):
    def test_empty_root_status_requested_empty_workspaces_populated(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            project.mkdir()
            (project / "apps" / "api").mkdir(parents=True)
            self._install(project, _empty_root_symfony())
            status = self._status(project)
            self.assertEqual(status.state, StatusState.HEALTHY)
            self.assertEqual(status.requested_components, [])
            self.assertEqual(len(status.workspaces), 1)
            ws = status.workspaces[0]
            self.assertEqual(ws.path, "apps/api")
            self.assertEqual(ws.requested_components, ["symfony"])
            self.assertIn("core", ws.resolved_components)
            self.assertIn("symfony", ws.resolved_components)
            self.assertIn("cursor", ws.assistant_output_counts)
            self.assertGreater(ws.assistant_output_counts["cursor"], 0)

    def test_workspace_diagnostics_sorted_with_counts(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = _make_monorepo(tmp)
            self._install(project, _reference_cursor_only())
            status = self._status(project)
            self.assertEqual(status.state, StatusState.HEALTHY)
            paths = [ws.path for ws in status.workspaces]
            self.assertEqual(
                paths,
                ["apps/api", "apps/mobile", "apps/web", "packages/shared"],
            )
            self.assertEqual(paths, sorted(paths))
            for ws in status.workspaces:
                self.assertTrue(ws.requested_components)
                self.assertTrue(ws.resolved_components)
                self.assertEqual(set(ws.assistant_output_counts.keys()), {"cursor"})
                self.assertGreater(ws.assistant_output_counts["cursor"], 0)
                self.assertEqual(ws.issues, [])

    def test_drift_beats_modified_precedence(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            project.mkdir()
            (project / "apps" / "api").mkdir(parents=True)
            self._install(project, _empty_root_symfony())

            managed = ManifestStore(project).load().managed_files[0]
            target = project.joinpath(*managed.relative_path.split("/"))
            target.write_text(
                target.read_text(encoding="utf-8") + "\n# edited\n",
                encoding="utf-8",
            )

            drifted = ProjectConfig(
                2,
                ("devops",),
                ("cursor",),
                (WorkspaceIntent("apps/api", ("symfony",)),),
            )
            (project / ".ekp" / "project.yaml").write_text(
                render_project_config_yaml(drifted), encoding="utf-8"
            )

            status = self._status(project)
            self.assertEqual(status.state, StatusState.CONFIGURATION_DRIFT)
            self.assertTrue(status.configuration_drift)
            self.assertIn(managed.relative_path, status.modified_paths)


if __name__ == "__main__":
    unittest.main()
