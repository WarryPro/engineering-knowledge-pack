"""AssemblyService tests."""

import unittest
from pathlib import Path

from ekp.assembly import AssemblyRequest, AssemblyService
from ekp.paths import get_ekp_root


class AssemblyServiceTests(unittest.TestCase):
    def setUp(self):
        self.service = AssemblyService()
        self.resource_root = get_ekp_root()

    def test_cursor_core_custom_output_root(self):
        import tempfile

        with tempfile.TemporaryDirectory(prefix="ekp-test-") as tmp:
            tmp_path = Path(tmp)
            workspace = tmp_path / "workspace"
            output = tmp_path / "output"

            result = self.service.assemble(
                AssemblyRequest(
                    profile="cursor-core",
                    verify=True,
                    clean=True,
                    resource_root=self.resource_root,
                    workspace_dir=workspace,
                    output_root=output,
                )
            )

            cursor_dir = result.bundle_path / "cursor"
            mdc_files = list(cursor_dir.glob("*.mdc"))
            self.assertEqual(result.profile, "cursor-core")
            self.assertEqual(result.rules_count, 65)
            self.assertEqual(len(mdc_files), 65)
            self.assertIn("cursor", result.adapters)
            self.assertTrue(str(result.bundle_path).startswith(str(output)))
            self.assertFalse(str(result.bundle_path).startswith(str(self.resource_root / "dist")))

    def test_cursor_core_does_not_write_repo_dist(self):
        import tempfile

        default_bundle = self.resource_root / "dist" / "cursor-core" / "cursor"
        existed_before = default_bundle.is_dir()

        with tempfile.TemporaryDirectory(prefix="ekp-test-") as tmp:
            tmp_path = Path(tmp)
            result = self.service.assemble(
                AssemblyRequest(
                    profile="cursor-core",
                    verify=True,
                    resource_root=self.resource_root,
                    workspace_dir=tmp_path / "workspace",
                    output_root=tmp_path / "output",
                )
            )
            self.assertEqual(len(list((result.bundle_path / "cursor").glob("*.mdc"))), 65)

        self.assertEqual(default_bundle.is_dir(), existed_before)

    def test_cursor_flutter_custom_output(self):
        import tempfile

        with tempfile.TemporaryDirectory(prefix="ekp-test-") as tmp:
            tmp_path = Path(tmp)
            result = self.service.assemble(
                AssemblyRequest(
                    profile="cursor-flutter",
                    verify=True,
                    resource_root=self.resource_root,
                    workspace_dir=tmp_path / "workspace",
                    output_root=tmp_path / "output",
                )
            )
            mdc_files = list((result.bundle_path / "cursor").glob("*.mdc"))
            self.assertEqual(result.rules_count, 75)
            self.assertEqual(len(mdc_files), 75)
