"""AZ-D workspace / schema2 lifecycle integration tests."""

from __future__ import annotations

import hashlib
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from ekp.composition import ComponentRegistry
from ekp.config.models import PROJECT_CONFIG_RELATIVE, ProjectConfig, WorkspaceIntent
from ekp.config.project import render_project_config_yaml
from ekp.install.composition_install import CompositionInstallService
from ekp.install.errors import EXIT_CONFLICT, EXIT_SELECTION, EXIT_SUCCESS
from ekp.install.manifest import ManifestStore
from ekp.lifecycle.configure import ConfigureProjectRequest, ConfigureService
from ekp.lifecycle.uninstall import UninstallRequest, UninstallService
from ekp.lifecycle.update import UpdateRequest, UpdateService
from ekp.paths import get_ekp_root
from ekp.status.models import StatusState
from ekp.status.service import StatusRequest, StatusService

WORKSPACE_DIRS = (
    "apps/api",
    "apps/mobile",
    "apps/web",
    "packages/shared",
)

# Reference monorepo managed-file counts (scoped assembly + deploy collect).
REF_CURSOR = 105
REF_COPILOT = 16
REF_CLAUDE = 37
REF_ANTIGRAVITY = 38


def _fingerprint(root: Path):
    items = {}
    for path in sorted(root.rglob("*")):
        if path.is_file():
            items[path.relative_to(root).as_posix()] = hashlib.sha256(
                path.read_bytes()
            ).hexdigest()
    return items


