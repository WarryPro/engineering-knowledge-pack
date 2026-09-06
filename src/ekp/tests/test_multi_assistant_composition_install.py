"""Internal multi-assistant composition install tests (AX-C; no public CLI)."""

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
from ekp.install.errors import EXIT_CONFLICT, EXIT_SUCCESS, InstallConflictError
from ekp.install.intent import build_composition_intent
from ekp.install.manifest import (
    INSTALL_MODE_COMPOSITION,
    InstallManifest,
    ManifestStore,
)
from ekp.install.service import InstallRequest, InstallService
from ekp.paths import get_ekp_root
from ekp.tests.fixtures import frontend_fixture, symfony_fixture


def _count_under(project: Path, pattern: str) -> int:
    return len(list(project.glob(pattern)))


def _fingerprint(root: Path):
    items = {}
    for path in sorted(root.rglob("*")):
        if path.is_file():
            items[path.relative_to(root).as_posix()] = hashlib.sha256(
                path.read_bytes()
            ).hexdigest()
    return items


class MultiAssistantCompositionInstallTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.registry = ComponentRegistry.load()
        cls.resource_root = get_ekp_root()

    def _service(self) -> CompositionInstallService:
        return CompositionInstallService(
            registry=self.registry,
            resource_root=self.resource_root,
        )

    def _install(self, project: Path, components, assistants):
        intent = build_composition_intent(
            components, self.registry, assistants=assistants
        )
        return self._service().install(project, intent), intent

    def test_copilot_only_core(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            project.mkdir()
            result, intent = self._install(project, ["core"], ["copilot"])
            self.assertEqual(result.exit_code, EXIT_SUCCESS)
            manifest = ManifestStore(project).load()
            self.assertEqual(manifest.adapters, ["copilot"])
            self.assertEqual(manifest.mode, INSTALL_MODE_COMPOSITION)
            self.assertEqual(len(manifest.managed_files), 2)
            self.assertTrue(all(m.adapter == "copilot" for m in manifest.managed_files))
            self.assertFalse((project / ".cursor").exists())
            self.assertTrue((project / ".github" / "copilot-instructions.md").is_file())
            cfg = ProjectConfigStore(project, registry=self.registry).load()
            self.assertEqual(cfg.assistants, ("copilot",))
            self.assertEqual(manifest.configuration_sha256, intent.configuration_sha256)

    def test_claude_only_core(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            project.mkdir()
            result, _ = self._install(project, ["core"], ["claude"])
            self.assertEqual(result.exit_code, EXIT_SUCCESS)
            manifest = ManifestStore(project).load()
            self.assertEqual(manifest.adapters, ["claude"])
            self.assertEqual(len(manifest.managed_files), 5)
            self.assertTrue((project / "CLAUDE.md").is_file())
            self.assertGreaterEqual(
                _count_under(project, ".claude/skills/*/SKILL.md"), 1
            )
            self.assertFalse((project / ".cursor").exists())

    def test_antigravity_only_core(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            project.mkdir()
            result, _ = self._install(project, ["core"], ["antigravity"])
            self.assertEqual(result.exit_code, EXIT_SUCCESS)
            manifest = ManifestStore(project).load()
            self.assertEqual(manifest.adapters, ["antigravity"])
            self.assertEqual(len(manifest.managed_files), 6)
            self.assertGreaterEqual(_count_under(project, ".agents/rules/*.md"), 1)
            self.assertFalse((project / ".cursor").exists())

    def test_all_four_core(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            project.mkdir()
            result, intent = self._install(
                project,
                ["core"],
                ["antigravity", "claude", "copilot", "cursor"],
            )
            self.assertEqual(result.exit_code, EXIT_SUCCESS)
            manifest = ManifestStore(project).load()
            self.assertEqual(
                manifest.adapters, ["antigravity", "claude", "copilot", "cursor"]
            )
            self.assertEqual(len(manifest.managed_files), 78)
            self.assertEqual(result.plan.managed_file_count, 78)
            self.assertEqual(result.plan.assistant_counts["cursor"], 65)
            self.assertEqual(result.plan.assistant_counts["copilot"], 2)
            self.assertEqual(result.plan.assistant_counts["claude"], 5)
            self.assertEqual(result.plan.assistant_counts["antigravity"], 6)
            cfg = ProjectConfigStore(project, registry=self.registry).load()
            self.assertEqual(
                set(cfg.assistants),
                {"antigravity", "claude", "copilot", "cursor"},
            )
            self.assertEqual(manifest.configuration_sha256, intent.configuration_sha256)

    def test_all_four_symfony_frontend(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            project.mkdir()
            result, intent = self._install(
                project,
                ["symfony", "frontend"],
                ["cursor", "copilot", "claude", "antigravity"],
            )
            self.assertEqual(result.exit_code, EXIT_SUCCESS)
            self.assertEqual(
                list(intent.composition.resolved_components),
                ["core", "php", "symfony", "typescript", "frontend"],
            )
            manifest = ManifestStore(project).load()
            self.assertEqual(len(manifest.managed_files), 137)
            self.assertEqual(result.plan.assistant_counts["cursor"], 110)
            self.assertEqual(result.plan.assistant_counts["copilot"], 6)
            self.assertEqual(result.plan.assistant_counts["claude"], 10)
            self.assertEqual(result.plan.assistant_counts["antigravity"], 11)
            paths = [m.relative_path for m in manifest.managed_files]
            self.assertEqual(len(paths), len(set(paths)))

    def test_copilot_claude_subset_sf_fe(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            project.mkdir()
            result, _ = self._install(
                project, ["symfony", "frontend"], ["copilot", "claude"]
            )
            self.assertEqual(result.exit_code, EXIT_SUCCESS)
            manifest = ManifestStore(project).load()
            self.assertEqual(manifest.adapters, ["claude", "copilot"])
            self.assertEqual(len(manifest.managed_files), 16)
            self.assertFalse((project / ".cursor").exists())
            self.assertFalse((project / ".agents").exists())
            self.assertEqual(result.plan.assistant_counts["copilot"], 6)
            self.assertEqual(result.plan.assistant_counts["claude"], 10)

    def test_assistant_order_equivalence_install(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            a_project = root / "a"
            b_project = root / "b"
            a_project.mkdir()
            b_project.mkdir()
            result_a, intent_a = self._install(
                a_project,
                ["core"],
                ["cursor", "copilot", "claude"],
            )
            result_b, intent_b = self._install(
                b_project,
                ["core"],
                ["claude", "cursor", "copilot"],
            )
            self.assertEqual(result_a.exit_code, EXIT_SUCCESS)
            self.assertEqual(result_b.exit_code, EXIT_SUCCESS)
            self.assertEqual(intent_a.configuration_sha256, intent_b.configuration_sha256)
            self.assertEqual(intent_a.assistants, intent_b.assistants)
            ma = ManifestStore(a_project).load()
            mb = ManifestStore(b_project).load()
            self.assertEqual(ma.adapters, mb.adapters)
            self.assertEqual(
                sorted(m.relative_path for m in ma.managed_files),
                sorted(m.relative_path for m in mb.managed_files),
            )

    def test_matching_multi_assistant_config_reuse(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            project.mkdir()
            intent = build_composition_intent(
                ["symfony", "frontend"],
                self.registry,
                assistants=["claude", "copilot"],
            )
            store = ProjectConfigStore(project, registry=self.registry)
            # Persist in non-canonical YAML order; semantic hash still matches.
            config = ProjectConfig(
                schema_version=1,
                components=("symfony", "frontend"),
                assistants=("copilot", "claude"),
            )
            store.create(config)
            before = (project / PROJECT_CONFIG_RELATIVE).read_bytes()
            result = self._service().install(project, intent)
            self.assertEqual(result.exit_code, EXIT_SUCCESS)
            self.assertEqual(result.plan.config_action, CONFIG_ACTION_REUSE)
            self.assertEqual((project / PROJECT_CONFIG_RELATIVE).read_bytes(), before)
            self.assertEqual(ManifestStore(project).load().adapters, ["claude", "copilot"])

    def test_assistant_mismatch_refusal(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            project.mkdir()
            store = ProjectConfigStore(project, registry=self.registry)
            store.create(
                ProjectConfig(
                    schema_version=1,
                    components=("symfony",),
                    assistants=("cursor", "copilot"),
                )
            )
            before = _fingerprint(project)
            intent = build_composition_intent(
                ["symfony"], self.registry, assistants=["cursor"]
            )
            result = self._service().install(project, intent)
            self.assertEqual(result.exit_code, EXIT_CONFLICT)
            self.assertFalse((project / ".ekp" / "install.json").exists())
            self.assertEqual(_fingerprint(project), before)

    def test_target_collision_refuses_entire_install(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            project.mkdir()
            (project / "CLAUDE.md").write_text("user\n", encoding="utf-8")
            before = _fingerprint(project)
            result, _ = self._install(
                project,
                ["core"],
                ["antigravity", "claude", "copilot", "cursor"],
            )
            self.assertEqual(result.exit_code, EXIT_CONFLICT)
            self.assertFalse((project / ".ekp" / "install.json").exists())
            self.assertFalse((project / ".cursor").exists())
            self.assertFalse((project / ".github" / "copilot-instructions.md").exists())
            self.assertFalse((project / ".agents").exists())
            self.assertEqual((project / "CLAUDE.md").read_text(encoding="utf-8"), "user\n")
            self.assertEqual(_fingerprint(project), before)

    def test_partial_apply_rollback(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            project.mkdir()
            foreign = project / ".github" / "workflows" / "ci.yml"
            foreign.parent.mkdir(parents=True)
            foreign.write_text("name: ci\n", encoding="utf-8")
            service = self._service()
            intent = build_composition_intent(
                ["core"],
                self.registry,
                assistants=["copilot", "claude"],
            )

            def _fail_after_files(plan, applied):
                raise InstallConflictError("controlled multi-assistant failure")

            service._after_managed_files_hook = _fail_after_files
            result = service.install(project, intent)
            self.assertEqual(result.exit_code, EXIT_CONFLICT)
            self.assertFalse((project / ".ekp" / "install.json").exists())
            self.assertFalse((project / "CLAUDE.md").exists())
            self.assertFalse((project / ".github" / "copilot-instructions.md").exists())
            self.assertEqual(foreign.read_text(encoding="utf-8"), "name: ci\n")

    def test_config_race(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            project.mkdir()
            service = self._service()
            intent = build_composition_intent(
                ["core"], self.registry, assistants=["copilot"]
            )

            def _inject_config(plan):
                # Appears after planning CREATE; _pre_apply already passed — inject via
                # hook is after create. Use a dry plan race instead:
                pass

            # Race: create config between plan and apply by planning then writing.
            dry = service.install(project, intent, dry_run=True)
            self.assertEqual(dry.exit_code, EXIT_SUCCESS)
            self.assertEqual(dry.plan.config_action, CONFIG_ACTION_CREATE)
            (project / ".ekp").mkdir(parents=True, exist_ok=True)
            (project / PROJECT_CONFIG_RELATIVE).write_text(
                render_project_config_yaml(
                    ProjectConfig(
                        schema_version=1,
                        components=("core",),
                        assistants=("cursor",),
                    )
                ),
                encoding="utf-8",
            )
            before = _fingerprint(project)
            result = service.install(project, intent)
            self.assertEqual(result.exit_code, EXIT_CONFLICT)
            self.assertFalse((project / ".ekp" / "install.json").exists())
            self.assertFalse((project / ".github" / "copilot-instructions.md").exists())
            self.assertEqual(_fingerprint(project), before)

    def test_manifest_race(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            project.mkdir()
            service = self._service()
            intent = build_composition_intent(
                ["core"], self.registry, assistants=["copilot"]
            )

            def _inject_manifest(plan, applied):
                ManifestStore(project).create(
                    InstallManifest(
                        schema_version=1,
                        ekp_version="0.19.0.dev0",
                        profile=PROJECT_COMPOSITION_PROFILE,
                        adapters=["copilot"],
                        installed_at="2026-01-01T00:00:00Z",
                        install_root=".",
                        managed_files=[],
                        mode=INSTALL_MODE_COMPOSITION,
                        configuration_sha256=intent.configuration_sha256,
                    )
                )

            service._after_managed_files_hook = _inject_manifest
            result = service.install(project, intent)
            self.assertEqual(result.exit_code, EXIT_CONFLICT)
            # Foreign/injected manifest preserved; managed files rolled back.
            self.assertTrue((project / ".ekp" / "install.json").is_file())
            self.assertFalse((project / ".github" / "copilot-instructions.md").exists())

    def test_target_race_non_cursor(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            project.mkdir()
            service = self._service()
            intent = build_composition_intent(
                ["core"], self.registry, assistants=["copilot"]
            )
            dry = service.install(project, intent, dry_run=True)
            self.assertEqual(dry.exit_code, EXIT_SUCCESS)
            target = project / ".github" / "copilot-instructions.md"
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text("race-winner\n", encoding="utf-8")
            result = service.install(project, intent)
            self.assertEqual(result.exit_code, EXIT_CONFLICT)
            self.assertEqual(target.read_text(encoding="utf-8"), "race-winner\n")
            self.assertFalse((project / ".ekp" / "install.json").exists())

    def test_public_cli_default_remains_cursor_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            project.mkdir()
            symfony_fixture(project)
            frontend_fixture(project)
            result = InstallService().install(
                InstallRequest(
                    path=str(project),
                    components=["symfony", "frontend"],
                    assume_yes=True,
                )
            )
            self.assertEqual(result.exit_code, EXIT_SUCCESS)
            manifest = ManifestStore(project).load()
            self.assertEqual(manifest.adapters, ["cursor"])
            self.assertEqual(len(manifest.managed_files), 110)
            self.assertFalse((project / "CLAUDE.md").exists())
            self.assertFalse((project / ".github" / "copilot-instructions.md").exists())
            self.assertFalse((project / ".agents").exists())

    def test_public_cli_all_four_assistants(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            project.mkdir()
            symfony_fixture(project)
            frontend_fixture(project)
            result = InstallService().install(
                InstallRequest(
                    path=str(project),
                    components=["symfony", "frontend"],
                    assistants=["cursor", "copilot", "claude", "antigravity"],
                    assume_yes=True,
                )
            )
            self.assertEqual(result.exit_code, EXIT_SUCCESS, result.message)
            manifest = ManifestStore(project).load()
            self.assertEqual(
                manifest.adapters, ["antigravity", "claude", "copilot", "cursor"]
            )
            self.assertEqual(len(manifest.managed_files), 137)


if __name__ == "__main__":
    unittest.main()
