"""Lifecycle filesystem safety hardening tests."""

from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from ekp.assembly import AssemblyRequest, AssemblyService
from ekp.install.cursor_deploy import CursorDeployService, sha256_file
from ekp.install.errors import InstallConflictError
from ekp.install.manifest import InstallManifest, ManagedFile, ManifestStore
from ekp.lifecycle.apply import LifecycleRollbackError, TransactionApplier
from ekp.lifecycle.plan import LifecycleOpKind
from ekp.lifecycle.uninstall import UninstallService, UninstallRequest, validate_lifecycle_manifest
from ekp.lifecycle.update import UpdateRequest, UpdateService, build_update_plan
from ekp.paths import get_ekp_root
from ekp.tests.fixtures import symfony_fixture
from ekp.tests.test_update_service import (
    _inventory_map,
    _make_bundle,
    _save_manifest,
    _write_file,
)
from ekp.version import get_version


class LegacyTempSymlinkTests(unittest.TestCase):
    @unittest.skipUnless(os.name != "nt", "Symlink test skipped on Windows")
    def test_manifest_save_ignores_legacy_tmp_symlink(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            project = root / "project"
            project.mkdir()
            outside = root / "outside.txt"
            outside.write_text("sentinel\n", encoding="utf-8")
            legacy = project / ".ekp" / "install.json.tmp"
            legacy.parent.mkdir(parents=True)
            legacy.symlink_to(outside)

            store = ManifestStore(project)
            manifest = InstallManifest(
                schema_version=1,
                ekp_version="0.15.0",
                profile="cursor-core",
                adapters=["cursor"],
                installed_at="2026-01-01T00:00:00Z",
                install_root=".",
                managed_files=[],
            )
            store.save(manifest)

            self.assertEqual(outside.read_text(encoding="utf-8"), "sentinel\n")
            self.assertTrue(store.exists())

    @unittest.skipUnless(os.name != "nt", "Symlink test skipped on Windows")
    def test_install_write_ignores_legacy_rule_tmp_symlink(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            project = root / "project"
            project.mkdir()
            assembly = AssemblyService().assemble(
                AssemblyRequest(
                    profile="cursor-core",
                    verify=True,
                    resource_root=get_ekp_root(),
                    workspace_dir=root / "workspace",
                    output_root=root / "output",
                )
            )
            outside = root / "outside.mdc"
            outside.write_text("sentinel\n", encoding="utf-8")
            first_rule = next((assembly.bundle_path / "cursor").glob("*.mdc"))
            target = project / ".cursor" / "rules" / first_rule.name
            target.parent.mkdir(parents=True, exist_ok=True)
            legacy = target.with_suffix(target.suffix + ".ekp.tmp")
            legacy.symlink_to(outside)

            deploy = CursorDeployService()
            plan = deploy.build_plan(
                project_root=project,
                bundle_path=assembly.bundle_path,
                profile="cursor-core",
                ekp_version="0.15.0",
            )
            deploy.apply(plan)

            self.assertEqual(outside.read_text(encoding="utf-8"), "sentinel\n")
            self.assertTrue(target.is_file())
            self.assertEqual(sha256_file(target), sha256_file(first_rule))

    @unittest.skipUnless(os.name != "nt", "Symlink test skipped on Windows")
    def test_update_write_ignores_legacy_rule_tmp_symlink(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            project = root / "project"
            project.mkdir()
            old_digest = _write_file(project, ".cursor/rules/a.mdc", "old\n")
            bundle = _make_bundle(root, {"a.mdc": "new\n"})
            snapshot = _save_manifest(project, {".cursor/rules/a.mdc": old_digest})
            outside = root / "outside.mdc"
            outside.write_text("sentinel\n", encoding="utf-8")
            legacy = project / ".cursor" / "rules" / "a.mdc.ekp.tmp"
            legacy.symlink_to(outside)

            plan = build_update_plan(
                project_root=project,
                snapshot=snapshot,
                running_version="0.16.0.dev0",
                inventory=_inventory_map(bundle),
                bundle_path=bundle,
            )
            TransactionApplier().apply_update(plan)

            target = project / ".cursor" / "rules" / "a.mdc"
            self.assertEqual(outside.read_text(encoding="utf-8"), "sentinel\n")
            self.assertEqual(target.read_text(encoding="utf-8"), "new\n")


class DirectoryRollbackTests(unittest.TestCase):
    def test_empty_directory_rollback_on_failure(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            project.mkdir()
            bundle = _make_bundle(Path(tmp), {"a.mdc": "new\n"})
            digest = sha256_file(bundle / "cursor" / "a.mdc")
            snapshot = _save_manifest(project, {".cursor/rules/a.mdc": digest})
            fp_before = snapshot.sha256
            plan = build_update_plan(
                project_root=project,
                snapshot=snapshot,
                running_version="0.16.0.dev0",
                inventory=_inventory_map(bundle),
                bundle_path=bundle,
            )
            rules_dir = project / ".cursor" / "rules"
            self.assertFalse(rules_dir.exists())

            original_replace = ManifestStore.replace

            def failing_replace(self_, manifest, expected_sha256):
                raise InstallConflictError("manifest changed")

            with mock.patch.object(ManifestStore, "replace", failing_replace):
                with self.assertRaises(InstallConflictError):
                    TransactionApplier().apply_update(plan)

            self.assertFalse(rules_dir.exists())
            self.assertFalse((project / ".cursor").exists())
            self.assertEqual(
                ManifestStore(project).load_with_fingerprint().sha256, fp_before
            )

    def test_directory_rollback_collision_exit_5(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            project.mkdir()
            bundle = _make_bundle(Path(tmp), {"a.mdc": "new\n"})
            digest = sha256_file(bundle / "cursor" / "a.mdc")
            snapshot = _save_manifest(project, {".cursor/rules/a.mdc": digest})
            plan = build_update_plan(
                project_root=project,
                snapshot=snapshot,
                running_version="0.16.0.dev0",
                inventory=_inventory_map(bundle),
                bundle_path=bundle,
            )
            rules_dir = project / ".cursor" / "rules"
            original_create_dirs = TransactionApplier._create_directories

            def failing_replace(self_, manifest, expected_sha256):
                raise InstallConflictError("manifest changed")

            def create_dirs_then_collision(self_, plan_, created_directories):
                original_create_dirs(self_, plan_, created_directories)
                rules_dir.mkdir(parents=True, exist_ok=True)
                (rules_dir / "user.txt").write_text("user\n", encoding="utf-8")

            with mock.patch.object(
                TransactionApplier, "_create_directories", create_dirs_then_collision
            ):
                with mock.patch.object(ManifestStore, "replace", failing_replace):
                    with self.assertRaises(LifecycleRollbackError):
                        TransactionApplier().apply_update(plan)

            self.assertTrue(rules_dir.exists())
            self.assertTrue((rules_dir / "user.txt").exists())


class ManifestIntegrityTests(unittest.TestCase):
    def _duplicate_manifest(self, project: Path) -> InstallManifest:
        managed = ManagedFile(
            relative_path=".cursor/rules/a.mdc",
            adapter="cursor",
            sha256="abc",
        )
        manifest = InstallManifest(
            schema_version=1,
            ekp_version="0.15.0",
            profile="cursor-symfony",
            adapters=["cursor"],
            installed_at="2026-01-01T00:00:00Z",
            install_root=".",
            managed_files=[managed, managed],
        )
        ManifestStore(project).save(manifest)
        return manifest

    def test_duplicate_managed_path_blocks_update(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            project.mkdir()
            self._duplicate_manifest(project)
            with mock.patch("ekp.lifecycle.update.get_version", return_value="0.16.0.dev0"):
                result = UpdateService().update(
                    UpdateRequest(path=str(project), assume_yes=True)
                )
            self.assertEqual(result.exit_code, 3)

    def test_duplicate_managed_path_blocks_uninstall(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            project.mkdir()
            self._duplicate_manifest(project)
            result = UninstallService().uninstall(
                UninstallRequest(path=str(project), assume_yes=True)
            )
            self.assertEqual(result.exit_code, 3)

    def test_managed_adapter_mismatch_blocks_lifecycle(self):
        manifest = InstallManifest(
            schema_version=1,
            ekp_version="0.15.0",
            profile="cursor-core",
            adapters=["cursor"],
            installed_at="2026-01-01T00:00:00Z",
            install_root=".",
            managed_files=[
                ManagedFile(
                    relative_path=".cursor/rules/a.mdc",
                    adapter="copilot",
                    sha256="abc",
                )
            ],
        )
        with self.assertRaises(InstallConflictError):
            validate_lifecycle_manifest(manifest)

    def test_valid_manifest_passes_integrity_checks(self):
        manifest = InstallManifest(
            schema_version=1,
            ekp_version="0.15.0",
            profile="cursor-core",
            adapters=["cursor"],
            installed_at="2026-01-01T00:00:00Z",
            install_root=".",
            managed_files=[
                ManagedFile(
                    relative_path=".cursor/rules/a.mdc",
                    adapter="cursor",
                    sha256="abc",
                )
            ],
        )
        validate_lifecycle_manifest(manifest)
