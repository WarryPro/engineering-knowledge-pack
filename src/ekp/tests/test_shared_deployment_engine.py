"""Shared deployment engine unit tests (assistant-agnostic)."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from typing import List

from ekp.install.deploy.base import Deployer
from ekp.install.deploy.engine import SharedDeploymentEngine
from ekp.install.deploy.hashing import sha256_file
from ekp.install.deploy.models import DesiredManagedFile
from ekp.install.errors import InstallAssemblyError, InstallConflictError
from ekp.install.manifest import ManagedFile
from ekp.install.plan import FileOpKind, FileOperation, InstallPlan


class _AssistantXDeployer(Deployer):
    """Synthetic deployer for architecture extensibility (not production-registered)."""

    @property
    def assistant_id(self) -> str:
        return "assistant-x"

    def collect_desired_files(self, bundle_path: Path) -> List[DesiredManagedFile]:
        source = bundle_path / "assistant-x" / "note.md"
        if not source.is_file():
            raise InstallAssemblyError("missing assistant-x output")
        return [
            DesiredManagedFile(
                relative_path="ASSISTANT-X.md",
                adapter=self.assistant_id,
                source_path=source,
                sha256=sha256_file(source),
            )
        ]


def _desired(
    relative: str,
    adapter: str,
    source: Path,
) -> DesiredManagedFile:
    return DesiredManagedFile(
        relative_path=relative,
        adapter=adapter,
        source_path=source,
        sha256=sha256_file(source),
    )


class SharedDeploymentEngineTests(unittest.TestCase):
    def setUp(self):
        self.engine = SharedDeploymentEngine()

    def _plan(
        self,
        project_root: Path,
        operations: List[FileOperation],
        directories: List[str],
    ) -> InstallPlan:
        return InstallPlan(
            project_root=project_root,
            profile="test",
            ekp_version="0.19.0.dev0",
            adapter="test",
            bundle_path=project_root,
            rules_count=len(operations),
            operations=operations,
            conflicts=[],
            directories_to_create=directories,
            dry_run=False,
        )

    def test_single_desired_file_create_and_hash(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            project = root / "project"
            project.mkdir()
            source = root / "src.md"
            source.write_text("hello\n", encoding="utf-8")
            desired = [_desired("docs/hello.md", "cursor", source)]
            ops, conflicts = self.engine.plan_first_install(project, desired)
            self.assertEqual(conflicts, [])
            self.assertEqual(len(ops), 1)
            self.assertEqual(ops[0].kind, FileOpKind.CREATE)
            dirs = self.engine.directories_to_create(project, ops)
            plan = self._plan(project, ops, dirs)
            applied = self.engine.apply_managed_files(plan)
            target = project / "docs" / "hello.md"
            self.assertTrue(target.is_file())
            self.assertEqual(sha256_file(target), sha256_file(source))
            self.assertEqual(applied.managed_files[0].adapter, "cursor")

    def test_multiple_desired_files_deterministic_ordering(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            sources = {}
            for name in ("z.md", "a.md", "m.md"):
                path = root / name
                path.write_text(name + "\n", encoding="utf-8")
                sources[name] = path
            # Intentionally unsorted input
            desired = [
                _desired("rules/z.md", "cursor", sources["z.md"]),
                _desired("rules/a.md", "cursor", sources["a.md"]),
                _desired("rules/m.md", "cursor", sources["m.md"]),
            ]
            ordered = self.engine.normalize_desired_files(desired)
            self.assertEqual(
                [item.relative_path for item in ordered],
                ["rules/a.md", "rules/m.md", "rules/z.md"],
            )
            project = root / "p"
            project.mkdir()
            ops, conflicts = self.engine.plan_first_install(project, ordered)
            self.assertEqual(conflicts, [])
            self.assertEqual(
                [op.relative_path for op in ops],
                ["rules/a.md", "rules/m.md", "rules/z.md"],
            )

    def test_duplicate_target_same_adapter(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            a = root / "a.md"
            b = root / "b.md"
            a.write_text("a\n", encoding="utf-8")
            b.write_text("b\n", encoding="utf-8")
            desired = [
                _desired("same.md", "cursor", a),
                _desired("same.md", "cursor", b),
            ]
            with self.assertRaises(InstallAssemblyError):
                self.engine.normalize_desired_files(desired)

    def test_duplicate_target_different_adapters(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            a = root / "a.md"
            b = root / "b.md"
            a.write_text("a\n", encoding="utf-8")
            b.write_text("b\n", encoding="utf-8")
            desired = [
                _desired("same.md", "cursor", a),
                _desired("same.md", "copilot", b),
            ]
            with self.assertRaises(InstallConflictError):
                self.engine.normalize_desired_files(desired)

    def test_unmanaged_collision(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            project = root / "project"
            project.mkdir()
            target = project / "owned.md"
            target.write_text("user\n", encoding="utf-8")
            source = root / "src.md"
            source.write_text("ekp\n", encoding="utf-8")
            ops, conflicts = self.engine.plan_first_install(
                project, [_desired("owned.md", "cursor", source)]
            )
            self.assertEqual(ops, [])
            self.assertEqual(conflicts, ["owned.md"])

    def test_unsafe_path_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "s.md"
            source.write_text("x\n", encoding="utf-8")
            with self.assertRaises(InstallAssemblyError):
                self.engine.normalize_desired_files(
                    [
                        DesiredManagedFile(
                            relative_path="../escape.md",
                            adapter="cursor",
                            source_path=source,
                            sha256=sha256_file(source),
                        )
                    ]
                )

    def test_root_level_desired_file_plan_create_rollback(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            project = root / "project"
            project.mkdir()
            # Preexisting sibling must survive rollback
            keep = project / "keep.txt"
            keep.write_text("keep\n", encoding="utf-8")
            source = root / "ROOT-FILE.md"
            source.write_text("root-body\n", encoding="utf-8")
            desired = [_desired("ROOT-FILE.md", "claude", source)]
            ops, conflicts = self.engine.plan_first_install(project, desired)
            self.assertEqual(conflicts, [])
            self.assertEqual(ops[0].kind, FileOpKind.CREATE)
            dirs = self.engine.directories_to_create(project, ops)
            self.assertEqual(dirs, [])
            plan = self._plan(project, ops, dirs)
            applied = self.engine.apply_managed_files(plan)
            target = project / "ROOT-FILE.md"
            self.assertTrue(target.is_file())
            self.assertEqual(sha256_file(target), sha256_file(source))
            self.engine.rollback(
                applied.created_files, applied.created_dirs, applied.preexisting_dirs
            )
            self.assertFalse(target.exists())
            self.assertTrue(keep.is_file())
            self.assertTrue(project.is_dir())

    def test_directory_creation_and_preexisting_parent_preserved(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            project = root / "project"
            parent = project / ".agents"
            parent.mkdir(parents=True)
            marker = parent / "user.txt"
            marker.write_text("mine\n", encoding="utf-8")
            source = root / "rule.md"
            source.write_text("rule\n", encoding="utf-8")
            desired = [_desired(".agents/rules/one.md", "antigravity", source)]
            ops, conflicts = self.engine.plan_first_install(project, desired)
            self.assertEqual(conflicts, [])
            dirs = self.engine.directories_to_create(project, ops)
            self.assertIn(".agents/rules", dirs)
            plan = self._plan(project, ops, dirs)
            applied = self.engine.apply_managed_files(plan)
            self.assertTrue((project / ".agents" / "rules" / "one.md").is_file())
            self.assertTrue(marker.is_file())
            # Rollback should remove created files/dirs but keep preexisting .agents
            self.engine.rollback(
                applied.created_files, applied.created_dirs, applied.preexisting_dirs
            )
            self.assertFalse((project / ".agents" / "rules" / "one.md").exists())
            self.assertTrue(parent.is_dir())
            self.assertTrue(marker.is_file())

    def test_create_race_refuses_overwrite(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            project = root / "project"
            project.mkdir()
            source = root / "src.md"
            source.write_text("ekp\n", encoding="utf-8")
            desired = [_desired("race.md", "cursor", source)]
            ops, conflicts = self.engine.plan_first_install(project, desired)
            self.assertEqual(conflicts, [])
            # Appear after planning
            (project / "race.md").write_text("intruder\n", encoding="utf-8")
            plan = self._plan(project, ops, [])
            with self.assertRaises(InstallConflictError):
                self.engine.apply_managed_files(plan)
            self.assertEqual((project / "race.md").read_text(encoding="utf-8"), "intruder\n")

    def test_restore_race_refuses_overwrite(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            project = root / "project"
            project.mkdir()
            source = root / "src.md"
            source.write_text("owned\n", encoding="utf-8")
            digest = sha256_file(source)
            managed = {
                "owned.md": ManagedFile(
                    relative_path="owned.md", adapter="cursor", sha256=digest
                )
            }
            # Missing owned file → RESTORE
            ops, conflicts = self.engine.plan_reinstall(
                project, [_desired("owned.md", "cursor", source)], managed
            )
            self.assertEqual(conflicts, [])
            self.assertEqual(ops[0].kind, FileOpKind.RESTORE)
            (project / "owned.md").write_text("appeared\n", encoding="utf-8")
            plan = self._plan(project, ops, [])
            with self.assertRaises(InstallConflictError):
                self.engine.apply_managed_files(plan)
            self.assertEqual((project / "owned.md").read_text(encoding="utf-8"), "appeared\n")

    def test_hash_verification_failure_rolls_back(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            project = root / "project"
            project.mkdir()
            source = root / "src.md"
            source.write_text("body\n", encoding="utf-8")
            desired = [_desired("file.md", "cursor", source)]
            ops, _ = self.engine.plan_first_install(project, desired)
            # Tamper expected hash after planning
            ops[0].expected_sha256 = "0" * 64
            plan = self._plan(project, ops, [])
            with self.assertRaises(Exception):
                self.engine.apply_managed_files(plan)
            self.assertFalse((project / "file.md").exists())

    def test_assistant_x_synthetic_extensibility(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            project = root / "project"
            project.mkdir()
            bundle = root / "bundle"
            out = bundle / "assistant-x"
            out.mkdir(parents=True)
            (out / "note.md").write_text("x-body\n", encoding="utf-8")
            deployer = _AssistantXDeployer()
            desired = deployer.collect_desired_files(bundle)
            self.assertEqual(desired[0].relative_path, "ASSISTANT-X.md")
            ops, conflicts = self.engine.plan_first_install(project, desired)
            self.assertEqual(conflicts, [])
            plan = self._plan(project, ops, self.engine.directories_to_create(project, ops))
            applied = self.engine.apply_managed_files(plan)
            self.assertTrue((project / "ASSISTANT-X.md").is_file())
            self.assertEqual(applied.managed_files[0].adapter, "assistant-x")


if __name__ == "__main__":
    unittest.main()
