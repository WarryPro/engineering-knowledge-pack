"""ConfigureService desired-state engine tests (AY-B; no public CLI)."""

from __future__ import annotations

import hashlib
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from ekp.composition import ComponentRegistry
from ekp.config.project import ProjectConfigStore, render_project_config_yaml
from ekp.install.composition_install import CompositionInstallService
from ekp.install.errors import EXIT_CONFLICT, EXIT_SELECTION, EXIT_SUCCESS
from ekp.install.intent import build_composition_intent
from ekp.install.manifest import ManifestStore
from ekp.lifecycle.apply import TransactionApplier
from ekp.lifecycle.configure import ConfigureRequest, ConfigureService
from ekp.lifecycle.plan import LifecycleOpKind
from ekp.lifecycle.uninstall import UninstallRequest, UninstallService
from ekp.lifecycle.update import UpdateRequest, UpdateService
from ekp.paths import get_ekp_root
from ekp.status.models import StatusState
from ekp.status.service import StatusRequest, StatusService
from ekp.tests.fixtures import frontend_fixture, symfony_fixture
from ekp.version import get_version


def _fingerprint(root: Path):
    items = {}
    for path in sorted(root.rglob("*")):
        if path.is_file():
            items[path.relative_to(root).as_posix()] = hashlib.sha256(
                path.read_bytes()
            ).hexdigest()
    return items


