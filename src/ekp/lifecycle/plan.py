"""Lifecycle plan model for uninstall and update."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import List, Optional

from ekp.install.manifest import InstallManifest


class LifecycleOpKind(str, Enum):
    CREATE = "create"
    WRITE = "write"
    DELETE = "delete"
    NOOP = "noop"


@dataclass
class LifecycleFileOperation:
    """Single planned lifecycle file action.

    ``adapter`` is required and must reflect actual ownership (no silent Cursor default).
    """

    relative_path: str
    kind: LifecycleOpKind
    adapter: str
    previous_sha256: Optional[str] = None
    expected_sha256: Optional[str] = None
    source_path: Optional[Path] = None


@dataclass
class LifecyclePlan:
    """Complete preflight lifecycle plan.

    ``adapters`` is the canonical multi-assistant representation (lexical when built).
    ``adapter`` is a compatibility property for single-adapter plans only.
    """

    project_root: Path
    profile: str
    old_version: str
    new_version: Optional[str]
    adapters: List[str]
    mode: str
    operations: List[LifecycleFileOperation] = field(default_factory=list)
    conflicts: List[str] = field(default_factory=list)
    directories_to_remove: List[str] = field(default_factory=list)
    directories_to_create: List[str] = field(default_factory=list)
    # SHA-256 of the exact manifest bytes parsed into this plan's ownership data.
    manifest_sha256: Optional[str] = None
    commit_manifest: bool = True
    new_manifest: Optional[InstallManifest] = None
    bundle_path: Optional[Path] = None
    dry_run: bool = False
    # Composition update: revalidate project.yaml semantic hash before/at commit.
    expected_configuration_sha256: Optional[str] = None

    @property
    def adapter(self) -> str:
        """Compatibility: sole adapter for single-assistant plans."""
        if len(self.adapters) != 1:
            raise AttributeError(
                "LifecyclePlan.adapter is only defined for single-adapter plans; "
                "use .adapters"
            )
        return self.adapters[0]

    @property
    def has_conflicts(self) -> bool:
        return bool(self.conflicts)

    @property
    def delete_count(self) -> int:
        return sum(1 for op in self.operations if op.kind == LifecycleOpKind.DELETE)

    @property
    def create_count(self) -> int:
        return sum(1 for op in self.operations if op.kind == LifecycleOpKind.CREATE)

    @property
    def write_count(self) -> int:
        return sum(1 for op in self.operations if op.kind == LifecycleOpKind.WRITE)

    @property
    def noop_count(self) -> int:
        return sum(1 for op in self.operations if op.kind == LifecycleOpKind.NOOP)

    @property
    def conflict_count(self) -> int:
        return len(self.conflicts)

    @property
    def missing_count(self) -> int:
        return self.noop_count
