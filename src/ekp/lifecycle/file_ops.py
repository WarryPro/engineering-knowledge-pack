"""Shared lifecycle file-operation classification (update + configure)."""

from __future__ import annotations

from pathlib import Path
from typing import List, Optional, Set

from ekp.install.cursor_deploy import CURSOR_ADAPTER
from ekp.install.paths import check_symlink_boundary, resolve_under_root
from ekp.lifecycle.plan import LifecycleFileOperation, LifecycleOpKind


def noop_operation(
    relative: str, old_sha: Optional[str], adapter: str
) -> LifecycleFileOperation:
    return LifecycleFileOperation(
        relative_path=relative,
        kind=LifecycleOpKind.NOOP,
        adapter=adapter,
        previous_sha256=old_sha,
    )


def classify_lifecycle_operation(
    *,
    relative: str,
    adapter: str,
    old_sha: Optional[str],
    new_sha: Optional[str],
    source_path: Optional[Path],
    disk_exists: bool,
    disk_sha: Optional[str],
) -> Optional[LifecycleFileOperation]:
    """Classify one path as CREATE/WRITE/DELETE/NOOP, or None for conflict."""
    if old_sha is not None and new_sha is not None:
        if old_sha == new_sha:
            if not disk_exists:
                return LifecycleFileOperation(
                    relative_path=relative,
                    kind=LifecycleOpKind.CREATE,
                    adapter=adapter,
                    previous_sha256=None,
                    expected_sha256=new_sha,
                    source_path=source_path,
                )
            if disk_sha == old_sha:
                return noop_operation(relative, old_sha, adapter)
            return None

        if not disk_exists:
            return LifecycleFileOperation(
                relative_path=relative,
                kind=LifecycleOpKind.CREATE,
                adapter=adapter,
                previous_sha256=None,
                expected_sha256=new_sha,
                source_path=source_path,
            )
        if disk_sha == old_sha:
            return LifecycleFileOperation(
                relative_path=relative,
                kind=LifecycleOpKind.WRITE,
                adapter=adapter,
                previous_sha256=old_sha,
                expected_sha256=new_sha,
                source_path=source_path,
            )
        return None

    if old_sha is None and new_sha is not None:
        if not disk_exists:
            return LifecycleFileOperation(
                relative_path=relative,
                kind=LifecycleOpKind.CREATE,
                adapter=adapter,
                previous_sha256=None,
                expected_sha256=new_sha,
                source_path=source_path,
            )
        return None

    if old_sha is not None and new_sha is None:
        if not disk_exists:
            return noop_operation(relative, old_sha, adapter)
        if disk_sha == old_sha:
            return LifecycleFileOperation(
                relative_path=relative,
                kind=LifecycleOpKind.DELETE,
                adapter=adapter,
                previous_sha256=old_sha,
                expected_sha256=None,
                source_path=None,
            )
        return None

    return noop_operation(relative, old_sha, adapter)


def directories_to_create_for_operations(
    project_root: Path, operations: List[LifecycleFileOperation]
) -> List[str]:
    needed: Set[str] = set()
    for operation in operations:
        if operation.kind != LifecycleOpKind.CREATE:
            continue
        parent = Path(operation.relative_path).parent
        current = parent
        while current.as_posix() not in (".", ""):
            needed.add(current.as_posix())
            current = current.parent

    created: List[str] = []
    for relative in sorted(needed, key=lambda path: path.count("/")):
        boundary = check_symlink_boundary(project_root, relative)
        if boundary:
            continue
        try:
            target = resolve_under_root(project_root, relative)
        except ValueError:
            continue
        if not target.exists():
            created.append(relative)
    return created


def fallback_adapter(old_item, new_item) -> str:
    if new_item is not None:
        return new_item.adapter
    if old_item is not None:
        return old_item.adapter
    return CURSOR_ADAPTER
