"""DeployRegistry — authoritative managed Consumer assistant capability."""

from __future__ import annotations

from typing import Dict, Tuple

from ekp.install.deploy.antigravity import AntigravityDeployer
from ekp.install.deploy.base import Deployer
from ekp.install.deploy.claude import ClaudeDeployer
from ekp.install.deploy.copilot import CopilotDeployer
from ekp.install.deploy.cursor import CursorDeployer


class DeployRegistry:
    """Registry of concrete Consumer deployers (not generation adapters)."""

    def __init__(self) -> None:
        self._deployers: Dict[str, Deployer] = {}

    def register(self, deployer: Deployer) -> None:
        assistant_id = deployer.assistant_id
        if not assistant_id:
            raise ValueError("Deployer assistant_id must be non-empty")
        if assistant_id in self._deployers:
            raise ValueError(
                "Deployer already registered for assistant: {}".format(assistant_id)
            )
        self._deployers[assistant_id] = deployer

    def get(self, assistant_id: str) -> Deployer:
        try:
            return self._deployers[assistant_id]
        except KeyError as exc:
            raise KeyError(
                "No Consumer deployer registered for assistant: {}".format(assistant_id)
            ) from exc

    def is_supported(self, assistant_id: str) -> bool:
        return assistant_id in self._deployers

    def supported_assistants(self) -> Tuple[str, ...]:
        return tuple(sorted(self._deployers.keys()))


def build_default_deploy_registry() -> DeployRegistry:
    """Production registry: all four managed Consumer deployers."""
    registry = DeployRegistry()
    registry.register(CursorDeployer())
    registry.register(CopilotDeployer())
    registry.register(ClaudeDeployer())
    registry.register(AntigravityDeployer())
    return registry
