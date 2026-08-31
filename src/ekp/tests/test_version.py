"""Version metadata tests."""

import unittest

from ekp.version import get_version


class VersionTests(unittest.TestCase):
    def test_version_is_non_empty(self):
        version = get_version()
        self.assertTrue(version)
        self.assertIn("0.15.0", version)
