"""Consumer managed-file deployment (Deployer / DeployRegistry / shared engine)."""

from ekp.install.deploy.antigravity import ANTIGRAVITY_ADAPTER, AntigravityDeployer
from ekp.install.deploy.base import Deployer
from ekp.install.deploy.claude import CLAUDE_ADAPTER, ClaudeDeployer
from ekp.install.deploy.copilot import COPILOT_ADAPTER, CopilotDeployer
from ekp.install.deploy.cursor import CURSOR_ADAPTER, CURSOR_RULES_DIR, CursorDeployer
from ekp.install.deploy.engine import AppliedManagedFiles, SharedDeploymentEngine
from ekp.install.deploy.hashing import sha256_file, sha256_text
from ekp.install.deploy.models import DesiredManagedFile
from ekp.install.deploy.registry import DeployRegistry, build_default_deploy_registry

__all__ = [
    "ANTIGRAVITY_ADAPTER",
    "CLAUDE_ADAPTER",
    "COPILOT_ADAPTER",
    "CURSOR_ADAPTER",
    "CURSOR_RULES_DIR",
    "AntigravityDeployer",
    "AppliedManagedFiles",
    "ClaudeDeployer",
    "CopilotDeployer",
    "CursorDeployer",
    "DeployRegistry",
    "Deployer",
    "DesiredManagedFile",
    "SharedDeploymentEngine",
    "build_default_deploy_registry",
    "sha256_file",
    "sha256_text",
]