class ConfigureServiceHelpers(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.registry = ComponentRegistry.load()
        cls.resource_root = get_ekp_root()
        cls.version = get_version()

    def _install(self, project: Path, components, assistants):
        intent = build_composition_intent(
            components, self.registry, assistants=assistants
        )
        result = CompositionInstallService(
            registry=self.registry,
            resource_root=self.resource_root,
        ).install(project, intent)
        self.assertEqual(result.exit_code, EXIT_SUCCESS, result.message)
        return intent

    def _status(self, project: Path):
        return StatusService().inspect(StatusRequest(path=str(project)))

    def _service(self) -> ConfigureService:
        return ConfigureService(
            registry=self.registry,
            resource_root=self.resource_root,
        )

    def _configure(self, project: Path, components, assistants, *, dry_run=False):
        return self._service().configure(
            ConfigureRequest(
                path=str(project),
                components=components,
                assistants=assistants,
                dry_run=dry_run,
            )
        )


class ConfigureHappyPathTests(ConfigureServiceHelpers):
    def test_noop_equivalent_intent_preserves_bytes(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            project.mkdir()
            self._install(project, ["core"], ["cursor"])
            path = project / ".ekp" / "project.yaml"
            # Noncanonical formatting with same semantic intent.
            raw = (
                b"# keep\nschema_version: 1\ncomponents: [core]\n"
                b"assistants:\n  - cursor\n"
            )
            path.write_bytes(raw)
            # Re-bind manifest hash to match rewritten config semantics
            # (still same semantic hash as install).
            store = ProjectConfigStore(project, registry=self.registry)
            snap = store.load_file_snapshot()
            manifest = ManifestStore(project).load()
            self.assertEqual(snap.configuration_sha256, manifest.configuration_sha256)
            before = _fingerprint(project)
            result = self._configure(project, ["core"], ["cursor"])
            self.assertEqual(result.exit_code, EXIT_SUCCESS, result.message)
            self.assertTrue(result.noop)
            self.assertEqual(path.read_bytes(), raw)
            self.assertEqual(_fingerprint(project), before)
            self.assertEqual(self._status(project).state, StatusState.HEALTHY)

    def test_noop_ordering_and_redundant_components(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            project.mkdir()
            self._install(project, ["symfony"], ["cursor", "copilot"])
            before = (project / ".ekp" / "project.yaml").read_bytes()
            result = self._configure(
                project,
                ["php", "symfony", "core"],
                ["copilot", "cursor", "cursor"],
            )
            self.assertEqual(result.exit_code, EXIT_SUCCESS, result.message)
            self.assertTrue(result.noop)
            self.assertEqual((project / ".ekp" / "project.yaml").read_bytes(), before)

    def test_assistant_add_core_cursor_to_cursor_copilot(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            project.mkdir()
            self._install(project, ["core"], ["cursor"])
            self.assertEqual(self._status(project).managed_total, 65)
            result = self._configure(project, ["core"], ["cursor", "copilot"])
            self.assertEqual(result.exit_code, EXIT_SUCCESS, result.message)
            status = self._status(project)
            self.assertEqual(status.state, StatusState.HEALTHY)
            self.assertEqual(status.managed_total, 67)
            manifest = ManifestStore(project).load()
            self.assertEqual(set(manifest.adapters), {"copilot", "cursor"})
            cursor = sum(1 for f in manifest.managed_files if f.adapter == "cursor")
            copilot = sum(1 for f in manifest.managed_files if f.adapter == "copilot")
            self.assertEqual(cursor, 65)
            self.assertEqual(copilot, 2)

    def test_assistant_remove_all_four_to_cursor(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            project.mkdir()
            self._install(
                project, ["core"], ["cursor", "copilot", "claude", "antigravity"]
            )
            self.assertEqual(self._status(project).managed_total, 78)
            # Foreign content in assistant dirs must survive.
            foreign = project / ".github" / "workflows" / "build.yml"
            foreign.parent.mkdir(parents=True, exist_ok=True)
            foreign.write_text("name: build\n", encoding="utf-8")
            (project / ".claude" / "settings.json").write_text("{}\n", encoding="utf-8")
            agents = project / ".agents" / "custom"
            agents.mkdir(parents=True, exist_ok=True)
            (agents / "note.txt").write_text("keep\n", encoding="utf-8")
            cursor_custom = project / ".cursor" / "custom"
            cursor_custom.mkdir(parents=True, exist_ok=True)
            (cursor_custom / "x.txt").write_text("keep\n", encoding="utf-8")

            result = self._configure(project, ["core"], ["cursor"])
            self.assertEqual(result.exit_code, EXIT_SUCCESS, result.message)
            status = self._status(project)
            self.assertEqual(status.state, StatusState.HEALTHY)
            self.assertEqual(status.managed_total, 65)
            self.assertEqual(status.adapters, ["cursor"])
            self.assertTrue(foreign.exists())
            self.assertEqual(foreign.read_text(encoding="utf-8"), "name: build\n")
            self.assertTrue((project / ".claude" / "settings.json").exists())
            self.assertTrue((agents / "note.txt").exists())
            self.assertTrue((cursor_custom / "x.txt").exists())

    def test_component_add_symfony_to_sf_fe(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            project.mkdir()
            symfony_fixture(project)
            frontend_fixture(project)
            self._install(project, ["symfony"], ["cursor"])
            self.assertEqual(self._status(project).managed_total, 83)
            result = self._configure(project, ["symfony", "frontend"], ["cursor"])
            self.assertEqual(result.exit_code, EXIT_SUCCESS, result.message)
            status = self._status(project)
            self.assertEqual(status.state, StatusState.HEALTHY)
            self.assertEqual(status.managed_total, 110)
            manifest = ManifestStore(project).load()
            snap = ProjectConfigStore(
                project, registry=self.registry
            ).load_snapshot()
            self.assertEqual(
                manifest.configuration_sha256, snap.configuration_sha256
            )

    def test_component_remove_sf_fe_to_symfony(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            project.mkdir()
            symfony_fixture(project)
            frontend_fixture(project)
            self._install(project, ["symfony", "frontend"], ["cursor"])
            self.assertEqual(self._status(project).managed_total, 110)
            result = self._configure(project, ["symfony"], ["cursor"])
            self.assertEqual(result.exit_code, EXIT_SUCCESS, result.message)
            status = self._status(project)
            self.assertEqual(status.state, StatusState.HEALTHY)
            self.assertEqual(status.managed_total, 83)

    def test_multi_dimension_sf_cursor_to_sf_fe_copilot_claude(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            project.mkdir()
            symfony_fixture(project)
            frontend_fixture(project)
            self._install(project, ["symfony"], ["cursor"])
            result = self._configure(
                project, ["symfony", "frontend"], ["copilot", "claude"]
            )
            self.assertEqual(result.exit_code, EXIT_SUCCESS, result.message)
            status = self._status(project)
            self.assertEqual(status.state, StatusState.HEALTHY)
            self.assertEqual(status.managed_total, 16)
            self.assertEqual(set(status.adapters), {"claude", "copilot"})
            self.assertNotIn("cursor", status.adapters)
            rules = project / ".cursor" / "rules"
            if rules.exists():
                self.assertEqual(list(rules.glob("*.mdc")), [])


class ConfigureRefusalTests(ConfigureServiceHelpers):
    def test_empty_assistants_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            project.mkdir()
            self._install(project, ["core"], ["cursor"])
            before = _fingerprint(project)
            result = self._configure(project, ["core"], [])
            self.assertEqual(result.exit_code, EXIT_SELECTION)
            self.assertEqual(_fingerprint(project), before)

    def test_empty_components_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            project.mkdir()
            self._install(project, ["core"], ["cursor"])
            before = _fingerprint(project)
            result = self._configure(project, [], ["cursor"])
            self.assertEqual(result.exit_code, EXIT_SELECTION)
            self.assertEqual(_fingerprint(project), before)

    def test_unknown_assistant_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            project.mkdir()
            self._install(project, ["core"], ["cursor"])
            before = _fingerprint(project)
            result = self._configure(project, ["core"], ["not-an-assistant"])
            self.assertEqual(result.exit_code, EXIT_SELECTION)
            self.assertEqual(_fingerprint(project), before)

    def test_unknown_component_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            project.mkdir()
            self._install(project, ["core"], ["cursor"])
            before = _fingerprint(project)
            result = self._configure(project, ["nope"], ["cursor"])
            self.assertEqual(result.exit_code, EXIT_SELECTION)
            self.assertEqual(_fingerprint(project), before)

    def test_not_installed_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            project.mkdir()
            result = self._configure(project, ["core"], ["cursor"])
            self.assertEqual(result.exit_code, EXIT_SELECTION)

    def test_legacy_refused(self):
        from ekp.install.service import InstallRequest, InstallService

        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            project.mkdir()
            outcome = InstallService().install(
                InstallRequest(
                    path=str(project),
                    profile="cursor-core",
                    assume_yes=True,
                )
            )
            self.assertEqual(outcome.exit_code, EXIT_SUCCESS, outcome.message)
            before = _fingerprint(project)
            result = self._configure(project, ["core"], ["cursor"])
            self.assertEqual(result.exit_code, EXIT_SELECTION)
            self.assertIn("composition", result.message.lower())
            self.assertEqual(_fingerprint(project), before)

    def test_version_mismatch_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            project.mkdir()
            self._install(project, ["core"], ["cursor"])
            store = ManifestStore(project)
            snap = store.load_with_fingerprint()
            manifest = snap.manifest
            mutated = type(manifest)(
                schema_version=manifest.schema_version,
                ekp_version="0.0.0",
                profile=manifest.profile,
                adapters=list(manifest.adapters),
                installed_at=manifest.installed_at,
                install_root=manifest.install_root,
                managed_files=list(manifest.managed_files),
                created_directories=list(manifest.created_directories),
                mode=manifest.mode,
                configuration_sha256=manifest.configuration_sha256,
            )
            store.replace(mutated, expected_sha256=snap.sha256)
            before = _fingerprint(project)
            result = self._configure(project, ["core"], ["cursor", "copilot"])
            self.assertEqual(result.exit_code, EXIT_SELECTION)
            self.assertEqual(_fingerprint(project), before)

    def test_incomplete_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            project.mkdir()
            self._install(project, ["core"], ["cursor"])
            managed = ManifestStore(project).load().managed_files[0]
            target = project / Path(managed.relative_path.replace("/", os.sep))
            target.unlink()
            before = _fingerprint(project)
            result = self._configure(project, ["core"], ["cursor", "copilot"])
            self.assertEqual(result.exit_code, EXIT_SELECTION)
            self.assertEqual(_fingerprint(project), before)

    def test_modified_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            project.mkdir()
            self._install(project, ["core"], ["cursor"])
            managed = ManifestStore(project).load().managed_files[0]
            target = project / Path(managed.relative_path.replace("/", os.sep))
            target.write_text(target.read_text(encoding="utf-8") + "\n# edited\n", encoding="utf-8")
            before = _fingerprint(project)
            result = self._configure(project, ["core"], ["cursor", "copilot"])
            self.assertEqual(result.exit_code, EXIT_SELECTION)
            self.assertEqual(_fingerprint(project), before)

    def test_configuration_drift_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            project.mkdir()
            self._install(project, ["core"], ["cursor"])
            (project / ".ekp" / "project.yaml").write_text(
                "schema_version: 1\ncomponents:\n  - symfony\nassistants:\n  - cursor\n",
                encoding="utf-8",
            )
            before = _fingerprint(project)
            result = self._configure(project, ["core"], ["cursor"])
            self.assertEqual(result.exit_code, EXIT_SELECTION)
            self.assertEqual(_fingerprint(project), before)

    def test_unmanaged_new_target_collision(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            project.mkdir()
            self._install(project, ["core"], ["cursor"])
            claude = project / "CLAUDE.md"
            claude.write_text("# foreign\n", encoding="utf-8")
            before = _fingerprint(project)
            result = self._configure(project, ["core"], ["cursor", "claude"])
            self.assertEqual(result.exit_code, EXIT_CONFLICT, result.message)
            self.assertEqual(_fingerprint(project), before)
            self.assertEqual(claude.read_text(encoding="utf-8"), "# foreign\n")

    def test_modified_delete_protection(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            project.mkdir()
            self._install(project, ["core"], ["cursor", "claude"])
            claude = project / "CLAUDE.md"
            claude.write_text(claude.read_text(encoding="utf-8") + "\n# user\n", encoding="utf-8")
            # Eligibility catches MODIFIED first.
            before = _fingerprint(project)
            result = self._configure(project, ["core"], ["cursor"])
            self.assertEqual(result.exit_code, EXIT_SELECTION)
            self.assertEqual(_fingerprint(project), before)


class ConfigureRaceAndDryRunTests(ConfigureServiceHelpers):
    def test_dry_run_zero_writes_and_temp_cleanup(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            project.mkdir()
            self._install(project, ["core"], ["cursor"])
            before = _fingerprint(project)
            result = self._configure(
                project, ["core"], ["cursor", "copilot"], dry_run=True
            )
            self.assertEqual(result.exit_code, EXIT_SUCCESS, result.message)
            self.assertFalse(result.noop)
            self.assertIsNotNone(result.plan)
            self.assertGreater(result.plan.create_count, 0)
            self.assertEqual(_fingerprint(project), before)
            if result.prepared is not None:
                self.assertTrue(result.prepared._closed)

    def test_plan_apply_same_plan_boundary(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            project.mkdir()
            self._install(project, ["core"], ["cursor"])
            service = self._service()
            prepared_result = service.prepare(
                ConfigureRequest(
                    path=str(project),
                    components=["core"],
                    assistants=["cursor", "copilot"],
                )
            )
            self.assertEqual(prepared_result.exit_code, EXIT_SUCCESS)
            plan_id = id(prepared_result.prepared.plan)
            apply_result = service.apply(prepared_result.prepared)
            self.assertEqual(apply_result.exit_code, EXIT_SUCCESS, apply_result.message)
            self.assertEqual(id(apply_result.plan), plan_id)
            self.assertEqual(self._status(project).managed_total, 67)

    def test_config_race_between_plan_and_apply(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            project.mkdir()
            self._install(project, ["core"], ["cursor"])
            service = self._service()
            prepared_result = service.prepare(
                ConfigureRequest(
                    path=str(project),
                    components=["core"],
                    assistants=["cursor", "copilot"],
                )
            )
            self.assertEqual(prepared_result.exit_code, EXIT_SUCCESS)
            # Whitespace-only change: same semantic, different physical bytes.
            path = project / ".ekp" / "project.yaml"
            path.write_bytes(path.read_bytes() + b"\n")
            before = _fingerprint(project)
            apply_result = service.apply(prepared_result.prepared)
            self.assertNotEqual(apply_result.exit_code, EXIT_SUCCESS)
            self.assertEqual(_fingerprint(project), before)

    def test_manifest_race_between_plan_and_apply(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            project.mkdir()
            self._install(project, ["core"], ["cursor"])
            service = self._service()
            prepared_result = service.prepare(
                ConfigureRequest(
                    path=str(project),
                    components=["core"],
                    assistants=["cursor", "copilot"],
                )
            )
            self.assertEqual(prepared_result.exit_code, EXIT_SUCCESS)
            store = ManifestStore(project)
            snap = store.load_with_fingerprint()
            manifest = snap.manifest
            store.replace(manifest, expected_sha256=snap.sha256)
            # replace rewrites bytes → fingerprint changes even if content equal
            # Force a real mutation:
            mutated = type(manifest)(
                schema_version=manifest.schema_version,
                ekp_version=manifest.ekp_version,
                profile=manifest.profile,
                adapters=list(manifest.adapters),
                installed_at="1999-01-01T00:00:00Z",
                install_root=manifest.install_root,
                managed_files=list(manifest.managed_files),
                created_directories=list(manifest.created_directories),
                mode=manifest.mode,
                configuration_sha256=manifest.configuration_sha256,
            )
            store.replace(mutated, expected_sha256=store.load_with_fingerprint().sha256)
            yaml_before = (project / ".ekp" / "project.yaml").read_bytes()
            apply_result = service.apply(prepared_result.prepared)
            self.assertNotEqual(apply_result.exit_code, EXIT_SUCCESS)
            self.assertEqual(
                (project / ".ekp" / "project.yaml").read_bytes(), yaml_before
            )

    def test_create_write_delete_races(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            project.mkdir()
            self._install(project, ["core"], ["cursor"])
            service = self._service()

            # CREATE race: place unmanaged file on a future Copilot path after plan.
            prepared = service.prepare(
                ConfigureRequest(
                    path=str(project),
                    components=["core"],
                    assistants=["cursor", "copilot"],
                )
            )
            self.assertEqual(prepared.exit_code, EXIT_SUCCESS)
            create_ops = [
                op
                for op in prepared.plan.operations
                if op.kind == LifecycleOpKind.CREATE
            ]
            self.assertTrue(create_ops)
            target = project / Path(create_ops[0].relative_path.replace("/", os.sep))
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text("foreign\n", encoding="utf-8")
            yaml_before = (project / ".ekp" / "project.yaml").read_bytes()
            apply_result = service.apply(prepared.prepared)
            self.assertNotEqual(apply_result.exit_code, EXIT_SUCCESS)
            self.assertEqual(
                (project / ".ekp" / "project.yaml").read_bytes(), yaml_before
            )

        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            project.mkdir()
            symfony_fixture(project)
            frontend_fixture(project)
            self._install(project, ["symfony"], ["cursor"])
            service = self._service()
            prepared = service.prepare(
                ConfigureRequest(
                    path=str(project),
                    components=["symfony", "frontend"],
                    assistants=["cursor"],
                )
            )
            self.assertEqual(prepared.exit_code, EXIT_SUCCESS)
            write_ops = [
                op
                for op in prepared.plan.operations
                if op.kind == LifecycleOpKind.WRITE
            ]
            if write_ops:
                target = project / Path(
                    write_ops[0].relative_path.replace("/", os.sep)
                )
                target.write_text(
                    target.read_text(encoding="utf-8") + "x", encoding="utf-8"
                )
                apply_result = service.apply(prepared.prepared)
                self.assertNotEqual(apply_result.exit_code, EXIT_SUCCESS)
            else:
                # Synthesize a WRITE race against an existing managed NOOP target.
                noop_ops = [
                    op
                    for op in prepared.plan.operations
                    if op.kind == LifecycleOpKind.NOOP and op.previous_sha256
                ]
                self.assertTrue(noop_ops)
                op = noop_ops[0]
                target = project / Path(op.relative_path.replace("/", os.sep))
                bogus = project / ".ekp" / "bogus-source.mdc"
                bogus.write_text("bogus-new\n", encoding="utf-8")
                from ekp.install.deploy.hashing import sha256_file
                from ekp.lifecycle.plan import LifecycleFileOperation

                prepared.plan.operations = [
                    LifecycleFileOperation(
                        relative_path=op.relative_path,
                        kind=LifecycleOpKind.WRITE,
                        adapter=op.adapter,
                        previous_sha256=op.previous_sha256,
                        expected_sha256=sha256_file(bogus),
                        source_path=bogus,
                    )
                    if item is op
                    else item
                    for item in prepared.plan.operations
                ]
                target.write_text(
                    target.read_text(encoding="utf-8") + "race\n", encoding="utf-8"
                )
                apply_result = service.apply(prepared.prepared)
                self.assertNotEqual(apply_result.exit_code, EXIT_SUCCESS)

        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            project.mkdir()
            self._install(project, ["core"], ["cursor", "copilot"])
            service = self._service()
            prepared = service.prepare(
                ConfigureRequest(
                    path=str(project),
                    components=["core"],
                    assistants=["cursor"],
                )
            )
            self.assertEqual(prepared.exit_code, EXIT_SUCCESS)
            delete_ops = [
                op
                for op in prepared.plan.operations
                if op.kind == LifecycleOpKind.DELETE
            ]
            self.assertTrue(delete_ops)
            target = project / Path(delete_ops[0].relative_path.replace("/", os.sep))
            target.write_text(
                target.read_text(encoding="utf-8") + "mut\n", encoding="utf-8"
            )
            apply_result = service.apply(prepared.prepared)
            self.assertNotEqual(apply_result.exit_code, EXIT_SUCCESS)


class ConfigureLifecycleParityTests(ConfigureServiceHelpers):
    def test_configure_twice_then_noop(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            project.mkdir()
            symfony_fixture(project)
            frontend_fixture(project)
            self._install(project, ["core"], ["cursor"])
            r1 = self._configure(project, ["symfony"], ["cursor"])
            self.assertEqual(r1.exit_code, EXIT_SUCCESS, r1.message)
            self.assertEqual(self._status(project).managed_total, 83)
            r2 = self._configure(project, ["symfony", "frontend"], ["cursor"])
            self.assertEqual(r2.exit_code, EXIT_SUCCESS, r2.message)
            self.assertEqual(self._status(project).managed_total, 110)
            before = (project / ".ekp" / "project.yaml").read_bytes()
            r3 = self._configure(project, ["frontend", "symfony"], ["cursor"])
            self.assertEqual(r3.exit_code, EXIT_SUCCESS, r3.message)
            self.assertTrue(r3.noop)
            self.assertEqual(
                (project / ".ekp" / "project.yaml").read_bytes(), before
            )

    def test_update_after_configure_healthy_noop(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            project.mkdir()
            self._install(project, ["core"], ["cursor"])
            result = self._configure(project, ["core"], ["cursor", "copilot"])
            self.assertEqual(result.exit_code, EXIT_SUCCESS, result.message)
            update = UpdateService().update(
                UpdateRequest(path=str(project), assume_yes=True)
            )
            self.assertEqual(update.exit_code, EXIT_SUCCESS, update.message)
            self.assertEqual(self._status(project).state, StatusState.HEALTHY)
            self.assertEqual(self._status(project).managed_total, 67)

    def test_uninstall_after_configure(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            project.mkdir()
            self._install(project, ["core"], ["cursor"])
            result = self._configure(project, ["core"], ["cursor", "copilot"])
            self.assertEqual(result.exit_code, EXIT_SUCCESS, result.message)
            uninstall = UninstallService().uninstall(
                UninstallRequest(path=str(project), assume_yes=True)
            )
            self.assertEqual(uninstall.exit_code, EXIT_SUCCESS, uninstall.message)
            self.assertFalse(ManifestStore(project).exists())
            self.assertTrue((project / ".ekp" / "project.yaml").exists())
            # New ownership removed; no managed Copilot instruction files remain.
            instructions = project / ".github" / "instructions"
            if instructions.exists():
                self.assertEqual(
                    [p for p in instructions.rglob("*") if p.is_file()],
                    [],
                )

    def test_no_redetect(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            project.mkdir()
            self._install(project, ["core"], ["cursor"])
            # Inject technology markers that must not affect configure.
            (project / "composer.json").write_text(
                '{"require":{"symfony/framework-bundle":"^6.0"}}\n',
                encoding="utf-8",
            )
            (project / "package.json").write_text(
                '{"dependencies":{"react":"18.0.0"}}\n', encoding="utf-8"
            )
            result = self._configure(project, ["core"], ["copilot"])
            self.assertEqual(result.exit_code, EXIT_SUCCESS, result.message)
            status = self._status(project)
            self.assertEqual(status.managed_total, 2)
            self.assertEqual(status.adapters, ["copilot"])
            snap = ProjectConfigStore(project, registry=self.registry).load_snapshot()
            self.assertEqual(list(snap.config.components), ["core"])


class ConfigurePublicPresenceTests(unittest.TestCase):
    def test_cli_exposes_configure(self):
        import inspect

        from ekp import cli

        source = inspect.getsource(cli)
        self.assertRegex(source, r'add_parser\(\s*"configure"')

    def test_configure_service_is_lifecycle_not_cli(self):
        from ekp.lifecycle.configure import ConfigureService as CS

        self.assertTrue(callable(CS().configure))
        self.assertTrue(callable(CS().inspect))
        self.assertTrue(callable(CS().prepare))
        self.assertTrue(callable(CS().apply))


if __name__ == "__main__":
    unittest.main()
