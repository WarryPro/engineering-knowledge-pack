"""Component registry, schema, and dependency closure tests."""

from __future__ import annotations

import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

import yaml
from jsonschema import Draft202012Validator

from ekp.composition import (
    ComponentRegistry,
    CompositionError,
    resolve_component_closure,
    resolve_knowledge_paths,
)
from ekp.paths import get_ekp_root

REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPTS_ADAPTERS = REPO_ROOT / "scripts" / "adapters"
if str(SCRIPTS_ADAPTERS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ADAPTERS))

from common.profile_resolve import resolve_profile_knowledge  # noqa: E402


class ComponentRegistryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root = get_ekp_root()
        cls.registry = ComponentRegistry.load(cls.root)

    def test_loads_eight_canonical_components(self):
        ids = self.registry.list_ids()
        self.assertEqual(
            ids,
            [
                "core",
                "devops",
                "flutter",
                "frontend",
                "nativescript",
                "php",
                "symfony",
                "typescript",
            ],
        )

    def test_filename_id_match_and_get(self):
        for component in self.registry.list_components():
            path = self.root / "components" / "{}.yaml".format(component.id)
            self.assertTrue(path.is_file())
            self.assertEqual(component.id, path.stem)
            self.assertIs(self.registry.get(component.id), component)

    def test_unknown_component_rejected(self):
        with self.assertRaises(CompositionError) as ctx:
            self.registry.get("unknown-stack")
        self.assertIn("unknown component", str(ctx.exception))


class ComponentClosureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.registry = ComponentRegistry.load()

    def test_symfony_closure(self):
        self.assertEqual(
            resolve_component_closure(["symfony"], self.registry),
            ["core", "php", "symfony"],
        )

    def test_frontend_closure(self):
        self.assertEqual(
            resolve_component_closure(["frontend"], self.registry),
            ["core", "typescript", "frontend"],
        )

    def test_nativescript_closure(self):
        self.assertEqual(
            resolve_component_closure(["nativescript"], self.registry),
            ["core", "typescript", "nativescript"],
        )

    def test_flutter_closure(self):
        self.assertEqual(
            resolve_component_closure(["flutter"], self.registry),
            ["core", "flutter"],
        )

    def test_devops_closure(self):
        self.assertEqual(
            resolve_component_closure(["devops"], self.registry),
            ["core", "devops"],
        )

    def test_multi_component_dedupe(self):
        self.assertEqual(
            resolve_component_closure(["symfony", "frontend"], self.registry),
            ["core", "php", "symfony", "typescript", "frontend"],
        )

    def test_multi_component_with_devops(self):
        resolved = resolve_component_closure(
            ["symfony", "frontend", "devops"], self.registry
        )
        self.assertEqual(
            resolved,
            ["core", "devops", "php", "symfony", "typescript", "frontend"],
        )
        self.assertEqual(len(resolved), len(set(resolved)))

    def test_redundant_request_normalized(self):
        self.assertEqual(
            resolve_component_closure(["symfony", "php", "symfony"], self.registry),
            ["core", "php", "symfony"],
        )

    def test_unknown_component_fails(self):
        with self.assertRaises(CompositionError) as ctx:
            resolve_component_closure(["unknown-stack"], self.registry)
        self.assertIn("unknown component", str(ctx.exception))

    def test_closure_independent_of_request_order(self):
        a = resolve_component_closure(["frontend", "symfony"], self.registry)
        b = resolve_component_closure(["symfony", "frontend"], self.registry)
        self.assertEqual(a, b)


