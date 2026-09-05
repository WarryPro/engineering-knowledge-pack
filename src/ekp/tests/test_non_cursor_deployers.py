"""Non-Cursor deployer contract tests (Copilot / Claude / Antigravity)."""

from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

from ekp.install.deploy.antigravity import AntigravityDeployer
from ekp.install.deploy.claude import ClaudeDeployer
from ekp.install.deploy.copilot import CopilotDeployer
from ekp.install.deploy.cursor import CursorDeployer
from ekp.install.deploy.engine import SharedDeploymentEngine
from ekp.install.deploy.hashing import sha256_file
from ekp.install.errors import InstallAssemblyError
from ekp.install.plan import FileOpKind, InstallPlan


def _write(path: Path, body: str = "body\n") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")
    return path


def _try_symlink(target: Path, link: Path) -> bool:
    try:
        if link.exists() or link.is_symlink():
            link.unlink()
        link.symlink_to(target, target_is_directory=target.is_dir())
        return True
    except OSError:
        return False


class CopilotDeployerTests(unittest.TestCase):
    def setUp(self):
        self.deployer = CopilotDeployer()
        self.engine = SharedDeploymentEngine()

    def _valid_bundle(self, root: Path) -> Path:
        bundle = root / "bundle"
        copilot = bundle / "copilot"
        _write(copilot / ".github" / "copilot-instructions.md", "always-on\n")
        _write(
            copilot / ".github" / "instructions" / "php.instructions.md",
            "php\n",
        )
        _write(copilot / "adapter-manifest.json", '{"adapter":"copilot"}\n')
        return bundle

    def test_exact_mapping_and_hashes(self):
        with tempfile.TemporaryDirectory() as tmp:
            bundle = self._valid_bundle(Path(tmp))
            desired = self.engine.normalize_desired_files(
                self.deployer.collect_desired_files(bundle)
            )
            self.assertEqual(
                [item.relative_path for item in desired],
                [
                    ".github/copilot-instructions.md",
                    ".github/instructions/php.instructions.md",
                ],
            )
            self.assertTrue(all(item.adapter == "copilot" for item in desired))
            for item in desired:
                self.assertEqual(item.sha256, sha256_file(item.source_path))

    def test_missing_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            bundle = Path(tmp) / "bundle"
            bundle.mkdir()
            with self.assertRaises(InstallAssemblyError):
                self.deployer.collect_desired_files(bundle)

    def test_empty_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            bundle = Path(tmp) / "bundle"
            (bundle / "copilot").mkdir(parents=True)
            with self.assertRaises(InstallAssemblyError):
                self.deployer.collect_desired_files(bundle)

    def test_unexpected_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            bundle = self._valid_bundle(Path(tmp))
            _write(bundle / "copilot" / ".github" / "workflows" / "ci.yml", "x\n")
            with self.assertRaises(InstallAssemblyError):
                self.deployer.collect_desired_files(bundle)

    def test_source_symlink_escape(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            outside = root / "outside.md"
            outside.write_text("secret\n", encoding="utf-8")
            bundle = root / "bundle"
            instructions = bundle / "copilot" / ".github"
            instructions.mkdir(parents=True)
            link = instructions / "copilot-instructions.md"
            if not _try_symlink(outside, link):
                self.skipTest("symlink creation not permitted")
            with self.assertRaises(InstallAssemblyError):
                self.deployer.collect_desired_files(bundle)

    def test_determinism(self):
        with tempfile.TemporaryDirectory() as tmp:
            bundle = self._valid_bundle(Path(tmp))
            a = [
                (i.relative_path, i.adapter, i.sha256)
                for i in self.engine.normalize_desired_files(
                    self.deployer.collect_desired_files(bundle)
                )
            ]
            b = [
                (i.relative_path, i.adapter, i.sha256)
                for i in self.engine.normalize_desired_files(
                    self.deployer.collect_desired_files(bundle)
                )
            ]
            self.assertEqual(a, b)


class ClaudeDeployerTests(unittest.TestCase):
    def setUp(self):
        self.deployer = ClaudeDeployer()
        self.engine = SharedDeploymentEngine()

    def _valid_bundle(self, root: Path) -> Path:
        bundle = root / "bundle"
        claude = bundle / "claude"
        _write(claude / "CLAUDE.md", "claude-root\n")
        _write(claude / ".claude" / "skills" / "ekp-layering" / "SKILL.md", "skill\n")
        _write(claude / "adapter-manifest.json", '{"adapter":"claude"}\n')
        return bundle

    def test_exact_mapping_including_root(self):
        with tempfile.TemporaryDirectory() as tmp:
            bundle = self._valid_bundle(Path(tmp))
            desired = self.engine.normalize_desired_files(
                self.deployer.collect_desired_files(bundle)
            )
            self.assertEqual(
                [item.relative_path for item in desired],
                [".claude/skills/ekp-layering/SKILL.md", "CLAUDE.md"],
            )
            self.assertTrue(all(item.adapter == "claude" for item in desired))

    def test_missing_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            bundle = Path(tmp) / "bundle"
            bundle.mkdir()
            with self.assertRaises(InstallAssemblyError):
                self.deployer.collect_desired_files(bundle)

    def test_empty_skills(self):
        with tempfile.TemporaryDirectory() as tmp:
            bundle = Path(tmp) / "bundle"
            claude = bundle / "claude"
            _write(claude / "CLAUDE.md", "x\n")
            (claude / ".claude" / "skills").mkdir(parents=True)
            with self.assertRaises(InstallAssemblyError):
                self.deployer.collect_desired_files(bundle)

    def test_unexpected_rules_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            bundle = self._valid_bundle(Path(tmp))
            _write(bundle / "claude" / ".claude" / "rules" / "x.md", "nope\n")
            with self.assertRaises(InstallAssemblyError):
                self.deployer.collect_desired_files(bundle)

    def test_source_symlink_escape(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            outside = root / "outside.md"
            outside.write_text("secret\n", encoding="utf-8")
            bundle = root / "bundle"
            claude = bundle / "claude"
            claude.mkdir(parents=True)
            link = claude / "CLAUDE.md"
            if not _try_symlink(outside, link):
                self.skipTest("symlink creation not permitted")
            _write(claude / ".claude" / "skills" / "ekp-x" / "SKILL.md", "skill\n")
            with self.assertRaises(InstallAssemblyError):
                self.deployer.collect_desired_files(bundle)

    def test_determinism(self):
        with tempfile.TemporaryDirectory() as tmp:
            bundle = self._valid_bundle(Path(tmp))
            a = self.engine.normalize_desired_files(
                self.deployer.collect_desired_files(bundle)
            )
            b = self.engine.normalize_desired_files(
                self.deployer.collect_desired_files(bundle)
            )
            self.assertEqual(
                [(i.relative_path, i.sha256) for i in a],
                [(i.relative_path, i.sha256) for i in b],
            )


class AntigravityDeployerTests(unittest.TestCase):
    def setUp(self):
        self.deployer = AntigravityDeployer()
        self.engine = SharedDeploymentEngine()

    def _valid_bundle(self, root: Path) -> Path:
        bundle = root / "bundle"
        anti = bundle / "antigravity"
        rules = anti / ".agents" / "rules"
        _write(rules / "00-orchestrator.md", "orch\n")
        _write(rules / "01-foundation.md", "found\n")
        _write(rules / "10-layering-part1.md", "part\n")
        _write(anti / "adapter-manifest.json", '{"adapter":"antigravity"}\n')
        return bundle

    def test_exact_mapping(self):
        with tempfile.TemporaryDirectory() as tmp:
            bundle = self._valid_bundle(Path(tmp))
            desired = self.engine.normalize_desired_files(
                self.deployer.collect_desired_files(bundle)
            )
            self.assertEqual(
                [item.relative_path for item in desired],
                [
                    ".agents/rules/00-orchestrator.md",
                    ".agents/rules/01-foundation.md",
                    ".agents/rules/10-layering-part1.md",
                ],
            )
            self.assertTrue(all(item.adapter == "antigravity" for item in desired))

    def test_missing_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            bundle = Path(tmp) / "bundle"
            bundle.mkdir()
            with self.assertRaises(InstallAssemblyError):
                self.deployer.collect_desired_files(bundle)

    def test_empty_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            bundle = Path(tmp) / "bundle"
            (bundle / "antigravity").mkdir(parents=True)
            with self.assertRaises(InstallAssemblyError):
                self.deployer.collect_desired_files(bundle)

    def test_unexpected_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            bundle = self._valid_bundle(Path(tmp))
            _write(bundle / "antigravity" / ".agents" / "workflows" / "x.md", "nope\n")
            with self.assertRaises(InstallAssemblyError):
                self.deployer.collect_desired_files(bundle)

    def test_source_symlink_escape(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            outside = root / "outside.md"
            outside.write_text("secret\n", encoding="utf-8")
            bundle = root / "bundle"
            rules = bundle / "antigravity" / ".agents" / "rules"
            rules.mkdir(parents=True)
            link = rules / "00-orchestrator.md"
            if not _try_symlink(outside, link):
                self.skipTest("symlink creation not permitted")
            with self.assertRaises(InstallAssemblyError):
                self.deployer.collect_desired_files(bundle)

    def test_determinism(self):
        with tempfile.TemporaryDirectory() as tmp:
            bundle = self._valid_bundle(Path(tmp))
            a = [
                i.relative_path
                for i in self.engine.normalize_desired_files(
                    self.deployer.collect_desired_files(bundle)
                )
            ]
            b = [
                i.relative_path
                for i in self.engine.normalize_desired_files(
                    self.deployer.collect_desired_files(bundle)
                )
            ]
            self.assertEqual(a, b)


class DeployerFilesystemSafetyMatrixTests(unittest.TestCase):
    """Unmanaged collision + CREATE race for representative targets per assistant."""

    def setUp(self):
        self.engine = SharedDeploymentEngine()

    def _plan_and_apply_ops(self, project: Path, desired):
        ops, conflicts = self.engine.plan_first_install(project, desired)
        return ops, conflicts

    def _install_plan(self, project, ops, dirs):
        return InstallPlan(
            project_root=project,
            profile="test",
            ekp_version="0.19.0.dev0",
            adapter="test",
            bundle_path=project,
            rules_count=len(ops),
            operations=ops,
            conflicts=[],
            directories_to_create=dirs,
        )

    def test_unmanaged_collision_matrix(self):
        cases = [
            ("cursor", ".cursor/rules/sample.mdc", "cursor-body\n"),
            ("copilot", ".github/copilot-instructions.md", "copilot-body\n"),
            (
                "copilot",
                ".github/instructions/php.instructions.md",
                "php-body\n",
            ),
            ("claude", "CLAUDE.md", "claude-body\n"),
            ("claude", ".claude/skills/ekp-x/SKILL.md", "skill-body\n"),
            ("antigravity", ".agents/rules/00-orchestrator.md", "anti-body\n"),
        ]
        for adapter, relative, body in cases:
            with self.subTest(adapter=adapter, relative=relative):
                with tempfile.TemporaryDirectory() as tmp:
                    root = Path(tmp)
                    project = root / "project"
                    project.mkdir()
                    target = project / relative
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_text("user-owned\n", encoding="utf-8")
                    source = root / "src.md"
                    source.write_text(body, encoding="utf-8")
                    from ekp.install.deploy.models import DesiredManagedFile

                    desired = [
                        DesiredManagedFile(
                            relative_path=relative,
                            adapter=adapter,
                            source_path=source,
                            sha256=sha256_file(source),
                        )
                    ]
                    ops, conflicts = self._plan_and_apply_ops(project, desired)
                    self.assertEqual(ops, [])
                    self.assertEqual(conflicts, [relative])
                    self.assertEqual(target.read_text(encoding="utf-8"), "user-owned\n")

    def test_create_race_matrix(self):
        cases = [
            ("cursor", ".cursor/rules/race.mdc"),
            ("copilot", ".github/copilot-instructions.md"),
            ("claude", "CLAUDE.md"),
            ("antigravity", ".agents/rules/race.md"),
        ]
        for adapter, relative in cases:
            with self.subTest(adapter=adapter, relative=relative):
                with tempfile.TemporaryDirectory() as tmp:
                    root = Path(tmp)
                    project = root / "project"
                    project.mkdir()
                    source = root / "src.md"
                    source.write_text("ekp\n", encoding="utf-8")
                    from ekp.install.deploy.models import DesiredManagedFile

                    desired = [
                        DesiredManagedFile(
                            relative_path=relative,
                            adapter=adapter,
                            source_path=source,
                            sha256=sha256_file(source),
                        )
                    ]
                    ops, conflicts = self.engine.plan_first_install(project, desired)
                    self.assertEqual(conflicts, [])
                    self.assertEqual(ops[0].kind, FileOpKind.CREATE)
                    target = project / relative
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_text("intruder\n", encoding="utf-8")
                    dirs = self.engine.directories_to_create(project, ops)
                    plan = self._install_plan(project, ops, dirs)
                    from ekp.install.errors import InstallConflictError

                    with self.assertRaises(InstallConflictError):
                        self.engine.apply_managed_files(plan)
                    self.assertEqual(target.read_text(encoding="utf-8"), "intruder\n")

    def test_project_symlink_boundaries(self):
        cases = [
            (".github", ".github/copilot-instructions.md"),
            (".github/instructions", ".github/instructions/php.instructions.md"),
            (".claude", ".claude/skills/ekp-x/SKILL.md"),
            (".claude/skills", ".claude/skills/ekp-x/SKILL.md"),
            (".agents", ".agents/rules/00-orchestrator.md"),
            (".agents/rules", ".agents/rules/00-orchestrator.md"),
        ]
        for link_rel, target_rel in cases:
            with self.subTest(link=link_rel, target=target_rel):
                with tempfile.TemporaryDirectory() as tmp:
                    root = Path(tmp)
                    project = root / "project"
                    project.mkdir()
                    outside = root / "outside"
                    outside.mkdir()
                    link = project / link_rel
                    link.parent.mkdir(parents=True, exist_ok=True)
                    if not _try_symlink(outside, link):
                        self.skipTest("symlink creation not permitted")
                    source = root / "src.md"
                    source.write_text("x\n", encoding="utf-8")
                    from ekp.install.deploy.models import DesiredManagedFile

                    desired = [
                        DesiredManagedFile(
                            relative_path=target_rel,
                            adapter="test",
                            source_path=source,
                            sha256=sha256_file(source),
                        )
                    ]
                    ops, conflicts = self.engine.plan_first_install(project, desired)
                    self.assertEqual(ops, [])
                    self.assertTrue(conflicts)
                    # No write outside project
                    self.assertEqual(list(outside.iterdir()), [])

        # CLAUDE.md as symlink target
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            project = root / "project"
            project.mkdir()
            outside = root / "outside.md"
            outside.write_text("out\n", encoding="utf-8")
            link = project / "CLAUDE.md"
            if not _try_symlink(outside, link):
                self.skipTest("symlink creation not permitted")
            source = root / "src.md"
            source.write_text("x\n", encoding="utf-8")
            from ekp.install.deploy.models import DesiredManagedFile

            desired = [
                DesiredManagedFile(
                    relative_path="CLAUDE.md",
                    adapter="claude",
                    source_path=source,
                    sha256=sha256_file(source),
                )
            ]
            ops, conflicts = self.engine.plan_first_install(project, desired)
            self.assertEqual(ops, [])
            self.assertTrue(conflicts)
            self.assertEqual(outside.read_text(encoding="utf-8"), "out\n")


if __name__ == "__main__":
    unittest.main()
