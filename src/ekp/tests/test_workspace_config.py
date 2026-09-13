"""Schema2 ProjectConfig and portable workspace-path foundation tests (AZ-A)."""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
import unittest
from pathlib import Path

import yaml
from jsonschema import Draft202012Validator

from ekp.composition import ComponentRegistry
from ekp.config import (
    ProjectConfig,
    ProjectConfigError,
    ProjectConfigStore,
    WorkspaceIntent,
    canonicalize_workspace_path,
    configuration_sha256,
    normalize_project_config,
)
from ekp.config.project import (
    project_config_content_sha256,
    render_project_config_yaml,
    validate_project_config_payload,
)
from ekp.config.workspaces import (
    validate_workspace_on_filesystem,
    workspace_paths_overlap,
)
from ekp.paths import get_ekp_root


SCHEMA2_HASH_A = "09cf2e9312aa182a2fc6438080bc4a9c687838077e4e7aeffe56c448e8655b14"
SCHEMA2_HASH_B = "e62a4fedaae9b849e684cab7ad01ed7f9e2eee0278b5e2d4515cb3d40b41308b"
SCHEMA2_HASH_C = "2320ef8549f08599beb643f9bb1d04de9304cda1531ec11d44d033fb44dae1de"


def _schema():
    return json.loads(
        (get_ekp_root() / "schema" / "project-config.schema.json").read_text(
            encoding="utf-8"
        )
    )


def _mkdir(root: Path, relative: str) -> Path:
    path = root / relative
    path.mkdir(parents=True, exist_ok=True)
    return path


class WorkspacePathCanonicalizationTests(unittest.TestCase):
    def test_accepts_canonical_relative_path(self):
        self.assertEqual(canonicalize_workspace_path("apps/api"), "apps/api")

    def test_rejects_empty_dot_absolute_drive_and_parent(self):
        cases = [
            "",
            ".",
            "/apps/api",
            "C:/apps/api",
            "C:\\apps\\api",
            "apps/../api",
            "apps/./api",
            "apps//api",
            "apps/api/",
            ".ekp",
            "apps/.ekp",
            ".ekp/apps",
        ]
        for raw in cases:
            with self.subTest(raw=raw):
                with self.assertRaises(ProjectConfigError):
                    canonicalize_workspace_path(raw)

    def test_rejects_backslash_and_glob_metacharacters(self):
        for raw in (
            "apps\\api",
            "apps/*/api",
            "apps/?/x",
            "apps/[a]/x",
            "apps/{a}/x",
        ):
            with self.subTest(raw=raw):
                with self.assertRaises(ProjectConfigError):
                    canonicalize_workspace_path(raw)

    def test_rejects_forbidden_portable_characters(self):
        for raw in (
            "apps/<api>",
            'apps/"api"',
            "apps/a:b",
            "apps/a|b",
        ):
            with self.subTest(raw=raw):
                with self.assertRaises(ProjectConfigError):
                    canonicalize_workspace_path(raw)

    def test_rejects_control_characters(self):
        with self.assertRaises(ProjectConfigError):
            canonicalize_workspace_path("apps/\x00api")

    def test_rejects_trailing_dot_or_space_segments(self):
        for raw in ("apps/api.", "apps/api ", "apps./x"):
            with self.subTest(raw=raw):
                with self.assertRaises(ProjectConfigError):
                    canonicalize_workspace_path(raw)

    def test_rejects_windows_reserved_device_names(self):
        for raw in (
            "CON",
            "con.txt",
            "apps/AUX",
            "packages/Lpt1.js",
            "foo/COM3.json",
            "nul",
        ):
            with self.subTest(raw=raw):
                with self.assertRaises(ProjectConfigError):
                    canonicalize_workspace_path(raw)

    def test_allows_non_reserved_similar_names(self):
        self.assertEqual(canonicalize_workspace_path("apps/console"), "apps/console")
        self.assertEqual(
            canonicalize_workspace_path("packages/auxiliary"),
            "packages/auxiliary",
        )

    def test_allows_unicode_segments(self):
        self.assertEqual(
            canonicalize_workspace_path("apps/serviço"),
            "apps/serviço",
        )


