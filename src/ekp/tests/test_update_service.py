"""Update lifecycle service, planning, and apply tests."""

from __future__ import annotations

import hashlib
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
from ekp.install.errors import InstallAssemblyError, InstallConflictError, InstallFilesystemError
from ekp.install.manifest import InstallManifest, ManagedFile, ManifestSnapshot, ManifestStore
from ekp.lifecycle.apply import LifecycleConflictError, LifecycleRollbackError, TransactionApplier
from ekp.lifecycle.plan import LifecycleOpKind
from ekp.lifecycle.update import UpdateRequest, UpdateService, build_update_plan
from ekp.paths import get_ekp_root
from ekp.status.models import StatusState
from ekp.status.service import StatusRequest, StatusService
from ekp.tests.fixtures import symfony_fixture
from ekp.version import get_version


def _make_bundle(root: Path, files: dict) -> Path:
    bundle = root / "bundle"
    cursor = bundle / "cursor"
    cursor.mkdir(parents=True)
    for name, content in files.items():
        (cursor / name).write_text(content, encoding="utf-8")
    return bundle


def _inventory_map(bundle: Path):
    deploy = CursorDeployService()
    return {
        relative: (source, digest)
        for relative, source, digest in deploy.inventory_bundle(bundle)
    }


def _write_file(project: Path, relative: str, content: str) -> str:
    target = project / Path(relative.replace("/", os.sep))
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")
    return sha256_file(target)


def _save_manifest(
    project: Path,
    managed: dict,
    *,
    ekp_version: str = "0.15.0",
    profile: str = "cursor-symfony",
    created_directories=None,
) -> ManifestSnapshot:
    managed_files = [
        ManagedFile(relative_path=relative, adapter="cursor", sha256=digest)
        for relative, digest in sorted(managed.items())
    ]
    manifest = InstallManifest(
        schema_version=1,
        ekp_version=ekp_version,
        profile=profile,
        adapters=["cursor"],
        installed_at="2026-09-01T20:25:28Z",
        install_root=".",
        managed_files=managed_files,
        created_directories=created_directories or [".cursor/rules"],
    )
    ManifestStore(project).save(manifest)
    return ManifestStore(project).load_with_fingerprint()


