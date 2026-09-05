"""All-four deployer infrastructure tests (no public Consumer install)."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from ekp.assembly import AssemblyService, CompositionAssemblyRequest
from ekp.install.deploy.engine import SharedDeploymentEngine
from ekp.install.deploy.hashing import sha256_file
from ekp.install.deploy.models import DesiredManagedFile
from ekp.install.deploy.registry import build_default_deploy_registry
from ekp.install.errors import InstallAssemblyError, InstallConflictError
from ekp.install.plan import InstallPlan
from ekp.paths import get_ekp_root


ALL_FOUR = ("cursor", "copilot", "claude", "antigravity")


def _write(path: Path, body: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")


def _collect_all(registry, bundle: Path, engine: SharedDeploymentEngine):
    desired = []
    for assistant_id in ALL_FOUR:
        desired.extend(registry.get(assistant_id).collect_desired_files(bundle))
    return engine.normalize_desired_files(desired)


class AllFourDeployInfraTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.registry = build_default_deploy_registry()
        cls.engine = SharedDeploymentEngine()
        cls.resource_root = get_ekp_root()

    def _assemble(self, components, output: Path):
        return AssemblyService().assemble_composition(
            CompositionAssemblyRequest(
                components=list(components),
                outputs=list(ALL_FOUR),
                verify=True,
                resource_root=self.resource_root,
                workspace_dir=output / "workspace",
                output_root=output / "output",
            )
        )

    def _install_plan(self, project, ops, dirs, conflicts=None):
        return InstallPlan(
            project_root=project,
            profile="infra-test",
            ekp_version="0.19.0.dev0",
            adapter="multi",
            bundle_path=project,
            rules_count=len(ops),
            operations=ops,
            conflicts=list(conflicts or []),
            directories_to_create=dirs,
        )

    def test_registry_contains_all_four(self):
        self.assertEqual(
            self.registry.supported_assistants(),
            ("antigravity", "claude", "copilot", "cursor"),
        )

    def test_core_all_four_unique_targets(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = self._assemble(["core"], Path(tmp))
            desired = _collect_all(self.registry, result.bundle_path, self.engine)
            paths = [item.relative_path for item in desired]
            self.assertEqual(len(paths), len(set(paths)))
            by_adapter = {}
            for item in desired:
                by_adapter.setdefault(item.adapter, []).append(item.relative_path)
            for assistant_id in ALL_FOUR:
                self.assertIn(assistant_id, by_adapter)
                self.assertGreater(len(by_adapter[assistant_id]), 0)
            # Store observed counts on the instance for report tooling if needed
            self.__class__.core_counts = {
                k: len(v) for k, v in sorted(by_adapter.items())
            }
            self.__class__.core_total = len(desired)

    def test_symfony_frontend_all_four_unique_and_cursor_110(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = self._assemble(["symfony", "frontend"], Path(tmp))
            self.assertEqual(
                list(result.composition.resolved_components),
                ["core", "php", "symfony", "typescript", "frontend"],
            )
            desired = _collect_all(self.registry, result.bundle_path, self.engine)
            paths = [item.relative_path for item in desired]
            self.assertEqual(len(paths), len(set(paths)))
            by_adapter = {}
            for item in desired:
                by_adapter.setdefault(item.adapter, 0)
                by_adapter[item.adapter] += 1
            self.assertEqual(by_adapter["cursor"], 110)
            self.__class__.sf_fe_counts = dict(sorted(by_adapter.items()))
            self.__class__.sf_fe_total = len(desired)

    def test_clean_project_all_four_dry_plan(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            result = self._assemble(["core"], root / "asm")
            project = root / "project"
            project.mkdir()
            desired = _collect_all(self.registry, result.bundle_path, self.engine)
            ops, conflicts = self.engine.plan_first_install(project, desired)
            self.assertEqual(conflicts, [])
            self.assertEqual(len(ops), len(desired))
            self.assertFalse((project / ".ekp").exists())
            self.assertFalse((project / ".ekp" / "project.yaml").exists())
            self.assertFalse((project / ".ekp" / "install.json").exists())

    def test_all_four_apply_rollback_and_foreign_preservation(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            result = self._assemble(["core"], root / "asm")
            project = root / "project"
            project.mkdir()

            foreign = {
                ".cursor/user-note.txt": "cursor-foreign\n",
                ".github/workflows/build.yml": "name: build\n",
                ".github/ISSUE_TEMPLATE/bug.md": "bug\n",
                ".claude/settings.json": '{"x":1}\n',
                ".claude/custom-user-file": "claude-user\n",
                ".agents/custom-user-file": "agents-user\n",
                ".agents/workflows/flow.md": "flow\n",
            }
            before = {}
            for rel, body in foreign.items():
                path = project / rel
                _write(path, body)
                before[rel] = sha256_file(path)

            desired = _collect_all(self.registry, result.bundle_path, self.engine)
            ops, conflicts = self.engine.plan_first_install(project, desired)
            self.assertEqual(conflicts, [])
            dirs = self.engine.directories_to_create(project, ops)
            # Never claim project root
            self.assertNotIn(".", dirs)
            plan = self._install_plan(project, ops, dirs)
            applied = self.engine.apply_managed_files(plan)

            self.assertTrue((project / "CLAUDE.md").is_file())
            self.assertTrue((project / ".github" / "copilot-instructions.md").is_file())
            self.assertTrue((project / ".agents" / "rules").is_dir())
            self.assertTrue((project / ".cursor" / "rules").is_dir())
            self.assertFalse((project / ".ekp" / "install.json").exists())
            self.assertFalse((project / ".ekp" / "project.yaml").exists())

            for rel, digest in before.items():
                self.assertEqual(sha256_file(project / rel), digest)

            self.engine.rollback(
                applied.created_files, applied.created_dirs, applied.preexisting_dirs
            )

            for rel, digest in before.items():
                self.assertEqual(sha256_file(project / rel), digest)
            self.assertFalse((project / "CLAUDE.md").exists())
            self.assertFalse((project / ".github" / "copilot-instructions.md").exists())
            # Preexisting .github must remain
            self.assertTrue((project / ".github" / "workflows" / "build.yml").is_file())

    def test_shared_github_parent_ownership(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            project = root / "project"
            project.mkdir()
            _write(project / ".github" / "workflows" / "build.yml", "name: build\n")
            source = root / "copilot-instructions.md"
            source.write_text("ekp\n", encoding="utf-8")
            desired = [
                DesiredManagedFile(
                    relative_path=".github/copilot-instructions.md",
                    adapter="copilot",
                    source_path=source,
                    sha256=sha256_file(source),
                )
            ]
            ops, conflicts = self.engine.plan_first_install(project, desired)
            self.assertEqual(conflicts, [])
            dirs = self.engine.directories_to_create(project, ops)
            plan = self._install_plan(project, ops, dirs)
            applied = self.engine.apply_managed_files(plan)
            self.assertTrue((project / ".github" / "copilot-instructions.md").is_file())
            # Preexisting .github is never transaction-owned for removal
            github_abs = (project / ".github").resolve()
            self.assertIn(github_abs, applied.preexisting_dirs)
            self.engine.rollback(
                applied.created_files, applied.created_dirs, applied.preexisting_dirs
            )
            self.assertFalse((project / ".github" / "copilot-instructions.md").exists())
            self.assertTrue((project / ".github" / "workflows" / "build.yml").is_file())
            self.assertTrue((project / ".github").is_dir())

    def test_root_and_nested_transaction(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            project = root / "project"
            project.mkdir()
            sources = {}
            for name, rel in (
                ("claude.md", "CLAUDE.md"),
                ("copilot.md", ".github/copilot-instructions.md"),
                ("anti.md", ".agents/rules/00-orchestrator.md"),
                ("cursor.mdc", ".cursor/rules/sample.mdc"),
            ):
                path = root / name
                path.write_text(name + "\n", encoding="utf-8")
                sources[rel] = path
            desired = [
                DesiredManagedFile(
                    relative_path=rel,
                    adapter=adapter,
                    source_path=sources[rel],
                    sha256=sha256_file(sources[rel]),
                )
                for adapter, rel in (
                    ("claude", "CLAUDE.md"),
                    ("copilot", ".github/copilot-instructions.md"),
                    ("antigravity", ".agents/rules/00-orchestrator.md"),
                    ("cursor", ".cursor/rules/sample.mdc"),
                )
            ]
            ops, conflicts = self.engine.plan_first_install(project, desired)
            self.assertEqual(conflicts, [])
            dirs = self.engine.directories_to_create(project, ops)
            self.assertNotIn(".", dirs)
            plan = self._install_plan(project, ops, dirs)
            applied = self.engine.apply_managed_files(plan)
            for rel in sources:
                self.assertTrue((project / rel).is_file())
            self.engine.rollback(
                applied.created_files, applied.created_dirs, applied.preexisting_dirs
            )
            for rel in sources:
                self.assertFalse((project / rel).exists())
            self.assertTrue(project.is_dir())

    def test_synthetic_cross_assistant_duplicate_still_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            a = root / "a.md"
            b = root / "b.md"
            a.write_text("a\n", encoding="utf-8")
            b.write_text("b\n", encoding="utf-8")
            desired = [
                DesiredManagedFile(
                    relative_path="CLAUDE.md",
                    adapter="claude",
                    source_path=a,
                    sha256=sha256_file(a),
                ),
                DesiredManagedFile(
                    relative_path="CLAUDE.md",
                    adapter="copilot",
                    source_path=b,
                    sha256=sha256_file(b),
                ),
            ]
            with self.assertRaises(InstallConflictError):
                self.engine.normalize_desired_files(desired)

    def test_directory_coexistence_assistant_specific(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            # Copilot with preexisting .github
            project = root / "copilot-proj"
            project.mkdir()
            _write(project / ".github" / "workflows" / "ci.yml", "ci\n")
            bundle = root / "copilot-bundle"
            _write(
                bundle / "copilot" / ".github" / "copilot-instructions.md", "c\n"
            )
            desired = self.registry.get("copilot").collect_desired_files(bundle)
            ops, conflicts = self.engine.plan_first_install(project, desired)
            self.assertEqual(conflicts, [])
            plan = self._install_plan(
                project, ops, self.engine.directories_to_create(project, ops)
            )
            self.engine.apply_managed_files(plan)
            self.assertEqual(
                (project / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8"),
                "ci\n",
            )

            # Claude with preexisting .claude user files
            project2 = root / "claude-proj"
            project2.mkdir()
            _write(project2 / ".claude" / "settings.json", "{}\n")
            _write(project2 / ".claude" / "custom-user-file", "keep\n")
            bundle2 = root / "claude-bundle"
            _write(bundle2 / "claude" / "CLAUDE.md", "root\n")
            _write(
                bundle2 / "claude" / ".claude" / "skills" / "ekp-x" / "SKILL.md",
                "skill\n",
            )
            desired2 = self.registry.get("claude").collect_desired_files(bundle2)
            ops2, conflicts2 = self.engine.plan_first_install(project2, desired2)
            self.assertEqual(conflicts2, [])
            plan2 = self._install_plan(
                project2, ops2, self.engine.directories_to_create(project2, ops2)
            )
            self.engine.apply_managed_files(plan2)
            self.assertEqual(
                (project2 / ".claude" / "custom-user-file").read_text(encoding="utf-8"),
                "keep\n",
            )

            # Antigravity with preexisting .agents
            project3 = root / "anti-proj"
            project3.mkdir()
            _write(project3 / ".agents" / "custom-user-file", "keep\n")
            _write(project3 / ".agents" / "workflows" / "x.md", "wf\n")
            bundle3 = root / "anti-bundle"
            _write(
                bundle3 / "antigravity" / ".agents" / "rules" / "00-orchestrator.md",
                "o\n",
            )
            desired3 = self.registry.get("antigravity").collect_desired_files(bundle3)
            ops3, conflicts3 = self.engine.plan_first_install(project3, desired3)
            self.assertEqual(conflicts3, [])
            plan3 = self._install_plan(
                project3, ops3, self.engine.directories_to_create(project3, ops3)
            )
            self.engine.apply_managed_files(plan3)
            self.assertEqual(
                (project3 / ".agents" / "custom-user-file").read_text(encoding="utf-8"),
                "keep\n",
            )


if __name__ == "__main__":
    unittest.main()
