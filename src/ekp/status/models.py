"""Status result models."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional


class StatusState(str, Enum):
    """Overall EKP installation state for a consumer project."""

    NOT_INSTALLED = "not_installed"
    HEALTHY = "healthy"
    MODIFIED = "modified"
    INCOMPLETE = "incomplete"
    VERSION_MISMATCH = "version_mismatch"
    CONFIGURATION_DRIFT = "configuration_drift"
    INVALID = "invalid"


@dataclass
class ManagedFileStatus:
    """Per-file integrity relative to the ownership manifest."""

    relative_path: str
    expected_sha256: str
    actual_sha256: Optional[str] = None
    missing: bool = False
    modified: bool = False
    unsafe: bool = False


@dataclass
class StatusResult:
    """Complete read-only status inspection result."""

    project_root: str
    installed: bool
    state: StatusState
    running_version: str
    schema_version: Optional[int] = None
    installed_version: Optional[str] = None
    profile: Optional[str] = None
    adapters: List[str] = field(default_factory=list)
    install_root: Optional[str] = None
    installed_at: Optional[str] = None
    managed_total: int = 0
    intact_count: int = 0
    modified_paths: List[str] = field(default_factory=list)
    missing_paths: List[str] = field(default_factory=list)
    unsafe_paths: List[str] = field(default_factory=list)
    error_message: Optional[str] = None
    # Composition-aware optional fields (absent / unused for legacy installs).
    mode: Optional[str] = None
    configuration_sha256: Optional[str] = None
    current_configuration_sha256: Optional[str] = None
    requested_components: List[str] = field(default_factory=list)
    resolved_components: List[str] = field(default_factory=list)
    assistants: List[str] = field(default_factory=list)
    configuration_drift: Optional[bool] = None

    @property
    def exit_code(self) -> int:
        if self.state == StatusState.INVALID:
            return 3
        return 0