class ComponentGraphValidationTests(unittest.TestCase):
    def _write_component(self, root: Path, payload: dict) -> None:
        components = root / "components"
        components.mkdir(parents=True, exist_ok=True)
        path = components / "{}.yaml".format(payload["id"])
        path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")

    def _seed_minimal_tree(self, root: Path) -> None:
        # Copy schema + one real knowledge file for path validation.
        shutil.copytree(REPO_ROOT / "schema", root / "schema")
        knowledge = root / "knowledge" / "engineering"
        knowledge.mkdir(parents=True)
        src = (
            REPO_ROOT
            / "knowledge"
            / "engineering"
            / "engineering-principles.md"
        )
        shutil.copy2(src, knowledge / "engineering-principles.md")
        profiles = root / "profiles"
        profiles.mkdir(parents=True)
        (profiles / "cursor-core.yaml").write_text(
            "name: cursor-core\ndescription: test\nknowledge:\n"
            "  - knowledge/engineering/engineering-principles.md\n",
            encoding="utf-8",
        )
        self._write_component(
            root,
            {
                "id": "core",
                "layer": "L0",
                "requires": [],
                "selectable": True,
                "legacy_profile": "cursor-core",
                "knowledge": ["knowledge/engineering/engineering-principles.md"],
            },
        )

    def test_unknown_dependency_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._seed_minimal_tree(root)
            self._write_component(
                root,
                {
                    "id": "broken",
                    "layer": "L1",
                    "requires": ["missing-component"],
                    "selectable": True,
                    "knowledge": ["knowledge/engineering/engineering-principles.md"],
                },
            )
            with self.assertRaises(CompositionError) as ctx:
                ComponentRegistry.load(root)
            self.assertIn("unknown dependency", str(ctx.exception))

    def test_cycle_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._seed_minimal_tree(root)
            # Replace core knowledge ownership conflict by using unique paths for a/b.
            # Use same knowledge file for both a and b would fail ownership first —
            # create two stub knowledge files.
            (root / "knowledge" / "a.md").write_text("# A\n", encoding="utf-8")
            (root / "knowledge" / "b.md").write_text("# B\n", encoding="utf-8")
            self._write_component(
                root,
                {
                    "id": "a",
                    "layer": "L1",
                    "requires": ["b"],
                    "selectable": True,
                    "knowledge": ["knowledge/a.md"],
                },
            )
            self._write_component(
                root,
                {
                    "id": "b",
                    "layer": "L1",
                    "requires": ["a"],
                    "selectable": True,
                    "knowledge": ["knowledge/b.md"],
                },
            )
            with self.assertRaises(CompositionError) as ctx:
                ComponentRegistry.load(root)
            self.assertIn("cycle", str(ctx.exception).lower())

    def test_higher_layer_dependency_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._seed_minimal_tree(root)
            (root / "knowledge" / "php.md").write_text("# PHP\n", encoding="utf-8")
            (root / "knowledge" / "symfony.md").write_text("# SY\n", encoding="utf-8")
            self._write_component(
                root,
                {
                    "id": "php",
                    "layer": "L1",
                    "requires": ["core"],
                    "selectable": True,
                    "knowledge": ["knowledge/php.md"],
                },
            )
            self._write_component(
                root,
                {
                    "id": "symfony",
                    "layer": "L2",
                    "requires": ["php"],
                    "selectable": True,
                    "knowledge": ["knowledge/symfony.md"],
                },
            )
            # Invalidate: php requires higher-layer symfony
            self._write_component(
                root,
                {
                    "id": "php",
                    "layer": "L1",
                    "requires": ["symfony"],
                    "selectable": True,
                    "knowledge": ["knowledge/php.md"],
                },
            )
            with self.assertRaises(CompositionError) as ctx:
                ComponentRegistry.load(root)
            self.assertIn("higher-layer", str(ctx.exception))

    def test_duplicate_direct_knowledge_ownership_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._seed_minimal_tree(root)
            shared = "knowledge/engineering/engineering-principles.md"
            self._write_component(
                root,
                {
                    "id": "php",
                    "layer": "L1",
                    "requires": ["core"],
                    "selectable": True,
                    "knowledge": [shared],
                },
            )
            with self.assertRaises(CompositionError) as ctx:
                ComponentRegistry.load(root)
            self.assertIn("claimed by both", str(ctx.exception))


class ComponentKnowledgeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.registry = ComponentRegistry.load()

    def test_all_non_core_reach_core(self):
        for component_id in self.registry.list_ids():
            if component_id == "core":
                continue
            closed = resolve_component_closure([component_id], self.registry)
            self.assertIn("core", closed)

    def test_resolved_knowledge_deterministic(self):
        closed = resolve_component_closure(["symfony", "frontend"], self.registry)
        paths_a = resolve_knowledge_paths(closed, self.registry)
        paths_b = resolve_knowledge_paths(closed, self.registry)
        self.assertEqual(paths_a, paths_b)
        self.assertEqual(len(paths_a), len(set(paths_a)))


class LegacyProfileParityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root = get_ekp_root()
        cls.registry = ComponentRegistry.load(cls.root)

    def _assert_parity(self, component_id: str) -> None:
        component = self.registry.get(component_id)
        self.assertIsNotNone(component.legacy_profile)
        closed = resolve_component_closure([component_id], self.registry)
        composed = resolve_knowledge_paths(closed, self.registry)
        legacy = resolve_profile_knowledge(self.root, component.legacy_profile)
        self.assertEqual(
            composed,
            legacy,
            msg="parity failed for {} ↔ {}".format(
                component_id, component.legacy_profile
            ),
        )

    def test_core_parity(self):
        self._assert_parity("core")

    def test_php_parity(self):
        self._assert_parity("php")

    def test_symfony_parity(self):
        self._assert_parity("symfony")

    def test_typescript_parity(self):
        self._assert_parity("typescript")

    def test_frontend_parity(self):
        self._assert_parity("frontend")

    def test_devops_parity(self):
        self._assert_parity("devops")

    def test_nativescript_parity(self):
        self._assert_parity("nativescript")

    def test_flutter_parity(self):
        self._assert_parity("flutter")


class ComponentSchemaTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        schema_path = get_ekp_root() / "schema" / "component.schema.json"
        cls.schema = json.loads(schema_path.read_text(encoding="utf-8"))
        cls.validator = Draft202012Validator(cls.schema)

    def _errors(self, payload):
        return list(self.validator.iter_errors(payload))

    def test_valid_component(self):
        payload = {
            "id": "php",
            "layer": "L1",
            "requires": ["core"],
            "knowledge": ["knowledge/php/php-fundamentals.md"],
            "selectable": True,
            "legacy_profile": "cursor-php",
        }
        self.assertEqual(self._errors(payload), [])

    def test_invalid_id(self):
        payload = {
            "id": "PHP",
            "layer": "L1",
            "requires": [],
            "knowledge": ["knowledge/php/php-fundamentals.md"],
            "selectable": True,
        }
        self.assertTrue(self._errors(payload))

    def test_invalid_layer(self):
        payload = {
            "id": "php",
            "layer": "L9",
            "requires": [],
            "knowledge": ["knowledge/php/php-fundamentals.md"],
            "selectable": True,
        }
        self.assertTrue(self._errors(payload))

    def test_duplicate_requires_rejected(self):
        payload = {
            "id": "symfony",
            "layer": "L2",
            "requires": ["php", "php"],
            "knowledge": ["knowledge/symfony/symfony-architecture.md"],
            "selectable": True,
        }
        self.assertTrue(self._errors(payload))

    def test_duplicate_knowledge_rejected(self):
        path = "knowledge/symfony/symfony-architecture.md"
        payload = {
            "id": "symfony",
            "layer": "L2",
            "requires": ["php"],
            "knowledge": [path, path],
            "selectable": True,
        }
        self.assertTrue(self._errors(payload))

    def test_unknown_property_rejected(self):
        payload = {
            "id": "php",
            "layer": "L1",
            "requires": ["core"],
            "knowledge": ["knowledge/php/php-fundamentals.md"],
            "selectable": True,
            "outputs": ["cursor"],
        }
        self.assertTrue(self._errors(payload))

    def test_unsafe_knowledge_path_pattern_rejected(self):
        payload = {
            "id": "php",
            "layer": "L1",
            "requires": ["core"],
            "knowledge": ["../secrets.md"],
            "selectable": True,
        }
        self.assertTrue(self._errors(payload))


if __name__ == "__main__":
    unittest.main()
