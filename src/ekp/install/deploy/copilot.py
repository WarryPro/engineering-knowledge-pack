"""Copilot Consumer deployer (bundle → DesiredManagedFile)."""

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

COPILOT_ADAPTER = "copilot"
COPILOT_INSTRUCTIONS = ".github/copilot-instructions.md"
COPILOT_INSTRUCTIONS_DIR = ".github/instructions"
INSTRUCTIONS_SUFFIX = ".instructions.md"


class CopilotDeployer(Deployer):
    """Map ``<bundle>/copilot/.github/...`` → project ``.github/...`` (identity)."""

    @property
    def assistant_id(self) -> str:
        return COPILOT_ADAPTER

    def collect_desired_files(self, bundle_path: Path) -> List[DesiredManagedFile]:
        adapter_dir = require_assistant_dir(bundle_path, COPILOT_ADAPTER)
        items: List[DesiredManagedFile] = []
        unexpected: List[str] = []

        for source in list_assistant_files(adapter_dir):
            rel = source.relative_to(adapter_dir).as_posix()
            if skip_adapter_manifest(rel):
                continue
            assert_source_contained(adapter_dir, source, rel)

            if rel == COPILOT_INSTRUCTIONS:
                items.append(
                    desired_file(
                        relative_path=rel,
                        adapter=COPILOT_ADAPTER,
                        source_path=source,
                    )
                )
                continue

            if rel.startswith(COPILOT_INSTRUCTIONS_DIR + "/"):
                name = Path(rel).name
                parent = Path(rel).parent.as_posix()
                if parent != COPILOT_INSTRUCTIONS_DIR:
                    unexpected.append(rel)
                    continue
                if not name.endswith(INSTRUCTIONS_SUFFIX):
                    unexpected.append(rel)
                    continue
                if not safe_path_component(name):
                    raise InstallAssemblyError(
                        "Unsafe generated Copilot filename: {}".format(name)
                    )
                items.append(
                    desired_file(
                        relative_path=rel,
                        adapter=COPILOT_ADAPTER,
                        source_path=source,
                    )
                )
                continue

            unexpected.append(rel)

        if unexpected:
            raise InstallAssemblyError(
                "Unexpected Copilot bundle files: {}".format(", ".join(unexpected))
            )
        return require_non_empty(items, COPILOT_ADAPTER, adapter_dir)
