"""Resource root resolution tests."""

import unittest
from pathlib import Path

from ekp.paths import get_ekp_root


class EkpRootTests(unittest.TestCase):
    def test_development_checkout_root(self):
        root = get_ekp_root()
        self.assertTrue((root / "knowledge").is_dir())
        self.assertTrue((root / "profiles").is_dir())
        self.assertTrue((root / "schema").is_dir())
        self.assertTrue((root / "scripts" / "assemble").is_dir())

    def test_root_is_canonical_not_package_dir(self):
        root = get_ekp_root()
        self.assertTrue((root / "pyproject.toml").is_file() or (root / "knowledge").is_dir())
        self.assertNotEqual(root.name, "ekp")
