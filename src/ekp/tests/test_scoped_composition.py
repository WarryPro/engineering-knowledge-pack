"""AZ-B scoped composition and knowledge inventory tests."""

from __future__ import annotations

import unittest
from unittest import mock

from ekp.assembly import AssemblyService
from ekp.composition import (
    CompositionError,
    KnowledgeScope,
    ScopedKnowledgeItem,
    resolve_composition,
    resolve_project_composition,
)
from ekp.composition.registry import ComponentRegistry
from ekp.config import ProjectConfig, WorkspaceIntent, configuration_sha256


CORE_PRINCIPLES = "knowledge/engineering/engineering-principles.md"


class ScopedKnowledgeItemInvariantTests(unittest.TestCase):
    def test_global_rejects_workspace_path(self):
        with self.assertRaises(CompositionError):
            ScopedKnowledgeItem(
                source_path=CORE_PRINCIPLES,
                scope=KnowledgeScope.GLOBAL,
                workspace_path="apps/api",
            )

    def test_workspace_requires_path(self):
        with self.assertRaises(CompositionError):
            ScopedKnowledgeItem(
                source_path=CORE_PRINCIPLES,
                scope=KnowledgeScope.WORKSPACE,
                workspace_path=None,
            )


class Schema1ProjectResolutionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.registry = ComponentRegistry.load()

    def test_schema1_is_global_only_preserving_knowledge_order(self):
        config = ProjectConfig(1, ("symfony",), ("cursor",))
        direct = resolve_composition(("symfony",), self.registry)
        result = resolve_project_composition(config, self.registry)
        self.assertIsNotNone(result.root)
        self.assertEqual(result.workspaces, ())
        self.assertEqual(
            result.root.knowledge_paths,
            direct.knowledge_paths,
        )
        self.assertEqual(
            tuple(item.source_path for item in result.inventory.global_items()),
            direct.knowledge_paths,
        )
        self.assertTrue(
            all(item.scope is KnowledgeScope.GLOBAL for item in result.inventory.items)
        )
        self.assertTrue(
            all(item.workspace_path is None for item in result.inventory.items)
        )


