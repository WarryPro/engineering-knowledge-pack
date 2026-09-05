"""Project intent configuration (.ekp/project.yaml) contract tests."""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
import unittest
from pathlib import Path

import yaml
from jsonschema import Draft202012Validator

from ekp.composition import Component, ComponentRegistry
from ekp.config import (
    PROJECT_CONFIG_RELATIVE,
    SUPPORTED_PROJECT_ASSISTANTS,
    ProjectConfig,
    ProjectConfigError,
    ProjectConfigStore,
    configuration_sha256,
    normalize_project_config,
)
from ekp.config.project import render_project_config_yaml, validate_project_config_payload
from ekp.paths import get_ekp_root


def _synthetic_registry() -> ComponentRegistry:
    components = {
        "core": Component(
            id="core",
            layer="L0",
            requires=(),
            knowledge=(),
            selectable=True,
        ),
        "hidden": Component(
            id="hidden",
            layer="L1",
            requires=("core",),
            knowledge=(),
            selectable=False,
        ),
        "visible": Component(
            id="visible",
            layer="L1",
            requires=("core",),
            knowledge=(),
            selectable=True,
        ),
    }
    return ComponentRegistry(components, Path(tempfile.gettempdir()))


class ProjectConfigSchemaTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        schema_path = get_ekp_root() / "schema" / "project-config.schema.json"
        cls.schema = json.loads(schema_path.read_text(encoding="utf-8"))
        cls.validator = Draft202012Validator(cls.schema)

    def _errors(self, payload):
        return list(self.validator.iter_errors(payload))

    def test_valid_core_only(self):
        payload = {
            "schema_version": 1,
            "components": ["core"],
            "assistants": ["cursor"],
        }
        self.assertEqual(self._errors(payload), [])

    def test_valid_symfony(self):
        payload = {
            "schema_version": 1,
            "components": ["symfony"],
            "assistants": ["cursor"],
        }
        self.assertEqual(self._errors(payload), [])

    def test_valid_symfony_frontend(self):
        payload = {
            "schema_version": 1,
            "components": ["symfony", "frontend"],
            "assistants": ["cursor"],
        }
        self.assertEqual(self._errors(payload), [])

    def test_missing_schema_version(self):
        payload = {"components": ["core"], "assistants": ["cursor"]}
        self.assertTrue(self._errors(payload))

    def test_wrong_schema_version(self):
        payload = {
            "schema_version": 2,
            "components": ["core"],
            "assistants": ["cursor"],
        }
        self.assertTrue(self._errors(payload))

    def test_missing_components(self):
        payload = {"schema_version": 1, "assistants": ["cursor"]}
        self.assertTrue(self._errors(payload))

    def test_empty_components(self):
        payload = {
            "schema_version": 1,
            "components": [],
            "assistants": ["cursor"],
        }
        self.assertTrue(self._errors(payload))

    def test_duplicate_components(self):
        payload = {
            "schema_version": 1,
            "components": ["symfony", "symfony"],
            "assistants": ["cursor"],
        }
        self.assertTrue(self._errors(payload))

    def test_missing_assistants(self):
        payload = {"schema_version": 1, "components": ["core"]}
        self.assertTrue(self._errors(payload))

    def test_empty_assistants(self):
        payload = {
            "schema_version": 1,
            "components": ["core"],
            "assistants": [],
        }
        self.assertTrue(self._errors(payload))

    def test_duplicate_assistants(self):
        payload = {
            "schema_version": 1,
            "components": ["core"],
            "assistants": ["cursor", "cursor"],
        }
        self.assertTrue(self._errors(payload))

    def test_unknown_key(self):
        payload = {
            "schema_version": 1,
            "components": ["core"],
            "assistants": ["cursor"],
            "profile": "cursor-core",
        }
        self.assertTrue(self._errors(payload))

    def test_assistant_id_pattern_allows_future_ids(self):
        payload = {
            "schema_version": 1,
            "components": ["core"],
            "assistants": ["copilot"],
        }
        self.assertEqual(self._errors(payload), [])


class ProjectConfigSemanticTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.registry = ComponentRegistry.load()
        cls.schema = json.loads(
            (get_ekp_root() / "schema" / "project-config.schema.json").read_text(
                encoding="utf-8"
            )
        )

    def _validate(self, payload, registry=None):
        return validate_project_config_payload(
            payload,
            registry or self.registry,
            schema=self.schema,
        )

    def test_unknown_component_rejected(self):
        with self.assertRaises(ProjectConfigError) as ctx:
            self._validate(
                {
                    "schema_version": 1,
                    "components": ["symfony", "made-up-framework"],
                    "assistants": ["cursor"],
                }
            )
        self.assertIn("unknown component", str(ctx.exception))

    def test_non_selectable_component_rejected(self):
        registry = _synthetic_registry()
        with self.assertRaises(ProjectConfigError) as ctx:
            self._validate(
                {
                    "schema_version": 1,
                    "components": ["hidden"],
                    "assistants": ["cursor"],
                },
                registry=registry,
            )
        self.assertIn("not selectable", str(ctx.exception))

    def test_cursor_assistant_accepted(self):
        config = self._validate(
            {
                "schema_version": 1,
                "components": ["core"],
                "assistants": ["cursor"],
            }
        )
        self.assertEqual(config.assistants, ("cursor",))

    def test_copilot_rejected(self):
        with self.assertRaises(ProjectConfigError) as ctx:
            self._validate(
                {
                    "schema_version": 1,
                    "components": ["core"],
                    "assistants": ["copilot"],
                }
            )
        self.assertIn("unsupported assistant", str(ctx.exception))

    def test_claude_rejected(self):
        with self.assertRaises(ProjectConfigError) as ctx:
            self._validate(
                {
                    "schema_version": 1,
                    "components": ["core"],
                    "assistants": ["claude"],
                }
            )
        self.assertIn("unsupported assistant", str(ctx.exception))

    def test_antigravity_rejected(self):
        with self.assertRaises(ProjectConfigError) as ctx:
            self._validate(
                {
                    "schema_version": 1,
                    "components": ["core"],
                    "assistants": ["antigravity"],
                }
            )
        self.assertIn("unsupported assistant", str(ctx.exception))

    def test_unknown_assistant_rejected(self):
        with self.assertRaises(ProjectConfigError) as ctx:
            self._validate(
                {
                    "schema_version": 1,
                    "components": ["core"],
                    "assistants": ["unknown"],
                }
            )
        self.assertIn("unsupported assistant", str(ctx.exception))

    def test_supported_assistants_constant(self):
        self.assertEqual(SUPPORTED_PROJECT_ASSISTANTS, ("cursor",))


class ProjectConfigNormalizationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.registry = ComponentRegistry.load()

    def _hash(self, components, assistants=("cursor",)):
        config = ProjectConfig(
            schema_version=1,
            components=tuple(components),
            assistants=tuple(assistants),
        )
        return configuration_sha256(config, self.registry)

    def test_order_insensitive_components(self):
        self.assertEqual(
            self._hash(["symfony", "frontend"]),
            self._hash(["frontend", "symfony"]),
        )

    def test_redundant_deps_same_hash(self):
        a = self._hash(["symfony"])
        b = self._hash(["php", "symfony"])
        c = self._hash(["core", "php", "symfony"])
        self.assertEqual(a, b)
        self.assertEqual(b, c)

    def test_different_composition_different_hash(self):
        self.assertNotEqual(
            self._hash(["symfony"]),
            self._hash(["symfony", "frontend"]),
        )

    def test_hash_deterministic(self):
        first = self._hash(["frontend", "symfony"])
        second = self._hash(["frontend", "symfony"])
        self.assertEqual(first, second)
        self.assertEqual(len(first), 64)

    def test_normalized_payload_shape(self):
        config = ProjectConfig(
            schema_version=1,
            components=("symfony", "frontend"),
            assistants=("cursor",),
        )
        normalized = normalize_project_config(config, self.registry)
        self.assertEqual(
            normalized,
            {
                "schema_version": 1,
                "components": ["frontend", "symfony"],
                "assistants": ["cursor"],
            },
        )

    def test_assistant_set_change_alters_hash(self):
        a = self._hash(["symfony"], assistants=("cursor",))
        b = self._hash(["symfony"], assistants=("cursor", "copilot"))
        self.assertNotEqual(a, b)

    def test_yaml_formatting_does_not_affect_hash(self):
        registry = self.registry
        schema = json.loads(
            (get_ekp_root() / "schema" / "project-config.schema.json").read_text(
                encoding="utf-8"
            )
        )
        variants = [
            "schema_version: 1\ncomponents:\n  - symfony\n  - frontend\nassistants:\n  - cursor\n",
            "assistants:\n- cursor\ncomponents:\n- frontend\n- symfony\nschema_version: 1\n",
            "# comment\n\nschema_version: 1\n\ncomponents:\n  -   symfony\n  - frontend\nassistants:\n  - cursor\n",
        ]
        digests = []
        for text in variants:
            payload = yaml.safe_load(text)
            config = validate_project_config_payload(payload, registry, schema=schema)
            digests.append(configuration_sha256(config, registry))
        self.assertEqual(len(set(digests)), 1)


class ProjectConfigLoadCreateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.registry = ComponentRegistry.load()

    def _store(self, project: Path) -> ProjectConfigStore:
        return ProjectConfigStore(project, registry=self.registry)

    def test_missing_config_returns_none(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = self._store(Path(tmp))
            self.assertIsNone(store.load())
            self.assertIsNone(store.load_snapshot())

    def test_valid_config_loads_with_hash(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            ekp = project / ".ekp"
            ekp.mkdir()
            (ekp / "project.yaml").write_bytes(
                (
                    "schema_version: 1\ncomponents:\n  - symfony\n  - frontend\n"
                    "assistants:\n  - cursor\n"
                ).encode("utf-8")
            )
            store = self._store(project)
            config = store.load()
            self.assertIsNotNone(config)
            self.assertEqual(config.components, ("symfony", "frontend"))
            snapshot = store.load_snapshot()
            self.assertEqual(
                snapshot.configuration_sha256,
                configuration_sha256(config, self.registry),
            )
            # load must not rewrite the user file
            raw = (ekp / "project.yaml").read_bytes()
            self.assertIn(b"symfony", raw)

    def test_invalid_config_raises(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            ekp = project / ".ekp"
            ekp.mkdir()
            (ekp / "project.yaml").write_text(
                "schema_version: 1\ncomponents: []\nassistants:\n  - cursor\n",
                encoding="utf-8",
            )
            with self.assertRaises(ProjectConfigError):
                self._store(project).load()

    def test_unsupported_schema_raises(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            (project / ".ekp").mkdir()
            # Bypass schema const by writing invalid version after structural fail —
            # use a mapping that fails semantic schema_version check via validate path.
            (project / ".ekp" / "project.yaml").write_text(
                "schema_version: 99\ncomponents:\n  - core\nassistants:\n  - cursor\n",
                encoding="utf-8",
            )
            with self.assertRaises(ProjectConfigError) as ctx:
                self._store(project).load()
            self.assertTrue(
                "schema" in str(ctx.exception).lower()
                or "unsupported" in str(ctx.exception).lower()
            )

    def test_non_object_yaml_root_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            (project / ".ekp").mkdir()
            (project / ".ekp" / "project.yaml").write_text("- just-a-list\n", encoding="utf-8")
            with self.assertRaises(ProjectConfigError) as ctx:
                self._store(project).load()
            self.assertIn("mapping", str(ctx.exception))

    def test_invalid_yaml_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            (project / ".ekp").mkdir()
            (project / ".ekp" / "project.yaml").write_text(
                "schema_version: [\n", encoding="utf-8"
            )
            with self.assertRaises(ProjectConfigError) as ctx:
                self._store(project).load()
            self.assertIn("invalid YAML", str(ctx.exception))

    def test_create_missing_config(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            store = self._store(project)
            created = store.create(
                ProjectConfig(
                    schema_version=1,
                    components=("symfony", "frontend"),
                    assistants=("cursor",),
                )
            )
            self.assertEqual(created.components, ("symfony", "frontend"))
            path = project / ".ekp" / "project.yaml"
            text = path.read_text(encoding="utf-8")
            self.assertEqual(
                text,
                "schema_version: 1\n"
                "components:\n"
                "  - symfony\n"
                "  - frontend\n"
                "assistants:\n"
                "  - cursor\n",
            )
            self.assertTrue(text.endswith("\n"))
            self.assertNotIn("\r", text)
            reloaded = store.load()
            self.assertEqual(reloaded, created)
            expected = configuration_sha256(created, self.registry)
            self.assertEqual(store.load_snapshot().configuration_sha256, expected)

    def test_create_preserves_requested_order(self):
        text = render_project_config_yaml(
            ProjectConfig(
                schema_version=1,
                components=("symfony", "frontend"),
                assistants=("cursor",),
            )
        )
        self.assertIn("  - symfony\n  - frontend\n", text)

    def test_create_refuses_existing(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            store = self._store(project)
            original = (
                "schema_version: 1\ncomponents:\n  - core\nassistants:\n  - cursor\n"
            )
            (project / ".ekp").mkdir()
            path = project / ".ekp" / "project.yaml"
            path.write_bytes(original.encode("utf-8"))
            before = path.read_bytes()
            with self.assertRaises(ProjectConfigError) as ctx:
                store.create(
                    ProjectConfig(
                        schema_version=1,
                        components=("symfony",),
                        assistants=("cursor",),
                    )
                )
            self.assertIn("already exists", str(ctx.exception))
            self.assertEqual(path.read_bytes(), before)

    def test_create_does_not_touch_install_manifest(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            store = self._store(project)
            store.create(
                ProjectConfig(
                    schema_version=1,
                    components=("core",),
                    assistants=("cursor",),
                )
            )
            self.assertFalse((project / ".ekp" / "install.json").exists())
            self.assertEqual(PROJECT_CONFIG_RELATIVE, ".ekp/project.yaml")

    def test_bundled_schema_available(self):
        path = get_ekp_root() / "schema" / "project-config.schema.json"
        self.assertTrue(path.is_file())
        schema = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(schema["properties"]["schema_version"]["const"], 1)


class ProjectConfigPathSafetyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.registry = ComponentRegistry.load()

    @unittest.skipUnless(os.name != "nt", "Symlink test skipped on Windows")
    def test_symlinked_project_yaml_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            project = root / "project"
            project.mkdir()
            (project / ".ekp").mkdir()
            outside = root / "outside-project.yaml"
            outside.write_text(
                "schema_version: 1\ncomponents:\n  - core\nassistants:\n  - cursor\n",
                encoding="utf-8",
            )
            (project / ".ekp" / "project.yaml").symlink_to(outside)
            store = ProjectConfigStore(project, registry=self.registry)
            with self.assertRaises(ProjectConfigError) as ctx:
                store.load()
            self.assertIn("symlink", str(ctx.exception).lower())

    @unittest.skipUnless(os.name != "nt", "Symlink test skipped on Windows")
    def test_symlinked_ekp_escaping_root_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            project = root / "project"
            project.mkdir()
            outside = root / "outside-ekp"
            outside.mkdir()
            (outside / "project.yaml").write_text(
                "schema_version: 1\ncomponents:\n  - core\nassistants:\n  - cursor\n",
                encoding="utf-8",
            )
            (project / ".ekp").symlink_to(outside, target_is_directory=True)
            with self.assertRaises(ProjectConfigError):
                ProjectConfigStore(project, registry=self.registry).load()


class ProjectConfigHashContractTests(unittest.TestCase):
    """Pin canonical serialization details for configuration_sha256."""

    @classmethod
    def setUpClass(cls):
        cls.registry = ComponentRegistry.load()

    def test_canonical_json_serialization(self):
        config = ProjectConfig(
            schema_version=1,
            components=("symfony", "frontend"),
            assistants=("cursor",),
        )
        normalized = normalize_project_config(config, self.registry)
        payload = json.dumps(
            normalized,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        )
        self.assertEqual(
            payload,
            '{"assistants":["cursor"],"components":["frontend","symfony"],"schema_version":1}',
        )
        digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()
        self.assertEqual(configuration_sha256(config, self.registry), digest)


if __name__ == "__main__":
    unittest.main()
