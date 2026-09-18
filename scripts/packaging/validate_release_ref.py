#!/usr/bin/env python3
"""Validate a Trusted Publishing target/ref and emit machine-readable outputs.

Release-only tooling — not an EKP runtime dependency.

Usage:
    python scripts/packaging/validate_release_ref.py --target testpypi --ref <40-char-sha>
    python scripts/packaging/validate_release_ref.py --target pypi --ref vX.Y.Z

Optional:
    --repo-root PATH
    --github-output PATH   (append KEY=VALUE lines; default: $GITHUB_OUTPUT if set)
    --json                 (print JSON summary to stdout)
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path

FULL_SHA_RE = re.compile(r"^[0-9a-f]{40}$")
RELEASE_TAG_RE = re.compile(r"^v(\d+\.\d+\.\d+)$")
FINAL_VERSION_RE = re.compile(r"^\d+\.\d+\.\d+$")

_PROJECT_VERSION_RE = re.compile(
    r'^version\s*=\s*["\']([^"\']+)["\']\s*(?:#.*)?$'
)


class ReleaseRefError(Exception):
    """Fail-closed publication ref validation error."""


def _run_git(repo: Path, *args: str) -> str:
    proc = subprocess.run(
        ["git", *args],
        cwd=str(repo),
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        raise ReleaseRefError(
            "git {} failed: {}".format(" ".join(args), (proc.stderr or proc.stdout).strip())
        )
    return proc.stdout.strip()


def read_pyproject_version(repo: Path) -> str:
    path = repo / "pyproject.toml"
    if not path.is_file():
        raise ReleaseRefError("pyproject.toml missing")
    return _parse_project_version(path.read_text(encoding="utf-8"))


def read_pyproject_version_at(repo: Path, commit: str) -> str:
    text = _run_git(repo, "show", "{}:pyproject.toml".format(commit))
    return _parse_project_version(text)


def _parse_project_version(text: str) -> str:
    in_project = False
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if stripped.startswith("[") and stripped.endswith("]"):
            in_project = stripped == "[project]"
            continue
        if not in_project:
            continue
        match = _PROJECT_VERSION_RE.match(stripped)
        if match:
            return match.group(1)
    raise ReleaseRefError("pyproject.toml [project].version not found")


def is_final_version(version: str) -> bool:
    return bool(FINAL_VERSION_RE.match(version))


def is_prerelease_version(version: str) -> bool:
    if is_final_version(version):
        return False
    lower = version.lower()
    if ".dev" in lower or "rc" in lower:
        return True
    # PEP 440 local/prerelease markers without being strict-final
    return not FINAL_VERSION_RE.match(version)


def _object_type(repo: Path, ref: str) -> str:
    return _run_git(repo, "cat-file", "-t", ref)


def _peel_commit(repo: Path, ref: str) -> str:
    return _run_git(repo, "rev-parse", "{}^{{commit}}".format(ref))


def _is_annotated_tag(repo: Path, tag: str) -> bool:
    """Return True only when refs/tags/<tag> is an annotated tag object."""
    try:
        full = "refs/tags/{}".format(tag)
        # Resolve the tag ref itself (not peeled)
        sha = _run_git(repo, "rev-parse", full)
        return _object_type(repo, sha) == "tag"
    except ReleaseRefError:
        return False


def _ref_exists(repo: Path, ref: str) -> bool:
    proc = subprocess.run(
        ["git", "rev-parse", "--verify", "--quiet", ref],
        cwd=str(repo),
        capture_output=True,
        text=True,
        check=False,
    )
    return proc.returncode == 0


def _authorized_testpypi_containers(repo: Path, commit: str) -> list[str]:
    """Refs that may contain a TestPyPI publication commit."""
    proc = subprocess.run(
        ["git", "for-each-ref", "--format=%(refname)", "--contains", commit],
        cwd=str(repo),
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        raise ReleaseRefError("unable to list refs containing {}".format(commit))
    allowed_prefixes = (
        "refs/heads/master",
        "refs/heads/staging",
        "refs/heads/feature/",
        "refs/remotes/origin/master",
        "refs/remotes/origin/staging",
        "refs/remotes/origin/feature/",
    )
    hits = []
    for line in proc.stdout.splitlines():
        ref = line.strip()
        if any(ref == p or ref.startswith(p) for p in allowed_prefixes):
            hits.append(ref)
    return hits


def assert_clean_worktree(repo: Path) -> None:
    porcelain = _run_git(repo, "status", "--porcelain=v1")
    if porcelain:
        raise ReleaseRefError(
            "working tree is dirty; refuse publication build:\n{}".format(porcelain)
        )


def validate_testpypi(repo: Path, ref: str) -> dict:
    if not ref or not ref.strip():
        raise ReleaseRefError("ref is required")
    ref = ref.strip().lower()
    if not FULL_SHA_RE.match(ref):
        raise ReleaseRefError(
            "testpypi ref must be a full 40-character lowercase Git commit SHA"
        )
    if not _ref_exists(repo, ref):
        raise ReleaseRefError("commit does not exist: {}".format(ref))
    if _object_type(repo, ref) != "commit":
        raise ReleaseRefError("testpypi ref must resolve to a commit object")
    resolved = _peel_commit(repo, ref)
    if resolved != ref:
        raise ReleaseRefError("internal SHA normalization mismatch")

    containers = _authorized_testpypi_containers(repo, resolved)
    if not containers:
        raise ReleaseRefError(
            "commit is not reachable from an authorized branch "
            "(master/staging/feature/* local or origin)"
        )

    version = read_pyproject_version_at(repo, resolved)
    if is_final_version(version):
        raise ReleaseRefError(
            "testpypi refuses final release version {!r}; use a development/prerelease".format(
                version
            )
        )
    if not is_prerelease_version(version):
        raise ReleaseRefError(
            "testpypi requires a development/prerelease package version, got {!r}".format(
                version
            )
        )

    return {
        "target": "testpypi",
        "ref": ref,
        "resolved_sha": resolved,
        "package_version": version,
        "authorized_refs": containers,
        "tag_name": "",
    }


def validate_pypi(repo: Path, ref: str) -> dict:
    if not ref or not ref.strip():
        raise ReleaseRefError("ref is required")
    ref = ref.strip()
    match = RELEASE_TAG_RE.match(ref)
    if not match:
        raise ReleaseRefError(
            "pypi ref must be an official annotated release tag of the form vX.Y.Z"
        )
    expected_version = match.group(1)

    if not _ref_exists(repo, "refs/tags/{}".format(ref)):
        raise ReleaseRefError("tag does not exist: {}".format(ref))
    if not _is_annotated_tag(repo, ref):
        raise ReleaseRefError(
            "production tag {!r} must be an annotated Git tag (lightweight tags refuse)".format(
                ref
            )
        )

    resolved = _peel_commit(repo, ref)
    version = read_pyproject_version_at(repo, resolved)
    if version != expected_version:
        raise ReleaseRefError(
            "package version {!r} does not equal tag version {!r}".format(
                version, expected_version
            )
        )
    if not is_final_version(version):
        raise ReleaseRefError(
            "production publication requires a final X.Y.Z version, got {!r}".format(
                version
            )
        )

    for required in ("refs/remotes/origin/master", "refs/remotes/origin/staging"):
        if not _ref_exists(repo, required):
            # Fall back to local branch names for synthetic fixtures
            local = required.replace("refs/remotes/origin/", "refs/heads/")
            if not _ref_exists(repo, local):
                raise ReleaseRefError("missing required ref {}".format(required))
            required_resolved = local
        else:
            required_resolved = required
        tip = _peel_commit(repo, required_resolved)
        if tip != resolved:
            raise ReleaseRefError(
                "tagged commit {!r} must equal {} ({!r})".format(
                    resolved, required_resolved, tip
                )
            )

    return {
        "target": "pypi",
        "ref": ref,
        "resolved_sha": resolved,
        "package_version": version,
        "authorized_refs": ["origin/master", "origin/staging", ref],
        "tag_name": ref,
    }


def validate(repo: Path, target: str, ref: str) -> dict:
    if not target:
        raise ReleaseRefError("target is required")
    target = target.strip().lower()
    if target not in ("testpypi", "pypi"):
        raise ReleaseRefError(
            "unknown target {!r}; expected testpypi or pypi".format(target)
        )
    if target == "testpypi":
        return validate_testpypi(repo, ref)
    return validate_pypi(repo, ref)


def _write_github_output(path: Path, payload: dict) -> None:
    lines = []
    for key in (
        "target",
        "ref",
        "resolved_sha",
        "package_version",
        "tag_name",
    ):
        lines.append("{}={}".format(key, payload.get(key, "")))
    with path.open("a", encoding="utf-8") as handle:
        handle.write("\n".join(lines) + "\n")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--target", required=True, help="testpypi or pypi")
    parser.add_argument("--ref", required=True, help="commit SHA or vX.Y.Z tag")
    parser.add_argument(
        "--repo-root",
        default=None,
        help="repository root (default: cwd)",
    )
    parser.add_argument(
        "--github-output",
        default=None,
        help="append machine-readable outputs (default: $GITHUB_OUTPUT)",
    )
    parser.add_argument(
        "--require-clean",
        action="store_true",
        help="fail if the working tree is dirty",
    )
    parser.add_argument("--json", action="store_true", help="print JSON to stdout")
    args = parser.parse_args(argv)

    repo = Path(args.repo_root or Path.cwd()).resolve()
    if not (repo / ".git").exists() and not (repo / "pyproject.toml").is_file():
        # Allow worktree / linked checkout layouts: still require git
        proc = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            cwd=str(repo),
            capture_output=True,
            text=True,
            check=False,
        )
        if proc.returncode != 0:
            print("error: not a git repository: {}".format(repo), file=sys.stderr)
            return 2
        repo = Path(proc.stdout.strip()).resolve()

    try:
        if args.require_clean:
            assert_clean_worktree(repo)
        payload = validate(repo, args.target, args.ref)
    except ReleaseRefError as exc:
        print("error: {}".format(exc), file=sys.stderr)
        return 1

    out_path = args.github_output or os.environ.get("GITHUB_OUTPUT")
    if out_path:
        _write_github_output(Path(out_path), payload)

    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print(
            "target={target} resolved_sha={resolved_sha} package_version={package_version}".format(
                **payload
            )
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
