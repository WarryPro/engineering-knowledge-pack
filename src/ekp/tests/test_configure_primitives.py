"""Low-level configure transition primitives (AY-A) — no ConfigureService."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest import mock

from ekp.composition import ComponentRegistry
from ekp.config.models import ProjectConfig
from ekp.config.normalization import configuration_sha256
from ekp.config.project import (
    ProjectConfigStore,
    project_config_content_sha256,
    render_project_config_yaml,
)
from ekp.install.cursor_deploy import sha256_file
from ekp.install.errors import InstallConflictError, InstallFilesystemError
from ekp.install.manifest import InstallManifest, ManifestStore
from ekp.lifecycle.apply import (
    LifecycleConflictError,
    LifecycleRollbackError,
    TransactionApplier,
)
from ekp.lifecycle.plan import LifecycleFileOperation, LifecycleOpKind, LifecyclePlan
from ekp.tests.test_update_service import _make_bundle, _save_manifest, _write_file


def _write_project_yaml(project: Path, text: str) -> bytes:
    path = project / ".ekp" / "project.yaml"
    path.parent.mkdir(parents=True, exist_ok=True)
    raw = text.encode("utf-8")
    path.write_bytes(raw)
    return raw


def _configure_plan(
    project: Path,
    *,
    snapshot,
    old_config: ProjectConfig,
    new_config: ProjectConfig,
    registry: ComponentRegistry,
    operations=None,
    directories_to_create=None,
    new_managed=None,
    dry_run: bool = False,
) -> LifecyclePlan:
    old_bytes = (project / ".ekp" / "project.yaml").read_bytes()
    new_bytes = render_project_config_yaml(new_config).encode("utf-8")
    old_semantic = configuration_sha256(old_config, registry)
    new_semantic = configuration_sha256(new_config, registry)
    managed = list(snapshot.manifest.managed_files)
    if new_managed is not None:
        managed = new_managed
    new_manifest = InstallManifest(
        schema_version=1,
        ekp_version="0.20.0.dev0",
        profile=snapshot.manifest.profile,
        adapters=list(snapshot.manifest.adapters),
        installed_at=snapshot.manifest.installed_at,
        install_root=snapshot.manifest.install_root,
        managed_files=managed,
        created_directories=list(snapshot.manifest.created_directories),
        mode=snapshot.manifest.mode,
        configuration_sha256=new_semantic,
    )
    return LifecyclePlan(
        project_root=project,
        profile=snapshot.manifest.profile,
        old_version=snapshot.manifest.ekp_version,
        new_version="0.20.0.dev0",
        adapters=list(snapshot.manifest.adapters),
        mode="composition",
        operations=list(operations or []),
        directories_to_create=list(directories_to_create or []),
        manifest_sha256=snapshot.sha256,
        commit_manifest=True,
        new_manifest=new_manifest,
        dry_run=dry_run,
        transition_kind="configure",
        expected_old_configuration_sha256=old_semantic,
        new_configuration_sha256=new_semantic,
        expected_project_config_content_sha256=project_config_content_sha256(old_bytes),
        new_project_config_bytes=new_bytes,
        new_project_config_content_sha256=project_config_content_sha256(new_bytes),
    )


class ConfigureTransitionApplyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.registry = ComponentRegistry.load()

    def test_dry_run_does_not_mutate(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            project.mkdir()
            old = _write_project_yaml(
                project,
                "schema_version: 1\ncomponents:\n  - core\nassistants:\n  - cursor\n",
            )
            digest = _write_file(project, ".cursor/rules/a.mdc", "old\n")
            snapshot = _save_manifest(project, {".cursor/rules/a.mdc": digest})
            plan = _configure_plan(
                project,
                snapshot=snapshot,
                old_config=ProjectConfig(1, ("core",), ("cursor",)),
                new_config=ProjectConfig(1, ("symfony",), ("cursor",)),
                registry=self.registry,
                dry_run=True,
            )
            with self.assertRaises(InstallFilesystemError):
                TransactionApplier().apply_configure_transition(plan)
            self.assertEqual((project / ".ekp" / "project.yaml").read_bytes(), old)
            self.assertEqual(
                ManifestStore(project).load_with_fingerprint().sha256, snapshot.sha256
            )

    def test_file_op_failure_after_config_replace_rolls_back(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            project = root / "project"
            project.mkdir()
            old_yaml = _write_project_yaml(
                project,
                "schema_version: 1\ncomponents: [core]\nassistants:\n  - cursor\n",
            )
            old_digest = _write_file(project, ".cursor/rules/a.mdc", "old\n")
            bundle = _make_bundle(root, {"a.mdc": "new\n"})
            snapshot = _save_manifest(project, {".cursor/rules/a.mdc": old_digest})
            source = bundle / "cursor" / "a.mdc"
            new_digest = sha256_file(source)
            ops = [
                LifecycleFileOperation(
                    relative_path=".cursor/rules/a.mdc",
                    kind=LifecycleOpKind.WRITE,
                    adapter="cursor",
                    previous_sha256=old_digest,
                    expected_sha256=new_digest,
                    source_path=source,
                )
            ]
            plan = _configure_plan(
                project,
                snapshot=snapshot,
                old_config=ProjectConfig(1, ("core",), ("cursor",)),
                new_config=ProjectConfig(1, ("symfony",), ("cursor",)),
                registry=self.registry,
                operations=ops,
            )
            plan.bundle_path = bundle

            original_write = TransactionApplier._apply_write

            def fail_write(self_, plan_, operation, backup_root, written):
                raise InstallConflictError("injected managed write failure")

            with mock.patch.object(TransactionApplier, "_apply_write", fail_write):
                with self.assertRaises(InstallConflictError):
                    TransactionApplier().apply_configure_transition(plan)

            self.assertEqual(
                (project / ".ekp" / "project.yaml").read_bytes(), old_yaml
            )
            self.assertEqual(
                (project / ".cursor" / "rules" / "a.mdc").read_text(encoding="utf-8"),
                "old\n",
            )
            self.assertEqual(
                ManifestStore(project).load_with_fingerprint().sha256, snapshot.sha256
            )
            self.assertTrue(callable(original_write))

    def test_manifest_race_after_config_and_files_rolls_back(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            project = root / "project"
            project.mkdir()
            old_yaml = _write_project_yaml(
                project,
                "schema_version: 1\ncomponents:\n  - core\nassistants:\n  - cursor\n",
            )
            old_digest = _write_file(project, ".cursor/rules/a.mdc", "old\n")
            bundle = _make_bundle(root, {"a.mdc": "new\n"})
            snapshot = _save_manifest(project, {".cursor/rules/a.mdc": old_digest})
            source = bundle / "cursor" / "a.mdc"
            new_digest = sha256_file(source)
            ops = [
                LifecycleFileOperation(
                    relative_path=".cursor/rules/a.mdc",
                    kind=LifecycleOpKind.WRITE,
                    adapter="cursor",
                    previous_sha256=old_digest,
                    expected_sha256=new_digest,
                    source_path=source,
                )
            ]
            plan = _configure_plan(
                project,
                snapshot=snapshot,
                old_config=ProjectConfig(1, ("core",), ("cursor",)),
                new_config=ProjectConfig(1, ("symfony",), ("cursor",)),
                registry=self.registry,
                operations=ops,
            )
            plan.bundle_path = bundle

            def failing_replace(self_, manifest, expected_sha256):
                raise InstallConflictError("manifest race")

            with mock.patch.object(ManifestStore, "replace", failing_replace):
                with self.assertRaises(InstallConflictError):
                    TransactionApplier().apply_configure_transition(plan)

            self.assertEqual(
                (project / ".ekp" / "project.yaml").read_bytes(), old_yaml
            )
            self.assertEqual(
                (project / ".cursor" / "rules" / "a.mdc").read_text(encoding="utf-8"),
                "old\n",
            )
            self.assertEqual(
                ManifestStore(project).load_with_fingerprint().sha256, snapshot.sha256
            )

    def test_config_mutation_during_file_apply_skips_config_overwrite(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            project = root / "project"
            project.mkdir()
            old_yaml = _write_project_yaml(
                project,
                "schema_version: 1\ncomponents:\n  - core\nassistants:\n  - cursor\n",
            )
            old_digest = _write_file(project, ".cursor/rules/a.mdc", "old\n")
            bundle = _make_bundle(root, {"a.mdc": "new\n"})
            snapshot = _save_manifest(project, {".cursor/rules/a.mdc": old_digest})
            source = bundle / "cursor" / "a.mdc"
            new_digest = sha256_file(source)
            ops = [
                LifecycleFileOperation(
                    relative_path=".cursor/rules/a.mdc",
                    kind=LifecycleOpKind.WRITE,
                    adapter="cursor",
                    previous_sha256=old_digest,
                    expected_sha256=new_digest,
                    source_path=source,
                )
            ]
            plan = _configure_plan(
                project,
                snapshot=snapshot,
                old_config=ProjectConfig(1, ("core",), ("cursor",)),
                new_config=ProjectConfig(1, ("symfony",), ("cursor",)),
                registry=self.registry,
                operations=ops,
            )
            plan.bundle_path = bundle

            original_write = TransactionApplier._apply_write
            external = (
                b"# mutated\nschema_version: 1\ncomponents:\n  - frontend\n"
                b"assistants:\n  - cursor\n"
            )

            def write_then_mutate(self_, plan_, operation, backup_root, written):
                original_write(self_, plan_, operation, backup_root, written)
                (project / ".ekp" / "project.yaml").write_bytes(external)

            with mock.patch.object(TransactionApplier, "_apply_write", write_then_mutate):
                with self.assertRaises((LifecycleConflictError, LifecycleRollbackError)):
                    TransactionApplier().apply_configure_transition(plan)

            # External mutation preserved; managed file restored; no manifest commit.
            self.assertEqual(
                (project / ".ekp" / "project.yaml").read_bytes(), external
            )
            self.assertEqual(
                (project / ".cursor" / "rules" / "a.mdc").read_text(encoding="utf-8"),
                "old\n",
            )
            self.assertEqual(
                ManifestStore(project).load_with_fingerprint().sha256, snapshot.sha256
            )
            self.assertNotEqual(old_yaml, external)

    def test_manifest_replace_never_before_config_and_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            project = root / "project"
            project.mkdir()
            _write_project_yaml(
                project,
                "schema_version: 1\ncomponents:\n  - core\nassistants:\n  - cursor\n",
            )
            old_digest = _write_file(project, ".cursor/rules/a.mdc", "old\n")
            bundle = _make_bundle(root, {"a.mdc": "new\n"})
            snapshot = _save_manifest(project, {".cursor/rules/a.mdc": old_digest})
            source = bundle / "cursor" / "a.mdc"
            new_digest = sha256_file(source)
            ops = [
                LifecycleFileOperation(
                    relative_path=".cursor/rules/a.mdc",
                    kind=LifecycleOpKind.WRITE,
                    adapter="cursor",
                    previous_sha256=old_digest,
                    expected_sha256=new_digest,
                    source_path=source,
                )
            ]
            plan = _configure_plan(
                project,
                snapshot=snapshot,
                old_config=ProjectConfig(1, ("core",), ("cursor",)),
                new_config=ProjectConfig(1, ("symfony",), ("cursor",)),
                registry=self.registry,
                operations=ops,
            )
            plan.bundle_path = bundle

            order = []
            original_replace_cfg = ProjectConfigStore.replace
            original_write = TransactionApplier._apply_write
            original_manifest = ManifestStore.replace

            def track_cfg(self_, *args, **kwargs):
                order.append("config")
                return original_replace_cfg(self_, *args, **kwargs)

            def track_write(self_, *args, **kwargs):
                order.append("files")
                return original_write(self_, *args, **kwargs)

            def track_manifest(self_, *args, **kwargs):
                order.append("manifest")
                return original_manifest(self_, *args, **kwargs)

            with mock.patch.object(ProjectConfigStore, "replace", track_cfg):
                with mock.patch.object(TransactionApplier, "_apply_write", track_write):
                    with mock.patch.object(ManifestStore, "replace", track_manifest):
                        TransactionApplier().apply_configure_transition(plan)

            self.assertEqual(order, ["config", "files", "manifest"])
            self.assertEqual(
                (project / ".cursor" / "rules" / "a.mdc").read_text(encoding="utf-8"),
                "new\n",
            )

    def test_created_directory_rollback(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            project = root / "project"
            project.mkdir()
            old_yaml = _write_project_yaml(
                project,
                "schema_version: 1\ncomponents:\n  - core\nassistants:\n  - cursor\n",
            )
            snapshot = _save_manifest(project, {})
            bundle = _make_bundle(root, {"a.mdc": "new\n"})
            source = bundle / "cursor" / "a.mdc"
            digest = sha256_file(source)
            ops = [
                LifecycleFileOperation(
                    relative_path=".cursor/rules/a.mdc",
                    kind=LifecycleOpKind.CREATE,
                    adapter="cursor",
                    expected_sha256=digest,
                    source_path=source,
                )
            ]
            plan = _configure_plan(
                project,
                snapshot=snapshot,
                old_config=ProjectConfig(1, ("core",), ("cursor",)),
                new_config=ProjectConfig(1, ("symfony",), ("cursor",)),
                registry=self.registry,
                operations=ops,
                directories_to_create=[".cursor", ".cursor/rules"],
            )
            plan.bundle_path = bundle

            def failing_replace(self_, manifest, expected_sha256):
                raise InstallConflictError("manifest race")

            with mock.patch.object(ManifestStore, "replace", failing_replace):
                with self.assertRaises(InstallConflictError):
                    TransactionApplier().apply_configure_transition(plan)

            self.assertEqual(
                (project / ".ekp" / "project.yaml").read_bytes(), old_yaml
            )
            self.assertFalse((project / ".cursor").exists())
            self.assertEqual(
                ManifestStore(project).load_with_fingerprint().sha256, snapshot.sha256
            )

    def test_apply_update_rejects_configure_transition_kind(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            project.mkdir()
            _write_project_yaml(
                project,
                "schema_version: 1\ncomponents:\n  - core\nassistants:\n  - cursor\n",
            )
            digest = _write_file(project, ".cursor/rules/a.mdc", "old\n")
            snapshot = _save_manifest(project, {".cursor/rules/a.mdc": digest})
            plan = _configure_plan(
                project,
                snapshot=snapshot,
                old_config=ProjectConfig(1, ("core",), ("cursor",)),
                new_config=ProjectConfig(1, ("symfony",), ("cursor",)),
                registry=self.registry,
            )
            with self.assertRaises(InstallFilesystemError):
                TransactionApplier().apply_update(plan)

    def test_mode_remains_install_semantic(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            project.mkdir()
            _write_project_yaml(
                project,
                "schema_version: 1\ncomponents:\n  - core\nassistants:\n  - cursor\n",
            )
            snapshot = _save_manifest(project, {})
            plan = _configure_plan(
                project,
                snapshot=snapshot,
                old_config=ProjectConfig(1, ("core",), ("cursor",)),
                new_config=ProjectConfig(1, ("symfony",), ("cursor",)),
                registry=self.registry,
            )
            self.assertEqual(plan.mode, "composition")
            self.assertEqual(plan.transition_kind, "configure")
            self.assertIsNone(plan.expected_configuration_sha256)


class PublicConfigureAbsenceTests(unittest.TestCase):
    def test_no_configure_cli_subcommand(self):
        import inspect

        from ekp import cli

        source = inspect.getsource(cli)
        self.assertNotIn('add_parser("configure"', source)
        self.assertNotRegex(source, r'add_parser\(\s*"configure"')

    def test_no_configure_service_module(self):
        import importlib.util

        spec = importlib.util.find_spec("ekp.install.configure")
        self.assertIsNone(spec)


if __name__ == "__main__":
    unittest.main()
