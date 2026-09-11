"""Generate Claude Code CLAUDE.md and Skills from EKP profiles."""

import shutil
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
ADAPTERS_DIR = SCRIPT_DIR.parent
if str(ADAPTERS_DIR) not in sys.path:
    sys.path.insert(0, str(ADAPTERS_DIR))

from common.paths import get_dist_path, get_repo_root
from common.profile_loader import load_profile_by_name
from common.selected_knowledge import collect_selected_units_for_paths

from claude.grouping import partition_units
from claude.writer import planned_files

ADAPTER_NAME = "claude"


def _write_text(path, content):
    # type: (Path, str) -> None
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _render_global(output_dir, profile, repo_root, get_markdown=None):
    # type: (Path, dict, Path, object) -> list
    """Render GLOBAL/schema1 Claude files. Does not clear ``output_dir``."""
    units = collect_selected_units_for_paths(
        list(profile.get("knowledge") or []),
        repo_root,
        adapter_priorities=profile.get("adapter_priorities") or ["high"],
        get_markdown=get_markdown,
        require_orchestrator=True,
    )
    always_on, skills = partition_units(units)
    planned = planned_files(always_on, skills)
    written = []
    for relpath, content, _sources, _kind in planned:
        target = output_dir / relpath
        _write_text(target, content)
        written.append(str(target))
    return sorted(written)


def generate(profile_name="ekp-core", output_dir=None, profile=None, repo_root=None):
    # type: (str, Path, dict, Path) -> list
    """
    Generate Claude Code files for a profile.

    Pipeline: extract → selection → Claude grouping → Claude writer.
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

    return _render_global(output_dir, profile, root, get_markdown=None)


def generate_scoped(project_resolution, output_dir, repo_root=None):
    # type: (object, Path, Path) -> list
    """
    Generate one Claude bundle for GLOBAL + workspace ``.claude/rules``.

    One shared source cache serves GLOBAL and every WORKSPACE render.
    Workspace knowledge goes only to path-scoped rules, never Skills.
    """
    from common.document_body import render_document_unit_body
    from common.scoped_gen import (
        build_invocation_markdown_cache,
        ephemeral_global_profile,
        global_knowledge_paths,
        units_for_paths,
        workspace_knowledge_paths,
        workspace_path_order,
        write_claimed_text,
    )
    from common.workspace_names import workspace_scoped_filename

    root = repo_root or get_repo_root()
    output_dir = Path(output_dir)
    inventory = project_resolution.inventory

    if output_dir.exists():
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    claimed = set()
    written = []
    get_markdown = build_invocation_markdown_cache(root, inventory)

    global_paths = global_knowledge_paths(inventory)
    if global_paths:
        profile = ephemeral_global_profile(global_paths, outputs=["claude"])
        for path in _render_global(
            output_dir, profile, root, get_markdown=get_markdown
        ):
            claimed.add(Path(path).relative_to(output_dir).as_posix())
            written.append(path)

    rules_prefix = ".claude/rules"
    for workspace_path in workspace_path_order(inventory):
        paths = workspace_knowledge_paths(inventory, workspace_path)
        if not paths:
            continue
        units = units_for_paths(paths, root, get_markdown)
        for unit in units:
            filename = workspace_scoped_filename(
                workspace_path, unit.source_path, "md"
            )
            relpath = "{}/{}".format(rules_prefix, filename)
            body = render_document_unit_body(unit)
            content = (
                "---\n"
                "paths:\n"
                '  - "{}/**"\n'
                "---\n"
                "\n"
                "{}"
            ).format(workspace_path, body.lstrip("\n"))
            written.append(
                write_claimed_text(output_dir, relpath, content, claimed)
            )

    return sorted(written)
