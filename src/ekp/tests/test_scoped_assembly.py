"""AZ-C scoped assistant assembly and adapter rendering tests."""

from __future__ import annotations

import hashlib
import re
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

REPO_ROOT = Path(__file__).resolve().parents[3]
ADAPTERS_DIR = REPO_ROOT / "scripts" / "adapters"
ASSEMBLE_DIR = REPO_ROOT / "scripts" / "assemble"
VALIDATE_DIR = REPO_ROOT / "scripts" / "validate"

for _path in (ADAPTERS_DIR, ASSEMBLE_DIR, VALIDATE_DIR):
    entry = str(_path)
    if entry not in sys.path:
        sys.path.insert(0, entry)

from assemble import assemble_project_resolution, verify_indexes
from common.paths import clear_path_context, get_dist_path, set_path_context
from common.registry import build_default_registry
from common.scoped_gen import ScopedGenerationError, claim_relative_path
from common.workspace_names import (
    prefix_apply_to_patterns,
    workspace_path_hash,
    workspace_scoped_filename,
)

from ekp.assembly import AssemblyService, ScopedProjectAssemblyRequest
from ekp.composition import ComponentRegistry, resolve_project_composition
from ekp.config import ProjectConfig, WorkspaceIntent

FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n(.*)$", re.DOTALL)


def _reference_config():
    return ProjectConfig(
        2,
        ("devops",),
        ("cursor", "copilot", "claude", "antigravity"),
        (
            WorkspaceIntent("apps/api", ("symfony",)),
            WorkspaceIntent("apps/web", ("frontend",)),
            WorkspaceIntent("apps/mobile", ("flutter",)),
            WorkspaceIntent("packages/shared", ("typescript",)),
        ),
    )


def _empty_root_config():
    return ProjectConfig(
        2,
        (),
        ("cursor", "copilot", "claude", "antigravity"),
        (WorkspaceIntent("apps/api", ("symfony",)),),
    )


class WorkspaceNamingTests(unittest.TestCase):
    def test_deterministic_d76_shape(self):
        name = workspace_scoped_filename(
            "apps/api", "knowledge/engineering/engineering-principles.md", "mdc"
        )
        expected_hash = workspace_path_hash("apps/api")
        self.assertEqual(
            name,
            "apps-api-{}-engineering-principles.mdc".format(expected_hash),
        )
        self.assertNotIn("/", name)
        self.assertEqual(len(expected_hash), 10)

    def test_prefix_apply_to_each_pattern(self):
        self.assertEqual(
            prefix_apply_to_patterns("**/*.php,**/*.twig", "apps/api"),
            "apps/api/**/*.php,apps/api/**/*.twig",
        )


class CollisionTests(unittest.TestCase):
    def test_duplicate_target_refused(self):
        claimed = set()
        claim_relative_path(claimed, "a.mdc")
        with self.assertRaises(ScopedGenerationError):
            claim_relative_path(claimed, "a.mdc")


class ScopedAssemblyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if verify_indexes(get_dist_path()):
            raise unittest.SkipTest("dist indexes not available")
        cls.registry = ComponentRegistry.load()

    def setUp(self):
        self.temp = tempfile.mkdtemp(prefix="ekp-azc-")
        self.output = Path(self.temp) / "out"
        self.workspace = Path(self.temp) / "idx"
        self.workspace.mkdir(parents=True)
        self.output.mkdir(parents=True)

    def tearDown(self):
        clear_path_context()
        shutil.rmtree(self.temp, ignore_errors=True)

    def _assemble(self, config, assistants=None):
        service = AssemblyService()
        return service.assemble_scoped_project(
            ScopedProjectAssemblyRequest(
                config=config,
                assistants=assistants or list(config.assistants),
                verify=True,
                clean=True,
                resource_root=REPO_ROOT,
                workspace_dir=self.workspace,
                output_root=self.output,
            )
        )

    def test_one_prepare_for_all_four_assistants(self):
        config = _reference_config()
        service = AssemblyService()
        with mock.patch.object(
            service, "prepare_project_composition", wraps=service.prepare_project_composition
        ) as prepare:
            service.assemble_scoped_project(
                ScopedProjectAssemblyRequest(
                    config=config,
                    verify=True,
                    clean=True,
                    resource_root=REPO_ROOT,
                    workspace_dir=self.workspace,
                    output_root=self.output,
                )
            )
        self.assertEqual(prepare.call_count, 1)

    def test_one_generate_scoped_call_per_assistant(self):
        config = _reference_config()
        resolution = resolve_project_composition(config, self.registry)
        registry = build_default_registry()
        counters = {name: 0 for name in config.assistants}

        def wrap(name, fn):
            def _wrapped(*args, **kwargs):
                counters[name] += 1
                return fn(*args, **kwargs)

            return _wrapped

        for name in config.assistants:
            adapter = registry.get(name)
            adapter["generate_scoped"] = wrap(name, adapter["generate_scoped"])

        set_path_context(repo_root=REPO_ROOT, dist_dir=self.workspace)
        try:
            # Indexes already exist in repo dist; copy context uses workspace.
            from validate import run_generate_index

            run_generate_index(output_dir=self.workspace, repo_root=REPO_ROOT)
            assemble_project_resolution(
                project_resolution=resolution,
                assistants=list(config.assistants),
                clean=True,
                verify=True,
                repo_root=REPO_ROOT,
                dist_dir=self.workspace,
                bundle_root=self.output,
                registry=registry,
            )
        finally:
            clear_path_context()

        self.assertEqual(counters, {name: 1 for name in config.assistants})

    def test_reference_monorepo_formats_and_one_bundle(self):
        result = self._assemble(_reference_config())
        bundle = result.bundle_path
        self.assertTrue(bundle.is_dir())
        for assistant in ("cursor", "copilot", "claude", "antigravity"):
            self.assertTrue((bundle / assistant).is_dir())
            self.assertFalse((bundle / "apps").exists())

        cursor_files = sorted((bundle / "cursor").glob("*.mdc"))
        self.assertGreater(len(cursor_files), 0)
        workspace_cursor = [
            p for p in cursor_files if "apps-api-" in p.name or "apps-web-" in p.name
        ]
        self.assertGreater(len(workspace_cursor), 0)
        for path in workspace_cursor:
            content = path.read_text(encoding="utf-8")
            match = FRONTMATTER_RE.match(content)
            self.assertIsNotNone(match, msg=path.name)
            front = match.group(1)
            self.assertIn("alwaysApply: false", front)
            self.assertIn("globs:", front)
            self.assertNotIn("alwaysApply: true", front)

        # No sibling leakage: api globs must not mention apps/web
        for path in (bundle / "cursor").glob("apps-api-*.mdc"):
            front = FRONTMATTER_RE.match(path.read_text(encoding="utf-8")).group(1)
            self.assertIn("globs: apps/api/**", front)
            self.assertNotIn("apps/web", front)

        copilot_root = bundle / "copilot" / ".github" / "copilot-instructions.md"
        self.assertTrue(copilot_root.is_file())
        instructions = list(
            (bundle / "copilot" / ".github" / "instructions").glob("*.instructions.md")
        )
        self.assertGreater(len(instructions), 0)
        for path in instructions:
            if "apps-api-" in path.name:
                front = FRONTMATTER_RE.match(path.read_text(encoding="utf-8")).group(1)
                apply = re.search(r'applyTo:\s*"([^"]+)"', front).group(1)
                self.assertTrue(
                    all(
                        part.strip().startswith("apps/api/")
                        for part in apply.split(",")
                    ),
                    msg=apply,
                )
                self.assertNotIn("apps/web/", apply)

        claude_rules = list((bundle / "claude" / ".claude" / "rules").glob("*.md"))
        self.assertGreater(len(claude_rules), 0)
        self.assertFalse((bundle / "claude" / "apps").exists())
        for path in claude_rules:
            content = path.read_text(encoding="utf-8")
            match = FRONTMATTER_RE.match(content)
            self.assertIsNotNone(match)
            self.assertIn("paths:", match.group(1))
            self.assertIn('- "', match.group(1))

        anti_rules = list((bundle / "antigravity" / ".agents" / "rules").glob("*.md"))
        self.assertGreater(len(anti_rules), 0)
        workspace_anti = [p for p in anti_rules if "apps-api-" in p.name]
        self.assertGreater(len(workspace_anti), 0)
        for path in workspace_anti:
            content = path.read_text(encoding="utf-8")
            self.assertLess(len(content), 12000)
            match = FRONTMATTER_RE.match(content)
            self.assertIsNotNone(match)
            front = match.group(1)
            self.assertIn("trigger: glob", front)
            self.assertIn("globs: apps/api/**", front)
            self.assertEqual(front.count("globs:"), 1)

        # Store counts for report stability via attributes
        self.__class__.ref_counts = {
            "cursor": len(cursor_files),
            "copilot": len(
                list((bundle / "copilot").rglob("*"))
            ),
            "claude": len(list((bundle / "claude").rglob("*"))),
            "antigravity": len(anti_rules),
        }
        # Prefer file counts of generated artifacts (not dirs)
        self.__class__.ref_counts = {
            "cursor": len(cursor_files),
            "copilot": len(
                [
                    p
                    for p in (bundle / "copilot").rglob("*")
                    if p.is_file() and p.name != "adapter-manifest.json"
                ]
            ),
            "claude": len(
                [
                    p
                    for p in (bundle / "claude").rglob("*")
                    if p.is_file() and p.name != "adapter-manifest.json"
                ]
            ),
            "antigravity": len(anti_rules),
        }

    def test_empty_root_no_synthetic_global(self):
        result = self._assemble(_empty_root_config())
        bundle = result.bundle_path
        self.assertEqual(len(result.project_resolution.inventory.global_items()), 0)

        self.assertFalse(
            (bundle / "copilot" / ".github" / "copilot-instructions.md").exists()
        )
        self.assertFalse((bundle / "claude" / "CLAUDE.md").exists())
        self.assertFalse((bundle / "claude" / ".claude" / "skills").exists())
        self.assertTrue((bundle / "claude" / ".claude" / "rules").is_dir())

        cursor_files = list((bundle / "cursor").glob("*.mdc"))
        self.assertGreater(len(cursor_files), 0)
        for path in cursor_files:
            front = FRONTMATTER_RE.match(path.read_text(encoding="utf-8")).group(1)
            self.assertIn("globs:", front)
            self.assertIn("alwaysApply: false", front)

        anti = list((bundle / "antigravity" / ".agents" / "rules").glob("*.md"))
        self.assertGreater(len(anti), 0)
        self.assertFalse((bundle / "antigravity" / ".agents" / "rules" / "00-orchestrator.md").exists())
        for path in anti:
            self.assertTrue(path.read_text(encoding="utf-8").lstrip().startswith("---"))

    def test_same_source_multi_scope_body(self):
        config = ProjectConfig(
            2,
            ("core",),
            ("antigravity", "claude"),
            (
                WorkspaceIntent("apps/api", ("core",)),
                WorkspaceIntent("apps/web", ("core",)),
            ),
        )
        result = self._assemble(config, assistants=["antigravity", "claude"])
        bundle = result.bundle_path
        source = "knowledge/engineering/engineering-principles.md"

        def bodies_for(adapter_dir, pattern):
            found = []
            for path in sorted(adapter_dir.rglob(pattern)):
                text = path.read_text(encoding="utf-8")
                if source not in text:
                    continue
                match = FRONTMATTER_RE.match(text)
                body = match.group(2) if match else text
                # Normalize away part labels in headings for split files
                found.append((path.name, body))
            return found

        anti_global = bundle / "antigravity" / ".agents" / "rules" / "01-foundation.md"
        self.assertTrue(anti_global.is_file())
        global_body = anti_global.read_text(encoding="utf-8")

        api = [
            b
            for name, b in bodies_for(
                bundle / "antigravity" / ".agents" / "rules", "*.md"
            )
            if name.startswith("apps-api-") and "engineering-principles" in name
        ]
        web = [
            b
            for name, b in bodies_for(
                bundle / "antigravity" / ".agents" / "rules", "*.md"
            )
            if name.startswith("apps-web-") and "engineering-principles" in name
        ]
        self.assertEqual(len(api), 1)
        self.assertEqual(len(web), 1)
        self.assertEqual(api[0], web[0])
        # Workspace body matches global plain body (wrapper is frontmatter only).
        self.assertEqual(api[0], global_body)

        claude_api = [
            b
            for name, b in bodies_for(bundle / "claude" / ".claude" / "rules", "*.md")
            if name.startswith("apps-api-") and "engineering-principles" in name
        ]
        claude_web = [
            b
            for name, b in bodies_for(bundle / "claude" / ".claude" / "rules", "*.md")
            if name.startswith("apps-web-") and "engineering-principles" in name
        ]
        self.assertEqual(claude_api[0], claude_web[0])

    def test_determinism(self):
        config = _empty_root_config()
        first = self._assemble(config)
        first_dir = first.bundle_path
        snapshot = {}
        for path in sorted(first_dir.rglob("*")):
            if path.is_file():
                rel = path.relative_to(first_dir).as_posix()
                snapshot[rel] = hashlib.sha256(path.read_bytes()).hexdigest()

        # Shuffle assistant order / workspace YAML order via equivalent config
        shuffled = ProjectConfig(
            2,
            (),
            ("antigravity", "claude", "copilot", "cursor"),
            (WorkspaceIntent("apps/api", ("symfony",)),),
        )
        second_out = Path(self.temp) / "out2"
        second_ws = Path(self.temp) / "idx2"
        second_ws.mkdir()
        second_out.mkdir()
        second = AssemblyService().assemble_scoped_project(
            ScopedProjectAssemblyRequest(
                config=shuffled,
                verify=True,
                clean=True,
                resource_root=REPO_ROOT,
                workspace_dir=second_ws,
                output_root=second_out,
            )
        )
        second_snap = {}
        for path in sorted(second.bundle_path.rglob("*")):
            if path.is_file():
                rel = path.relative_to(second.bundle_path).as_posix()
                second_snap[rel] = hashlib.sha256(path.read_bytes()).hexdigest()

        # Ignore generated_at timestamps in manifests by comparing non-manifest files
        def strip_manifests(data):
            return {
                k: v
                for k, v in data.items()
                if not k.endswith("manifest.json") and k != "assemble-manifest.json"
            }

        self.assertEqual(strip_manifests(snapshot), strip_manifests(second_snap))


class Schema1ParitySmokeTests(unittest.TestCase):
    """Ensure AZ-C did not break historical generate() entry points."""

    def setUp(self):
        self.temp = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.temp, ignore_errors=True)

    def test_cursor_core_still_65(self):
        from cursor.generate import generate

        if verify_indexes(get_dist_path()):
            self.skipTest("dist indexes not available")
        written = generate(
            profile_name="cursor-core",
            output_dir=Path(self.temp) / "cursor",
        )
        self.assertEqual(len(written), 65)


if __name__ == "__main__":
    unittest.main()
