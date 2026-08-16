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
from common.selected_knowledge import collect_selected_units

from claude.grouping import partition_units
from claude.writer import planned_files

ADAPTER_NAME = "claude"


def _write_text(path, content):
    # type: (Path, str) -> None
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


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

    units = collect_selected_units(profile, root)
    always_on, skills = partition_units(units)
    planned = planned_files(always_on, skills)

    written = []
    for relpath, content, _sources, _kind in planned:
        target = output_dir / relpath
        _write_text(target, content)
        written.append(str(target))

    return sorted(written)
