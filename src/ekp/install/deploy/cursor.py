"""Cursor Consumer deployer (bundle → DesiredManagedFile)."""

from __future__ import annotations

from pathlib import Path
from typing import List

from ekp.install.deploy.base import Deployer
from ekp.install.deploy.hashing import sha256_file
from ekp.install.deploy.models import DesiredManagedFile
from ekp.install.errors import InstallAssemblyError
from ekp.install.paths import relative_posix_path

CURSOR_ADAPTER = "cursor"
CURSOR_RULES_DIR = ".cursor/rules"


class CursorDeployer(Deployer):
    """Map ``<bundle>/cursor/*.mdc`` → ``.cursor/rules/*.mdc``."""

    @property
    def assistant_id(self) -> str:
        return CURSOR_ADAPTER

    def collect_desired_files(self, bundle_path: Path) -> List[DesiredManagedFile]:
        cursor_dir = bundle_path / "cursor"
        if not cursor_dir.is_dir():
            raise InstallAssemblyError(
                "Assembled bundle is missing cursor output: {}".format(cursor_dir)
            )

        items: List[DesiredManagedFile] = []
        for source in sorted(cursor_dir.glob("*.mdc")):
            name = source.name
            if ".." in name or "/" in name or "\\" in name:
                raise InstallAssemblyError("Unsafe generated filename: {}".format(name))
            resolved = source.resolve()
            try:
                resolved.relative_to(cursor_dir.resolve())
            except ValueError as exc:
                raise InstallAssemblyError(
                    "Generated file escapes bundle cursor directory: {}".format(name)
                ) from exc
            relative_target = relative_posix_path("{}/{}".format(CURSOR_RULES_DIR, name))
            items.append(
                DesiredManagedFile(
                    relative_path=relative_target,
                    adapter=CURSOR_ADAPTER,
                    source_path=source,
                    sha256=sha256_file(source),
                )
            )
        return items