class WorkspaceOverlapTests(unittest.TestCase):
    def test_ancestor_descendant_overlap(self):
        self.assertTrue(workspace_paths_overlap("apps", "apps/api"))
        self.assertTrue(workspace_paths_overlap("apps/api", "apps"))

    def test_sibling_prefix_not_overlap(self):
        self.assertFalse(workspace_paths_overlap("apps/foo", "apps/foobar"))


class WorkspaceFilesystemValidationTests(unittest.TestCase):
    def test_exists_as_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _mkdir(root, "apps/api")
            validate_workspace_on_filesystem(root, "apps/api")

    def test_missing_and_file_refusals(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _mkdir(root, "apps")
            with self.assertRaises(ProjectConfigError):
                validate_workspace_on_filesystem(root, "apps/missing")
            file_path = root / "apps" / "file-ws"
            file_path.write_text("x", encoding="utf-8")
            with self.assertRaises(ProjectConfigError):
                validate_workspace_on_filesystem(root, "apps/file-ws")

    def test_symlink_final_and_intermediate_refusals(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            target = _mkdir(root, "apps/real")
            link = root / "apps" / "linked"
            try:
                os.symlink(str(target), str(link), target_is_directory=True)
            except OSError:
                self.skipTest("symlink creation not permitted on this platform")
            with self.assertRaises(ProjectConfigError):
                validate_workspace_on_filesystem(root, "apps/linked")

            intermediate = root / "apps" / "via"
            try:
                os.symlink(str(root / "apps"), str(intermediate), target_is_directory=True)
            except OSError:
                self.skipTest("symlink creation not permitted on this platform")
            with self.assertRaises(ProjectConfigError):
                validate_workspace_on_filesystem(root, "apps/via/real")


class Schema2JsonSchemaTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.schema = _schema()
        cls.validator = Draft202012Validator(cls.schema)

    def test_schema2_valid_empty_root(self):
        payload = {
            "schema_version": 2,
            "components": [],
            "assistants": ["cursor"],
            "workspaces": [{"path": "apps/api", "components": ["symfony"]}],
        }
        self.assertEqual(list(self.validator.iter_errors(payload)), [])

    def test_schema2_requires_workspaces(self):
        payload = {
            "schema_version": 2,
            "components": ["core"],
            "assistants": ["cursor"],
        }
        self.assertTrue(list(self.validator.iter_errors(payload)))

    def test_schema1_forbids_workspaces_property(self):
        payload = {
            "schema_version": 1,
            "components": ["core"],
            "assistants": ["cursor"],
            "workspaces": [{"path": "apps/api", "components": ["symfony"]}],
        }
        self.assertTrue(list(self.validator.iter_errors(payload)))


class Schema1RendererParityTests(unittest.TestCase):
    def test_schema1_render_bytes_unchanged(self):
        text = render_project_config_yaml(
            ProjectConfig(1, ("core",), ("cursor",))
        )
        self.assertEqual(
            text,
            "schema_version: 1\ncomponents:\n  - core\nassistants:\n  - cursor\n",
        )
        self.assertNotIn("workspaces", text)


class Schema2RenderRoundtripTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.registry = ComponentRegistry.load()
        cls.schema = _schema()

    def test_empty_root_render_and_roundtrip(self):
        config = ProjectConfig(
            schema_version=2,
            components=(),
            assistants=("cursor",),
            workspaces=(WorkspaceIntent("apps/api", ("symfony",)),),
        )
        text = render_project_config_yaml(config)
        self.assertIn("components: []\n", text)
        self.assertIn('path: "apps/api"', text)
        loaded = yaml.safe_load(text)
        self.assertEqual(loaded["components"], [])
        validated = validate_project_config_payload(
            loaded, self.registry, schema=self.schema
        )
        self.assertEqual(
            configuration_sha256(validated, self.registry),
            configuration_sha256(config, self.registry),
        )
        self.assertEqual(render_project_config_yaml(validated), text)

    def test_unicode_path_roundtrip(self):
        config = ProjectConfig(
            schema_version=2,
            components=("devops",),
            assistants=("cursor",),
            workspaces=(WorkspaceIntent("apps/serviço", ("symfony",)),),
        )
        text = render_project_config_yaml(config)
        loaded = yaml.safe_load(text)
        validated = validate_project_config_payload(
            loaded, self.registry, schema=self.schema
        )
        self.assertEqual(validated.workspaces[0].path, "apps/serviço")
        self.assertEqual(
            configuration_sha256(validated, self.registry),
            configuration_sha256(config, self.registry),
        )


class Schema2SemanticHashGoldenTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.registry = ComponentRegistry.load()

    def _config_a(self):
        return ProjectConfig(
            schema_version=2,
            components=(),
            assistants=("cursor",),
            workspaces=(WorkspaceIntent("apps/api", ("symfony",)),),
        )

    def _config_b(self):
        return ProjectConfig(
            schema_version=2,
            components=("devops",),
            assistants=("cursor", "claude"),
            workspaces=(
                WorkspaceIntent("apps/api", ("symfony",)),
                WorkspaceIntent("apps/web", ("frontend",)),
            ),
        )

    def _config_c(self):
        return ProjectConfig(
            schema_version=2,
            components=("devops",),
            assistants=("cursor", "copilot", "claude", "antigravity"),
            workspaces=(
                WorkspaceIntent("apps/api", ("symfony",)),
                WorkspaceIntent("apps/web", ("frontend",)),
                WorkspaceIntent("apps/mobile", ("flutter",)),
                WorkspaceIntent("packages/shared", ("typescript",)),
            ),
        )

    def test_golden_a_empty_root(self):
        config = self._config_a()
        normalized = normalize_project_config(config, self.registry)
        expected = {
            "assistants": ["cursor"],
            "components": [],
            "schema_version": 2,
            "workspaces": [{"components": ["symfony"], "path": "apps/api"}],
        }
        self.assertEqual(normalized, expected)
        self.assertEqual(configuration_sha256(config, self.registry), SCHEMA2_HASH_A)

    def test_golden_b_root_two_workspaces(self):
        config = self._config_b()
        normalized = normalize_project_config(config, self.registry)
        expected = {
            "assistants": ["claude", "cursor"],
            "components": ["devops"],
            "schema_version": 2,
            "workspaces": [
                {"components": ["symfony"], "path": "apps/api"},
                {"components": ["frontend"], "path": "apps/web"},
            ],
        }
        self.assertEqual(normalized, expected)
        self.assertEqual(configuration_sha256(config, self.registry), SCHEMA2_HASH_B)

    def test_golden_c_reference_monorepo(self):
        config = self._config_c()
        normalized = normalize_project_config(config, self.registry)
        expected = {
            "assistants": ["antigravity", "claude", "copilot", "cursor"],
            "components": ["devops"],
            "schema_version": 2,
            "workspaces": [
                {"components": ["symfony"], "path": "apps/api"},
                {"components": ["flutter"], "path": "apps/mobile"},
                {"components": ["frontend"], "path": "apps/web"},
                {"components": ["typescript"], "path": "packages/shared"},
            ],
        }
        self.assertEqual(normalized, expected)
        self.assertEqual(configuration_sha256(config, self.registry), SCHEMA2_HASH_C)

    def test_equivalence_across_ordering_and_redundancy(self):
        base = configuration_sha256(self._config_b(), self.registry)
        variants = [
            ProjectConfig(
                2,
                ("devops",),
                ("claude", "cursor"),
                (
                    WorkspaceIntent("apps/web", ("frontend",)),
                    WorkspaceIntent("apps/api", ("symfony",)),
                ),
            ),
            ProjectConfig(
                2,
                ("devops",),
                ("cursor", "claude"),
                (
                    WorkspaceIntent("apps/api", ("php", "symfony")),
                    WorkspaceIntent("apps/web", ("frontend",)),
                ),
            ),
            ProjectConfig(
                2,
                ("devops", "core"),
                ("cursor", "claude"),
                (
                    WorkspaceIntent("apps/api", ("symfony",)),
                    WorkspaceIntent("apps/web", ("frontend",)),
                ),
            ),
        ]
        for config in variants:
            with self.subTest(config=config):
                self.assertEqual(configuration_sha256(config, self.registry), base)


class Schema2ValidationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.registry = ComponentRegistry.load()
        cls.schema = _schema()

    def test_rejects_duplicate_and_overlapping_workspaces(self):
        with self.assertRaises(ProjectConfigError):
            validate_project_config_payload(
                {
                    "schema_version": 2,
                    "components": [],
                    "assistants": ["cursor"],
                    "workspaces": [
                        {"path": "apps/api", "components": ["symfony"]},
                        {"path": "apps/api", "components": ["frontend"]},
                    ],
                },
                self.registry,
                schema=self.schema,
            )
        with self.assertRaises(ProjectConfigError):
            validate_project_config_payload(
                {
                    "schema_version": 2,
                    "components": [],
                    "assistants": ["cursor"],
                    "workspaces": [
                        {"path": "apps", "components": ["devops"]},
                        {"path": "apps/api", "components": ["symfony"]},
                    ],
                },
                self.registry,
                schema=self.schema,
            )

    def test_rejects_unknown_workspace_component(self):
        with self.assertRaises(ProjectConfigError):
            validate_project_config_payload(
                {
                    "schema_version": 2,
                    "components": [],
                    "assistants": ["cursor"],
                    "workspaces": [
                        {"path": "apps/api", "components": ["no-such-component"]},
                    ],
                },
                self.registry,
                schema=self.schema,
            )


class Schema2StoreTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.registry = ComponentRegistry.load()

    def _schema2_config(self):
        return ProjectConfig(
            schema_version=2,
            components=("devops",),
            assistants=("cursor",),
            workspaces=(
                WorkspaceIntent("apps/api", ("symfony",)),
                WorkspaceIntent("apps/web", ("frontend",)),
            ),
        )

    def test_create_load_snapshot_replace_rollback(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _mkdir(root, "apps/api")
            _mkdir(root, "apps/web")
            store = ProjectConfigStore(root, registry=self.registry)

            schema1 = ProjectConfig(1, ("core",), ("cursor",))
            created = store.create(schema1)
            self.assertEqual(created.schema_version, 1)
            snap = store.load_file_snapshot()
            self.assertIsNotNone(snap)
            self.assertEqual(
                snap.configuration_sha256,
                configuration_sha256(schema1, self.registry),
            )

            schema2 = self._schema2_config()
            handle = store.replace(
                schema2, expected_content_sha256=snap.content_sha256
            )
            self.assertEqual(handle.config.schema_version, 2)
            self.assertEqual(
                handle.new_configuration_sha256,
                configuration_sha256(schema2, self.registry),
            )
            loaded = store.load()
            self.assertEqual(loaded.schema_version, 2)
            self.assertEqual(len(loaded.workspaces), 2)

            store.rollback_replace(
                expected_current_content_sha256=handle.new_content_sha256,
                old_bytes=handle.old_bytes,
            )
            restored = store.load_file_snapshot()
            self.assertEqual(restored.raw_bytes, handle.old_bytes)
            self.assertEqual(restored.config.schema_version, 1)
            self.assertEqual(restored.raw_bytes, snap.raw_bytes)

    def test_create_schema2_requires_existing_directories(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            store = ProjectConfigStore(root, registry=self.registry)
            with self.assertRaises(ProjectConfigError):
                store.create(self._schema2_config())

    def test_schema2_to_schema1_replace(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _mkdir(root, "apps/api")
            _mkdir(root, "apps/web")
            store = ProjectConfigStore(root, registry=self.registry)
            store.create(self._schema2_config())
            snap = store.load_file_snapshot()
            schema1 = ProjectConfig(1, ("symfony",), ("cursor",))
            handle = store.replace(
                schema1, expected_content_sha256=snap.content_sha256
            )
            self.assertEqual(handle.config.schema_version, 1)
            self.assertNotIn(
                "workspaces",
                render_project_config_yaml(handle.config),
            )
            # physical fingerprint distinct from semantic
            self.assertNotEqual(
                handle.new_content_sha256,
                handle.new_configuration_sha256,
            )
            self.assertEqual(
                handle.new_content_sha256,
                project_config_content_sha256(handle.new_bytes),
            )


if __name__ == "__main__":
    unittest.main()
