"""AZ-D-CLOSURE — schema2 workspace lifecycle safety matrix."""

from __future__ import annotations

import hashlib
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from ekp.assembly import AssemblyService
from ekp.composition import ComponentRegistry, resolve_composition
from ekp.config.models import PROJECT_CONFIG_RELATIVE, ProjectConfig, WorkspaceIntent
from ekp.config.project import ProjectConfigStore, render_project_config_yaml
from ekp.install.composition_install import CompositionInstallService
from ekp.install.errors import (
    EXIT_SELECTION,
    EXIT_SUCCESS,
    InstallConflictError,
    InstallFilesystemError,
)
from ekp.install.manifest import InstallManifest, ManifestStore
from ekp.lifecycle.apply import TransactionApplier
from ekp.lifecycle.configure import ConfigureProjectRequest, ConfigureService
from ekp.lifecycle.plan import LifecycleOpKind
from ekp.lifecycle.uninstall import UninstallRequest, UninstallService
from ekp.lifecycle.update import UpdateRequest, UpdateService
from ekp.paths import get_ekp_root
from ekp.status.models import StatusState
from ekp.status.service import StatusRequest, StatusService
from ekp.workspace_identity import workspace_filename_prefix

WORKSPACE_DIRS = (
    "apps/api",
    "apps/mobile",
    "apps/web",
    "packages/shared",
)

REF_CURSOR = 105
REF_COPILOT = 16
REF_CLAUDE = 37
REF_ANTIGRAVITY = 38

ALL_ASSISTANTS = ("cursor", "copilot", "claude", "antigravity")


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
        ALL_ASSISTANTS,
        (
            WorkspaceIntent("apps/api", ("symfony",)),
            WorkspaceIntent("apps/mobile", ("flutter",)),
            WorkspaceIntent("apps/web", ("frontend",)),
            WorkspaceIntent("packages/shared", ("typescript",)),
        ),
    )


def _reference_configure_desired():
    """Same as reference except packages/shared: typescript → frontend."""
    return ProjectConfig(
        2,
        ("devops",),
        ALL_ASSISTANTS,
        (
            WorkspaceIntent("apps/api", ("symfony",)),
            WorkspaceIntent("apps/mobile", ("flutter",)),
            WorkspaceIntent("apps/web", ("frontend",)),
            WorkspaceIntent("packages/shared", ("frontend",)),
        ),
    )


def _cursor_symfony_root_devops():
    return ProjectConfig(
        2,
        ("devops",),
        ("cursor",),
        (WorkspaceIntent("apps/api", ("symfony",)),),
    )


def _cursor_symfony_empty_root():
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
        sentinel = project / relative / "APP_SENTINEL.txt"
        sentinel.write_text("keep:{}\n".format(relative), encoding="utf-8")
    return project


def _adapter_counts(project: Path) -> dict:
    counts = {}
    for item in ManifestStore(project).load().managed_files:
        counts[item.adapter] = counts.get(item.adapter, 0) + 1
    return counts


def _scoped_managed(project: Path, adapter: str, workspace_path: str = "apps/api"):
    prefix = workspace_filename_prefix(workspace_path)
    for item in ManifestStore(project).load().managed_files:
        if item.adapter != adapter:
            continue
        name = Path(item.relative_path).name
        if name.startswith(prefix):
            return item
    raise AssertionError(
        "no scoped managed file for adapter={} workspace={}".format(
            adapter, workspace_path
        )
    )


