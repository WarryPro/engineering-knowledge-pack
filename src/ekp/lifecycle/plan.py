"""Lifecycle plan model for uninstall and future update."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import List, Optional


class LifecycleOpKind(str, Enum):
    CREATE = "create"
    WRITE = "write"
    DELETE = "delete"
    NOOP = "noop"


@dataclass
class LifecycleFileOperation:
    """Single planned lifecycle file action."""

    relative_path: str
    kind: LifecycleOpKind
    previous_sha256: Optional[str] = None
    expected_sha256: Optional[str] = None
    source_path: Optional[Path] = None
    adapter: str = "cursor"


@dataclass
class LifecyclePlan:
    """Complete preflight lifecycle plan."""

    project_root: Path
    profile: str
    old_version: str
    new_version: Optional[str]
    adapter: str
    mode: str
    operations: List[LifecycleFileOperation] = field(default_factory=list)
    conflicts: List[str] = field(default_factory=list)
    directories_to_remove: List[str] = field(default_factory=list)
    manifest_sha256: Optional[str] = None
    dry_run: bool = False

    @property
    def has_conflicts(self) -> bool:
        return bool(self.conflicts)

    @property
    def delete_count(self) -> int:
        return sum(1 for op in self.operations if op.kind == LifecycleOpKind.DELETE)

    @property
    def noop_count(self) -> int:
        return sum(1 for op in self.operations if op.kind == LifecycleOpKind.NOOP)

    @property
    def conflict_count(self) -> int:
        return len(self.conflicts)

    @property
    def missing_count(self) -> int:
        return self.noop_count
