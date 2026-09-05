"""Multi-assistant composition lifecycle tests (AX-D; no public --assistant)."""

from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from ekp.composition import PROJECT_COMPOSITION_PROFILE, ComponentRegistry
from ekp.config import PROJECT_CONFIG_RELATIVE, ProjectConfig, ProjectConfigStore
from ekp.config.project import render_project_config_yaml
from ekp.install.composition_install import CompositionInstallService
from ekp.install.deploy.models import DesiredManagedFile
from ekp.install.errors import (
    EXIT_CONFLICT,
    EXIT_SUCCESS,
    InstallAssemblyError,
    InstallConflictError,
)
from ekp.install.intent import build_composition_intent
from ekp.install.manifest import (
    INSTALL_MODE_COMPOSITION,
    InstallManifest,
    ManagedFile,
    ManifestStore,
)
from ekp.lifecycle.plan import LifecycleOpKind
from ekp.lifecycle.uninstall import UninstallRequest, UninstallService, validate_lifecycle_manifest
from ekp.lifecycle.update import UpdateRequest, UpdateService, build_update_plan
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


class MultiAssistantLifecycleHelpers(unittest.TestCase):
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

    def _update(self, project: Path, *, dry_run=False):
        return UpdateService().update(
            UpdateRequest(path=str(project), assume_yes=True, dry_run=dry_run)
        )

    def _uninstall(self, project: Path):
        return UninstallService().uninstall(
            UninstallRequest(path=str(project), assume_yes=True)
        )


