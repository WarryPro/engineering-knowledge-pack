"""Composition → existing assembly pipeline tests (AW-C)."""

from __future__ import annotations

import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

from ekp.assembly import (
    AssemblyRequest,
    AssemblyResult,
    AssemblyService,
    CompositionAssemblyRequest,
)
from ekp.composition import (
    COMPOSITION_ADAPTER_PRIORITIES,
    PROJECT_COMPOSITION_PROFILE,
    ComponentRegistry,
    CompositionError,
    build_ephemeral_composition_profile,
    resolve_composition,
    resolve_knowledge_paths,
)
from ekp.paths import get_ekp_root

REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPTS_ADAPTERS = REPO_ROOT / "scripts" / "adapters"
SCRIPTS_ASSEMBLE = REPO_ROOT / "scripts" / "assemble"
if str(SCRIPTS_ADAPTERS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ADAPTERS))
if str(SCRIPTS_ASSEMBLE) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ASSEMBLE))

from assemble import assemble, assemble_resolved_profile  # noqa: E402
from common.profile_loader import load_profile_by_name  # noqa: E402
from common.profile_resolve import resolve_profile_knowledge  # noqa: E402


def _mdc_inventory(cursor_dir: Path):
    files = sorted(cursor_dir.glob("*.mdc"))
    return {path.name: hashlib.sha256(path.read_bytes()).hexdigest() for path in files}


class ResolvedCompositionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.registry = ComponentRegistry.load()

    def test_symfony_reduction_and_closure(self):
        for request in (
            ["symfony"],
            ["php", "symfony"],
            ["core", "php", "symfony"],
        ):
            resolved = resolve_composition(request, self.registry)
            self.assertEqual(resolved.requested_components, ("symfony",))
            self.assertEqual(
                resolved.resolved_components, ("core", "php", "symfony")
            )

    def test_multi_stack_closure(self):
        resolved = resolve_composition(["symfony", "frontend"], self.registry)
        self.assertEqual(
            resolved.requested_components, ("frontend", "symfony")
        )
        self.assertEqual(
            resolved.resolved_components,
            ("core", "php", "symfony", "typescript", "frontend"),
        )

    def test_devops_composition(self):
        resolved = resolve_composition(
            ["symfony", "frontend", "devops"], self.registry
        )
        # Dependency-first with lexical ready-node ties: devops (→core) precedes php.
        self.assertEqual(
            resolved.resolved_components,
            ("core", "devops", "php", "symfony", "typescript", "frontend"),
        )
        self.assertEqual(
            set(resolved.resolved_components),
            {"core", "php", "symfony", "typescript", "frontend", "devops"},
        )

    def test_empty_components_fail(self):
        with self.assertRaises(CompositionError):
            resolve_composition([], self.registry)

    def test_unknown_component_fail(self):
        with self.assertRaises(CompositionError):
            resolve_composition(["does-not-exist"], self.registry)

    def test_duplicate_requests_safe(self):
        resolved = resolve_composition(["symfony", "symfony"], self.registry)
        self.assertEqual(resolved.requested_components, ("symfony",))
        self.assertEqual(
            len(resolved.knowledge_paths), len(set(resolved.knowledge_paths))
        )

    def test_ephemeral_profile_contract(self):
        composition = resolve_composition(["symfony"], self.registry)
        profile = build_ephemeral_composition_profile(composition, ["cursor"])
        self.assertEqual(
            profile,
            {
                "name": PROJECT_COMPOSITION_PROFILE,
                "description": "Ephemeral composition of: symfony",
                "knowledge": list(composition.knowledge_paths),
                "adapter_priorities": list(COMPOSITION_ADAPTER_PRIORITIES),
                "outputs": ["cursor"],
            },
        )
        self.assertNotIn("includes", profile)

    def test_empty_outputs_fail(self):
        composition = resolve_composition(["core"], self.registry)
        with self.assertRaises(CompositionError):
            build_ephemeral_composition_profile(composition, [])


class KnowledgeParityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root = get_ekp_root()
        cls.registry = ComponentRegistry.load(cls.root)

    def test_eight_component_knowledge_parity(self):
        for component_id in self.registry.list_ids():
            component = self.registry.get(component_id)
            self.assertIsNotNone(component.legacy_profile)
            composition = resolve_composition([component_id], self.registry)
            legacy = resolve_profile_knowledge(self.root, component.legacy_profile)
            self.assertEqual(
                list(composition.knowledge_paths),
                legacy,
                msg="knowledge parity failed for {}".format(component_id),
            )


class CompositionAssemblyParityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.service = AssemblyService()
        cls.root = get_ekp_root()
        cls.registry = ComponentRegistry.load(cls.root)

    def _assemble_profile(self, profile: str, tmp: Path) -> AssemblyResult:
        return self.service.assemble(
            AssemblyRequest(
                profile=profile,
                verify=True,
                clean=True,
                resource_root=self.root,
                workspace_dir=tmp / "workspace-{}".format(profile),
                output_root=tmp / "output-{}".format(profile),
            )
        )

    def _assemble_components(self, components, tmp: Path, tag: str) -> AssemblyResult:
        return self.service.assemble_composition(
            CompositionAssemblyRequest(
                components=list(components),
                outputs=["cursor"],
                verify=True,
                clean=True,
                resource_root=self.root,
                workspace_dir=tmp / "workspace-{}".format(tag),
                output_root=tmp / "output-{}".format(tag),
            )
        )

    def test_eight_component_cursor_byte_parity(self):
        with tempfile.TemporaryDirectory(prefix="ekp-awc-parity-") as tmp:
            tmp_path = Path(tmp)
            for component_id in self.registry.list_ids():
                component = self.registry.get(component_id)
                legacy = self._assemble_profile(component.legacy_profile, tmp_path)
                composed = self._assemble_components(
                    [component_id], tmp_path, "comp-{}".format(component_id)
                )
                self.assertEqual(composed.profile, PROJECT_COMPOSITION_PROFILE)
                self.assertIsNotNone(composed.composition)
                legacy_inv = _mdc_inventory(legacy.bundle_path / "cursor")
                composed_inv = _mdc_inventory(composed.bundle_path / "cursor")
                self.assertEqual(
                    composed_inv,
                    legacy_inv,
                    msg="Cursor byte parity failed for {}".format(component_id),
                )
                self.assertEqual(composed.rules_count, legacy.rules_count)

    def test_core_only_rule_count(self):
        with tempfile.TemporaryDirectory(prefix="ekp-awc-core-") as tmp:
            result = self._assemble_components(["core"], Path(tmp), "core")
            self.assertEqual(result.rules_count, 65)
            self.assertEqual(len(list((result.bundle_path / "cursor").glob("*.mdc"))), 65)

    def test_symfony_composition(self):
        with tempfile.TemporaryDirectory(prefix="ekp-awc-sf-") as tmp:
            result = self._assemble_components(["symfony"], Path(tmp), "sf")
            self.assertEqual(
                result.composition.resolved_components, ("core", "php", "symfony")
            )
            self.assertEqual(result.rules_count, 83)

    def test_symfony_frontend_composition(self):
        with tempfile.TemporaryDirectory(prefix="ekp-awc-sf-fe-") as tmp:
            result = self._assemble_components(
                ["symfony", "frontend"], Path(tmp), "sf-fe"
            )
            self.assertEqual(
                result.composition.resolved_components,
                ("core", "php", "symfony", "typescript", "frontend"),
            )
            knowledge = resolve_knowledge_paths(
                list(result.composition.resolved_components), self.registry
            )
            self.assertEqual(list(result.composition.knowledge_paths), knowledge)
            self.assertEqual(
                len(result.composition.knowledge_paths),
                len(set(result.composition.knowledge_paths)),
            )
            self.assertTrue((result.bundle_path / "cursor").is_dir())
            self.assertGreater(result.rules_count, 83)
            # No physical combination profile required.
            self.assertFalse(
                (self.root / "profiles" / "cursor-symfony-frontend.yaml").exists()
            )

    def test_request_order_determinism(self):
        with tempfile.TemporaryDirectory(prefix="ekp-awc-order-") as tmp:
            tmp_path = Path(tmp)
            a = self._assemble_components(["symfony", "frontend"], tmp_path, "a")
            b = self._assemble_components(["frontend", "symfony"], tmp_path, "b")
            self.assertEqual(a.composition, b.composition)
            self.assertEqual(
                _mdc_inventory(a.bundle_path / "cursor"),
                _mdc_inventory(b.bundle_path / "cursor"),
            )

    def test_redundant_dependency_request_determinism(self):
        with tempfile.TemporaryDirectory(prefix="ekp-awc-redund-") as tmp:
            tmp_path = Path(tmp)
            variants = [
                ["symfony"],
                ["php", "symfony"],
                ["core", "php", "symfony"],
            ]
            inventories = []
            for index, components in enumerate(variants):
                result = self._assemble_components(
                    components, tmp_path, "r{}".format(index)
                )
                inventories.append(_mdc_inventory(result.bundle_path / "cursor"))
                self.assertEqual(result.composition.requested_components, ("symfony",))
            self.assertEqual(inventories[0], inventories[1])
            self.assertEqual(inventories[1], inventories[2])

    def test_symfony_frontend_devops(self):
        with tempfile.TemporaryDirectory(prefix="ekp-awc-devops-") as tmp:
            result = self._assemble_components(
                ["symfony", "frontend", "devops"], Path(tmp), "sfd"
            )
            self.assertEqual(
                result.composition.resolved_components,
                ("core", "devops", "php", "symfony", "typescript", "frontend"),
            )
            self.assertEqual(
                len(result.composition.knowledge_paths),
                len(set(result.composition.knowledge_paths)),
            )
            self.assertGreater(result.rules_count, 0)
            self.assertEqual(
                len(list((result.bundle_path / "cursor").glob("*.mdc"))),
                result.rules_count,
            )

    def test_invalid_component_fails_before_bundle(self):
        with tempfile.TemporaryDirectory(prefix="ekp-awc-bad-") as tmp:
            tmp_path = Path(tmp)
            with self.assertRaises(RuntimeError):
                self._assemble_components(["does-not-exist"], tmp_path, "bad")
            bundle = tmp_path / "output-bad" / PROJECT_COMPOSITION_PROFILE
            self.assertFalse(bundle.exists())

    def test_empty_components_fail(self):
        with tempfile.TemporaryDirectory(prefix="ekp-awc-empty-") as tmp:
            with self.assertRaises(RuntimeError):
                self._assemble_components([], Path(tmp), "empty")

    def test_empty_outputs_fail(self):
        with tempfile.TemporaryDirectory(prefix="ekp-awc-out-") as tmp:
            tmp_path = Path(tmp)
            with self.assertRaises(RuntimeError):
                self.service.assemble_composition(
                    CompositionAssemblyRequest(
                        components=["core"],
                        outputs=[],
                        resource_root=self.root,
                        workspace_dir=tmp_path / "workspace",
                        output_root=tmp_path / "output",
                    )
                )

    def test_clean_removes_stale_composition(self):
        with tempfile.TemporaryDirectory(prefix="ekp-awc-clean-") as tmp:
            tmp_path = Path(tmp)
            workspace = tmp_path / "workspace"
            output = tmp_path / "output"
            first = self.service.assemble_composition(
                CompositionAssemblyRequest(
                    components=["symfony", "frontend"],
                    verify=True,
                    clean=True,
                    resource_root=self.root,
                    workspace_dir=workspace,
                    output_root=output,
                )
            )
            first_count = first.rules_count
            second = self.service.assemble_composition(
                CompositionAssemblyRequest(
                    components=["symfony"],
                    verify=True,
                    clean=True,
                    resource_root=self.root,
                    workspace_dir=workspace,
                    output_root=output,
                )
            )
            self.assertEqual(second.rules_count, 83)
            self.assertLess(second.rules_count, first_count)
            self.assertEqual(
                _mdc_inventory(second.bundle_path / "cursor"),
                _mdc_inventory(
                    self._assemble_components(["symfony"], tmp_path, "sf-ref").bundle_path
                    / "cursor"
                ),
            )

    def test_temp_workspace_default(self):
        result = self.service.assemble_composition(
            CompositionAssemblyRequest(
                components=["core"],
                verify=True,
                resource_root=self.root,
            )
        )
        self.assertEqual(result.rules_count, 65)
        self.assertIsNotNone(result._temp_ctx)
        self.assertFalse(
            str(result.bundle_path).startswith(str(self.root / "dist"))
        )

    def test_profile_assembly_composition_is_none(self):
        with tempfile.TemporaryDirectory(prefix="ekp-awc-prof-") as tmp:
            result = self._assemble_profile("cursor-core", Path(tmp))
            self.assertIsNone(result.composition)
            self.assertEqual(result.profile, "cursor-core")
            self.assertEqual(result.rules_count, 65)


