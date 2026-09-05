"""Shared bundle source safety helpers for identity-mapping deployers."""

from __future__ import annotations

from pathlib import Path
from typing import Iterable, List

from ekp.install.deploy.hashing import sha256_file
from ekp.install.deploy.models import DesiredManagedFile
from ekp.install.errors import InstallAssemblyError
from ekp.install.paths import relative_posix_path

ADAPTER_MANIFEST_NAME = "adapter-manifest.json"


def require_assistant_dir(bundle_path: Path, assistant_id: str) -> Path:
    adapter_dir = bundle_path / assistant_id
    if not adapter_dir.is_dir():
        raise InstallAssemblyError(
            "Assembled bundle is missing {} output: {}".format(assistant_id, adapter_dir)
        )
    return adapter_dir


def list_assistant_files(adapter_dir: Path) -> List[Path]:
    """Return sorted regular files under ``adapter_dir`` (rejects symlinks)."""
    files: List[Path] = []
    for path in sorted(adapter_dir.rglob("*")):
        if path.is_symlink():
            raise InstallAssemblyError(
                "Generated bundle contains symlink (refused): {}".format(
                    path.relative_to(adapter_dir).as_posix()
                )
            )
        if path.is_file():
            files.append(path)
    return files


def assert_source_contained(adapter_dir: Path, source: Path, rel: str) -> None:
    """Ensure ``source`` is a non-symlink file contained under ``adapter_dir``."""
    if source.is_symlink():
        raise InstallAssemblyError(
            "Generated file is a symlink (refused): {}".format(rel)
        )
    if not source.is_file():
        raise InstallAssemblyError(
            "Generated path is not a regular file: {}".format(rel)
        )
    try:
        source.resolve().relative_to(adapter_dir.resolve())
    except ValueError as exc:
        raise InstallAssemblyError(
            "Generated file escapes bundle {} directory: {}".format(
                adapter_dir.name, rel
            )
        ) from exc


def safe_path_component(name: str) -> bool:
    if not name or name in (".", ".."):
        return False
    if "/" in name or "\\" in name or ".." in name:
        return False
    return True


def validate_relative_target(rel: str) -> str:
    try:
        return relative_posix_path(rel)
    except ValueError as exc:
        raise InstallAssemblyError("Unsafe generated path: {}".format(rel)) from exc


def desired_file(
    *,
    relative_path: str,
    adapter: str,
    source_path: Path,
) -> DesiredManagedFile:
    normalized = validate_relative_target(relative_path)
    return DesiredManagedFile(
        relative_path=normalized,
        adapter=adapter,
        source_path=source_path,
        sha256=sha256_file(source_path),
    )


def skip_adapter_manifest(rel: str) -> bool:
    return rel == ADAPTER_MANIFEST_NAME


def require_non_empty(
    items: Iterable[DesiredManagedFile], assistant_id: str, adapter_dir: Path
) -> List[DesiredManagedFile]:
    collected = list(items)
    if not collected:
        raise InstallAssemblyError(
            "Assembled {} output has no deployable managed files: {}".format(
                assistant_id, adapter_dir
            )
        )
    return collected