class UpdatePlanMatrixTests(unittest.TestCase):
    def _plan(self, project, snapshot, bundle, running_version="0.16.0.dev0"):
        return build_update_plan(
            project_root=project,
            snapshot=snapshot,
            running_version=running_version,
            inventory=_inventory_map(bundle),
            bundle_path=bundle,
        )

    def test_old_new_same_hash_disk_match_is_noop(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            project.mkdir()
            digest = _write_file(project, ".cursor/rules/a.mdc", "same\n")
            bundle = _make_bundle(Path(tmp), {"a.mdc": "same\n"})
            snapshot = _save_manifest(project, {".cursor/rules/a.mdc": digest})
            plan = self._plan(project, snapshot, bundle)
            self.assertEqual(plan.operations[0].kind, LifecycleOpKind.NOOP)

    def test_old_new_same_hash_missing_disk_is_create(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            project.mkdir()
            bundle = _make_bundle(Path(tmp), {"a.mdc": "same\n"})
            digest = sha256_file(bundle / "cursor" / "a.mdc")
            snapshot = _save_manifest(project, {".cursor/rules/a.mdc": digest})
            plan = self._plan(project, snapshot, bundle)
            self.assertEqual(plan.operations[0].kind, LifecycleOpKind.CREATE)

    def test_old_new_changed_hash_disk_old_is_write(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            project.mkdir()
            old_digest = _write_file(project, ".cursor/rules/a.mdc", "old\n")
            bundle = _make_bundle(Path(tmp), {"a.mdc": "new\n"})
            snapshot = _save_manifest(project, {".cursor/rules/a.mdc": old_digest})
            plan = self._plan(project, snapshot, bundle)
            self.assertEqual(plan.operations[0].kind, LifecycleOpKind.WRITE)

    def test_new_only_absent_is_create(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            project.mkdir()
            bundle = _make_bundle(Path(tmp), {"a.mdc": "new\n"})
            snapshot = _save_manifest(project, {})
            plan = self._plan(project, snapshot, bundle)
            self.assertEqual(plan.operations[0].kind, LifecycleOpKind.CREATE)

    def test_new_only_exists_is_conflict(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            project.mkdir()
            _write_file(project, ".cursor/rules/a.mdc", "user\n")
            bundle = _make_bundle(Path(tmp), {"a.mdc": "new\n"})
            snapshot = _save_manifest(project, {})
            plan = self._plan(project, snapshot, bundle)
            self.assertTrue(plan.has_conflicts)

    def test_old_only_matching_is_delete(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            project.mkdir()
            digest = _write_file(project, ".cursor/rules/a.mdc", "gone\n")
            bundle = _make_bundle(Path(tmp), {})
            snapshot = _save_manifest(project, {".cursor/rules/a.mdc": digest})
            plan = self._plan(project, snapshot, bundle)
            self.assertEqual(plan.operations[0].kind, LifecycleOpKind.DELETE)

    def test_old_only_missing_is_noop(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            project.mkdir()
            bundle = _make_bundle(Path(tmp), {})
            digest = hashlib.sha256(b"gone\n").hexdigest()
            snapshot = _save_manifest(project, {".cursor/rules/a.mdc": digest})
            plan = self._plan(project, snapshot, bundle)
            self.assertEqual(plan.operations[0].kind, LifecycleOpKind.NOOP)

    def test_same_version_inventory_drift_is_exit_4(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            project.mkdir()
            digest = _write_file(project, ".cursor/rules/a.mdc", "same\n")
            bundle = _make_bundle(Path(tmp), {"b.mdc": "other\n"})
            snapshot = _save_manifest(
                project, {".cursor/rules/a.mdc": digest}, ekp_version=get_version()
            )
            with self.assertRaises(InstallAssemblyError):
                self._plan(project, snapshot, bundle, running_version=get_version())

    def test_cross_version_manifest_commit_even_if_noops(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            project.mkdir()
            digest = _write_file(project, ".cursor/rules/a.mdc", "same\n")
            bundle = _make_bundle(Path(tmp), {"a.mdc": "same\n"})
            snapshot = _save_manifest(project, {".cursor/rules/a.mdc": digest})
            plan = self._plan(project, snapshot, bundle)
            self.assertTrue(plan.commit_manifest)
            self.assertEqual(plan.new_manifest.ekp_version, "0.16.0.dev0")

    def test_same_version_no_file_changes_skips_manifest_commit(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            project.mkdir()
            digest = _write_file(project, ".cursor/rules/a.mdc", "same\n")
            bundle = _make_bundle(Path(tmp), {"a.mdc": "same\n"})
            snapshot = _save_manifest(
                project, {".cursor/rules/a.mdc": digest}, ekp_version=get_version()
            )
            plan = self._plan(project, snapshot, bundle, running_version=get_version())
            self.assertFalse(plan.commit_manifest)


class UpdateServiceIntegrationTests(unittest.TestCase):
    RUNNING_VERSION = "0.16.0.dev0"

    def setUp(self):
        self.deploy = CursorDeployService()
        self.assembly = AssemblyService()
        self.resource_root = get_ekp_root()

    def _install_symfony_v015(self, project: Path):
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

    def _run_update(self, **kwargs):
        with mock.patch("ekp.lifecycle.update.get_version", return_value=self.RUNNING_VERSION):
            return UpdateService().update(UpdateRequest(**kwargs))

    def test_missing_manifest_exit_2(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = self._run_update(path=tmp, assume_yes=True)
            self.assertEqual(result.exit_code, 2)
            self.assertIn("ekp install", result.message)

    def test_v015_to_running_update(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            project.mkdir()
            self._install_symfony_v015(project)
            installed_at_before = ManifestStore(project).load().installed_at
            before_fp = ManifestStore(project).load_with_fingerprint().sha256

            result = self._run_update(path=str(project), assume_yes=True)
            self.assertEqual(result.exit_code, 0, result.message)

            manifest = ManifestStore(project).load()
            self.assertEqual(manifest.ekp_version, self.RUNNING_VERSION)
            self.assertEqual(manifest.profile, "cursor-symfony")
            self.assertEqual(len(manifest.managed_files), 83)
            self.assertEqual(manifest.installed_at, installed_at_before)

            with mock.patch("ekp.status.service.get_version", return_value=self.RUNNING_VERSION):
                status = StatusService().inspect(StatusRequest(path=str(project)))
            self.assertEqual(status.state, StatusState.HEALTHY)
            self.assertEqual(status.installed_version, self.RUNNING_VERSION)

    def test_dry_run_writes_nothing(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            project.mkdir()
            self._install_symfony_v015(project)
            before = list(project.rglob("*"))
            fp_before = ManifestStore(project).load_with_fingerprint().sha256

            result = self._run_update(path=str(project), dry_run=True)
            self.assertEqual(result.exit_code, 0)
            self.assertIn("Dry run", result.message)
            after = list(project.rglob("*"))
            self.assertEqual(sorted(before), sorted(after))
            self.assertEqual(
                ManifestStore(project).load_with_fingerprint().sha256, fp_before
            )

    def test_modified_managed_file_blocks_update(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            project.mkdir()
            self._install_symfony_v015(project)
            target = next((project / ".cursor" / "rules").glob("*.mdc"))
            target.write_text("modified\n", encoding="utf-8")

            result = self._run_update(path=str(project), assume_yes=True)
            self.assertEqual(result.exit_code, 3)
            self.assertEqual(ManifestStore(project).load().ekp_version, "0.15.0")

    def test_same_version_missing_file_repair(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            project.mkdir()
            bundle = _make_bundle(Path(tmp), {"a.mdc": "same\n"})
            digest = _write_file(project, ".cursor/rules/a.mdc", "same\n")
            snapshot = _save_manifest(
                project,
                {".cursor/rules/a.mdc": digest},
                ekp_version=get_version(),
                profile="cursor-core",
            )
            target = project / ".cursor" / "rules" / "a.mdc"
            target.unlink()
            fp_before = snapshot.sha256

            plan = build_update_plan(
                project_root=project,
                snapshot=snapshot,
                running_version=get_version(),
                inventory=_inventory_map(bundle),
                bundle_path=bundle,
            )
            TransactionApplier().apply_update(plan)

            self.assertTrue(target.exists())
            self.assertEqual(
                ManifestStore(project).load_with_fingerprint().sha256, fp_before
            )


class UpdateApplySafetyTests(unittest.TestCase):
    def setUp(self):
        self.applier = TransactionApplier()

    def _bundle_and_plan(self, tmp, old_files, new_files, running="0.16.0.dev0"):
        project = Path(tmp) / "project"
        project.mkdir()
        managed = {}
        for relative, content in old_files.items():
            managed[relative] = _write_file(project, relative, content)
        bundle = _make_bundle(Path(tmp), new_files)
        snapshot = _save_manifest(project, managed)
        plan = build_update_plan(
            project_root=project,
            snapshot=snapshot,
            running_version=running,
            inventory=_inventory_map(bundle),
            bundle_path=bundle,
        )
        return project, plan

    def test_create_toctou_rolls_back(self):
        with tempfile.TemporaryDirectory() as tmp:
            project, plan = self._bundle_and_plan(
                tmp,
                {},
                {"a.mdc": "new\n"},
            )
            create_rel = plan.operations[0].relative_path
            create_path = project / Path(create_rel.replace("/", os.sep))
            create_path.parent.mkdir(parents=True, exist_ok=True)
            original_create = TransactionApplier._apply_create

            def patched_create(self_, plan_, operation, created):
                create_path.write_text("appeared\n", encoding="utf-8")
                return original_create(self_, plan_, operation, created)

            with mock.patch.object(TransactionApplier, "_apply_create", patched_create):
                with self.assertRaises(LifecycleConflictError):
                    self.applier.apply_update(plan)

    def test_write_post_backup_toctou_rolls_back(self):
        with tempfile.TemporaryDirectory() as tmp:
            project, plan = self._bundle_and_plan(
                tmp,
                {".cursor/rules/a.mdc": "old\n"},
                {"a.mdc": "new\n"},
            )
            target = project / ".cursor" / "rules" / "a.mdc"
            original_validate = TransactionApplier._validate_write_target
            calls = {"n": 0}

            def validate_and_mutate(self_, project_root, relative, expected_sha256):
                result = original_validate(self_, project_root, relative, expected_sha256)
                calls["n"] += 1
                if calls["n"] == 2 and result is not None:
                    target.write_text("mutated\n", encoding="utf-8")
                return result

            with mock.patch.object(
                TransactionApplier, "_validate_write_target", validate_and_mutate
            ):
                with self.assertRaises(LifecycleConflictError):
                    self.applier.apply_update(plan)

            self.assertEqual(target.read_text(encoding="utf-8"), "mutated\n")

    def test_source_mutation_exit_4(self):
        with tempfile.TemporaryDirectory() as tmp:
            project, plan = self._bundle_and_plan(
                tmp,
                {},
                {"a.mdc": "new\n"},
            )
            op = plan.operations[0]
            op.source_path.write_text("mutated\n", encoding="utf-8")
            with self.assertRaises(InstallAssemblyError):
                self.applier.apply_update(plan)

    def test_manifest_cas_conflict_preserves_manifest_b(self):
        with tempfile.TemporaryDirectory() as tmp:
            project, plan = self._bundle_and_plan(
                tmp,
                {".cursor/rules/a.mdc": "old\n"},
                {"a.mdc": "new\n"},
            )
            manifest_path = project / ".ekp" / "install.json"
            original_apply_write = TransactionApplier._apply_write

            def apply_write_then_mutate_manifest(self_, plan_, operation, backup_root, written):
                result = original_apply_write(self_, plan_, operation, backup_root, written)
                manifest_path.write_text(
                    manifest_path.read_text(encoding="utf-8") + "\n",
                    encoding="utf-8",
                )
                return result

            with mock.patch.object(
                TransactionApplier, "_apply_write", apply_write_then_mutate_manifest
            ):
                with self.assertRaises(InstallConflictError) as ctx:
                    self.applier.apply_update(plan)
            self.assertEqual(ctx.exception.exit_code, 3)
            self.assertIn("\n", manifest_path.read_text(encoding="utf-8"))

    def test_manifest_pre_replace_race(self):
        with tempfile.TemporaryDirectory() as tmp:
            project, plan = self._bundle_and_plan(
                tmp,
                {".cursor/rules/a.mdc": "old\n"},
                {"a.mdc": "new\n"},
            )
            manifest_path = project / ".ekp" / "install.json"
            original_replace = ManifestStore.replace

            def replace_race(self_, manifest, expected_sha256):
                manifest_path.write_text(
                    manifest_path.read_text(encoding="utf-8") + "# changed\n",
                    encoding="utf-8",
                )
                return original_replace(self_, manifest, expected_sha256)

            with mock.patch.object(ManifestStore, "replace", replace_race):
                with self.assertRaises(InstallConflictError):
                    self.applier.apply_update(plan)

    def test_write_rollback_collision_exit_5(self):
        with tempfile.TemporaryDirectory() as tmp:
            project, plan = self._bundle_and_plan(
                tmp,
                {".cursor/rules/a.mdc": "old\n"},
                {"a.mdc": "new\n"},
            )
            original_apply_write = TransactionApplier._apply_write
            target = project / ".cursor" / "rules" / "a.mdc"

            def write_then_fail(self_, plan_, operation, backup_root, written):
                original_apply_write(self_, plan_, operation, backup_root, written)
                target.write_text("user changed again\n", encoding="utf-8")
                raise OSError("simulated failure")

            with mock.patch.object(TransactionApplier, "_apply_write", write_then_fail):
                with self.assertRaises(LifecycleRollbackError) as ctx:
                    self.applier.apply_update(plan)
            self.assertEqual(target.read_text(encoding="utf-8"), "user changed again\n")
            self.assertIn("rollback incomplete", str(ctx.exception).lower())

    def test_create_rollback_collision_exit_5(self):
        with tempfile.TemporaryDirectory() as tmp:
            project, plan = self._bundle_and_plan(
                tmp,
                {},
                {"a.mdc": "new\n"},
            )
            rel = plan.operations[0].relative_path
            target = project / Path(rel.replace("/", os.sep))
            original_apply_create = TransactionApplier._apply_create

            def create_then_fail(self_, plan_, operation, created):
                original_apply_create(self_, plan_, operation, created)
                target.write_text("user modified\n", encoding="utf-8")
                raise OSError("simulated failure")

            with mock.patch.object(TransactionApplier, "_apply_create", create_then_fail):
                with self.assertRaises(LifecycleRollbackError):
                    self.applier.apply_update(plan)
            self.assertEqual(target.read_text(encoding="utf-8"), "user modified\n")

    def test_mixed_transaction_rollback_restores_state(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            project.mkdir()
            old_digest = _write_file(project, ".cursor/rules/keep.mdc", "keep\n")
            remove_digest = _write_file(project, ".cursor/rules/remove.mdc", "remove\n")
            bundle = _make_bundle(
                Path(tmp),
                {"keep.mdc": "keep\n", "add.mdc": "add\n", "change.mdc": "new\n"},
            )
            change_old = _write_file(project, ".cursor/rules/change.mdc", "old\n")
            snapshot = _save_manifest(
                project,
                {
                    ".cursor/rules/keep.mdc": old_digest,
                    ".cursor/rules/remove.mdc": remove_digest,
                    ".cursor/rules/change.mdc": change_old,
                },
            )
            fp_before = snapshot.sha256
            plan = build_update_plan(
                project_root=project,
                snapshot=snapshot,
                running_version="0.16.0.dev0",
                inventory=_inventory_map(bundle),
                bundle_path=bundle,
            )
            calls = {"n": 0}
            original_apply_delete = TransactionApplier._apply_delete

            def fail_on_delete(self_, project_root, operation, backup_root, deleted):
                calls["n"] += 1
                if operation.relative_path.endswith("remove.mdc"):
                    raise OSError("fail after mixed ops")
                return original_apply_delete(self_, project_root, operation, backup_root, deleted)

            with mock.patch.object(TransactionApplier, "_apply_delete", fail_on_delete):
                with self.assertRaises(InstallFilesystemError):
                    self.applier.apply_update(plan)

            self.assertTrue((project / ".cursor/rules/keep.mdc").exists())
            self.assertTrue((project / ".cursor/rules/remove.mdc").exists())
            self.assertEqual(
                (project / ".cursor/rules/change.mdc").read_text(encoding="utf-8"), "old\n"
            )
            self.assertFalse((project / ".cursor/rules/add.mdc").exists())
            self.assertEqual(
                ManifestStore(project).load_with_fingerprint().sha256, fp_before
            )


class UpdateCliTests(unittest.TestCase):
    def test_cli_update_help(self):
        import io
        from contextlib import redirect_stdout

        buffer = io.StringIO()
        with redirect_stdout(buffer):
            try:
                main(["update", "--help"])
            except SystemExit as exc:
                self.assertEqual(exc.code, 0)
        output = buffer.getvalue()
        self.assertIn("update", output)
        self.assertIn("--dry-run", output)

    def test_cli_help_lists_update(self):
        import io
        from contextlib import redirect_stdout

        buffer = io.StringIO()
        with redirect_stdout(buffer):
            try:
                main(["--help"])
            except SystemExit:
                pass
        self.assertIn("update", buffer.getvalue())