class AssembleResolvedProfileTests(unittest.TestCase):
    """Prove reusable resolved-profile core accepts in-memory contracts."""

    def test_assemble_resolved_profile_with_ephemeral_contract(self):
        with tempfile.TemporaryDirectory(prefix="ekp-awc-resolved-") as tmp:
            tmp_path = Path(tmp)
            service = AssemblyService()
            # Generate indexes via service helper path.
            workspace = tmp_path / "workspace"
            output = tmp_path / "output"
            workspace.mkdir()
            output.mkdir()
            service._generate_indexes(get_ekp_root(), workspace)

            registry = ComponentRegistry.load()
            composition = resolve_composition(["core"], registry)
            profile = build_ephemeral_composition_profile(composition, ["cursor"])
            manifest = assemble_resolved_profile(
                profile_name=PROJECT_COMPOSITION_PROFILE,
                profile=profile,
                clean=True,
                verify=True,
                repo_root=get_ekp_root(),
                dist_dir=workspace,
                bundle_root=output,
            )
            self.assertEqual(manifest["profile"], PROJECT_COMPOSITION_PROFILE)
            self.assertEqual(manifest["rules_count"], 65)
            assemble_manifest = json.loads(
                (
                    output / PROJECT_COMPOSITION_PROFILE / "assemble-manifest.json"
                ).read_text(encoding="utf-8")
            )
            self.assertEqual(assemble_manifest["profile"], PROJECT_COMPOSITION_PROFILE)

    def test_named_assemble_still_loads_profile_yaml(self):
        with tempfile.TemporaryDirectory(prefix="ekp-awc-named-") as tmp:
            tmp_path = Path(tmp)
            service = AssemblyService()
            workspace = tmp_path / "workspace"
            output = tmp_path / "output"
            workspace.mkdir()
            output.mkdir()
            service._generate_indexes(get_ekp_root(), workspace)
            manifest = assemble(
                profile_name="cursor-core",
                clean=True,
                verify=True,
                repo_root=get_ekp_root(),
                dist_dir=workspace,
                bundle_root=output,
            )
            self.assertEqual(manifest["profile"], "cursor-core")
            self.assertEqual(manifest["rules_count"], 65)
            loaded = load_profile_by_name("cursor-core", repo_root=get_ekp_root())
            self.assertEqual(loaded["adapter_priorities"], ["high"])


if __name__ == "__main__":
    unittest.main()
