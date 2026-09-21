"""CLI discoverability tests (BA-C)."""

from __future__ import annotations

import io
import os
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest import mock

from ekp.cli import main
from ekp.composition import ComponentRegistry
from ekp.discovery import (
    format_discovery_table,
    list_selectable_components,
    list_supported_assistants,
)
from ekp.install.deploy.registry import build_default_deploy_registry
from ekp.install.errors import EXIT_SELECTION, EXIT_SUCCESS
from ekp.install.intent import build_composition_intent, validate_composition_assistants
from ekp.install.errors import InstallSelectionError
from ekp.version import get_version


class VersionFlagTests(unittest.TestCase):
    def test_version_flag_prints_package_version_only(self):
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            with self.assertRaises(SystemExit) as ctx:
                main(["--version"])
        self.assertEqual(ctx.exception.code, 0)
        output = buffer.getvalue().strip()
        self.assertEqual(output, get_version())
        self.assertNotIn("resource_root", output)

    def test_version_subcommand_still_prints_resource_root(self):
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            code = main(["version"])
        self.assertEqual(code, 0)
        output = buffer.getvalue()
        self.assertIn(get_version(), output)
        self.assertIn("resource_root:", output)


class ListDiscoveryTests(unittest.TestCase):
    def test_list_components_matches_selectable_registry(self):
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            code = main(["list", "components"])
        self.assertEqual(code, EXIT_SUCCESS)
        output = buffer.getvalue()
        expected_ids = [
            c.id
            for c in ComponentRegistry.load().list_components()
            if c.selectable
        ]
        self.assertEqual(expected_ids, sorted(expected_ids))
        for component_id in expected_ids:
            self.assertIn(component_id, output)
        # Dependency-only components must not appear if any exist.
        for component in ComponentRegistry.load().list_components():
            if not component.selectable:
                self.assertNotIn(component.id + " ", output)
                self.assertFalse(output.strip().endswith(component.id))

    def test_list_assistants_matches_deploy_registry(self):
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            code = main(["list", "assistants"])
        self.assertEqual(code, EXIT_SUCCESS)
        output = buffer.getvalue()
        supported = list(build_default_deploy_registry().supported_assistants())
        self.assertEqual(supported, sorted(supported))
        for assistant_id in supported:
            self.assertIn(assistant_id, output)
        self.assertIn("cursor", output)
        self.assertIn("default", output.lower())

    def test_list_output_is_deterministic(self):
        first = format_discovery_table(list_selectable_components())
        second = format_discovery_table(list_selectable_components())
        self.assertEqual(first, second)
        self.assertEqual(
            format_discovery_table(list_supported_assistants()),
            format_discovery_table(list_supported_assistants()),
        )

    def test_bare_list_prints_help(self):
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            code = main(["list"])
        self.assertEqual(code, EXIT_SUCCESS)
        output = buffer.getvalue()
        self.assertIn("components", output)
        self.assertIn("assistants", output)

    def test_list_from_empty_directory_does_not_mutate_project(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            before = sorted(p.name for p in root.iterdir())
            cwd = os.getcwd()
            try:
                os.chdir(root)
                buffer = io.StringIO()
                with redirect_stdout(buffer):
                    code_components = main(["list", "components"])
                    code_assistants = main(["list", "assistants"])
            finally:
                os.chdir(cwd)
            self.assertEqual(code_components, EXIT_SUCCESS)
            self.assertEqual(code_assistants, EXIT_SUCCESS)
            after = sorted(p.name for p in root.iterdir())
            self.assertEqual(before, after)
            self.assertFalse((root / ".ekp").exists())


class RemediationMessageTests(unittest.TestCase):
    def test_unknown_component_points_to_list_components(self):
        registry = ComponentRegistry.load()
        with self.assertRaises(InstallSelectionError) as ctx:
            build_composition_intent(["not-a-real-component"], registry)
        self.assertEqual(ctx.exception.exit_code, EXIT_SELECTION)
        self.assertIn("ekp list components", str(ctx.exception))

    def test_unsupported_assistant_points_to_list_assistants(self):
        with self.assertRaises(InstallSelectionError) as ctx:
            validate_composition_assistants(["not-a-real-assistant"])
        self.assertEqual(ctx.exception.exit_code, EXIT_SELECTION)
        self.assertIn("ekp list assistants", str(ctx.exception))

    def test_empty_project_yes_mentions_list_components(self):
        stderr = io.StringIO()
        with tempfile.TemporaryDirectory() as tmp:
            with redirect_stderr(stderr):
                code = main(["install", "--path", tmp, "--yes"])
        self.assertEqual(code, EXIT_SELECTION)
        self.assertIn("ekp list components", stderr.getvalue())

    def test_top_level_help_includes_examples(self):
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            with self.assertRaises(SystemExit) as ctx:
                main(["--help"])
        self.assertEqual(ctx.exception.code, 0)
        help_text = buffer.getvalue()
        self.assertIn("list components", help_text)
        self.assertIn("ekp update", help_text)
        self.assertIn("ekp configure", help_text)

    def test_configure_refuses_not_installed_with_recovery(self):
        with tempfile.TemporaryDirectory() as tmp:
            stderr = io.StringIO()
            with redirect_stderr(stderr):
                code = main(
                    [
                        "configure",
                        "--path",
                        tmp,
                        "--component",
                        "typescript",
                        "--assistant",
                        "cursor",
                        "--yes",
                    ]
                )
            self.assertEqual(code, EXIT_SELECTION)
            message = stderr.getvalue()
            self.assertIn("not installed", message.lower())
            self.assertIn("ekp install", message)


if __name__ == "__main__":
    unittest.main()