class MultiAssistantStatusTests(MultiAssistantLifecycleHelpers):
    def test_copilot_only_core_healthy(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            project.mkdir()
            self._install(project, ["core"], ["copilot"])
            result = self._status(project)
            self.assertEqual(result.state, StatusState.HEALTHY)
            self.assertEqual(result.managed_total, 2)
            self.assertEqual(result.adapters, ["copilot"])
            self.assertEqual(result.assistants, ["copilot"])
            self.assertFalse(result.configuration_drift)

    def test_claude_only_core_healthy(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            project.mkdir()
            self._install(project, ["core"], ["claude"])
            result = self._status(project)
            self.assertEqual(result.state, StatusState.HEALTHY)
            self.assertEqual(result.managed_total, 5)
            self.assertEqual(result.adapters, ["claude"])

    def test_antigravity_only_core_healthy(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            project.mkdir()
            self._install(project, ["core"], ["antigravity"])
            result = self._status(project)
            self.assertEqual(result.state, StatusState.HEALTHY)
            self.assertEqual(result.managed_total, 6)
            self.assertEqual(result.adapters, ["antigravity"])

    def test_all_four_core_healthy(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            project.mkdir()
            self._install(
                project,
                ["core"],
                ["cursor", "copilot", "claude", "antigravity"],
            )
            result = self._status(project)
            self.assertEqual(result.state, StatusState.HEALTHY)
            self.assertEqual(result.managed_total, 78)
            self.assertEqual(
                result.adapters, ["antigravity", "claude", "copilot", "cursor"]
            )
            self.assertEqual(
                set(result.assistants),
                {"antigravity", "claude", "copilot", "cursor"},
            )
            self.assertFalse(result.configuration_drift)

    def test_all_four_sf_fe_healthy(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            project.mkdir()
            symfony_fixture(project)
            frontend_fixture(project)
            self._install(
                project,
                ["symfony", "frontend"],
                ["cursor", "copilot", "claude", "antigravity"],
            )
            result = self._status(project)
            self.assertEqual(result.state, StatusState.HEALTHY)
            self.assertEqual(result.managed_total, 137)
            self.assertEqual(
                set(result.resolved_components),
                {"core", "php", "symfony", "typescript", "frontend"},
            )

    def test_missing_copilot_file_incomplete(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            project.mkdir()
            self._install(
                project,
                ["core"],
                ["cursor", "copilot", "claude", "antigravity"],
            )
            target = project / ".github" / "copilot-instructions.md"
            self.assertTrue(target.is_file())
            target.unlink()
            result = self._status(project)
            self.assertEqual(result.state, StatusState.INCOMPLETE)
            self.assertIn(".github/copilot-instructions.md", result.missing_paths)

    def test_modified_claude_md_modified(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            project.mkdir()
            self._install(
                project,
                ["core"],
                ["cursor", "copilot", "claude", "antigravity"],
            )
            (project / "CLAUDE.md").write_text("user edit\n", encoding="utf-8")
            result = self._status(project)
            self.assertEqual(result.state, StatusState.MODIFIED)
            self.assertIn("CLAUDE.md", result.modified_paths)

    def test_assistant_add_configuration_drift(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            project.mkdir()
            self._install(project, ["core"], ["cursor"])
            store = ProjectConfigStore(project, registry=self.registry)
            cfg = store.load()
            drifted = ProjectConfig(
                schema_version=cfg.schema_version,
                components=cfg.components,
                assistants=("cursor", "copilot"),
            )
            (project / PROJECT_CONFIG_RELATIVE).write_text(
                render_project_config_yaml(drifted), encoding="utf-8"
            )
            result = self._status(project)
            self.assertEqual(result.state, StatusState.CONFIGURATION_DRIFT)
            self.assertTrue(result.configuration_drift)
            update = self._update(project)
            self.assertEqual(update.exit_code, EXIT_CONFLICT)
            self.assertFalse((project / ".github" / "copilot-instructions.md").exists())

    def test_assistant_remove_configuration_drift(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            project.mkdir()
            self._install(project, ["core"], ["cursor", "copilot"])
            store = ProjectConfigStore(project, registry=self.registry)
            cfg = store.load()
            drifted = ProjectConfig(
                schema_version=cfg.schema_version,
                components=cfg.components,
                assistants=("cursor",),
            )
            (project / PROJECT_CONFIG_RELATIVE).write_text(
                render_project_config_yaml(drifted), encoding="utf-8"
            )
            result = self._status(project)
            self.assertEqual(result.state, StatusState.CONFIGURATION_DRIFT)
            update = self._update(project)
            self.assertEqual(update.exit_code, EXIT_CONFLICT)
            self.assertTrue((project / ".github" / "copilot-instructions.md").is_file())

    def test_unsupported_manifest_adapter_invalid(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            project.mkdir()
            self._install(project, ["core"], ["cursor"])
            store = ManifestStore(project)
            manifest = store.load()
            payload = json.loads(
                (project / ".ekp" / "install.json").read_text(encoding="utf-8")
            )
            payload["adapters"] = ["unknown-ai"]
            for item in payload["managed_files"]:
                item["adapter"] = "unknown-ai"
            (project / ".ekp" / "install.json").write_text(
                json.dumps(payload, indent=2) + "\n", encoding="utf-8"
            )
            before = _fingerprint(project)
            result = self._status(project)
            self.assertEqual(result.state, StatusState.INVALID)
            self.assertEqual(before, _fingerprint(project))

    def test_manifest_file_adapter_mismatch_invalid(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            project.mkdir()
            self._install(project, ["core"], ["cursor", "copilot"])
            payload = json.loads(
                (project / ".ekp" / "install.json").read_text(encoding="utf-8")
            )
            payload["managed_files"][0]["adapter"] = "claude"
            (project / ".ekp" / "install.json").write_text(
                json.dumps(payload, indent=2) + "\n", encoding="utf-8"
            )
            result = self._status(project)
            self.assertEqual(result.state, StatusState.INVALID)

    def test_manifest_adapter_lacking_managed_ownership_invalid(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            project.mkdir()
            self._install(project, ["core"], ["cursor", "copilot"])
            payload = json.loads(
                (project / ".ekp" / "install.json").read_text(encoding="utf-8")
            )
            payload["managed_files"] = [
                item
                for item in payload["managed_files"]
                if item["adapter"] == "cursor"
            ]
            (project / ".ekp" / "install.json").write_text(
                json.dumps(payload, indent=2) + "\n", encoding="utf-8"
            )
            result = self._status(project)
            self.assertEqual(result.state, StatusState.INVALID)

    def test_config_only_not_installed(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            project.mkdir()
            store = ProjectConfigStore(project, registry=self.registry)
            store.create(
                ProjectConfig(
                    schema_version=1,
                    components=("core",),
                    assistants=("cursor",),
                )
            )
            result = self._status(project)
            self.assertEqual(result.state, StatusState.NOT_INSTALLED)

    def test_assistant_order_difference_healthy(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            project.mkdir()
            intent = self._install(project, ["core"], ["copilot", "claude"])
            # Rewrite YAML with reverse assistant order; semantic hash must match.
            cfg = ProjectConfig(
                schema_version=1,
                components=("core",),
                assistants=("claude", "copilot"),
            )
            yaml_text = render_project_config_yaml(cfg)
            (project / PROJECT_CONFIG_RELATIVE).write_text(yaml_text, encoding="utf-8")
            snap = ProjectConfigStore(project, registry=self.registry).load_snapshot()
            self.assertEqual(snap.configuration_sha256, intent.configuration_sha256)
            result = self._status(project)
            self.assertEqual(result.state, StatusState.HEALTHY)


class MultiAssistantUpdateTests(MultiAssistantLifecycleHelpers):
    def test_single_non_cursor_noop(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            project.mkdir()
            self._install(project, ["core"], ["copilot"])
            before = (project / ".ekp" / "install.json").read_bytes()
            result = self._update(project)
            self.assertEqual(result.exit_code, EXIT_SUCCESS, result.message)
            self.assertEqual((project / ".ekp" / "install.json").read_bytes(), before)
            self.assertEqual(self._status(project).state, StatusState.HEALTHY)

    def test_all_four_noop(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            project.mkdir()
            self._install(
                project,
                ["core"],
                ["cursor", "copilot", "claude", "antigravity"],
            )
            before = (project / ".ekp" / "install.json").read_bytes()
            before_fp = _fingerprint(project)
            dry = self._update(project, dry_run=True)
            self.assertEqual(dry.exit_code, EXIT_SUCCESS)
            self.assertIn("Assistants:", dry.message)
            self.assertEqual(before_fp, _fingerprint(project))
            result = self._update(project)
            self.assertEqual(result.exit_code, EXIT_SUCCESS, result.message)
            self.assertEqual((project / ".ekp" / "install.json").read_bytes(), before)
            self.assertEqual(before_fp, _fingerprint(project))

    def test_multi_adapter_repair(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            project.mkdir()
            self._install(
                project,
                ["core"],
                ["cursor", "copilot", "claude", "antigravity"],
            )
            copilot = project / ".github" / "copilot-instructions.md"
            skill = next((project / ".claude" / "skills").rglob("*"))
            while skill.is_dir():
                skill = next(skill.iterdir())
            copilot.unlink()
            skill.unlink()
            self.assertEqual(self._status(project).state, StatusState.INCOMPLETE)
            before_manifest = (project / ".ekp" / "install.json").read_bytes()
            cursor_rule = next((project / ".cursor" / "rules").glob("*.mdc"))
            cursor_bytes = cursor_rule.read_bytes()
            result = self._update(project)
            self.assertEqual(result.exit_code, EXIT_SUCCESS, result.message)
            self.assertTrue(copilot.is_file())
            self.assertTrue(skill.is_file())
            self.assertEqual(self._status(project).state, StatusState.HEALTHY)
            self.assertEqual(
                (project / ".ekp" / "install.json").read_bytes(), before_manifest
            )
            self.assertEqual(cursor_rule.read_bytes(), cursor_bytes)

    def test_claude_md_root_repair(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            project.mkdir()
            self._install(project, ["core"], ["claude"])
            target = project / "CLAUDE.md"
            target.unlink()
            result = self._update(project)
            self.assertEqual(result.exit_code, EXIT_SUCCESS, result.message)
            self.assertTrue(target.is_file())
            self.assertEqual(self._status(project).state, StatusState.HEALTHY)

    def test_managed_modification_refuses(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            project.mkdir()
            self._install(
                project,
                ["core"],
                ["cursor", "copilot", "claude", "antigravity"],
            )
            before = _fingerprint(project)
            (project / "CLAUDE.md").write_text("tampered\n", encoding="utf-8")
            result = self._update(project)
            self.assertEqual(result.exit_code, EXIT_CONFLICT)
            # Restore fingerprint check excluding the intentionally modified file.
            after = _fingerprint(project)
            self.assertEqual(
                {k: v for k, v in before.items() if k != "CLAUDE.md"},
                {k: v for k, v in after.items() if k != "CLAUDE.md"},
            )

    def test_no_redetect_on_update(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            project.mkdir()
            symfony_fixture(project)
            self._install(project, ["symfony"], ["copilot", "claude"])
            yaml_before = (project / PROJECT_CONFIG_RELATIVE).read_bytes()
            frontend_fixture(project)
            (project / "pubspec.yaml").write_text("name: x\n", encoding="utf-8")
            (project / "Dockerfile").write_text("FROM scratch\n", encoding="utf-8")
            result = self._update(project)
            self.assertEqual(result.exit_code, EXIT_SUCCESS, result.message)
            cfg = ProjectConfigStore(project, registry=self.registry).load()
            self.assertEqual(list(cfg.components), ["symfony"])
            self.assertEqual(set(cfg.assistants), {"claude", "copilot"})
            self.assertEqual((project / PROJECT_CONFIG_RELATIVE).read_bytes(), yaml_before)
            status = self._status(project)
            self.assertEqual(status.state, StatusState.HEALTHY)
            self.assertEqual(set(status.requested_components), {"symfony"})

    def test_synthetic_cross_version_plan_matrix(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            project = root / "project"
            project.mkdir()
            bundle = root / "bundle"
            (bundle / "cursor").mkdir(parents=True)
            (bundle / "copilot").mkdir(parents=True)
            (bundle / "antigravity").mkdir(parents=True)
            (project / ".cursor" / "rules").mkdir(parents=True)
            (project / ".cursor" / "rules" / "a.mdc").write_bytes(b"cursor-old\n")
            (project / ".claude" / "skills").mkdir(parents=True)
            (project / ".claude" / "skills" / "gone.md").write_bytes(b"claude-old\n")
            (project / ".agents" / "rules").mkdir(parents=True)
            (project / ".agents" / "rules" / "keep.md").write_bytes(b"same\n")
            (bundle / "cursor" / "a.mdc").write_bytes(b"cursor-new\n")
            (bundle / "copilot" / "new.md").write_bytes(b"copilot-new\n")
            (bundle / "antigravity" / "keep.md").write_bytes(b"same\n")

            def digest(path: Path) -> str:
                return hashlib.sha256(path.read_bytes()).hexdigest()

            cursor_old = hashlib.sha256(b"cursor-old\n").hexdigest()
            claude_old = hashlib.sha256(b"claude-old\n").hexdigest()
            anti_same = digest(bundle / "antigravity" / "keep.md")

            manifest = InstallManifest(
                schema_version=1,
                ekp_version="0.18.0",
                profile=PROJECT_COMPOSITION_PROFILE,
                adapters=["antigravity", "claude", "cursor"],
                installed_at="2026-01-01T00:00:00Z",
                install_root=".",
                managed_files=[
                    ManagedFile(
                        relative_path=".cursor/rules/a.mdc",
                        adapter="cursor",
                        sha256=cursor_old,
                    ),
                    ManagedFile(
                        relative_path=".claude/skills/gone.md",
                        adapter="claude",
                        sha256=claude_old,
                    ),
                    ManagedFile(
                        relative_path=".agents/rules/keep.md",
                        adapter="antigravity",
                        sha256=anti_same,
                    ),
                ],
                mode=INSTALL_MODE_COMPOSITION,
                configuration_sha256="a" * 64,
            )
            ManifestStore(project).save(manifest)
            snapshot = ManifestStore(project).load_with_fingerprint()

            desired = [
                DesiredManagedFile(
                    relative_path=".cursor/rules/a.mdc",
                    adapter="cursor",
                    source_path=bundle / "cursor" / "a.mdc",
                    sha256=digest(bundle / "cursor" / "a.mdc"),
                ),
                DesiredManagedFile(
                    relative_path=".github/instructions/new.instructions.md",
                    adapter="copilot",
                    source_path=bundle / "copilot" / "new.md",
                    sha256=digest(bundle / "copilot" / "new.md"),
                ),
                DesiredManagedFile(
                    relative_path=".agents/rules/keep.md",
                    adapter="antigravity",
                    source_path=bundle / "antigravity" / "keep.md",
                    sha256=anti_same,
                ),
            ]
            plan = build_update_plan(
                project_root=project,
                snapshot=snapshot,
                running_version=self.version,
                desired=desired,
                bundle_path=bundle,
            )
            by_path = {op.relative_path: op for op in plan.operations}
            self.assertEqual(by_path[".cursor/rules/a.mdc"].kind, LifecycleOpKind.WRITE)
            self.assertEqual(by_path[".cursor/rules/a.mdc"].adapter, "cursor")
            self.assertEqual(
                by_path[".github/instructions/new.instructions.md"].kind,
                LifecycleOpKind.CREATE,
            )
            self.assertEqual(
                by_path[".github/instructions/new.instructions.md"].adapter, "copilot"
            )
            self.assertEqual(
                by_path[".claude/skills/gone.md"].kind, LifecycleOpKind.DELETE
            )
            self.assertEqual(by_path[".claude/skills/gone.md"].adapter, "claude")
            self.assertEqual(
                by_path[".agents/rules/keep.md"].kind, LifecycleOpKind.NOOP
            )
            self.assertEqual(by_path[".agents/rules/keep.md"].adapter, "antigravity")
            self.assertIn(".github/instructions", plan.directories_to_create)
            self.assertTrue(plan.commit_manifest)
            self.assertEqual(
                plan.new_manifest.adapters,
                ["antigravity", "copilot", "cursor"],
            )

    def test_same_version_adapter_ownership_immutability(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            project = root / "project"
            project.mkdir()
            bundle = root / "bundle"
            (bundle / "cursor").mkdir(parents=True)
            (bundle / "cursor" / "a.mdc").write_text("same\n", encoding="utf-8")
            digest = hashlib.sha256(b"same\n").hexdigest()
            (project / ".cursor" / "rules").mkdir(parents=True)
            (project / ".cursor" / "rules" / "a.mdc").write_text(
                "same\n", encoding="utf-8"
            )
            manifest = InstallManifest(
                schema_version=1,
                ekp_version=self.version,
                profile=PROJECT_COMPOSITION_PROFILE,
                adapters=["cursor"],
                installed_at="2026-01-01T00:00:00Z",
                install_root=".",
                managed_files=[
                    ManagedFile(
                        relative_path=".cursor/rules/a.mdc",
                        adapter="cursor",
                        sha256=digest,
                    )
                ],
                mode=INSTALL_MODE_COMPOSITION,
                configuration_sha256="b" * 64,
            )
            ManifestStore(project).save(manifest)
            snapshot = ManifestStore(project).load_with_fingerprint()
            # Same bytes/path but claimed under copilot — must refuse.
            desired = [
                DesiredManagedFile(
                    relative_path=".cursor/rules/a.mdc",
                    adapter="copilot",
                    source_path=bundle / "cursor" / "a.mdc",
                    sha256=digest,
                )
            ]
            with self.assertRaises(InstallAssemblyError):
                build_update_plan(
                    project_root=project,
                    snapshot=snapshot,
                    running_version=self.version,
                    desired=desired,
                    bundle_path=bundle,
                )

    def test_v018_cursor_composition_migration(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            project.mkdir()
            symfony_fixture(project)
            intent = build_composition_intent(
                ["symfony"], self.registry, assistants=["cursor"]
            )
            result = CompositionInstallService(
                registry=self.registry,
                resource_root=self.resource_root,
            ).install(project, intent)
            self.assertEqual(result.exit_code, EXIT_SUCCESS)
            yaml_bytes = (project / PROJECT_CONFIG_RELATIVE).read_bytes()
            bound_hash = ManifestStore(project).load().configuration_sha256
            payload = json.loads(
                (project / ".ekp" / "install.json").read_text(encoding="utf-8")
            )
            payload["ekp_version"] = "0.18.0"
            (project / ".ekp" / "install.json").write_text(
                json.dumps(payload, indent=2) + "\n", encoding="utf-8"
            )
            status = self._status(project)
            self.assertEqual(status.state, StatusState.VERSION_MISMATCH)
            dry = self._update(project, dry_run=True)
            self.assertEqual(dry.exit_code, EXIT_SUCCESS)
            update = self._update(project)
            self.assertEqual(update.exit_code, EXIT_SUCCESS, update.message)
            manifest = ManifestStore(project).load()
            self.assertEqual(manifest.ekp_version, self.version)
            self.assertEqual(manifest.adapters, ["cursor"])
            self.assertEqual(manifest.configuration_sha256, bound_hash)
            self.assertEqual((project / PROJECT_CONFIG_RELATIVE).read_bytes(), yaml_bytes)
            self.assertFalse((project / ".github").exists())
            self.assertFalse((project / "CLAUDE.md").exists())
            self.assertFalse((project / ".agents").exists())
            self.assertEqual(self._status(project).state, StatusState.HEALTHY)
            self.assertEqual(len(manifest.managed_files), 83)

    def test_v018_sf_fe_cursor_migration(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            project.mkdir()
            symfony_fixture(project)
            frontend_fixture(project)
            intent = build_composition_intent(
                ["symfony", "frontend"], self.registry, assistants=["cursor"]
            )
            result = CompositionInstallService(
                registry=self.registry,
                resource_root=self.resource_root,
            ).install(project, intent)
            self.assertEqual(result.exit_code, EXIT_SUCCESS)
            payload = json.loads(
                (project / ".ekp" / "install.json").read_text(encoding="utf-8")
            )
            self.assertEqual(len(payload["managed_files"]), 110)
            payload["ekp_version"] = "0.18.0"
            (project / ".ekp" / "install.json").write_text(
                json.dumps(payload, indent=2) + "\n", encoding="utf-8"
            )
            update = self._update(project)
            self.assertEqual(update.exit_code, EXIT_SUCCESS, update.message)
            manifest = ManifestStore(project).load()
            self.assertEqual(manifest.adapters, ["cursor"])
            self.assertEqual(len(manifest.managed_files), 110)
            self.assertEqual(self._status(project).state, StatusState.HEALTHY)

    def test_multi_adapter_rollback(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            project.mkdir()
            self._install(project, ["core"], ["copilot", "claude"])
            payload = json.loads(
                (project / ".ekp" / "install.json").read_text(encoding="utf-8")
            )
            payload["ekp_version"] = "0.18.0"
            # Force a CREATE by removing a managed file before cross-version update.
            (project / "CLAUDE.md").unlink()
            (project / ".ekp" / "install.json").write_text(
                json.dumps(payload, indent=2) + "\n", encoding="utf-8"
            )
            before = _fingerprint(project)
            fp = ManifestStore(project).load_with_fingerprint().sha256

            def failing_replace(self_, manifest, expected_sha256):
                raise InstallConflictError("manifest race")

            with mock.patch.object(ManifestStore, "replace", failing_replace):
                result = self._update(project)
            self.assertEqual(result.exit_code, EXIT_CONFLICT)
            self.assertEqual(
                ManifestStore(project).load_with_fingerprint().sha256, fp
            )
            # CLAUDE.md may have been created then rolled back.
            after = _fingerprint(project)
            self.assertEqual(before, after)

    def test_config_toctou_refuses_and_rolls_back(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            project.mkdir()
            self._install(project, ["core"], ["copilot", "claude"])
            payload = json.loads(
                (project / ".ekp" / "install.json").read_text(encoding="utf-8")
            )
            payload["ekp_version"] = "0.18.0"
            (project / "CLAUDE.md").unlink()
            (project / ".ekp" / "install.json").write_text(
                json.dumps(payload, indent=2) + "\n", encoding="utf-8"
            )
            before = _fingerprint(project)
            from ekp.lifecycle.apply import TransactionApplier

            original = TransactionApplier._revalidate_composition_config
            calls = {"n": 0}

            def drift_revalidate(self_, plan):
                calls["n"] += 1
                if calls["n"] >= 2:
                    cfg = ProjectConfig(
                        schema_version=1,
                        components=("core",),
                        assistants=("cursor",),
                    )
                    (project / PROJECT_CONFIG_RELATIVE).write_text(
                        render_project_config_yaml(cfg), encoding="utf-8"
                    )
                original(self_, plan)

            with mock.patch.object(
                TransactionApplier, "_revalidate_composition_config", drift_revalidate
            ):
                result = self._update(project)
            self.assertEqual(result.exit_code, EXIT_CONFLICT)
            # Managed ownership restored; config intentionally drifted mid-flight.
            after = _fingerprint(project)
            self.assertEqual(
                {k: v for k, v in before.items() if k != PROJECT_CONFIG_RELATIVE},
                {k: v for k, v in after.items() if k != PROJECT_CONFIG_RELATIVE},
            )
            self.assertEqual(
                self._status(project).state, StatusState.CONFIGURATION_DRIFT
            )

    def test_target_race_copilot_create_refuses(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            project.mkdir()
            self._install(project, ["core"], ["copilot"])
            payload = json.loads(
                (project / ".ekp" / "install.json").read_text(encoding="utf-8")
            )
            payload["ekp_version"] = "0.18.0"
            target = project / ".github" / "copilot-instructions.md"
            target.unlink()
            (project / ".ekp" / "install.json").write_text(
                json.dumps(payload, indent=2) + "\n", encoding="utf-8"
            )
            before_manifest = (project / ".ekp" / "install.json").read_bytes()

            from ekp.lifecycle.apply import TransactionApplier

            original_create = TransactionApplier._apply_create

            def raced_create(self_, plan, operation, created):
                target.write_text("foreign race winner\n", encoding="utf-8")
                return original_create(self_, plan, operation, created)

            with mock.patch.object(TransactionApplier, "_apply_create", raced_create):
                result = self._update(project)
            self.assertEqual(result.exit_code, EXIT_CONFLICT)
            self.assertEqual(
                (project / ".ekp" / "install.json").read_bytes(), before_manifest
            )
            self.assertEqual(
                target.read_text(encoding="utf-8"), "foreign race winner\n"
            )


class MultiAssistantUninstallTests(MultiAssistantLifecycleHelpers):
    def test_copilot_only_uninstall(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            project.mkdir()
            self._install(project, ["core"], ["copilot"])
            result = self._uninstall(project)
            self.assertEqual(result.exit_code, EXIT_SUCCESS, result.message)
            self.assertFalse((project / ".ekp" / "install.json").exists())
            self.assertTrue((project / PROJECT_CONFIG_RELATIVE).is_file())
            self.assertFalse((project / ".github" / "copilot-instructions.md").exists())
            self.assertEqual(self._status(project).state, StatusState.NOT_INSTALLED)

    def test_claude_only_uninstall(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            project.mkdir()
            self._install(project, ["core"], ["claude"])
            result = self._uninstall(project)
            self.assertEqual(result.exit_code, EXIT_SUCCESS)
            self.assertFalse((project / "CLAUDE.md").exists())
            self.assertTrue((project / PROJECT_CONFIG_RELATIVE).is_file())

    def test_antigravity_only_uninstall(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            project.mkdir()
            self._install(project, ["core"], ["antigravity"])
            result = self._uninstall(project)
            self.assertEqual(result.exit_code, EXIT_SUCCESS)
            rules = project / ".agents" / "rules"
            self.assertTrue(not rules.exists() or not any(rules.iterdir()))

    def test_all_four_uninstall(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            project.mkdir()
            self._install(
                project,
                ["core"],
                ["cursor", "copilot", "claude", "antigravity"],
            )
            (project / ".github" / "workflows").mkdir(parents=True)
            (project / ".github" / "workflows" / "ci.yml").write_text("x\n", encoding="utf-8")
            (project / ".claude" / "settings.json").write_text("{}\n", encoding="utf-8")
            (project / ".claude" / "custom-user-file").write_text("u\n", encoding="utf-8")
            (project / ".agents" / "workflows").mkdir(parents=True)
            (project / ".agents" / "workflows" / "w.yml").write_text("w\n", encoding="utf-8")
            (project / ".cursor" / "custom-user-file").write_text("c\n", encoding="utf-8")
            result = self._uninstall(project)
            self.assertEqual(result.exit_code, EXIT_SUCCESS, result.message)
            self.assertFalse((project / ".ekp" / "install.json").exists())
            self.assertTrue((project / PROJECT_CONFIG_RELATIVE).is_file())
            self.assertTrue((project / ".ekp").is_dir())
            self.assertTrue((project / ".github" / "workflows" / "ci.yml").is_file())
            self.assertTrue((project / ".claude" / "settings.json").is_file())
            self.assertTrue((project / ".claude" / "custom-user-file").is_file())
            self.assertTrue((project / ".agents" / "workflows" / "w.yml").is_file())
            self.assertTrue((project / ".cursor" / "custom-user-file").is_file())
            self.assertEqual(self._status(project).state, StatusState.NOT_INSTALLED)

    def test_sf_fe_all_four_uninstall(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            project.mkdir()
            symfony_fixture(project)
            frontend_fixture(project)
            self._install(
                project,
                ["symfony", "frontend"],
                ["cursor", "copilot", "claude", "antigravity"],
            )
            count = len(ManifestStore(project).load().managed_files)
            self.assertEqual(count, 137)
            result = self._uninstall(project)
            self.assertEqual(result.exit_code, EXIT_SUCCESS, result.message)
            self.assertFalse((project / ".ekp" / "install.json").exists())
            self.assertTrue((project / PROJECT_CONFIG_RELATIVE).is_file())

    def test_copilot_claude_subset_lifecycle(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            project.mkdir()
            symfony_fixture(project)
            frontend_fixture(project)
            self._install(project, ["symfony", "frontend"], ["copilot", "claude"])
            manifest = ManifestStore(project).load()
            self.assertEqual(len(manifest.managed_files), 16)
            self.assertEqual(manifest.adapters, ["claude", "copilot"])
            self.assertFalse((project / ".cursor").exists())
            self.assertEqual(self._status(project).state, StatusState.HEALTHY)
            (project / ".github" / "copilot-instructions.md").unlink()
            self.assertEqual(self._status(project).state, StatusState.INCOMPLETE)
            self.assertEqual(self._update(project).exit_code, EXIT_SUCCESS)
            self.assertEqual(self._status(project).state, StatusState.HEALTHY)
            self.assertEqual(self._uninstall(project).exit_code, EXIT_SUCCESS)
            self.assertEqual(self._status(project).state, StatusState.NOT_INSTALLED)

    def test_modified_claude_md_uninstall_refuse(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            project.mkdir()
            self._install(project, ["core"], ["claude"])
            (project / "CLAUDE.md").write_text("user\n", encoding="utf-8")
            before = _fingerprint(project)
            result = self._uninstall(project)
            self.assertEqual(result.exit_code, EXIT_CONFLICT)
            self.assertEqual(before, _fingerprint(project))

    def test_modified_copilot_uninstall_refuse(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            project.mkdir()
            self._install(project, ["core"], ["copilot"])
            path = project / ".github" / "copilot-instructions.md"
            path.write_text("user\n", encoding="utf-8")
            before = _fingerprint(project)
            result = self._uninstall(project)
            self.assertEqual(result.exit_code, EXIT_CONFLICT)
            self.assertEqual(before, _fingerprint(project))

    def test_incomplete_install_uninstall_recovery(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            project.mkdir()
            self._install(project, ["core"], ["copilot", "claude"])
            (project / ".github" / "copilot-instructions.md").unlink()
            result = self._uninstall(project)
            self.assertEqual(result.exit_code, EXIT_SUCCESS, result.message)
            self.assertFalse((project / ".ekp" / "install.json").exists())
            self.assertFalse((project / "CLAUDE.md").exists())

    def test_uninstall_config_independence(self):
        cases = ("healthy", "drifted", "invalid", "missing")
        for case in cases:
            with self.subTest(case=case):
                with tempfile.TemporaryDirectory() as tmp:
                    project = Path(tmp) / "project"
                    project.mkdir()
                    self._install(project, ["core"], ["copilot"])
                    config_path = project / PROJECT_CONFIG_RELATIVE
                    if case == "drifted":
                        cfg = ProjectConfig(
                            schema_version=1,
                            components=("core",),
                            assistants=("cursor",),
                        )
                        config_path.write_text(
                            render_project_config_yaml(cfg), encoding="utf-8"
                        )
                    elif case == "invalid":
                        config_path.write_text("not: valid: yaml: [\n", encoding="utf-8")
                    elif case == "missing":
                        config_path.unlink()
                    result = self._uninstall(project)
                    self.assertEqual(result.exit_code, EXIT_SUCCESS, result.message)
                    self.assertFalse((project / ".ekp" / "install.json").exists())

    def test_composition_multi_adapter_manifest_valid(self):
        digest = "a" * 64
        manifest = InstallManifest(
            schema_version=1,
            ekp_version="0.19.0.dev0",
            profile=PROJECT_COMPOSITION_PROFILE,
            adapters=["claude", "copilot"],
            installed_at="2026-01-01T00:00:00Z",
            install_root=".",
            managed_files=[
                ManagedFile(
                    relative_path=".github/copilot-instructions.md",
                    adapter="copilot",
                    sha256=digest,
                ),
                ManagedFile(
                    relative_path="CLAUDE.md",
                    adapter="claude",
                    sha256=digest,
                ),
            ],
            mode=INSTALL_MODE_COMPOSITION,
            configuration_sha256=digest,
        )
        validate_lifecycle_manifest(manifest)


class MultiAssistantFullLifecycleTests(MultiAssistantLifecycleHelpers):
    def test_v017_legacy_symfony_migration(self):
        from ekp.install.service import InstallRequest, InstallService

        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            project.mkdir()
            symfony_fixture(project)
            result = InstallService().install(
                InstallRequest(
                    path=str(project),
                    assume_yes=True,
                    profile="cursor-symfony",
                )
            )
            self.assertEqual(result.exit_code, EXIT_SUCCESS, result.message)
            self.assertFalse((project / PROJECT_CONFIG_RELATIVE).exists())
            payload = json.loads(
                (project / ".ekp" / "install.json").read_text(encoding="utf-8")
            )
            self.assertEqual(payload["profile"], "cursor-symfony")
            self.assertNotIn("mode", payload)
            payload["ekp_version"] = "0.17.0"
            (project / ".ekp" / "install.json").write_text(
                json.dumps(payload, indent=2) + "\n", encoding="utf-8"
            )
            status = self._status(project)
            self.assertEqual(status.state, StatusState.VERSION_MISMATCH)
            self.assertEqual(status.mode, "legacy-profile")
            update = self._update(project)
            self.assertEqual(update.exit_code, EXIT_SUCCESS, update.message)
            manifest = ManifestStore(project).load()
            self.assertEqual(manifest.ekp_version, self.version)
            self.assertEqual(manifest.profile, "cursor-symfony")
            self.assertEqual(manifest.effective_mode, "legacy-profile")
            self.assertEqual(manifest.adapters, ["cursor"])
            self.assertEqual(len(manifest.managed_files), 83)
            self.assertFalse((project / PROJECT_CONFIG_RELATIVE).exists())
            self.assertEqual(self._status(project).state, StatusState.HEALTHY)

    def test_single_non_cursor_full_lifecycle(self):
        for assistant, expected in (
            ("copilot", 2),
            ("claude", 5),
            ("antigravity", 6),
        ):
            with self.subTest(assistant=assistant):
                with tempfile.TemporaryDirectory() as tmp:
                    project = Path(tmp) / "project"
                    project.mkdir()
                    self._install(project, ["core"], [assistant])
                    self.assertEqual(self._status(project).managed_total, expected)
                    self.assertEqual(self._status(project).state, StatusState.HEALTHY)
                    self.assertEqual(
                        self._update(project, dry_run=True).exit_code, EXIT_SUCCESS
                    )
                    self.assertEqual(self._update(project).exit_code, EXIT_SUCCESS)
                    self.assertFalse((project / ".cursor").exists())
                    self.assertEqual(self._uninstall(project).exit_code, EXIT_SUCCESS)
                    self.assertEqual(
                        self._status(project).state, StatusState.NOT_INSTALLED
                    )

    def test_all_four_core_full_lifecycle(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            project.mkdir()
            self._install(
                project,
                ["core"],
                ["cursor", "copilot", "claude", "antigravity"],
            )
            self.assertEqual(self._status(project).managed_total, 78)
            self.assertEqual(self._update(project).exit_code, EXIT_SUCCESS)
            (project / ".github" / "copilot-instructions.md").unlink()
            self.assertEqual(self._update(project).exit_code, EXIT_SUCCESS)
            self.assertEqual(self._status(project).state, StatusState.HEALTHY)
            self.assertEqual(self._uninstall(project).exit_code, EXIT_SUCCESS)
            self.assertEqual(self._status(project).state, StatusState.NOT_INSTALLED)


if __name__ == "__main__":
    unittest.main()
