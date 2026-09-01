"""Uninstall lifecycle service and apply tests."""

from __future__ import annotations

import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from ekp.assembly import AssemblyRequest, AssemblyService
from ekp.cli import main
from ekp.install.cursor_deploy import CursorDeployService, sha256_file
from ekp.install.errors import InstallConflictError, InstallFilesystemError
from ekp.install.manifest import InstallManifest, ManagedFile, ManifestStore
from ekp.install.service import InstallRequest, InstallService
from ekp.lifecycle.apply import LifecycleConflictError, LifecycleRollbackError, TransactionApplier
from ekp.lifecycle.plan import LifecycleOpKind
from ekp.lifecycle.uninstall import (
    UninstallRequest,
    UninstallService,
    build_uninstall_plan,
    validate_lifecycle_manifest,
)
from ekp.paths import get_ekp_root
from ekp.status.service import StatusRequest, StatusService
from ekp.status.models import StatusState
from ekp.tests.fixtures import symfony_fixture


def _v015_manifest_dict(managed_files, created_directories=None):
    return {
        "schema_version": 1,
        "ekp_version": "0.15.0",
        "profile": "cursor-symfony",
        "adapters": ["cursor"],
        "installed_at": "2026-09-01T20:25:28Z",
        "install_root": ".",
        "managed_files": managed_files,
        "created_directories": created_directories or [".cursor/rules"],
    }


