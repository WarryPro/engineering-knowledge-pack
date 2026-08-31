"""Install deployment and planning tests."""

import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from ekp.assembly import AssemblyRequest, AssemblyService
from ekp.install.cursor_deploy import CursorDeployService, sha256_file
from ekp.install.errors import InstallAssemblyError, InstallConflictError, InstallSelectionError
from ekp.install.manifest import InstallManifest, ManagedFile, ManifestStore
from ekp.install.plan import FileOpKind
from ekp.install.service import InstallRequest, InstallService
from ekp.paths import get_ekp_root
from ekp.tests.fixtures import flutter_fixture, symfony_fixture
from ekp.version import get_version


class InstallDeployTests(unittest.TestCase):
    def setUp(self):
        self.deploy = CursorDeployService()
        self.assembly = AssemblyService()
        self.resource_root = get_ekp_root()
        self.version = get_version()

    def _assemble(self, profile: str, output: Path):
        return self.assembly.assemble(
            AssemblyRequest(
                profile=profile,
                verify=True,
                resource_root=self.resource_root,
                workspace_dir=output / "workspace",
                output_root=output / "output",
            )
        )

    def test_symfony_first_install(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            project = root / "project"
            project.mkdir()
            symfony_fixture(project)

            assembly = self._assemble("cursor-symfony", root / "asm")
            plan = self.deploy.build_plan(
                project_root=project,
                bundle_path=assembly.bundle_path,
                profile="cursor-symfony",
                ekp_version=self.version,
            )
            self.assertEqual(plan.rules_count, 83)
            self.assertEqual(len(plan.files_to_write), 83)
            self.assertFalse(plan.has_conflicts)

            self.deploy.apply(plan)
            rules = list((project / ".cursor" / "rules").glob("*.mdc"))
            self.assertEqual(len(rules), 83)
            manifest = ManifestStore(project).load()
            self.assertEqual(len(manifest.managed_files), 83)

    def test_idempotent_reinstall(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            project = root / "project"
            project.mkdir()
            symfony_fixture(project)
            assembly = self._assemble("cursor-symfony", root / "asm")
            plan = self.deploy.build_plan(
                project_root=project,
                bundle_path=assembly.bundle_path,
                profile="cursor-symfony",
                ekp_version=self.version,
            )
            self.deploy.apply(plan)

            plan2 = self.deploy.build_plan(
                project_root=project,
                bundle_path=assembly.bundle_path,
                profile="cursor-symfony",
                ekp_version=self.version,
                existing_manifest=ManifestStore(project).load(),
            )
            self.assertTrue(plan2.is_noop)

    def test_unmanaged_collision(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            project = root / "project"
            project.mkdir()
            symfony_fixture(project)
            assembly = self._assemble("cursor-symfony", root / "asm")
            sample = next((assembly.bundle_path / "cursor").glob("*.mdc"))
            target = project / ".cursor" / "rules" / sample.name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text("user-owned\n", encoding="utf-8")

            plan = self.deploy.build_plan(
                project_root=project,
                bundle_path=assembly.bundle_path,
                profile="cursor-symfony",
                ekp_version=self.version,
            )
            self.assertTrue(plan.has_conflicts)
            self.assertFalse((project / ".ekp" / "install.json").exists())

    def test_modified_managed_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            project = root / "project"
            project.mkdir()
            symfony_fixture(project)
            assembly = self._assemble("cursor-symfony", root / "asm")
            plan = self.deploy.build_plan(
                project_root=project,
                bundle_path=assembly.bundle_path,
                profile="cursor-symfony",
                ekp_version=self.version,
            )
            self.deploy.apply(plan)
            target = next((project / ".cursor" / "rules").glob("*.mdc"))
            target.write_text("modified\n", encoding="utf-8")

            plan2 = self.deploy.build_plan(
                project_root=project,
                bundle_path=assembly.bundle_path,
                profile="cursor-symfony",
                ekp_version=self.version,
                existing_manifest=ManifestStore(project).load(),
            )
            self.assertTrue(plan2.has_conflicts)
            self.assertIn("Managed file modified", plan2.conflicts[0])

    def test_profile_mismatch(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            assembly = self._assemble("cursor-symfony", root / "asm")
            manifest = InstallManifest(
                schema_version=1,
                ekp_version=self.version,
                profile="cursor-symfony",
                adapters=["cursor"],
                installed_at="2026-01-01T00:00:00Z",
                install_root=".",
                managed_files=[],
            )
            with self.assertRaises(InstallSelectionError):
                self.deploy.build_plan(
                    project_root=root / "project",
                    bundle_path=assembly.bundle_path,
                    profile="cursor-flutter",
                    ekp_version=self.version,
                    existing_manifest=manifest,
                )

    def test_dry_run_writes_nothing(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            project = root / "project"
            project.mkdir()
            before = list(project.rglob("*"))
            assembly = self._assemble("cursor-flutter", root / "asm")
            plan = self.deploy.build_plan(
                project_root=project,
                bundle_path=assembly.bundle_path,
                profile="cursor-flutter",
                ekp_version=self.version,
                dry_run=True,
            )
            self.assertEqual(plan.rules_count, 75)
            after = list(project.rglob("*"))
            self.assertEqual(before, after)

    def test_path_traversal_rejected(self):
        with self.assertRaises(ValueError):
            from ekp.install.paths import resolve_under_root

            resolve_under_root(Path(".").resolve(), "../outside")

    @unittest.skipUnless(os.name != "nt", "Symlink test skipped on Windows")
    def test_symlink_target_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            project = root / "project"
            project.mkdir()
            symfony_fixture(project)
            outside = root / "outside"
            outside.mkdir()
            rules = project / ".cursor"
            rules.mkdir()
            rules.symlink_to(outside, target_is_directory=True)

            assembly = self._assemble("cursor-symfony", root / "asm")
            plan = self.deploy.build_plan(
                project_root=project,
                bundle_path=assembly.bundle_path,
                profile="cursor-symfony",
                ekp_version=self.version,
            )
            self.assertTrue(plan.has_conflicts)


class InstallServiceTests(unittest.TestCase):
    def test_empty_noninteractive_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = InstallService().install(
                InstallRequest(path=tmp, assume_yes=True)
            )
            self.assertEqual(result.exit_code, 2)

    def test_explicit_core_empty_project(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = InstallService().install(
                InstallRequest(path=tmp, profile="cursor-core", assume_yes=True)
            )
            self.assertEqual(result.exit_code, 0)
            manifest = ManifestStore(Path(tmp)).load()
            self.assertEqual(manifest.profile, "cursor-core")
            self.assertEqual(len(manifest.managed_files), 65)

    def test_flutter_auto_install(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            flutter_fixture(root)
            result = InstallService().install(
                InstallRequest(path=str(root), assume_yes=True)
            )
            self.assertEqual(result.exit_code, 0)
            manifest = ManifestStore(root).load()
            self.assertEqual(manifest.profile, "cursor-flutter")
            self.assertEqual(len(manifest.managed_files), 75)

    def test_collision_via_service(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            symfony_fixture(root)
            service = InstallService()
            assembly = AssemblyService().assemble(
                AssemblyRequest(profile="cursor-symfony", verify=True)
            )
            sample = next((assembly.bundle_path / "cursor").glob("*.mdc"))
            target = root / ".cursor" / "rules" / sample.name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text("blocked", encoding="utf-8")
            assembly._temp_ctx.cleanup()

            result = service.install(InstallRequest(path=str(root), assume_yes=True))
            self.assertEqual(result.exit_code, 3)
            self.assertFalse((root / ".ekp" / "install.json").exists())

    def test_rollback_on_failure(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            symfony_fixture(root)
            service = InstallService()

            with mock.patch("ekp.install.cursor_deploy.shutil.copyfile", side_effect=OSError("simulated")):
                result = service.install(
                    InstallRequest(path=str(root), profile="cursor-core", assume_yes=True)
                )
            self.assertEqual(result.exit_code, 5)
            self.assertFalse((root / ".ekp" / "install.json").exists())
            self.assertEqual(list((root / ".cursor" / "rules").glob("*.mdc")), [])
