"""Git change detection for incremental validation."""

import subprocess
from pathlib import Path

GRAPH_INVALIDATION_PREFIXES = (
    "schema/knowledge-frontmatter.schema.json",
    "schema/graph-rules.yaml",
    "schema/concept-namespaces.json",
    "schema/principle-exceptions.json",
)


def _is_knowledge_guide(path):
    # type: (str) -> bool
    if not path.startswith("knowledge/") or not path.endswith(".md"):
        return False
    name = Path(path).name
    return name != "README.md" and not name.startswith("adr-")


def get_changed_files(repo_root):
    # type: (Path) -> dict
    """
    Detect added, modified, and deleted paths vs HEAD.

    Returns dict with keys added, modified, deleted (lists of repo-relative paths),
    or None if git is unavailable.
    """
    try:
        diff_output = subprocess.check_output(
            ["git", "diff", "--name-only", "HEAD"],
            cwd=str(repo_root),
            stderr=subprocess.STDOUT,
        )
        untracked_output = subprocess.check_output(
            ["git", "ls-files", "--others", "--exclude-standard"],
            cwd=str(repo_root),
            stderr=subprocess.STDOUT,
        )
    except (OSError, subprocess.CalledProcessError):
        return None

    modified = [
        line.strip().replace("\\", "/")
        for line in diff_output.decode("utf-8").splitlines()
        if line.strip()
    ]
    added = [
        line.strip().replace("\\", "/")
        for line in untracked_output.decode("utf-8").splitlines()
        if line.strip()
    ]

    deleted = []
    try:
        deleted_output = subprocess.check_output(
            ["git", "diff", "--name-only", "--diff-filter=D", "HEAD"],
            cwd=str(repo_root),
            stderr=subprocess.STDOUT,
        )
        deleted = [
            line.strip().replace("\\", "/")
            for line in deleted_output.decode("utf-8").splitlines()
            if line.strip()
        ]
    except (OSError, subprocess.CalledProcessError):
        pass

    return {"added": added, "modified": modified, "deleted": deleted}


def get_all_changed_paths(change_set):
    # type: (dict) -> set
    paths = set()
    for key in ("added", "modified", "deleted"):
        paths.update(change_set.get(key, []))
    return paths


def requires_full_graph_validation(change_set):
    # type: (dict) -> bool
    """Return True when a change may affect the global dependency graph."""
    for path in get_all_changed_paths(change_set):
        for prefix in GRAPH_INVALIDATION_PREFIXES:
            if path == prefix or path.startswith(prefix):
                return True
    return False


def changed_knowledge_guides(change_set):
    # type: (dict) -> set
    guides = set()
    for key in ("added", "modified"):
        for path in change_set.get(key, []):
            if _is_knowledge_guide(path):
                guides.add(path)
    for path in change_set.get("deleted", []):
        if _is_knowledge_guide(path):
            guides.add(path)
    return guides