class UninstallServiceTests(unittest.TestCase):
    def setUp(self):
        self.deploy = CursorDeployService()
        self.assembly = AssemblyService()
        self.resource_root = get_ekp_root()

    def _install_symfony(self, project: Path):
        symfony_fixture(project)
        assembly = self.assembly.assemble(
            AssemblyRequest(
                profile="cursor-symfony",
                verify=True,
                resource_root=self.resource_root,
                workspace_dir=project.parent / "asm-workspace",
                output_root=project.parent / "asm-output",
            )
        )
        plan = self.deploy.build_plan(
            project_root=project,
            bundle_path=assembly.bundle_path,
            profile="cursor-symfony",
            ekp_version="0.15.0",
        )
        self.deploy.apply(plan)
        manifest = ManifestStore(project).load()
        manifest.ekp_version = "0.15.0"
        ManifestStore(project).save(manifest)
        return manifest

    def test_no_manifest_is_idempotent(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = UninstallService().uninstall(
                UninstallRequest(path=tmp, assume_yes=True)
            )
            self.assertEqual(result.exit_code, 0)
            self.assertIn("not installed", result.message)

    def test_normal_uninstall(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            project.mkdir()
            self._install_symfony(project)

            result = UninstallService().uninstall(
                UninstallRequest(path=str(project), assume_yes=True)
            )
            self.assertEqual(result.exit_code, 0)
            self.assertFalse(ManifestStore(project).exists())
            self.assertEqual(list((project / ".cursor" / "rules").glob("*.mdc")), [])

            status = StatusService().inspect(StatusRequest(path=str(project)))
            self.assertEqual(status.state, StatusState.NOT_INSTALLED)

    def test_modified_managed_file_blocks_uninstall(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            project.mkdir()
            self._install_symfony(project)
            target = next((project / ".cursor" / "rules").glob("*.mdc"))
            target.write_text("modified\n", encoding="utf-8")

            result = UninstallService().uninstall(
                UninstallRequest(path=str(project), assume_yes=True)
            )
            self.assertEqual(result.exit_code, 3)
            self.assertTrue(ManifestStore(project).exists())
            self.assertTrue(target.exists())

    def test_missing_managed_file_allows_uninstall(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            project.mkdir()
            self._install_symfony(project)
            target = next((project / ".cursor" / "rules").glob("*.mdc"))
            target.unlink()

            result = UninstallService().uninstall(
                UninstallRequest(path=str(project), assume_yes=True)
            )
            self.assertEqual(result.exit_code, 0)
            self.assertFalse(ManifestStore(project).exists())
            self.assertEqual(list((project / ".cursor" / "rules").glob("*.mdc")), [])

    def test_unmanaged_file_survives(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            project.mkdir()
            self._install_symfony(project)
            user_rule = project / ".cursor" / "rules" / "user-rule.mdc"
            user_rule.write_text("user-owned\n", encoding="utf-8")

            result = UninstallService().uninstall(
                UninstallRequest(path=str(project), assume_yes=True)
            )
            self.assertEqual(result.exit_code, 0)
            self.assertTrue(user_rule.exists())
            self.assertTrue((project / ".cursor" / "rules").exists())

    def test_dry_run_writes_nothing(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            project.mkdir()
            self._install_symfony(project)
            before = list(project.rglob("*"))

            result = UninstallService().uninstall(
                UninstallRequest(path=str(project), dry_run=True)
            )
            self.assertEqual(result.exit_code, 0)
            self.assertIn("Dry run", result.message)
            after = list(project.rglob("*"))
            self.assertEqual(sorted(before), sorted(after))

    def test_v015_schema1_manifest(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            project.mkdir(parents=True)
            rules_dir = project / ".cursor" / "rules"
            rules_dir.mkdir(parents=True)
            managed_path = rules_dir / "demo.mdc"
            managed_path.write_text("demo\n", encoding="utf-8")
            digest = sha256_file(managed_path)

            manifest_path = project / ".ekp" / "install.json"
            manifest_path.parent.mkdir(parents=True)
            manifest_path.write_text(
                json.dumps(
                    _v015_manifest_dict(
                        [
                            {
                                "relative_path": ".cursor/rules/demo.mdc",
                                "adapter": "cursor",
                                "sha256": digest,
                            }
                        ]
                    ),
                    indent=2,
                )
                + "\n",
                encoding="utf-8",
            )

            result = UninstallService().uninstall(
                UninstallRequest(path=str(project), assume_yes=True)
            )
            self.assertEqual(result.exit_code, 0)
            self.assertFalse(managed_path.exists())
            self.assertFalse(manifest_path.exists())
            self.assertFalse(rules_dir.exists())
            self.assertTrue((project / ".cursor").exists())
            self.assertTrue((project / ".ekp").exists())

    def test_non_cursor_adapter_rejected(self):
        manifest = InstallManifest(
            schema_version=1,
            ekp_version="0.15.0",
            profile="cursor-core",
            adapters=["cursor", "copilot"],
            installed_at="2026-01-01T00:00:00Z",
            install_root=".",
            managed_files=[],
        )
        with self.assertRaises(Exception):
            validate_lifecycle_manifest(manifest)

    def test_recorded_empty_cursor_rules_removed(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            rules_dir = project / ".cursor" / "rules"
            rules_dir.mkdir(parents=True)
            manifest_path = project / ".ekp" / "install.json"
            manifest_path.parent.mkdir(parents=True)
            manifest_path.write_text(
                json.dumps(_v015_manifest_dict([], [".cursor/rules"]), indent=2) + "\n",
                encoding="utf-8",
            )

            result = UninstallService().uninstall(
                UninstallRequest(path=str(project), assume_yes=True)
            )
            self.assertEqual(result.exit_code, 0)
            self.assertFalse(rules_dir.exists())

    def test_unrecorded_empty_cursor_preserved(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            cursor_dir = project / ".cursor"
            cursor_dir.mkdir(parents=True)
            manifest_path = project / ".ekp" / "install.json"
            manifest_path.parent.mkdir(parents=True)
            manifest_path.write_text(
                json.dumps(_v015_manifest_dict([], []), indent=2) + "\n",
                encoding="utf-8",
            )

            result = UninstallService().uninstall(
                UninstallRequest(path=str(project), assume_yes=True)
            )
            self.assertEqual(result.exit_code, 0)
            self.assertTrue(cursor_dir.exists())

    def test_unrecorded_empty_ekp_preserved(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            project.mkdir()
            ekp_dir = project / ".ekp"
            ekp_dir.mkdir()
            manifest_path = ekp_dir / "install.json"
            manifest_path.write_text(
                json.dumps(_v015_manifest_dict([], []), indent=2) + "\n",
                encoding="utf-8",
            )

            result = UninstallService().uninstall(
                UninstallRequest(path=str(project), assume_yes=True)
            )
            self.assertEqual(result.exit_code, 0)
            self.assertTrue(ekp_dir.exists())

    def test_unsafe_recorded_directory_blocks_preflight(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            project.mkdir()
            rules_dir = project / ".cursor" / "rules"
            rules_dir.mkdir(parents=True)
            managed_path = rules_dir / "demo.mdc"
            managed_path.write_text("demo\n", encoding="utf-8")
            digest = sha256_file(managed_path)

            manifest = InstallManifest(
                schema_version=1,
                ekp_version="0.15.0",
                profile="cursor-symfony",
                adapters=["cursor"],
                installed_at="2026-09-01T00:00:00Z",
                install_root=".",
                managed_files=[
                    ManagedFile(
                        relative_path=".cursor/rules/demo.mdc",
                        adapter="cursor",
                        sha256=digest,
                    )
                ],
                created_directories=["../outside"],
            )

            ManifestStore(project).save(manifest)
            plan = build_uninstall_plan(project, manifest)
            self.assertTrue(plan.has_conflicts)
            self.assertTrue(managed_path.exists())


class TransactionApplierTests(unittest.TestCase):
    def setUp(self):
        self.applier = TransactionApplier()
        self.deploy = CursorDeployService()
        self.assembly = AssemblyService()

    def _plan_for_project(self, project: Path):
        symfony_fixture(project)
        assembly = self.assembly.assemble(
            AssemblyRequest(
                profile="cursor-symfony",
                verify=True,
                workspace_dir=project.parent / "workspace",
                output_root=project.parent / "output",
            )
        )
        install_plan = self.deploy.build_plan(
            project_root=project,
            bundle_path=assembly.bundle_path,
            profile="cursor-symfony",
            ekp_version="0.15.0",
        )
        self.deploy.apply(install_plan)
        manifest = ManifestStore(project).load()
        return build_uninstall_plan(project, manifest)

    def test_post_backup_target_mutation_rolls_back(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            project.mkdir()
            plan = self._plan_for_project(project)
            delete_ops = [
                op for op in plan.operations if op.kind == LifecycleOpKind.DELETE
            ]
            self.assertGreaterEqual(len(delete_ops), 2)
            first_rel = delete_ops[0].relative_path
            second_rel = delete_ops[1].relative_path
            first_path = project / Path(first_rel.replace("/", os.sep))
            second_path = project / Path(second_rel.replace("/", os.sep))
            original_copy2 = shutil.copy2

            def copy2_and_mutate(src, dst):
                original_copy2(src, dst)
                if src == second_path:
                    src.write_text("mutated after backup\n", encoding="utf-8")

            with mock.patch("ekp.lifecycle.apply.shutil.copy2", side_effect=copy2_and_mutate):
                with self.assertRaises(LifecycleConflictError):
                    self.applier.apply_uninstall(plan)

            self.assertTrue(ManifestStore(project).exists())
            self.assertTrue(first_path.exists())
            self.assertTrue(second_path.exists())
            self.assertEqual(
                second_path.read_text(encoding="utf-8"), "mutated after backup\n"
            )

    def test_manifest_changed_after_plan_rolls_back(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            project.mkdir()
            plan = self._plan_for_project(project)
            manifest_path = project / ".ekp" / "install.json"
            original_bytes = manifest_path.read_bytes()
            manifest_path.write_bytes(original_bytes + b"\n")

            with self.assertRaises(InstallConflictError):
                self.applier.apply_uninstall(plan)

            self.assertTrue(manifest_path.exists())
            self.assertEqual(manifest_path.read_bytes(), original_bytes + b"\n")
            self.assertGreater(
                len(list((project / ".cursor" / "rules").glob("*.mdc"))), 0
            )

    @unittest.skipUnless(os.name != "nt", "Symlink test skipped on Windows")
    def test_manifest_symlink_replacement_blocks_delete(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            project = root / "project"
            project.mkdir()
            plan = self._plan_for_project(project)
            manifest_path = project / ".ekp" / "install.json"
            outside = root / "outside-install.json"
            outside.write_bytes(manifest_path.read_bytes())
            manifest_path.unlink()
            manifest_path.symlink_to(outside)

            with self.assertRaises(InstallConflictError):
                self.applier.apply_uninstall(plan)

            self.assertTrue(manifest_path.is_symlink())
            self.assertGreater(
                len(list((project / ".cursor" / "rules").glob("*.mdc"))), 0
            )

    def test_rollback_collision_preserves_replacement(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            project.mkdir()
            plan = self._plan_for_project(project)
            delete_ops = [
                op for op in plan.operations if op.kind == LifecycleOpKind.DELETE
            ]
            self.assertGreaterEqual(len(delete_ops), 2)
            first_rel = delete_ops[0].relative_path
            second_rel = delete_ops[1].relative_path
            first_path = project / Path(first_rel.replace("/", os.sep))
            original_apply_delete = TransactionApplier._apply_delete

            def patched_apply_delete(self_, project_root, operation, backup_root, deleted):
                original_apply_delete(
                    self_, project_root, operation, backup_root, deleted
                )
                if operation.relative_path == first_rel:
                    first_path.write_text("user replacement\n", encoding="utf-8")
                if operation.relative_path == second_rel:
                    raise OSError("simulated delete failure")

            with mock.patch.object(TransactionApplier, "_apply_delete", patched_apply_delete):
                with self.assertRaises(LifecycleRollbackError) as ctx:
                    self.applier.apply_uninstall(plan)

            self.assertEqual(first_path.read_text(encoding="utf-8"), "user replacement\n")
            self.assertIn("rollback incomplete", str(ctx.exception).lower())
            self.assertTrue(ManifestStore(project).exists())

    def test_rollback_incomplete_preserves_backup_workspace(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            project.mkdir()
            plan = self._plan_for_project(project)
            delete_ops = [
                op for op in plan.operations if op.kind == LifecycleOpKind.DELETE
            ]
            failing_rel = delete_ops[0].relative_path
            original_apply_delete = TransactionApplier._apply_delete

            def patched_apply_delete(self_, project_root, operation, backup_root, deleted):
                if operation.relative_path == failing_rel:
                    raise OSError("simulated delete failure")
                return original_apply_delete(
                    self_, project_root, operation, backup_root, deleted
                )

            with mock.patch.object(TransactionApplier, "_apply_delete", patched_apply_delete):
                with mock.patch.object(
                    TransactionApplier,
                    "_rollback_deleted",
                    return_value=False,
                ):
                    with self.assertRaises(LifecycleRollbackError) as ctx:
                        self.applier.apply_uninstall(plan)

            message = str(ctx.exception)
            self.assertIn("Recovery data preserved at:", message)
            backup_path = Path(message.rsplit(":", 1)[-1].strip().split(" ", 1)[0])
            self.assertTrue(backup_path.exists())
            self.assertTrue(backup_path.name.startswith("ekp-lifecycle-"))

    def test_manifest_identity_conflict_exit_3(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            project.mkdir()
            plan = self._plan_for_project(project)
            manifest_path = project / ".ekp" / "install.json"
            manifest_path.write_text(
                manifest_path.read_text(encoding="utf-8") + "\n",
                encoding="utf-8",
            )

            with self.assertRaises(InstallConflictError) as ctx:
                self.applier.apply_uninstall(plan)
            self.assertEqual(ctx.exception.exit_code, 3)
            self.assertTrue(manifest_path.exists())

    def test_toctou_revalidation_rolls_back(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            project.mkdir()
            plan = self._plan_for_project(project)
            delete_ops = [
                op for op in plan.operations if op.kind == LifecycleOpKind.DELETE
            ]
            self.assertGreaterEqual(len(delete_ops), 2)
            first_rel = delete_ops[0].relative_path
            second_rel = delete_ops[1].relative_path
            first_path = project / Path(first_rel.replace("/", os.sep))
            second_path = project / Path(second_rel.replace("/", os.sep))

            second_path.write_text("changed-before-apply\n", encoding="utf-8")

            with self.assertRaises(LifecycleConflictError):
                self.applier.apply_uninstall(plan)

            self.assertTrue(ManifestStore(project).exists())
            self.assertTrue(first_path.exists())
            self.assertTrue(second_path.exists())
            self.assertEqual(second_path.read_text(encoding="utf-8"), "changed-before-apply\n")

    def test_rollback_restores_deleted_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            project.mkdir()
            plan = self._plan_for_project(project)
            delete_ops = [
                op for op in plan.operations if op.kind == LifecycleOpKind.DELETE
            ]
            self.assertGreaterEqual(len(delete_ops), 2)
            failing_rel = delete_ops[1].relative_path
            original_apply_delete = TransactionApplier._apply_delete
            calls = {"count": 0}

            def patched_apply_delete(self_, project_root, operation, backup_root, deleted):
                calls["count"] += 1
                if operation.relative_path == failing_rel:
                    raise OSError("simulated delete failure")
                return original_apply_delete(self_, project_root, operation, backup_root, deleted)

            with mock.patch.object(TransactionApplier, "_apply_delete", patched_apply_delete):
                with self.assertRaises(Exception):
                    self.applier.apply_uninstall(plan)

            self.assertTrue(ManifestStore(project).exists())
            for op in delete_ops:
                path = project / Path(op.relative_path.replace("/", os.sep))
                self.assertTrue(path.exists())

    def test_rollback_incomplete_reports_exit_5(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            project.mkdir()
            plan = self._plan_for_project(project)
            delete_ops = [
                op for op in plan.operations if op.kind == LifecycleOpKind.DELETE
            ]
            failing_rel = delete_ops[0].relative_path
            original_apply_delete = TransactionApplier._apply_delete
            calls = {"count": 0}

            def patched_apply_delete(self_, project_root, operation, backup_root, deleted):
                calls["count"] += 1
                if operation.relative_path == failing_rel:
                    raise OSError("simulated delete failure")
                return original_apply_delete(self_, project_root, operation, backup_root, deleted)

            with mock.patch.object(TransactionApplier, "_apply_delete", patched_apply_delete):
                with mock.patch.object(
                    TransactionApplier,
                    "_rollback_deleted",
                    return_value=False,
                ):
                    with self.assertRaises(LifecycleRollbackError) as ctx:
                        self.applier.apply_uninstall(plan)
            self.assertIn("rollback incomplete", str(ctx.exception).lower())

    def test_manifest_delete_failure_restores_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            project.mkdir()
            plan = self._plan_for_project(project)
            managed_before = len(list((project / ".cursor" / "rules").glob("*.mdc")))

            with mock.patch(
                "ekp.lifecycle.apply.ManifestStore.delete",
                side_effect=OSError("manifest delete failed"),
            ):
                with self.assertRaises(InstallFilesystemError) as ctx:
                    self.applier.apply_uninstall(plan)
            self.assertEqual(ctx.exception.exit_code, 5)

            self.assertTrue(ManifestStore(project).exists())
            self.assertEqual(
                len(list((project / ".cursor" / "rules").glob("*.mdc"))),
                managed_before,
            )

    @unittest.skipUnless(os.name != "nt", "Symlink test skipped on Windows")
    def test_symlink_managed_file_blocks_uninstall(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            project = root / "project"
            project.mkdir()
            plan = self._plan_for_project(project)
            target = next((project / ".cursor" / "rules").glob("*.mdc"))
            outside = root / "outside.mdc"
            outside.write_text("outside\n", encoding="utf-8")
            target.unlink()
            target.symlink_to(outside)

            replan = build_uninstall_plan(project, ManifestStore(project).load())
            self.assertTrue(replan.has_conflicts)

            result = UninstallService().uninstall(
                UninstallRequest(path=str(project), assume_yes=True)
            )
            self.assertEqual(result.exit_code, 3)
            self.assertTrue(ManifestStore(project).exists())

    @unittest.skipUnless(os.name != "nt", "Symlink test skipped on Windows")
    def test_cursor_symlink_escape_blocks_uninstall(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            project = root / "project"
            project.mkdir()
            plan = self._plan_for_project(project)
            outside = root / "outside"
            outside.mkdir()
            cursor = project / ".cursor"
            cursor.rename(outside / "cursor-real")
            (project / ".cursor").symlink_to(outside / "cursor-real", target_is_directory=True)

            replan = build_uninstall_plan(project, ManifestStore(project).load())
            self.assertTrue(replan.has_conflicts)

            result = UninstallService().uninstall(
                UninstallRequest(path=str(project), assume_yes=True)
            )
            self.assertEqual(result.exit_code, 3)


class UninstallCliTests(unittest.TestCase):
    def test_cli_uninstall_help(self):
        import io
        from contextlib import redirect_stdout

        buffer = io.StringIO()
        with redirect_stdout(buffer):
            try:
                main(["uninstall", "--help"])
            except SystemExit as exc:
                self.assertEqual(exc.code, 0)
        self.assertIn("uninstall", buffer.getvalue())
        self.assertIn("--dry-run", buffer.getvalue())

    def test_cli_no_manifest(self):
        import io
        from contextlib import redirect_stdout

        with tempfile.TemporaryDirectory() as tmp:
            buffer = io.StringIO()
            with redirect_stdout(buffer):
                code = main(["uninstall", "--path", tmp, "--yes"])
            self.assertEqual(code, 0)
            self.assertIn("not installed", buffer.getvalue())
