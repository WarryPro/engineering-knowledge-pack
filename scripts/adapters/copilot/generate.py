"""Generate GitHub Copilot instruction files from EKP profiles."""

import shutil
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
ADAPTERS_DIR = SCRIPT_DIR.parent
if str(ADAPTERS_DIR) not in sys.path:
    sys.path.insert(0, str(ADAPTERS_DIR))

from common.paths import get_dist_path, get_repo_root
from common.profile_loader import load_profile_by_name
from common.selected_knowledge import collect_selected_units

from copilot.grouping import group_by_name, partition_units
from copilot.writer import planned_files

ADAPTER_NAME = "copilot"


def _write_text(path, content):
    # type: (Path, str) -> None
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def generate(profile_name="ekp-core", output_dir=None, profile=None, repo_root=None):
    # type: (str, Path, dict, Path) -> list
    """
    Generate Copilot instruction files for a profile.

    Pipeline: extract → selection → Copilot grouping → Copilot writer.
    Returns a sorted list of written file paths.
    """
    root = repo_root or get_repo_root()
    if profile is None:
        profile = load_profile_by_name(profile_name, repo_root=root)

    if output_dir is None:
        output_dir = get_dist_path() / profile_name / ADAPTER_NAME
    else:
        output_dir = Path(output_dir)

    if output_dir.exists():
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    units = collect_selected_units(profile, root)
    always_on, grouped = partition_units(units)
    planned = planned_files(always_on, grouped, group_by_name)

    written = []
    for relpath, content, _sources in planned:
        target = output_dir / relpath
        _write_text(target, content)
        written.append(str(target))

    return sorted(written)


def generate_scoped(project_resolution, output_dir, repo_root=None):
    # type: (object, Path, Path) -> list
    """
    Generate one Copilot bundle for GLOBAL + all workspace scopes.

    Workspace knowledge never enters ``copilot-instructions.md``.
    """
    from common.scoped_gen import (
        build_invocation_markdown_cache,
        ephemeral_global_profile,
        global_knowledge_paths,
        units_for_paths,
        workspace_knowledge_paths,
        workspace_path_order,
        write_claimed_text,
    )
    from common.workspace_names import (
        prefix_apply_to_patterns,
        workspace_scoped_filename,
    )
    from copilot.writer import render_path_instructions
    from copilot.grouping import instruction_relpath

    root = repo_root or get_repo_root()
    output_dir = Path(output_dir)
    inventory = project_resolution.inventory

    if output_dir.exists():
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    claimed = set()
    written = []

    global_paths = global_knowledge_paths(inventory)
    if global_paths:
        profile = ephemeral_global_profile(global_paths, outputs=["copilot"])
        for path in generate(
            profile_name="project-composition",
            output_dir=output_dir,
            profile=profile,
            repo_root=root,
        ):
            rel = Path(path).relative_to(output_dir).as_posix()
            claimed.add(rel)
            written.append(path)

    get_markdown = build_invocation_markdown_cache(root, inventory)
    for workspace_path in workspace_path_order(inventory):
        paths = workspace_knowledge_paths(inventory, workspace_path)
        if not paths:
            continue
        units = units_for_paths(paths, root, get_markdown)
        always_on, grouped = partition_units(units)

        if always_on:
            # Workspace always-on cannot use repository-wide instructions.
            general_group = {
                "name": "general",
                "filename": workspace_scoped_filename(
                    workspace_path,
                    "workspace-general.md",
                    "instructions.md",
                ),
                "apply_to": "{}/**".format(workspace_path),
            }
            relpath = instruction_relpath(general_group["filename"])
            content = render_path_instructions(general_group, always_on)
            written.append(
                write_claimed_text(output_dir, relpath, content, claimed)
            )

        for name in sorted(grouped.keys()):
            group = group_by_name(name)
            units_in_group = grouped[name]
            scoped_group = {
                "name": group["name"],
                "filename": workspace_scoped_filename(
                    workspace_path,
                    "workspace-{}.md".format(group["name"]),
                    "instructions.md",
                ),
                "apply_to": prefix_apply_to_patterns(
                    group["apply_to"], workspace_path
                ),
            }
            relpath = instruction_relpath(scoped_group["filename"])
            content = render_path_instructions(scoped_group, units_in_group)
            written.append(
                write_claimed_text(output_dir, relpath, content, claimed)
            )

    return sorted(written)
