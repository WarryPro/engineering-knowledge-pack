"""DeployRegistry unit tests."""

from __future__ import annotations

import unittest
from pathlib import Path
from typing import List

from ekp.install.deploy.base import Deployer
from ekp.install.deploy.cursor import CursorDeployer
from ekp.install.deploy.models import DesiredManagedFile
from ekp.install.deploy.registry import DeployRegistry, build_default_deploy_registry


class _SyntheticDeployer(Deployer):
    def __init__(self, assistant_id: str = "assistant-x") -> None:
        self._assistant_id = assistant_id

    @property
    def assistant_id(self) -> str:
        return self._assistant_id

    def collect_desired_files(self, bundle_path: Path) -> List[DesiredManagedFile]:
        return []


class DeployRegistryTests(unittest.TestCase):
    def test_register_and_get_cursor(self):
        registry = DeployRegistry()
        deployer = CursorDeployer()
        registry.register(deployer)
        self.assertIs(registry.get("cursor"), deployer)
        self.assertTrue(registry.is_supported("cursor"))

    def test_default_registry_cursor_only(self):
        registry = build_default_deploy_registry()
        self.assertEqual(registry.supported_assistants(), ("cursor",))
        self.assertIsInstance(registry.get("cursor"), CursorDeployer)
        self.assertFalse(registry.is_supported("copilot"))
        self.assertFalse(registry.is_supported("claude"))
        self.assertFalse(registry.is_supported("antigravity"))

    def test_unknown_assistant_fails(self):
        registry = build_default_deploy_registry()
        with self.assertRaises(KeyError):
            registry.get("copilot")

    def test_duplicate_registration_fails(self):
        registry = DeployRegistry()
        registry.register(CursorDeployer())
        with self.assertRaises(ValueError):
            registry.register(CursorDeployer())

    def test_supported_assistants_deterministic(self):
        registry = DeployRegistry()
        registry.register(_SyntheticDeployer("zulu"))
        registry.register(_SyntheticDeployer("alpha"))
        registry.register(CursorDeployer())
        self.assertEqual(registry.supported_assistants(), ("alpha", "cursor", "zulu"))


if __name__ == "__main__":
    unittest.main()