def _reference_config():
    return ProjectConfig(
        2,
        ("devops",),
        ("cursor", "copilot", "claude", "antigravity"),
        (
            WorkspaceIntent("apps/api", ("symfony",)),
            WorkspaceIntent("apps/mobile", ("flutter",)),
            WorkspaceIntent("apps/web", ("frontend",)),
            WorkspaceIntent("packages/shared", ("typescript",)),
        ),
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


def _empty_root_symfony(assistants=("cursor",)):
    return ProjectConfig(
        2,
        (),
        tuple(assistants),
        (WorkspaceIntent("apps/api", ("symfony",)),),
    )


def _make_monorepo(tmp: str) -> Path:
    project = Path(tmp) / "project"
    project.mkdir()
    for relative in WORKSPACE_DIRS:
        (project / relative).mkdir(parents=True, exist_ok=True)
    return project


def _adapter_counts(project: Path) -> dict:
    manifest = ManifestStore(project).load()
    counts = {}
    for item in manifest.managed_files:
        counts[item.adapter] = counts.get(item.adapter, 0) + 1
    return counts


class WorkspaceLifecycleHelpers(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.resource_root = get_ekp_root()
        cls.registry = ComponentRegistry.load(cls.resource_root)

    def _install_service(self) -> CompositionInstallService:
        return CompositionInstallService(
            registry=self.registry,
            resource_root=self.resource_root,
        )

    def _install(self, project: Path, config: ProjectConfig, *, dry_run=False):
        result = self._install_service().install_project_config(
            project, config, dry_run=dry_run
        )
        if not dry_run:
            self.assertEqual(result.exit_code, EXIT_SUCCESS, result.message)
        return result

    def _status(self, project: Path):
        return StatusService().inspect(StatusRequest(path=str(project)))

    def _configure(self, project: Path, desired: ProjectConfig, *, dry_run=False):
        return ConfigureService(
            registry=self.registry,
            resource_root=self.resource_root,
        ).configure_project(
            ConfigureProjectRequest(
                path=str(project),
                desired_config=desired,
                dry_run=dry_run,
            )
        )

    def _update(self, project: Path, *, dry_run=False):
        return UpdateService().update(
            UpdateRequest(path=str(project), assume_yes=True, dry_run=dry_run)
        )

    def _uninstall(self, project: Path):
        return UninstallService().uninstall(
            UninstallRequest(path=str(project), assume_yes=True)
        )


class WorkspaceInstallTests(WorkspaceLifecycleHelpers):
    def test_reference_install_healthy_and_counts(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = _make_monorepo(tmp)
            self._install(project, _reference_config())
            status = self._status(project)
            self.assertEqual(status.state, StatusState.HEALTHY)
            counts = _adapter_counts(project)
            self.assertEqual(counts.get("cursor"), REF_CURSOR)
            self.assertEqual(counts.get("copilot"), REF_COPILOT)
            self.assertEqual(counts.get("claude"), REF_CLAUDE)
            self.assertEqual(counts.get("antigravity"), REF_ANTIGRAVITY)
            self.assertEqual(status.managed_total, sum(counts.values()))
            created = set(ManifestStore(project).load().created_directories)
            for relative in WORKSPACE_DIRS:
                self.assertNotIn(relative, created)
                self.assertTrue((project / relative).is_dir())

    def test_empty_root_install_no_global_assistant_roots(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            project.mkdir()
            (project / "apps" / "api").mkdir(parents=True)
            config = _empty_root_symfony(
                ("cursor", "copilot", "claude", "antigravity")
            )
            self._install(project, config)
            status = self._status(project)
            self.assertEqual(status.state, StatusState.HEALTHY)
            self.assertEqual(status.requested_components, [])
            self.assertFalse((project / "CLAUDE.md").exists())
            self.assertFalse(
                (project / ".github" / "copilot-instructions.md").exists()
            )
            rules = project / ".cursor" / "rules"
            self.assertTrue(rules.is_dir())
            self.assertGreater(len(list(rules.glob("*.mdc"))), 0)

    def test_schema1_install_frontend_cursor(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            project.mkdir()
            config = ProjectConfig(1, ("frontend",), ("cursor",), ())
            self._install(project, config)
            status = self._status(project)
            self.assertEqual(status.state, StatusState.HEALTHY)
            self.assertEqual(status.requested_components, ["frontend"])
            self.assertEqual(status.managed_total, 92)

    def test_dry_run_install_writes_nothing(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = _make_monorepo(tmp)
            before = _fingerprint(project)
            result = self._install(
                project, _reference_cursor_only(), dry_run=True
            )
            self.assertEqual(result.exit_code, EXIT_SUCCESS, result.message)
            self.assertEqual(_fingerprint(project), before)
            self.assertFalse((project / PROJECT_CONFIG_RELATIVE).exists())
            self.assertFalse((project / ".ekp" / "install.json").exists())

    def test_collision_preexisting_desired_path_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = _make_monorepo(tmp)
            config = _empty_root_symfony(("cursor",))
            dry = self._install(project, config, dry_run=True)
            self.assertEqual(dry.exit_code, EXIT_SUCCESS, dry.message)
            sample = dry.plan.deployment_plan.operations[0].relative_path
            target = project / Path(*sample.split("/"))
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text("user-owned\n", encoding="utf-8")
            before = _fingerprint(project)
            result = self._install_service().install_project_config(project, config)
            self.assertEqual(result.exit_code, EXIT_CONFLICT, result.message)
            self.assertEqual(_fingerprint(project), before)
            self.assertFalse((project / PROJECT_CONFIG_RELATIVE).exists())
            self.assertFalse((project / ".ekp" / "install.json").exists())


class WorkspaceUpdateConfigureTests(WorkspaceLifecycleHelpers):
    def test_update_preserves_project_yaml_bytes_no_detection(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = _make_monorepo(tmp)
            self._install(project, _reference_cursor_only())
            yaml_path = project / PROJECT_CONFIG_RELATIVE
            before_bytes = yaml_path.read_bytes()
            with mock.patch(
                "ekp.detection.service.DetectionService.detect"
            ) as detect:
                result = self._update(project)
                self.assertEqual(detect.call_count, 0)
            self.assertEqual(result.exit_code, EXIT_SUCCESS, result.message)
            self.assertEqual(yaml_path.read_bytes(), before_bytes)
            self.assertEqual(self._status(project).state, StatusState.HEALTHY)

    def test_configure_schema_transitions_and_noop(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = _make_monorepo(tmp)
            schema1 = ProjectConfig(1, ("frontend",), ("cursor",), ())
            self._install(project, schema1)
            self.assertEqual(self._status(project).state, StatusState.HEALTHY)

            schema2 = ProjectConfig(
                2,
                (),
                ("cursor",),
                (WorkspaceIntent("apps/web", ("frontend",)),),
            )
            result = self._configure(project, schema2)
            self.assertEqual(result.exit_code, EXIT_SUCCESS, result.message)
            self.assertFalse(result.noop)
            status = self._status(project)
            self.assertEqual(status.state, StatusState.HEALTHY)
            self.assertEqual(status.requested_components, [])
            self.assertEqual(len(status.workspaces), 1)
            self.assertEqual(status.workspaces[0].path, "apps/web")

            schema2_changed = ProjectConfig(
                2,
                ("devops",),
                ("cursor",),
                (
                    WorkspaceIntent("apps/api", ("symfony",)),
                    WorkspaceIntent("apps/web", ("frontend",)),
                ),
            )
            result = self._configure(project, schema2_changed)
            self.assertEqual(result.exit_code, EXIT_SUCCESS, result.message)
            self.assertFalse(result.noop)
            status = self._status(project)
            self.assertEqual(status.state, StatusState.HEALTHY)
            self.assertEqual(status.requested_components, ["devops"])
            self.assertEqual(
                [ws.path for ws in status.workspaces],
                ["apps/api", "apps/web"],
            )

            back_to_schema1 = ProjectConfig(1, ("symfony",), ("cursor",), ())
            result = self._configure(project, back_to_schema1)
            self.assertEqual(result.exit_code, EXIT_SUCCESS, result.message)
            self.assertFalse(result.noop)
            status = self._status(project)
            self.assertEqual(status.state, StatusState.HEALTHY)
            self.assertEqual(status.requested_components, ["symfony"])
            self.assertEqual(status.workspaces, [])

            # Semantic NOOP: matching hash must skip assembly entirely.
            with mock.patch(
                "ekp.assembly.AssemblyService.assemble_composition"
            ) as assemble_composition, mock.patch(
                "ekp.assembly.AssemblyService.assemble_scoped_project"
            ) as assemble_scoped:
                noop = self._configure(project, back_to_schema1)
            self.assertEqual(noop.exit_code, EXIT_SUCCESS, noop.message)
            self.assertTrue(noop.noop)
            self.assertEqual(assemble_composition.call_count, 0)
            self.assertEqual(assemble_scoped.call_count, 0)
            self.assertEqual(
                len(noop.plan.operations) if noop.plan is not None else 0, 0
            )


class WorkspaceIntegrityGateTests(WorkspaceLifecycleHelpers):
    def test_configuration_drift_status_and_refusals(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = _make_monorepo(tmp)
            config = _empty_root_symfony(("cursor",))
            self._install(project, config)
            drifted = ProjectConfig(
                2,
                ("devops",),
                ("cursor",),
                (WorkspaceIntent("apps/api", ("symfony",)),),
            )
            (project / PROJECT_CONFIG_RELATIVE).write_text(
                render_project_config_yaml(drifted), encoding="utf-8"
            )
            status = self._status(project)
            self.assertEqual(status.state, StatusState.CONFIGURATION_DRIFT)
            self.assertTrue(status.configuration_drift)

            before = _fingerprint(project)
            configure = self._configure(
                project,
                ProjectConfig(
                    2,
                    (),
                    ("cursor", "copilot"),
                    (WorkspaceIntent("apps/api", ("symfony",)),),
                ),
            )
            self.assertEqual(configure.exit_code, EXIT_SELECTION)
            update = self._update(project)
            self.assertEqual(update.exit_code, EXIT_CONFLICT)
            self.assertEqual(_fingerprint(project), before)

    def test_modified_scoped_file_configure_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = _make_monorepo(tmp)
            self._install(project, _empty_root_symfony(("cursor",)))
            managed = ManifestStore(project).load().managed_files[0]
            target = project.joinpath(*managed.relative_path.split("/"))
            target.write_text(
                target.read_text(encoding="utf-8") + "\n# edited\n",
                encoding="utf-8",
            )
            status = self._status(project)
            self.assertEqual(status.state, StatusState.MODIFIED)
            self.assertIn(managed.relative_path, status.modified_paths)

            before = _fingerprint(project)
            result = self._configure(
                project,
                ProjectConfig(
                    2,
                    ("devops",),
                    ("cursor",),
                    (WorkspaceIntent("apps/api", ("symfony",)),),
                ),
            )
            self.assertEqual(result.exit_code, EXIT_SELECTION)
            self.assertEqual(_fingerprint(project), before)

    def test_incomplete_missing_scoped_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = _make_monorepo(tmp)
            self._install(project, _empty_root_symfony(("cursor",)))
            managed = ManifestStore(project).load().managed_files[0]
            target = project.joinpath(*managed.relative_path.split("/"))
            target.unlink()
            status = self._status(project)
            self.assertEqual(status.state, StatusState.INCOMPLETE)
            self.assertIn(managed.relative_path, status.missing_paths)


class WorkspaceUninstallTests(WorkspaceLifecycleHelpers):
    def test_uninstall_removes_managed_preserves_workspaces_no_assembly(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = _make_monorepo(tmp)
            self._install(project, _reference_cursor_only())
            managed_paths = [
                item.relative_path
                for item in ManifestStore(project).load().managed_files
            ]
            self.assertGreater(len(managed_paths), 0)

            with mock.patch(
                "ekp.composition.resolve_project_composition"
            ) as resolve_pc, mock.patch(
                "ekp.assembly.AssemblyService.assemble_scoped_project"
            ) as assemble_scoped, mock.patch(
                "ekp.assembly.AssemblyService.assemble_composition"
            ) as assemble_composition:
                result = self._uninstall(project)

            self.assertEqual(result.exit_code, EXIT_SUCCESS, result.message)
            self.assertEqual(resolve_pc.call_count, 0)
            self.assertEqual(assemble_scoped.call_count, 0)
            self.assertEqual(assemble_composition.call_count, 0)

            self.assertFalse((project / ".ekp" / "install.json").exists())
            self.assertTrue((project / PROJECT_CONFIG_RELATIVE).is_file())
            for relative in managed_paths:
                self.assertFalse(
                    (project / Path(*relative.split("/"))).exists(),
                    msg=relative,
                )
            for relative in WORKSPACE_DIRS:
                self.assertTrue((project / relative).is_dir())
            self.assertEqual(self._status(project).state, StatusState.NOT_INSTALLED)


if __name__ == "__main__":
    unittest.main()
