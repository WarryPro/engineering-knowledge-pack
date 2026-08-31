"""Install plan model."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import List, Optional


class FileOpKind(str, Enum):
    CREATE = "create"
    WRITE = "write"
    RESTORE = "restore"
    NOOP = "noop"


@dataclass
class FileOperation:
    """Single planned consumer file action."""

    relative_path: str
    kind: FileOpKind
    source_path: Optional[Path]
    expected_sha256: str
    adapter: str = "cursor"


@dataclass
class InstallPlan:
    """Complete preflight installation plan."""

    project_root: Path
    profile: str
    ekp_version: str
    adapter: str
    bundle_path: Path
    rules_count: int
    operations: List[FileOperation] = field(default_factory=list)
    conflicts: List[str] = field(default_factory=list)
    directories_to_create: List[str] = field(default_factory=list)
    additional_concerns: List[str] = field(default_factory=list)
    dry_run: bool = False

    @property
    def has_conflicts(self) -> bool:
        return bool(self.conflicts)

    @property
    def is_noop(self) -> bool:
        return not self.has_conflicts and all(
            op.kind == FileOpKind.NOOP for op in self.operations
        )

    @property
    def files_to_write(self) -> List[FileOperation]:
        return [
            op
            for op in self.operations
            if op.kind in (FileOpKind.CREATE, FileOpKind.WRITE, FileOpKind.RESTORE)
        ]

    @property
    def would_create_directories(self) -> List[str]:
        return list(self.directories_to_create)