class SafetyHelpers(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.resource_root = get_ekp_root()
        cls.registry = ComponentRegistry.load(cls.resource_root)

    def _install_service(self) -> CompositionInstallService:
        return CompositionInstallService(
            registry=self.registry,
            resource_root=self.resource_root,
        )

    def _configure_service(self) -> ConfigureService:
        return ConfigureService(
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
        return self._configure_service().configure_project(
            ConfigureProjectRequest(
                path=str(project),
                desired_config=desired,
                dry_run=dry_run,
            )
        )

    def _prepare(self, project: Path, desired: ProjectConfig, *, dry_run=False):
        return self._configure_service().prepare_project(
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

    def _assert_workspace_sentinels(self, project: Path):
        for relative in WORKSPACE_DIRS:
            sentinel = project / relative / "APP_SENTINEL.txt"
            self.assertTrue(sentinel.is_file(), relative)
            self.assertEqual(
                sentinel.read_text(encoding="utf-8"),
                "keep:{}\n".format(relative),
            )

    def _assert_install_fully_rolled_back(self, project: Path, before):
        self.assertFalse((project / ".ekp" / "install.json").exists())
        self.assertFalse((project / PROJECT_CONFIG_RELATIVE).exists())
        self.assertFalse((project / ".ekp").exists())
        for relative in (".cursor", ".github", ".claude", ".agents"):
            self.assertFalse(
                (project / relative).exists(),
                msg="leftover assistant root after rollback: {}".format(relative),
            )
        self.assertEqual(_fingerprint(project), before)
        self._assert_workspace_sentinels(project)


class TransitionMatrixTests(SafetyHelpers):
    def test_schema1_to_schema1_noop(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            project.mkdir()
            # Install with ordered components; desired uses normalized reorder.
            current = ProjectConfig(1, ("frontend", "symfony"), ("cursor",), ())
            self._install(project, current)
            yaml_path = project / PROJECT_CONFIG_RELATIVE
            manifest_path = project / ".ekp" / "install.json"
            yaml_before = yaml_path.read_bytes()
            manifest_before = manifest_path.read_bytes()
            files_before = _fingerprint(project)

            desired = ProjectConfig(1, ("symfony", "frontend"), ("cursor",), ())
            with mock.patch.object(
                AssemblyService, "assemble_composition"
            ) as assemble_composition, mock.patch.object(
                AssemblyService, "assemble_scoped_project"
            ) as assemble_scoped:
                result = self._configure(project, desired)

            self.assertEqual(result.exit_code, EXIT_SUCCESS, result.message)
            self.assertTrue(result.noop)
            self.assertEqual(assemble_composition.call_count, 0)
            self.assertEqual(assemble_scoped.call_count, 0)
            self.assertEqual(yaml_path.read_bytes(), yaml_before)
            self.assertEqual(manifest_path.read_bytes(), manifest_before)
            self.assertEqual(_fingerprint(project), files_before)
            self.assertEqual(self._status(project).state, StatusState.HEALTHY)

    def test_schema1_to_schema2(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = _make_monorepo(tmp)
            self._install(
                project, ProjectConfig(1, ("frontend",), ("cursor",), ())
            )
            desired = ProjectConfig(
                2,
                (),
                ("cursor",),
                (WorkspaceIntent("apps/web", ("frontend",)),),
            )
            result = self._configure(project, desired)
            self.assertEqual(result.exit_code, EXIT_SUCCESS, result.message)
            self.assertFalse(result.noop)
            status = self._status(project)
            self.assertEqual(status.state, StatusState.HEALTHY)
            self.assertEqual(status.requested_components, [])
            self.assertEqual([ws.path for ws in status.workspaces], ["apps/web"])

    def test_schema2_to_schema2_noop(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = _make_monorepo(tmp)
            current = ProjectConfig(
                2,
                ("devops",),
                ("cursor",),
                (
                    WorkspaceIntent("apps/web", ("frontend",)),
                    WorkspaceIntent("apps/api", ("symfony",)),
                ),
            )
            self._install(project, current)
            yaml_before = (project / PROJECT_CONFIG_RELATIVE).read_bytes()
            # Reordered workspaces / components — same semantic hash.
            desired = ProjectConfig(
                2,
                ("devops",),
                ("cursor",),
                (
                    WorkspaceIntent("apps/api", ("symfony",)),
                    WorkspaceIntent("apps/web", ("frontend",)),
                ),
            )
            with mock.patch.object(
                AssemblyService, "assemble_scoped_project"
            ) as assemble_scoped, mock.patch.object(
                AssemblyService, "assemble_composition"
            ) as assemble_composition:
                result = self._configure(project, desired)
            self.assertEqual(result.exit_code, EXIT_SUCCESS, result.message)
            self.assertTrue(result.noop)
            self.assertEqual(assemble_scoped.call_count, 0)
            self.assertEqual(assemble_composition.call_count, 0)
            self.assertEqual(
                (project / PROJECT_CONFIG_RELATIVE).read_bytes(), yaml_before
            )
            self.assertEqual(self._status(project).state, StatusState.HEALTHY)

    def test_schema2_changed_workspaces(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = _make_monorepo(tmp)
            current = ProjectConfig(
                2,
                (),
                ("cursor",),
                (WorkspaceIntent("apps/api", ("symfony",)),),
            )
            self._install(project, current)
            desired = ProjectConfig(
                2,
                (),
                ("cursor",),
                (
                    WorkspaceIntent("apps/api", ("symfony",)),
                    WorkspaceIntent("apps/web", ("frontend",)),
                ),
            )
            result = self._configure(project, desired)
            self.assertEqual(result.exit_code, EXIT_SUCCESS, result.message)
            status = self._status(project)
            self.assertEqual(status.state, StatusState.HEALTHY)
            self.assertEqual(
                [ws.path for ws in status.workspaces],
                ["apps/api", "apps/web"],
            )

    def test_schema2_empty_root_to_non_empty_root(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = _make_monorepo(tmp)
            self._install(project, _cursor_symfony_empty_root())
            result = self._configure(project, _cursor_symfony_root_devops())
            self.assertEqual(result.exit_code, EXIT_SUCCESS, result.message)
            status = self._status(project)
            self.assertEqual(status.state, StatusState.HEALTHY)
            self.assertEqual(status.requested_components, ["devops"])
            self.assertIn("devops", status.resolved_components)
            self.assertEqual([ws.path for ws in status.workspaces], ["apps/api"])

    def test_schema2_non_empty_root_to_empty_root(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = _make_monorepo(tmp)
            self._install(project, _cursor_symfony_root_devops())
            before_sentinels = {
                rel: (project / rel / "APP_SENTINEL.txt").read_bytes()
                for rel in WORKSPACE_DIRS
            }
            # Capture a GLOBAL-ish cursor root file if present.
            rules_dir = project / ".cursor" / "rules"
            globalish = [
                p
                for p in rules_dir.glob("*.mdc")
                if not p.name.startswith(workspace_filename_prefix("apps/api"))
            ]
            self.assertTrue(globalish, "expected non-workspace GLOBAL cursor outputs")

            result = self._configure(project, _cursor_symfony_empty_root())
            self.assertEqual(result.exit_code, EXIT_SUCCESS, result.message)
            status = self._status(project)
            self.assertEqual(status.state, StatusState.HEALTHY)
            self.assertEqual(status.requested_components, [])
            self.assertEqual(status.resolved_components, [])
            self.assertEqual([ws.path for ws in status.workspaces], ["apps/api"])
            self.assertGreater(
                status.workspaces[0].assistant_output_counts.get("cursor", 0), 0
            )
            # GLOBAL-only outputs from devops root should be gone.
            for path in globalish:
                self.assertFalse(path.exists(), path.name)
            # Workspace-scoped remain.
            scoped = list(
                rules_dir.glob(
                    "{}*.mdc".format(workspace_filename_prefix("apps/api"))
                )
            )
            self.assertTrue(scoped)
            self.assertTrue((project / "apps" / "api").is_dir())
            for rel, payload in before_sentinels.items():
                self.assertEqual(
                    (project / rel / "APP_SENTINEL.txt").read_bytes(), payload
                )

    def test_schema2_to_schema1(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = _make_monorepo(tmp)
            self._install(project, _cursor_symfony_empty_root())
            desired = ProjectConfig(1, ("symfony",), ("cursor",), ())
            result = self._configure(project, desired)
            self.assertEqual(result.exit_code, EXIT_SUCCESS, result.message)
            status = self._status(project)
            self.assertEqual(status.state, StatusState.HEALTHY)
            self.assertEqual(status.requested_components, ["symfony"])
            self.assertEqual(status.workspaces, [])
            yaml_text = (project / PROJECT_CONFIG_RELATIVE).read_text(encoding="utf-8")
            self.assertIn("schema_version: 1", yaml_text)
            self.assertNotIn("workspaces:", yaml_text)


class FourAssistantReferenceLifecycleTests(SafetyHelpers):
    def test_four_assistant_reference_lifecycle(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = _make_monorepo(tmp)
            config = _reference_config()

            # --- install ---
            install = self._install(project, config)
            self.assertEqual(install.exit_code, EXIT_SUCCESS)
            status = self._status(project)
            self.assertEqual(status.state, StatusState.HEALTHY)
            yaml_text = (project / PROJECT_CONFIG_RELATIVE).read_text(encoding="utf-8")
            self.assertIn("schema_version: 2", yaml_text)
            manifest = ManifestStore(project).load()
            self.assertEqual(manifest.schema_version, 1)
            counts = _adapter_counts(project)
            self.assertEqual(counts.get("cursor"), REF_CURSOR)
            self.assertEqual(counts.get("copilot"), REF_COPILOT)
            self.assertEqual(counts.get("claude"), REF_CLAUDE)
            self.assertEqual(counts.get("antigravity"), REF_ANTIGRAVITY)
            created = set(manifest.created_directories)
            for relative in WORKSPACE_DIRS:
                self.assertTrue((project / relative).is_dir())
                self.assertNotIn(relative, created)
            self._assert_workspace_sentinels(project)

            # --- update ---
            yaml_before = (project / PROJECT_CONFIG_RELATIVE).read_bytes()
            with mock.patch(
                "ekp.detection.service.DetectionService.detect"
            ) as detect:
                update = self._update(project)
            self.assertEqual(update.exit_code, EXIT_SUCCESS, update.message)
            self.assertEqual(detect.call_count, 0)
            self.assertEqual(
                (project / PROJECT_CONFIG_RELATIVE).read_bytes(), yaml_before
            )
            status = self._status(project)
            self.assertEqual(status.state, StatusState.HEALTHY)
            manifest = ManifestStore(project).load()
            self.assertEqual(set(manifest.adapters), set(ALL_ASSISTANTS))
            self.assertEqual(set(status.assistants), set(ALL_ASSISTANTS))
            self.assertEqual(
                [ws.path for ws in status.workspaces],
                ["apps/api", "apps/mobile", "apps/web", "packages/shared"],
            )

            # --- configure (packages/shared typescript → frontend) ---
            desired = _reference_configure_desired()
            configure_svc = self._configure_service()
            with mock.patch.object(
                configure_svc.assembly,
                "assemble_scoped_project",
                wraps=configure_svc.assembly.assemble_scoped_project,
            ) as assemble_scoped:
                prepared = configure_svc.prepare_project(
                    ConfigureProjectRequest(
                        path=str(project),
                        desired_config=desired,
                        dry_run=False,
                    )
                )
                self.assertEqual(prepared.exit_code, EXIT_SUCCESS, prepared.message)
                self.assertFalse(prepared.noop)
                self.assertIsNotNone(prepared.prepared)
                self.assertEqual(assemble_scoped.call_count, 1)
                apply_result = configure_svc.apply(prepared.prepared)
                self.assertEqual(
                    apply_result.exit_code, EXIT_SUCCESS, apply_result.message
                )
                self.assertEqual(assemble_scoped.call_count, 1)

            status = self._status(project)
            self.assertEqual(status.state, StatusState.HEALTHY)
            manifest = ManifestStore(project).load()
            self.assertEqual(set(manifest.adapters), set(ALL_ASSISTANTS))
            loaded = ProjectConfigStore(project, registry=self.registry).load()
            self.assertEqual(loaded.schema_version, 2)
            self.assertEqual(list(loaded.components), ["devops"])
            self.assertEqual(set(loaded.assistants), set(ALL_ASSISTANTS))
            shared_intent = next(
                ws for ws in loaded.workspaces if ws.path == "packages/shared"
            )
            self.assertEqual(list(shared_intent.components), ["frontend"])
            shared = next(ws for ws in status.workspaces if ws.path == "packages/shared")
            self.assertEqual(shared.requested_components, ["frontend"])

            # --- uninstall ---
            managed_paths = [
                item.relative_path for item in ManifestStore(project).load().managed_files
            ]
            with mock.patch(
                "ekp.composition.resolve_project_composition"
            ) as resolve_pc, mock.patch(
                "ekp.composition.resolve_composition"
            ) as resolve_c, mock.patch.object(
                AssemblyService, "assemble_scoped_project"
            ) as assemble_scoped, mock.patch.object(
                AssemblyService, "assemble_composition"
            ) as assemble_composition:
                uninstall = self._uninstall(project)
            self.assertEqual(uninstall.exit_code, EXIT_SUCCESS, uninstall.message)
            self.assertEqual(resolve_pc.call_count, 0)
            self.assertEqual(resolve_c.call_count, 0)
            self.assertEqual(assemble_scoped.call_count, 0)
            self.assertEqual(assemble_composition.call_count, 0)
            self.assertFalse((project / ".ekp" / "install.json").exists())
            self.assertTrue((project / PROJECT_CONFIG_RELATIVE).is_file())
            for relative in managed_paths:
                self.assertFalse(
                    (project / Path(*relative.split("/"))).exists(), relative
                )
            self._assert_workspace_sentinels(project)
            self.assertEqual(self._status(project).state, StatusState.NOT_INSTALLED)


class InstallRollbackTests(SafetyHelpers):
    def test_install_rollback_after_project_yaml(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = _make_monorepo(tmp)
            before = _fingerprint(project)
            service = self._install_service()

            def boom(plan):
                self.assertTrue((project / PROJECT_CONFIG_RELATIVE).is_file())
                raise InstallFilesystemError("injected after project.yaml")

            service._after_config_hook = boom
            result = service.install_project_config(
                project, _cursor_symfony_empty_root()
            )
            self.assertNotEqual(result.exit_code, EXIT_SUCCESS)
            self._assert_install_fully_rolled_back(project, before)

    def test_install_rollback_during_managed_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = _make_monorepo(tmp)
            before = _fingerprint(project)
            service = self._install_service()
            writes = {"n": 0}

            import ekp.install.deploy.engine as engine_mod

            real_create = engine_mod.exclusive_create_from_temp

            def boom_create(temp_path, target):
                writes["n"] += 1
                if writes["n"] >= 1:
                    raise InstallFilesystemError(
                        "injected during managed-file write"
                    )
                return real_create(temp_path, target)

            with mock.patch.object(
                engine_mod, "exclusive_create_from_temp", boom_create
            ):
                result = service.install_project_config(
                    project, _cursor_symfony_empty_root()
                )
            self.assertNotEqual(result.exit_code, EXIT_SUCCESS)
            self.assertGreaterEqual(writes["n"], 1)
            self._assert_install_fully_rolled_back(project, before)

    def test_install_rollback_after_managed_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = _make_monorepo(tmp)
            before = _fingerprint(project)
            service = self._install_service()

            def boom(plan, applied):
                self.assertTrue((project / PROJECT_CONFIG_RELATIVE).is_file())
                self.assertTrue(applied.managed_files)
                raise InstallFilesystemError("injected after managed files")

            service._after_managed_files_hook = boom
            result = service.install_project_config(
                project, _cursor_symfony_empty_root()
            )
            self.assertNotEqual(result.exit_code, EXIT_SUCCESS)
            self._assert_install_fully_rolled_back(project, before)

    def test_install_rollback_manifest_create_failure(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = _make_monorepo(tmp)
            before = _fingerprint(project)
            service = self._install_service()

            def boom_create(self_, manifest):
                raise InstallConflictError("injected manifest create failure")

            with mock.patch.object(ManifestStore, "create", boom_create):
                result = service.install_project_config(
                    project, _cursor_symfony_empty_root()
                )
            self.assertNotEqual(result.exit_code, EXIT_SUCCESS)
            self._assert_install_fully_rolled_back(project, before)


class ConfigureRollbackTests(SafetyHelpers):
    def _healthy_schema2(self, tmp: str) -> Path:
        project = _make_monorepo(tmp)
        self._install(project, _cursor_symfony_root_devops())
        return project

    def _desired_change(self) -> ProjectConfig:
        return ProjectConfig(
            2,
            ("devops",),
            ("cursor",),
            (
                WorkspaceIntent("apps/api", ("symfony",)),
                WorkspaceIntent("apps/web", ("frontend",)),
            ),
        )

    def test_configure_rollback_after_project_yaml(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = self._healthy_schema2(tmp)
            before = _fingerprint(project)
            prepared = self._prepare(project, self._desired_change())
            self.assertEqual(prepared.exit_code, EXIT_SUCCESS, prepared.message)

            # Fail on the first managed-file op immediately after yaml CAS replace.
            def fail_create(self_, plan, operation, created):
                raise InstallConflictError(
                    "injected immediately after project.yaml replace"
                )

            def fail_write(self_, plan, operation, backup_root, written):
                raise InstallConflictError(
                    "injected immediately after project.yaml replace"
                )

            def fail_delete(self_, project_root, operation, backup_root, deleted):
                raise InstallConflictError(
                    "injected immediately after project.yaml replace"
                )

            with mock.patch.object(
                TransactionApplier, "_apply_create", fail_create
            ), mock.patch.object(
                TransactionApplier, "_apply_write", fail_write
            ), mock.patch.object(TransactionApplier, "_apply_delete", fail_delete):
                result = self._configure_service().apply(prepared.prepared)
            self.assertNotEqual(result.exit_code, EXIT_SUCCESS, result.message)
            self.assertEqual(_fingerprint(project), before)
            self.assertEqual(self._status(project).state, StatusState.HEALTHY)
            self._assert_workspace_sentinels(project)

    def test_configure_rollback_during_managed_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = self._healthy_schema2(tmp)
            before = _fingerprint(project)
            prepared = self._prepare(project, self._desired_change())
            self.assertEqual(prepared.exit_code, EXIT_SUCCESS, prepared.message)

            seen = {"n": 0}
            real_create = TransactionApplier._apply_create

            def fail_after_one(self_, plan, operation, created):
                seen["n"] += 1
                if seen["n"] == 1:
                    return real_create(self_, plan, operation, created)
                raise InstallConflictError("injected managed create failure")

            creates = [
                op
                for op in prepared.prepared.plan.operations
                if op.kind == LifecycleOpKind.CREATE
            ]
            self.assertGreaterEqual(len(creates), 2)
            with mock.patch.object(TransactionApplier, "_apply_create", fail_after_one):
                result = self._configure_service().apply(prepared.prepared)
            self.assertNotEqual(result.exit_code, EXIT_SUCCESS, result.message)
            self.assertGreaterEqual(seen["n"], 2)
            self.assertEqual(_fingerprint(project), before)
            self.assertEqual(self._status(project).state, StatusState.HEALTHY)
            self._assert_workspace_sentinels(project)

    def test_configure_rollback_after_managed_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = self._healthy_schema2(tmp)
            before = _fingerprint(project)
            prepared = self._prepare(project, self._desired_change())
            self.assertEqual(prepared.exit_code, EXIT_SUCCESS, prepared.message)

            def boom(self_, plan, store):
                raise InstallConflictError("injected after managed files")

            with mock.patch.object(
                TransactionApplier, "_verify_new_configure_config", boom
            ):
                result = self._configure_service().apply(prepared.prepared)
            self.assertNotEqual(result.exit_code, EXIT_SUCCESS, result.message)
            self.assertEqual(_fingerprint(project), before)
            self.assertEqual(self._status(project).state, StatusState.HEALTHY)
            self._assert_workspace_sentinels(project)

    def test_configure_rollback_manifest_replace_failure(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = self._healthy_schema2(tmp)
            before = _fingerprint(project)
            prepared = self._prepare(project, self._desired_change())
            self.assertEqual(prepared.exit_code, EXIT_SUCCESS, prepared.message)

            def boom_replace(self_, manifest, expected_sha256):
                raise InstallConflictError("injected manifest replace failure")

            with mock.patch.object(ManifestStore, "replace", boom_replace):
                result = self._configure_service().apply(prepared.prepared)
            self.assertNotEqual(result.exit_code, EXIT_SUCCESS, result.message)
            self.assertEqual(_fingerprint(project), before)
            self.assertEqual(self._status(project).state, StatusState.HEALTHY)
            self._assert_workspace_sentinels(project)


class ConfigureToctouTests(SafetyHelpers):
    def _base(self, tmp: str) -> Path:
        project = _make_monorepo(tmp)
        self._install(project, _cursor_symfony_empty_root())
        return project

    def _desired(self) -> ProjectConfig:
        return ProjectConfig(
            2,
            ("devops",),
            ("cursor",),
            (WorkspaceIntent("apps/api", ("symfony",)),),
        )

    def test_toctou_project_yaml_physical_cas(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = self._base(tmp)
            prepared = self._prepare(project, self._desired())
            self.assertEqual(prepared.exit_code, EXIT_SUCCESS, prepared.message)
            path = project / PROJECT_CONFIG_RELATIVE
            # Semantically equivalent whitespace drift → physical bytes differ.
            path.write_bytes(path.read_bytes() + b"\n")
            before = _fingerprint(project)
            result = self._configure_service().apply(prepared.prepared)
            self.assertNotEqual(result.exit_code, EXIT_SUCCESS)
            self.assertEqual(_fingerprint(project), before)

    def test_toctou_managed_file_modified(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = self._base(tmp)
            prepared = self._prepare(project, self._desired())
            self.assertEqual(prepared.exit_code, EXIT_SUCCESS, prepared.message)
            managed = _scoped_managed(project, "cursor")
            target = project.joinpath(*managed.relative_path.split("/"))
            edited = target.read_text(encoding="utf-8") + "\n# user edit\n"
            target.write_text(edited, encoding="utf-8")
            result = self._configure_service().apply(prepared.prepared)
            self.assertNotEqual(result.exit_code, EXIT_SUCCESS)
            self.assertEqual(target.read_text(encoding="utf-8"), edited)

    def test_toctou_new_unmanaged_collision(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = self._base(tmp)
            prepared = self._prepare(project, self._desired())
            self.assertEqual(prepared.exit_code, EXIT_SUCCESS, prepared.message)
            creates = [
                op
                for op in prepared.prepared.plan.operations
                if op.kind == LifecycleOpKind.CREATE
            ]
            self.assertTrue(creates)
            target = project.joinpath(*creates[0].relative_path.split("/"))
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text("foreign collision\n", encoding="utf-8")
            yaml_before = (project / PROJECT_CONFIG_RELATIVE).read_bytes()
            result = self._configure_service().apply(prepared.prepared)
            self.assertNotEqual(result.exit_code, EXIT_SUCCESS)
            self.assertEqual(
                (project / PROJECT_CONFIG_RELATIVE).read_bytes(), yaml_before
            )
            self.assertEqual(target.read_text(encoding="utf-8"), "foreign collision\n")

    def test_toctou_manifest_mutation(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = self._base(tmp)
            prepared = self._prepare(project, self._desired())
            self.assertEqual(prepared.exit_code, EXIT_SUCCESS, prepared.message)
            store = ManifestStore(project)
            snap = store.load_with_fingerprint()
            mutated = InstallManifest(
                schema_version=snap.manifest.schema_version,
                ekp_version=snap.manifest.ekp_version,
                profile=snap.manifest.profile,
                adapters=list(snap.manifest.adapters),
                installed_at="1999-01-01T00:00:00Z",
                install_root=snap.manifest.install_root,
                managed_files=list(snap.manifest.managed_files),
                created_directories=list(snap.manifest.created_directories),
                mode=snap.manifest.mode,
                configuration_sha256=snap.manifest.configuration_sha256,
            )
            store.replace(mutated, expected_sha256=snap.sha256)
            yaml_before = (project / PROJECT_CONFIG_RELATIVE).read_bytes()
            files_before = _fingerprint(project)
            result = self._configure_service().apply(prepared.prepared)
            self.assertNotEqual(result.exit_code, EXIT_SUCCESS)
            self.assertEqual(
                (project / PROJECT_CONFIG_RELATIVE).read_bytes(), yaml_before
            )
            # Transition must not apply; allow only install.json fingerprint change
            # from our intentional mutation.
            after = _fingerprint(project)
            self.assertEqual(
                {k: v for k, v in after.items() if k != ".ekp/install.json"},
                {k: v for k, v in files_before.items() if k != ".ekp/install.json"},
            )

    def test_toctou_workspace_directory_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = self._base(tmp)
            prepared = self._prepare(project, self._desired())
            self.assertEqual(prepared.exit_code, EXIT_SUCCESS, prepared.message)
            shutil.rmtree(project / "apps" / "api")
            before = _fingerprint(project)
            result = self._configure_service().apply(prepared.prepared)
            self.assertNotEqual(result.exit_code, EXIT_SUCCESS, result.message)
            self.assertEqual(_fingerprint(project), before)
            self.assertFalse((project / "apps" / "api").exists())


class DriftIncompletePrecedenceTests(SafetyHelpers):
    def test_scoped_drift_all_four_assistants(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = _make_monorepo(tmp)
            self._install(project, _reference_config())
            for adapter in ALL_ASSISTANTS:
                managed = _scoped_managed(project, adapter)
                target = project.joinpath(*managed.relative_path.split("/"))
                original = target.read_bytes()
                target.write_bytes(original + b"\n# drift\n")
                status = self._status(project)
                self.assertEqual(status.state, StatusState.MODIFIED, adapter)
                before = _fingerprint(project)
                configure = self._configure(project, _reference_configure_desired())
                self.assertEqual(configure.exit_code, EXIT_SELECTION, adapter)
                self.assertEqual(_fingerprint(project), before)
                self.assertEqual(target.read_bytes(), original + b"\n# drift\n")
                target.write_bytes(original)
                self.assertEqual(self._status(project).state, StatusState.HEALTHY)

    def test_incomplete_scoped_file_diagnostics(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = _make_monorepo(tmp)
            self._install(project, _cursor_symfony_empty_root())
            managed = _scoped_managed(project, "cursor")
            target = project.joinpath(*managed.relative_path.split("/"))
            target.unlink()
            status = self._status(project)
            self.assertEqual(status.state, StatusState.INCOMPLETE)
            self.assertIn(managed.relative_path, status.missing_paths)
            self.assertTrue(status.workspaces)
            ws = next(w for w in status.workspaces if w.path == "apps/api")
            self.assertTrue(
                any("missing managed file" in issue for issue in ws.issues)
            )
            # Restore
            # cannot easily restore without reinstall; leave incomplete for assertion done

    def test_status_invalid_wins(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = _make_monorepo(tmp)
            self._install(project, _cursor_symfony_empty_root())
            store = ManifestStore(project)
            snap = store.load_with_fingerprint()
            # Hash matches config but adapters disagree → INVALID.
            mutated = InstallManifest(
                schema_version=snap.manifest.schema_version,
                ekp_version=snap.manifest.ekp_version,
                profile=snap.manifest.profile,
                adapters=["cursor", "copilot"],
                installed_at=snap.manifest.installed_at,
                install_root=snap.manifest.install_root,
                managed_files=list(snap.manifest.managed_files),
                created_directories=list(snap.manifest.created_directories),
                mode=snap.manifest.mode,
                configuration_sha256=snap.manifest.configuration_sha256,
            )
            store.replace(mutated, expected_sha256=snap.sha256)
            # Also modify a file — INVALID must still win.
            managed = _scoped_managed(project, "cursor")
            target = project.joinpath(*managed.relative_path.split("/"))
            target.write_bytes(target.read_bytes() + b"\n#x\n")
            status = self._status(project)
            self.assertEqual(status.state, StatusState.INVALID)

    def test_status_drift_beats_modified(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = _make_monorepo(tmp)
            self._install(project, _cursor_symfony_empty_root())
            managed = _scoped_managed(project, "cursor")
            target = project.joinpath(*managed.relative_path.split("/"))
            target.write_bytes(target.read_bytes() + b"\n#m\n")
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
            self.assertIn(managed.relative_path, status.modified_paths)

    def test_status_version_mismatch_beats_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = _make_monorepo(tmp)
            self._install(project, _cursor_symfony_empty_root())
            managed = _scoped_managed(project, "cursor")
            project.joinpath(*managed.relative_path.split("/")).unlink()
            store = ManifestStore(project)
            snap = store.load_with_fingerprint()
            mutated = InstallManifest(
                schema_version=snap.manifest.schema_version,
                ekp_version="0.0.0-test",
                profile=snap.manifest.profile,
                adapters=list(snap.manifest.adapters),
                installed_at=snap.manifest.installed_at,
                install_root=snap.manifest.install_root,
                managed_files=list(snap.manifest.managed_files),
                created_directories=list(snap.manifest.created_directories),
                mode=snap.manifest.mode,
                configuration_sha256=snap.manifest.configuration_sha256,
            )
            store.replace(mutated, expected_sha256=snap.sha256)
            status = self._status(project)
            self.assertEqual(status.state, StatusState.VERSION_MISMATCH)
            self.assertIn(managed.relative_path, status.missing_paths)

    def test_status_incomplete_beats_modified(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = _make_monorepo(tmp)
            self._install(project, _cursor_symfony_empty_root())
            files = [
                item
                for item in ManifestStore(project).load().managed_files
                if item.adapter == "cursor"
            ]
            self.assertGreaterEqual(len(files), 2)
            missing = project.joinpath(*files[0].relative_path.split("/"))
            modified = project.joinpath(*files[1].relative_path.split("/"))
            missing.unlink()
            modified.write_bytes(modified.read_bytes() + b"\n#m\n")
            status = self._status(project)
            self.assertEqual(status.state, StatusState.INCOMPLETE)

    def test_status_modified_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = _make_monorepo(tmp)
            self._install(project, _cursor_symfony_empty_root())
            managed = _scoped_managed(project, "cursor")
            target = project.joinpath(*managed.relative_path.split("/"))
            target.write_bytes(target.read_bytes() + b"\n#m\n")
            self.assertEqual(self._status(project).state, StatusState.MODIFIED)

    def test_status_healthy(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = _make_monorepo(tmp)
            self._install(project, _cursor_symfony_empty_root())
            self.assertEqual(self._status(project).state, StatusState.HEALTHY)

    def test_empty_root_status_no_flat_resolve(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = _make_monorepo(tmp)
            self._install(project, _cursor_symfony_empty_root())
            with mock.patch(
                "ekp.status.service.resolve_composition", wraps=resolve_composition
            ) as flat_resolve:
                status = self._status(project)
            self.assertEqual(status.state, StatusState.HEALTHY)
            self.assertEqual(status.requested_components, [])
            self.assertEqual(status.resolved_components, [])
            self.assertEqual(flat_resolve.call_count, 0)
            self.assertEqual([ws.path for ws in status.workspaces], ["apps/api"])
            self.assertTrue(status.workspaces[0].resolved_components)
            self.assertGreater(
                status.workspaces[0].assistant_output_counts.get("cursor", 0), 0
            )


class DryRunAndUpdateProofTests(SafetyHelpers):
    def test_schema2_install_dry_run(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = _make_monorepo(tmp)
            before = _fingerprint(project)
            result = self._install(project, _reference_config(), dry_run=True)
            self.assertEqual(result.exit_code, EXIT_SUCCESS, result.message)
            self.assertIsNotNone(result.plan)
            self.assertEqual(_fingerprint(project), before)
            self.assertFalse((project / PROJECT_CONFIG_RELATIVE).exists())
            self.assertFalse((project / ".ekp" / "install.json").exists())
            self.assertFalse((project / ".cursor").exists())
            self.assertFalse((project / ".github").exists())
            self.assertFalse((project / ".claude").exists())
            self.assertFalse((project / ".agents").exists())
            self._assert_workspace_sentinels(project)

    def test_schema2_configure_dry_run(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = _make_monorepo(tmp)
            self._install(project, _cursor_symfony_empty_root())
            before = _fingerprint(project)
            yaml_before = (project / PROJECT_CONFIG_RELATIVE).read_bytes()
            manifest_before = (project / ".ekp" / "install.json").read_bytes()
            result = self._configure(
                project, _cursor_symfony_root_devops(), dry_run=True
            )
            self.assertEqual(result.exit_code, EXIT_SUCCESS, result.message)
            self.assertFalse(result.noop)
            self.assertIsNotNone(result.plan)
            self.assertGreater(len(result.plan.operations), 0)
            self.assertEqual(
                (project / PROJECT_CONFIG_RELATIVE).read_bytes(), yaml_before
            )
            self.assertEqual(
                (project / ".ekp" / "install.json").read_bytes(), manifest_before
            )
            self.assertEqual(_fingerprint(project), before)

    def test_schema2_update_dry_run_and_byte_freeze(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = _make_monorepo(tmp)
            self._install(project, _cursor_symfony_empty_root())
            yaml_before = (project / PROJECT_CONFIG_RELATIVE).read_bytes()
            manifest_before = (project / ".ekp" / "install.json").read_bytes()
            files_before = _fingerprint(project)
            with mock.patch(
                "ekp.detection.service.DetectionService.detect"
            ) as detect:
                dry = self._update(project, dry_run=True)
            self.assertEqual(dry.exit_code, EXIT_SUCCESS, dry.message)
            self.assertEqual(detect.call_count, 0)
            self.assertEqual(
                (project / PROJECT_CONFIG_RELATIVE).read_bytes(), yaml_before
            )
            self.assertEqual(
                (project / ".ekp" / "install.json").read_bytes(), manifest_before
            )
            self.assertEqual(_fingerprint(project), files_before)

            with mock.patch(
                "ekp.detection.service.DetectionService.detect"
            ) as detect2:
                live = self._update(project)
            self.assertEqual(live.exit_code, EXIT_SUCCESS, live.message)
            self.assertEqual(detect2.call_count, 0)
            self.assertEqual(
                (project / PROJECT_CONFIG_RELATIVE).read_bytes(), yaml_before
            )
            self.assertEqual(self._status(project).state, StatusState.HEALTHY)

    def test_uninstall_no_resolve_adapters(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = _make_monorepo(tmp)
            self._install(project, _cursor_symfony_empty_root())
            with mock.patch(
                "ekp.composition.resolve_project_composition"
            ) as resolve_pc, mock.patch(
                "ekp.composition.resolve_composition"
            ) as resolve_c, mock.patch.object(
                AssemblyService, "assemble_scoped_project"
            ) as assemble_scoped, mock.patch(
                "ekp.assembly.AssemblyService.assemble_composition"
            ) as assemble_composition:
                result = self._uninstall(project)
            self.assertEqual(result.exit_code, EXIT_SUCCESS, result.message)
            self.assertEqual(resolve_pc.call_count, 0)
            self.assertEqual(resolve_c.call_count, 0)
            self.assertEqual(assemble_scoped.call_count, 0)
            self.assertEqual(assemble_composition.call_count, 0)


class DirectoryRollbackClosureTests(SafetyHelpers):
    """AZ-D-ROLLBACK-CLOSURE — complete cleanup of transaction-created dirs."""

    def test_clean_project_four_assistant_manifest_failure(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = _make_monorepo(tmp)
            before = _fingerprint(project)
            for relative in (".cursor", ".github", ".claude", ".agents", ".ekp"):
                self.assertFalse((project / relative).exists())
            service = self._install_service()

            def boom_create(self_, manifest):
                raise InstallConflictError("injected manifest create failure")

            with mock.patch.object(ManifestStore, "create", boom_create):
                result = service.install_project_config(project, _reference_config())
            self.assertNotEqual(result.exit_code, EXIT_SUCCESS, result.message)
            for relative in (".cursor", ".github", ".claude", ".agents", ".ekp"):
                self.assertFalse(
                    (project / relative).exists(),
                    msg="leftover root: {}".format(relative),
                )
            self.assertFalse((project / ".ekp" / "install.json").exists())
            self.assertFalse((project / PROJECT_CONFIG_RELATIVE).exists())
            self.assertEqual(_fingerprint(project), before)
            self._assert_workspace_sentinels(project)

    def test_preexisting_assistant_roots_preserved(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = _make_monorepo(tmp)
            sentinels = {}
            for relative in (".cursor", ".github", ".claude", ".agents"):
                root = project / relative
                root.mkdir(parents=True)
                marker = root / "USER_ROOT_SENTINEL.txt"
                payload = "keep-root:{}\n".format(relative)
                marker.write_bytes(payload.encode("utf-8"))
                sentinels[relative] = payload
            before = _fingerprint(project)
            service = self._install_service()

            def boom(plan, applied):
                raise InstallFilesystemError("injected after managed files")

            service._after_managed_files_hook = boom
            result = service.install_project_config(
                project, _cursor_symfony_empty_root()
            )
            self.assertNotEqual(result.exit_code, EXIT_SUCCESS)
            for relative, payload in sentinels.items():
                root = project / relative
                self.assertTrue(root.is_dir())
                self.assertEqual(
                    (root / "USER_ROOT_SENTINEL.txt").read_bytes(),
                    payload.encode("utf-8"),
                )
            # EKP-only children removed.
            self.assertFalse((project / ".cursor" / "rules").exists())
            self.assertFalse((project / PROJECT_CONFIG_RELATIVE).exists())
            self.assertFalse((project / ".ekp" / "install.json").exists())
            self.assertFalse((project / ".ekp").exists())
            self._assert_workspace_sentinels(project)
            self.assertEqual(_fingerprint(project), before)

    def test_ekp_preexisting_retained(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = _make_monorepo(tmp)
            ekp = project / ".ekp"
            ekp.mkdir()
            foreign = ekp / "foreign-notes.txt"
            foreign.write_text("do-not-delete\n", encoding="utf-8")
            before = _fingerprint(project)
            service = self._install_service()

            def boom(plan, applied):
                raise InstallFilesystemError("injected after managed files")

            service._after_managed_files_hook = boom
            result = service.install_project_config(
                project, _cursor_symfony_empty_root()
            )
            self.assertNotEqual(result.exit_code, EXIT_SUCCESS)
            self.assertTrue(ekp.is_dir())
            self.assertEqual(
                foreign.read_text(encoding="utf-8"), "do-not-delete\n"
            )
            self.assertFalse((project / PROJECT_CONFIG_RELATIVE).exists())
            self.assertFalse((project / ".ekp" / "install.json").exists())
            self.assertFalse((project / ".cursor").exists())
            self.assertEqual(_fingerprint(project), before)

    def test_partial_deployment_failure_cleans_roots(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = _make_monorepo(tmp)
            before = _fingerprint(project)
            service = self._install_service()
            import ekp.install.deploy.engine as engine_mod

            real_create = engine_mod.exclusive_create_from_temp
            writes = {"n": 0}

            def boom_create(temp_path, target):
                writes["n"] += 1
                if writes["n"] >= 2:
                    raise InstallFilesystemError(
                        "injected mid managed-file deployment"
                    )
                return real_create(temp_path, target)

            with mock.patch.object(
                engine_mod, "exclusive_create_from_temp", boom_create
            ):
                result = service.install_project_config(project, _reference_config())
            self.assertNotEqual(result.exit_code, EXIT_SUCCESS)
            self.assertGreaterEqual(writes["n"], 2)
            self._assert_install_fully_rolled_back(project, before)

    def test_schema1_cursor_rollback_cleans_cursor_root(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            project.mkdir()
            before = _fingerprint(project)
            service = self._install_service()

            def boom(plan, applied):
                raise InstallFilesystemError("injected after schema1 managed files")

            service._after_managed_files_hook = boom
            result = service.install_project_config(
                project, ProjectConfig(1, ("frontend",), ("cursor",), ())
            )
            self.assertNotEqual(result.exit_code, EXIT_SUCCESS)
            self.assertFalse((project / ".cursor").exists())
            self.assertFalse((project / ".ekp").exists())
            self.assertFalse((project / ".ekp" / "install.json").exists())
            self.assertEqual(_fingerprint(project), before)

    def test_successful_manifest_created_directories_leaf_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = _make_monorepo(tmp)
            result = self._install(project, _cursor_symfony_empty_root())
            self.assertEqual(result.exit_code, EXIT_SUCCESS)
            manifest = ManifestStore(project).load()
            created = set(manifest.created_directories)
            # Planned leaf dirs may appear; bare parents alone are not required.
            self.assertNotIn("apps/api", created)
            for relative in WORKSPACE_DIRS:
                self.assertNotIn(relative, created)
            # Successful install retains assistant roots (not a rollback case).
            self.assertTrue((project / ".cursor").is_dir())
            self.assertIn(".ekp", created)
            # Leaf ownership for cursor rules is expected when newly created.
            self.assertTrue(
                any(
                    item == ".cursor/rules" or item.startswith(".cursor/")
                    for item in created
                )
            )


if __name__ == "__main__":
    unittest.main()
