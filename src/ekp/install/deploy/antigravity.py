"""Antigravity Consumer deployer (bundle → DesiredManagedFile)."""

from __future__ import annotations

from pathlib import Path
from typing import List

from ekp.install.deploy._source import (
    assert_source_contained,
    desired_file,
    list_assistant_files,
    require_assistant_dir,
    require_non_empty,
    safe_path_component,
    skip_adapter_manifest,
)
from ekp.install.deploy.base import Deployer
from ekp.install.deploy.models import DesiredManagedFile
from ekp.install.errors import InstallAssemblyError

ANTIGRAVITY_ADAPTER = "antigravity"
ANTIGRAVITY_RULES_DIR = ".agents/rules"


class AntigravityDeployer(Deployer):
    """Map ``<bundle>/antigravity/.agents/rules/*.md`` → project ``.agents/rules/*.md``."""

    @property
    def assistant_id(self) -> str:
        return ANTIGRAVITY_ADAPTER

    def collect_desired_files(self, bundle_path: Path) -> List[DesiredManagedFile]:
        adapter_dir = require_assistant_dir(bundle_path, ANTIGRAVITY_ADAPTER)
        items: List[DesiredManagedFile] = []
        unexpected: List[str] = []

        for source in list_assistant_files(adapter_dir):
            rel = source.relative_to(adapter_dir).as_posix()
            if skip_adapter_manifest(rel):
                continue
            assert_source_contained(adapter_dir, source, rel)

            if rel.startswith(ANTIGRAVITY_RULES_DIR + "/"):
                name = Path(rel).name
                parent = Path(rel).parent.as_posix()
                if parent != ANTIGRAVITY_RULES_DIR:
                    unexpected.append(rel)
                    continue
                if not name.endswith(".md"):
                    unexpected.append(rel)
                    continue
                if not safe_path_component(name):
                    raise InstallAssemblyError(
                        "Unsafe generated Antigravity filename: {}".format(name)
                    )
                items.append(
                    desired_file(
                        relative_path=rel,
                        adapter=ANTIGRAVITY_ADAPTER,
                        source_path=source,
                    )
                )
                continue

            unexpected.append(rel)

        if unexpected:
            raise InstallAssemblyError(
                "Unexpected Antigravity bundle files: {}".format(", ".join(unexpected))
            )
        return require_non_empty(items, ANTIGRAVITY_ADAPTER, adapter_dir)