class Schema2ProjectResolutionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.registry = ComponentRegistry.load()

    def test_root_and_workspaces_independent_closures(self):
        config = ProjectConfig(
            2,
            ("devops",),
            ("cursor",),
            (
                WorkspaceIntent("apps/api", ("symfony",)),
                WorkspaceIntent("apps/web", ("frontend",)),
            ),
        )
        result = resolve_project_composition(config, self.registry)
        self.assertEqual(result.root.resolved_components, ("core", "devops"))
        by_path = {item.path: item.composition for item in result.workspaces}
        self.assertEqual(by_path["apps/api"].resolved_components, ("core", "php", "symfony"))
        self.assertEqual(
            by_path["apps/web"].resolved_components,
            ("core", "typescript", "frontend"),
        )
        # Root does not propagate devops into workspaces.
        self.assertNotIn("devops", by_path["apps/api"].resolved_components)
        self.assertNotIn("devops", by_path["apps/web"].resolved_components)
        # Workspace stacks do not become global.
        global_sources = {item.source_path for item in result.inventory.global_items()}
        self.assertNotIn("knowledge/symfony/symfony-architecture.md", global_sources)
        self.assertNotIn(
            "knowledge/frontend/frontend-architecture.md", global_sources
        )

    def test_empty_root_yields_no_global_items(self):
        config = ProjectConfig(
            2,
            (),
            ("cursor",),
            (WorkspaceIntent("apps/api", ("symfony",)),),
        )
        result = resolve_project_composition(config, self.registry)
        self.assertIsNone(result.root)
        self.assertEqual(result.inventory.global_items(), ())
        self.assertGreater(len(result.inventory.workspace_items("apps/api")), 0)
        self.assertEqual(
            result.workspaces[0].composition.resolved_components,
            ("core", "php", "symfony"),
        )

    def test_workspace_order_and_assistant_independence(self):
        a = ProjectConfig(
            2,
            ("devops",),
            ("cursor",),
            (
                WorkspaceIntent("apps/web", ("frontend",)),
                WorkspaceIntent("apps/api", ("symfony",)),
            ),
        )
        b = ProjectConfig(
            2,
            ("devops",),
            ("cursor", "claude", "antigravity"),
            (
                WorkspaceIntent("apps/api", ("php", "symfony")),
                WorkspaceIntent("apps/web", ("frontend",)),
            ),
        )
        ra = resolve_project_composition(a, self.registry)
        rb = resolve_project_composition(b, self.registry)
        self.assertEqual(
            [item.path for item in ra.workspaces],
            ["apps/api", "apps/web"],
        )
        self.assertEqual(ra.inventory.items, rb.inventory.items)
        self.assertEqual(ra.root.resolved_components, rb.root.resolved_components)

    def test_multi_scope_same_source_and_intra_scope_dedup(self):
        config = ProjectConfig(
            2,
            ("devops",),
            ("cursor",),
            (
                WorkspaceIntent("apps/api", ("symfony",)),
                WorkspaceIntent("apps/web", ("frontend",)),
            ),
        )
        result = resolve_project_composition(config, self.registry)
        principles = [
            item
            for item in result.inventory.items
            if item.source_path == CORE_PRINCIPLES
        ]
        self.assertEqual(len(principles), 3)
        scopes = {(item.scope, item.workspace_path) for item in principles}
        self.assertEqual(
            scopes,
            {
                (KnowledgeScope.GLOBAL, None),
                (KnowledgeScope.WORKSPACE, "apps/api"),
                (KnowledgeScope.WORKSPACE, "apps/web"),
            },
        )
        # Intra-scope uniqueness for every source.
        seen = set()
        for item in result.inventory.items:
            key = (item.source_path, item.scope, item.workspace_path)
            self.assertNotIn(key, seen)
            seen.add(key)
        # Unique source cache keys: 3 scoped refs → 1 unique path for principles.
        unique = result.inventory.unique_source_paths()
        self.assertEqual(unique.count(CORE_PRINCIPLES), 1)
        self.assertLess(len(unique), len(result.inventory.items))

    def test_inventory_ordering(self):
        config = ProjectConfig(
            2,
            ("devops",),
            ("cursor",),
            (
                WorkspaceIntent("packages/shared", ("typescript",)),
                WorkspaceIntent("apps/mobile", ("flutter",)),
                WorkspaceIntent("apps/web", ("frontend",)),
                WorkspaceIntent("apps/api", ("symfony",)),
            ),
        )
        result = resolve_project_composition(config, self.registry)
        items = result.inventory.items
        # GLOBAL first
        first_workspace_index = next(
            i for i, item in enumerate(items) if item.scope is KnowledgeScope.WORKSPACE
        )
        self.assertTrue(
            all(item.scope is KnowledgeScope.GLOBAL for item in items[:first_workspace_index])
        )
        workspace_order = []
        for item in items[first_workspace_index:]:
            if not workspace_order or workspace_order[-1] != item.workspace_path:
                workspace_order.append(item.workspace_path)
        self.assertEqual(
            workspace_order,
            ["apps/api", "apps/mobile", "apps/web", "packages/shared"],
        )
        # Within each scope, match ResolvedComposition.knowledge_paths.
        self.assertEqual(
            tuple(item.source_path for item in result.inventory.global_items()),
            result.root.knowledge_paths,
        )
        for workspace in result.workspaces:
            self.assertEqual(
                tuple(
                    item.source_path
                    for item in result.inventory.workspace_items(workspace.path)
                ),
                workspace.composition.knowledge_paths,
            )

    def test_reference_monorepo_resolution(self):
        config = ProjectConfig(
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
        result = resolve_project_composition(config, self.registry)
        self.assertEqual(len(result.workspaces), 4)
        self.assertEqual(
            [item.path for item in result.workspaces],
            ["apps/api", "apps/mobile", "apps/web", "packages/shared"],
        )
        expected = {
            "apps/api": ("core", "php", "symfony"),
            "apps/mobile": ("core", "flutter"),
            "apps/web": ("core", "typescript", "frontend"),
            "packages/shared": ("core", "typescript"),
        }
        for workspace in result.workspaces:
            self.assertEqual(
                workspace.composition.resolved_components,
                expected[workspace.path],
            )
        self.assertEqual(result.root.resolved_components, ("core", "devops"))

    def test_config_hash_independent_of_resolution(self):
        config = ProjectConfig(
            2,
            ("devops",),
            ("cursor",),
            (WorkspaceIntent("apps/api", ("symfony",)),),
        )
        before = configuration_sha256(config, self.registry)
        resolve_project_composition(config, self.registry)
        after = configuration_sha256(config, self.registry)
        self.assertEqual(before, after)
        # Still the AZ-A golden for empty-root-like? This one has devops root.
        # Just assert resolution does not mutate config identity hashing.

    def test_resolve_composition_empty_still_refuses(self):
        with self.assertRaises(CompositionError):
            resolve_composition([], self.registry)


class AssemblyPrepareBoundaryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.registry = ComponentRegistry.load()

    def test_prepare_does_not_invoke_adapters_or_indexes(self):
        config = ProjectConfig(
            2,
            (),
            ("cursor",),
            (WorkspaceIntent("apps/api", ("symfony",)),),
        )
        service = AssemblyService()
        with mock.patch.object(service, "_generate_indexes") as indexes:
            with mock.patch.object(service, "_run_assemble") as assemble:
                with mock.patch.object(service, "_run_assemble_resolved") as resolved:
                    result = service.prepare_project_composition(
                        config, registry=self.registry
                    )
        indexes.assert_not_called()
        assemble.assert_not_called()
        resolved.assert_not_called()
        self.assertIsNone(result.root)
        self.assertEqual(len(result.workspaces), 1)


if __name__ == "__main__":
    unittest.main()
