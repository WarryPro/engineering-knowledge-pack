"""Ownership manifest model and persistence."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from ekp.install.errors import InstallConflictError
from ekp.install.paths import check_symlink_boundary, relative_posix_path, resolve_under_root

MANIFEST_RELATIVE = ".ekp/install.json"
SUPPORTED_SCHEMA_VERSION = 1
REQUIRED_FIELDS = (
    "schema_version",
    "ekp_version",
    "profile",
    "adapters",
    "installed_at",
    "install_root",
    "managed_files",
)


@dataclass
class ManagedFile:
    """Single EKP-owned consumer file."""

    relative_path: str
    adapter: str
    sha256: str

    def to_dict(self) -> Dict[str, str]:
        return {
            "relative_path": self.relative_path,
            "adapter": self.adapter,
            "sha256": self.sha256,
        }

    @classmethod
    def from_dict(cls, payload: Dict[str, Any]) -> "ManagedFile":
        return cls(
            relative_path=relative_posix_path(str(payload["relative_path"])),
            adapter=str(payload["adapter"]),
            sha256=str(payload["sha256"]),
        )


@dataclass
class InstallManifest:
    """Authoritative EKP ownership record for a consumer project."""

    schema_version: int
    ekp_version: str
    profile: str
    adapters: List[str]
    installed_at: str
    install_root: str
    managed_files: List[ManagedFile] = field(default_factory=list)
    created_directories: List[str] = field(default_factory=list)

    def managed_by_path(self) -> Dict[str, ManagedFile]:
        return {item.relative_path: item for item in self.managed_files}

    def to_dict(self) -> Dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "ekp_version": self.ekp_version,
            "profile": self.profile,
            "adapters": list(self.adapters),
            "installed_at": self.installed_at,
            "install_root": self.install_root,
            "managed_files": [item.to_dict() for item in self.managed_files],
            "created_directories": list(self.created_directories),
        }

    @classmethod
    def from_dict(cls, payload: Dict[str, Any]) -> "InstallManifest":
        schema_version = payload.get("schema_version")
        if schema_version != SUPPORTED_SCHEMA_VERSION:
            raise InstallConflictError(
                "Unsupported EKP install manifest schema version: {}".format(schema_version)
            )

        for key in REQUIRED_FIELDS:
            if key not in payload:
                raise InstallConflictError(
                    "Existing install manifest is missing required field: {}".format(key)
                )

        managed_files = [
            ManagedFile.from_dict(item) for item in payload.get("managed_files", [])
        ]
        return cls(
            schema_version=int(schema_version),
            ekp_version=str(payload["ekp_version"]),
            profile=str(payload["profile"]),
            adapters=[str(item) for item in payload["adapters"]],
            installed_at=str(payload["installed_at"]),
            install_root=str(payload["install_root"]),
            managed_files=managed_files,
            created_directories=[
                relative_posix_path(str(item))
                for item in payload.get("created_directories", [])
            ],
        )


class ManifestStore:
    """Load and atomically persist install manifests."""

    def __init__(self, project_root: Path):
        self.project_root = project_root.resolve()
        self.manifest_path = resolve_under_root(self.project_root, MANIFEST_RELATIVE)

    def exists(self) -> bool:
        return self.manifest_path.is_file()

    def load(self) -> Optional[InstallManifest]:
        if not self.exists():
            return None

        if self.manifest_path.is_symlink():
            raise InstallConflictError(
                "Refusing to use symlinked ownership manifest: {}".format(MANIFEST_RELATIVE)
            )

        try:
            payload = json.loads(self.manifest_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise InstallConflictError(
                "Existing install manifest is not valid JSON: {}".format(MANIFEST_RELATIVE)
            ) from exc

        if not isinstance(payload, dict):
            raise InstallConflictError(
                "Existing install manifest is not a valid EKP ownership record."
            )

        try:
            return InstallManifest.from_dict(payload)
        except InstallConflictError:
            raise
        except (TypeError, ValueError, KeyError) as exc:
            raise InstallConflictError(
                "Existing install manifest is not a valid EKP ownership record."
            ) from exc

    def save(self, manifest: InstallManifest) -> None:
        boundary = check_symlink_boundary(self.project_root, MANIFEST_RELATIVE)
        if boundary:
            raise InstallConflictError(boundary)

        manifest_dir = self.manifest_path.parent
        manifest_dir.mkdir(parents=True, exist_ok=True)

        temp_path = self.manifest_path.with_suffix(".json.tmp")
        payload = json.dumps(manifest.to_dict(), indent=2, sort_keys=True) + "\n"
        try:
            with temp_path.open("w", encoding="utf-8") as handle:
                handle.write(payload)
                handle.flush()
                try:
                    os.fsync(handle.fileno())
                except OSError:
                    pass
            os.replace(str(temp_path), str(self.manifest_path))
        finally:
            if temp_path.exists():
                temp_path.unlink(missing_ok=True)

    def delete(self) -> None:
        """Remove the ownership manifest after managed files are deleted."""
        if self.manifest_path.is_symlink():
            raise InstallConflictError(
                "Refusing to remove symlinked ownership manifest: {}".format(MANIFEST_RELATIVE)
            )
        if not self.manifest_path.exists():
            return
        self.manifest_path.unlink()


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
