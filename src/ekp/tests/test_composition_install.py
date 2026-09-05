"""Composition install persistence tests (AW-E1)."""

from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from ekp.composition import PROJECT_COMPOSITION_PROFILE, ComponentRegistry
from ekp.config import PROJECT_CONFIG_RELATIVE, ProjectConfig, ProjectConfigStore
from ekp.config.project import render_project_config_yaml
from ekp.install.composition_install import (
    CONFIG_ACTION_CREATE,
    CONFIG_ACTION_REUSE,
    CompositionInstallService,
)
from ekp.install.errors import (
    EXIT_CONFLICT,
    EXIT_SELECTION,
    InstallFilesystemError,
)
from ekp.install.intent import build_composition_intent
from ekp.install.manifest import (
    INSTALL_MODE_COMPOSITION,
    InstallManifest,
    ManifestStore,
)
from ekp.install.service import InstallRequest, InstallService
from ekp.paths import get_ekp_root
from ekp.tests.fixtures import devops_fixture, frontend_fixture, symfony_fixture
from ekp.version import get_version


def _fingerprint(root: Path):
    items = {}
    for path in sorted(root.rglob("*")):
        if path.is_file():
            items[path.relative_to(root).as_posix()] = hashlib.sha256(
                path.read_bytes()
            ).hexdigest()
    return items


def _rule_count(project: Path) -> int:
    rules = project / ".cursor" / "rules"
    return len(list(rules.glob("*.mdc"))) if rules.is_dir() else 0


class CompositionInstallTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.registry = ComponentRegistry.load()
        cls.resource_root = get_ekp_root()
        cls.version = get_version()

    def _service(self) -> CompositionInstallService:
        return CompositionInstallService(
            registry=self.registry,
            resource_root=self.resource_root,
        )

    def _intent(self, *components: str):
        return build_composition_intent(components, self.registry)

    def _assert_composition_manifest(self, project: Path, expected_rules: int, digest: str):
        manifest = ManifestStore(project).load()
        self.assertIsNotNone(manifest)
        self.assertEqual(manifest.profile, PROJECT_COMPOSITION_PROFILE)
        self.assertEqual(manifest.mode, INSTALL_MODE_COMPOSITION)
        self.assertEqual(manifest.effective_mode, INSTALL_MODE_COMPOSITION)
        self.assertEqual(manifest.adapters, ["cursor"])
        self.assertEqual(manifest.configuration_sha256, digest)
        self.assertEqual(len(manifest.managed_files), expected_rules)
        self.assertTrue(all(m.adapter == "cursor" for m in manifest.managed_files))
        managed_paths = {m.relative_path for m in manifest.managed_files}
        self.assertNotIn(PROJECT_CONFIG_RELATIVE, managed_paths)
        self.assertEqual(_rule_count(project), expected_rules)
        raw = json.loads((project / ".ekp" / "install.json").read_text(encoding="utf-8"))
        self.assertEqual(raw["schema_version"], 1)
        self.assertEqual(raw["mode"], INSTALL_MODE_COMPOSITION)

    def test_symfony_composition_install(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            project.mkdir()
            symfony_fixture(project)
            intent = self._intent("symfony")
            result = self._service().install(project, intent)
            self.assertEqual(result.exit_code, 0, result.message)
            self.assertTrue((project / PROJECT_CONFIG_RELATIVE).is_file())
            self._assert_composition_manifest(project, 83, intent.configuration_sha256)

    def test_symfony_frontend_composition_install(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            project.mkdir()
            symfony_fixture(project)
            frontend_fixture(project)
            intent = self._intent("symfony", "frontend")
            result = self._service().install(project, intent)
            self.assertEqual(result.exit_code, 0, result.message)
            self.assertEqual(
                list(intent.composition.resolved_components),
                ["core", "php", "symfony", "typescript", "frontend"],
            )
            self._assert_composition_manifest(project, 110, intent.configuration_sha256)
            store = ProjectConfigStore(project, registry=self.registry)
            self.assertEqual(
                store.load_snapshot().configuration_sha256,
                intent.configuration_sha256,
            )

    def test_symfony_frontend_devops_composition_install(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            project.mkdir()
            symfony_fixture(project)
            frontend_fixture(project)
            devops_fixture(project)
            intent = self._intent("symfony", "frontend", "devops")
            result = self._service().install(project, intent)
            self.assertEqual(result.exit_code, 0, result.message)
            self._assert_composition_manifest(project, 119, intent.configuration_sha256)
            paths = [m.relative_path for m in result.manifest.managed_files]
            self.assertEqual(len(paths), len(set(paths)))

    def test_matching_existing_config_reused(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            project.mkdir()
            symfony_fixture(project)
            frontend_fixture(project)
            intent = self._intent("symfony", "frontend")
            store = ProjectConfigStore(project, registry=self.registry)
            store.create(
                ProjectConfig(
                    schema_version=1,
                    components=intent.components,
                    assistants=intent.assistants,
                )
            )
            before = (project / PROJECT_CONFIG_RELATIVE).read_bytes()
            result = self._service().install(project, intent)
            self.assertEqual(result.exit_code, 0, result.message)
            self.assertEqual(result.plan.config_action, CONFIG_ACTION_REUSE)
            self.assertEqual((project / PROJECT_CONFIG_RELATIVE).read_bytes(), before)
            self._assert_composition_manifest(project, 110, intent.configuration_sha256)

    def test_semantic_equivalent_config_reused_unchanged(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            project.mkdir()
            symfony_fixture(project)
            frontend_fixture(project)
            intent = self._intent("symfony", "frontend")
            # Different order / comments / redundant dep — same semantic hash.
            yaml_text = (
                "# project intent\n"
                "schema_version: 1\n"
                "assistants:\n"
                "  - cursor\n"
                "components:\n"
                "  - frontend\n"
                "  - symfony\n"
            )
            config_path = project / ".ekp" / "project.yaml"
            config_path.parent.mkdir(parents=True, exist_ok=True)
            config_path.write_text(yaml_text, encoding="utf-8")
            before = config_path.read_bytes()
            result = self._service().install(project, intent)
            self.assertEqual(result.exit_code, 0, result.message)
            self.assertEqual(result.plan.config_action, CONFIG_ACTION_REUSE)
            self.assertEqual(config_path.read_bytes(), before)
            self._assert_composition_manifest(project, 110, intent.configuration_sha256)

    def test_semantic_mismatch_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            project.mkdir()
            symfony_fixture(project)
            intent = self._intent("symfony")
            store = ProjectConfigStore(project, registry=self.registry)
            store.create(
                ProjectConfig(
                    schema_version=1,
                    components=("symfony", "frontend"),
                    assistants=("cursor",),
                )
            )
            before = _fingerprint(project)
            result = self._service().install(project, intent)
            self.assertEqual(result.exit_code, EXIT_CONFLICT, result.message)
            self.assertEqual(_fingerprint(project), before)
            self.assertFalse((project / ".ekp" / "install.json").exists())
            self.assertEqual(_rule_count(project), 0)

    def test_invalid_config_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            project.mkdir()
            symfony_fixture(project)
            intent = self._intent("symfony")
            config_path = project / ".ekp" / "project.yaml"
            config_path.parent.mkdir(parents=True, exist_ok=True)
            config_path.write_text("schema_version: 1\ncomponents: []\n", encoding="utf-8")
            before = config_path.read_bytes()
            result = self._service().install(project, intent)
            self.assertEqual(result.exit_code, EXIT_SELECTION, result.message)
            self.assertEqual(config_path.read_bytes(), before)
            self.assertFalse((project / ".ekp" / "install.json").exists())
            self.assertEqual(_rule_count(project), 0)

    def test_existing_manifest_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            project.mkdir()
            symfony_fixture(project)
            ManifestStore(project).create(
                InstallManifest(
                    schema_version=1,
                    ekp_version=self.version,
                    profile="cursor-symfony",
                    adapters=["cursor"],
                    installed_at="2026-01-01T00:00:00Z",
                    install_root=".",
                    managed_files=[],
                )
            )
            before = _fingerprint(project)
            result = self._service().install(project, self._intent("symfony"))
            self.assertEqual(result.exit_code, EXIT_CONFLICT, result.message)
            self.assertEqual(_fingerprint(project), before)

    def test_rule_collision_preflight(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            project.mkdir()
            symfony_fixture(project)
            # Plant collision using a known cursor-symfony rule name shape.
            # Assemble once via dry-run plan to learn a target name.
            service = self._service()
            intent = self._intent("symfony")
            # Create a likely colliding file name used by symfony profiles.
            rules = project / ".cursor" / "rules"
            rules.mkdir(parents=True, exist_ok=True)
            # Use dry-run first on a sibling project to discover a real rule name.
            sibling = Path(tmp) / "sibling"
            sibling.mkdir()
            dry = service.install(sibling, intent, dry_run=True)
            self.assertEqual(dry.exit_code, 0, dry.message)
            sample = dry.plan.cursor_plan.operations[0].relative_path
            target = project / Path(*sample.split("/"))
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text("user-owned\n", encoding="utf-8")
            before = target.read_bytes()
            result = service.install(project, intent)
            self.assertEqual(result.exit_code, EXIT_CONFLICT, result.message)
            self.assertFalse((project / PROJECT_CONFIG_RELATIVE).exists())
            self.assertFalse((project / ".ekp" / "install.json").exists())
            self.assertEqual(target.read_bytes(), before)

    def test_dry_run_zero_writes(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            project.mkdir()
            symfony_fixture(project)
            frontend_fixture(project)
            before = _fingerprint(project)
            intent = self._intent("symfony", "frontend")
            result = self._service().install(project, intent, dry_run=True)
            self.assertEqual(result.exit_code, 0, result.message)
            self.assertEqual(result.plan.config_action, CONFIG_ACTION_CREATE)
            self.assertEqual(result.plan.rules_count, 110)
            self.assertEqual(result.plan.cursor_plan.profile, PROJECT_COMPOSITION_PROFILE)
            self.assertEqual(result.plan.configuration_sha256, intent.configuration_sha256)
            self.assertIn("mode: composition", result.message)
            self.assertEqual(_fingerprint(project), before)

    def test_failure_rollback(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            project.mkdir()
            symfony_fixture(project)
            intent = self._intent("symfony")
            service = self._service()

            def boom(plan, applied):
                self.assertTrue((project / PROJECT_CONFIG_RELATIVE).is_file())
                self.assertGreater(_rule_count(project), 0)
                raise InstallFilesystemError("injected apply failure")

            service._after_managed_files_hook = boom
            result = service.install(project, intent)
            self.assertNotEqual(result.exit_code, 0, result.message)
            self.assertFalse((project / ".ekp" / "install.json").exists())
            self.assertFalse((project / PROJECT_CONFIG_RELATIVE).exists())
            self.assertEqual(_rule_count(project), 0)

    def test_modified_config_preserved_on_rollback(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            project.mkdir()
            symfony_fixture(project)
            intent = self._intent("symfony")
            service = self._service()
            mutated = b"schema_version: 1\ncomponents:\n  - symfony\nassistants:\n  - cursor\n# mutated\n"

            def mutate_then_fail(plan):
                path = project / PROJECT_CONFIG_RELATIVE
                path.write_bytes(mutated)
                raise InstallFilesystemError("injected after config")

            service._after_config_hook = mutate_then_fail
            result = service.install(project, intent)
            self.assertNotEqual(result.exit_code, 0, result.message)
            self.assertIn("left in place", result.message)
            self.assertEqual((project / PROJECT_CONFIG_RELATIVE).read_bytes(), mutated)
            self.assertFalse((project / ".ekp" / "install.json").exists())
            self.assertEqual(_rule_count(project), 0)

    def test_manifest_race(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            project.mkdir()
            symfony_fixture(project)
            intent = self._intent("symfony")
            service = self._service()
            foreign = InstallManifest(
                schema_version=1,
                ekp_version=self.version,
                profile="cursor-core",
                adapters=["cursor"],
                installed_at="2026-01-01T00:00:00Z",
                install_root=".",
                managed_files=[],
            )

            def plant_manifest(plan, applied):
                ManifestStore(project).save(foreign)

            service._after_managed_files_hook = plant_manifest
            result = service.install(project, intent)
            self.assertEqual(result.exit_code, EXIT_CONFLICT, result.message)
            loaded = ManifestStore(project).load()
            self.assertEqual(loaded.profile, "cursor-core")
            self.assertIsNone(loaded.mode)
            self.assertEqual(_rule_count(project), 0)
            self.assertFalse((project / PROJECT_CONFIG_RELATIVE).exists())

    def test_rule_target_race(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            project.mkdir()
            symfony_fixture(project)
            intent = self._intent("symfony")
            service = self._service()
            planted = {"path": None, "bytes": b"foreign-rule\n"}

            def plant_rule(plan):
                rel = plan.cursor_plan.operations[0].relative_path
                target = project / Path(*rel.split("/"))
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(planted["bytes"])
                planted["path"] = target

            service._after_config_hook = plant_rule
            result = service.install(project, intent)
            self.assertEqual(result.exit_code, EXIT_CONFLICT, result.message)
            self.assertFalse((project / ".ekp" / "install.json").exists())
            self.assertFalse((project / PROJECT_CONFIG_RELATIVE).exists())
            self.assertIsNotNone(planted["path"])
            self.assertEqual(planted["path"].read_bytes(), planted["bytes"])
            # Only the foreign file should remain among rules.
            self.assertEqual(_rule_count(project), 1)

    def test_config_race(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            project.mkdir()
            symfony_fixture(project)
            intent = self._intent("symfony")
            service = self._service()
            foreign = render_project_config_yaml(
                ProjectConfig(
                    schema_version=1,
                    components=("frontend",),
                    assistants=("cursor",),
                )
            ).encode("utf-8")

            # Force create action then plant config after planning via hook on apply.
            # Pre-apply revalidation runs before create; plant during a custom hook
            # by temporarily wrapping _pre_apply_revalidate.
            original = service._pre_apply_revalidate

            def plant_then_validate(plan, store, registry):
                path = project / PROJECT_CONFIG_RELATIVE
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(foreign)
                original(plan, store, registry)

            service._pre_apply_revalidate = plant_then_validate
            result = service.install(project, intent)
            self.assertEqual(result.exit_code, EXIT_CONFLICT, result.message)
            self.assertEqual((project / PROJECT_CONFIG_RELATIVE).read_bytes(), foreign)
            self.assertFalse((project / ".ekp" / "install.json").exists())
            self.assertEqual(_rule_count(project), 0)

    def test_legacy_profile_install_still_works(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            project.mkdir()
            symfony_fixture(project)
            result = InstallService().install(
                InstallRequest(path=str(project), profile="cursor-symfony", assume_yes=True)
            )
            self.assertEqual(result.exit_code, 0, result.message)
            self.assertEqual(_rule_count(project), 83)
            payload = json.loads(
                (project / ".ekp" / "install.json").read_text(encoding="utf-8")
            )
            self.assertEqual(payload["profile"], "cursor-symfony")
            self.assertNotIn("mode", payload)
            self.assertNotIn("configuration_sha256", payload)


if __name__ == "__main__":
    unittest.main()
