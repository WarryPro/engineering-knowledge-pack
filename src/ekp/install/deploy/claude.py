"""Claude Consumer deployer (bundle → DesiredManagedFile)."""

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

CLAUDE_ADAPTER = "claude"
CLAUDE_MD = "CLAUDE.md"
CLAUDE_SKILLS_DIR = ".claude/skills"
SKILL_FILENAME = "SKILL.md"


class ClaudeDeployer(Deployer):
    """Map ``<bundle>/claude/...`` → project root / ``.claude/skills/...`` (identity)."""

    @property
    def assistant_id(self) -> str:
        return CLAUDE_ADAPTER

    def collect_desired_files(self, bundle_path: Path) -> List[DesiredManagedFile]:
        adapter_dir = require_assistant_dir(bundle_path, CLAUDE_ADAPTER)
        items: List[DesiredManagedFile] = []
        unexpected: List[str] = []
        saw_claude_md = False
        skill_count = 0

        for source in list_assistant_files(adapter_dir):
            rel = source.relative_to(adapter_dir).as_posix()
            if skip_adapter_manifest(rel):
                continue
            assert_source_contained(adapter_dir, source, rel)

            if rel == CLAUDE_MD:
                saw_claude_md = True
                items.append(
                    desired_file(
                        relative_path=rel,
                        adapter=CLAUDE_ADAPTER,
                        source_path=source,
                    )
                )
                continue

            if rel.startswith(CLAUDE_SKILLS_DIR + "/"):
                parts = Path(rel).parts
                # Expected: .claude / skills / <skill-id> / SKILL.md
                if (
                    len(parts) != 4
                    or parts[0] != ".claude"
                    or parts[1] != "skills"
                    or parts[3] != SKILL_FILENAME
                ):
                    unexpected.append(rel)
                    continue
                skill_id = parts[2]
                if not safe_path_component(skill_id):
                    raise InstallAssemblyError(
                        "Unsafe generated Claude skill id: {}".format(skill_id)
                    )
                skill_count += 1
                items.append(
                    desired_file(
                        relative_path=rel,
                        adapter=CLAUDE_ADAPTER,
                        source_path=source,
                    )
                )
                continue

            unexpected.append(rel)

        if unexpected:
            raise InstallAssemblyError(
                "Unexpected Claude bundle files: {}".format(", ".join(unexpected))
            )
        if not saw_claude_md:
            raise InstallAssemblyError(
                "Assembled Claude output is missing CLAUDE.md: {}".format(adapter_dir)
            )
        if skill_count == 0:
            raise InstallAssemblyError(
                "Assembled Claude output has no skills: {}".format(adapter_dir)
            )
        return require_non_empty(items, CLAUDE_ADAPTER, adapter_dir)
