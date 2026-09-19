#!/usr/bin/env python3
"""Build reproducible publication artifacts outside the checkout.

Release-only tooling — not an EKP runtime dependency.

Performs:
  - clean worktree gate
  - Build A / Build B outside the repository
  - SHA256 equality gate
  - wheel/sdist content contract audit (BA-A)
  - twine check
  - version consistency across pyproject / wheel METADATA / filenames
  - authoritative copy + SHA256SUMS into --release-dist
"""

from __future__ import annotations

import argparse
import hashlib
import re
import shutil
import subprocess
import sys
import tarfile
import zipfile
from pathlib import Path

_PROJECT_VERSION_RE = re.compile(
    r'^version\s*=\s*["\']([^"\']+)["\']\s*(?:#.*)?$'
)

WHEEL_REQUIRED_PREFIXES = (
    "ekp/",
    "ekp/_resources/knowledge/",
    "ekp/_resources/profiles/",
    "ekp/_resources/components/",
    "ekp/_resources/schema/",
    "ekp/_resources/scripts/adapters/",
    "ekp/_resources/scripts/assemble/",
    "ekp/_resources/scripts/validate/",
)

SDIST_REQUIRED_RELATIVE = (
    "pyproject.toml",
    "README.md",
    "LICENSE",
    "src/ekp/",
    "src/ekp/tests/",
    "knowledge/",
    "profiles/",
    "components/",
    "schema/",
    "scripts/adapters/",
    "scripts/assemble/",
    "scripts/validate/",
)

SDIST_FORBIDDEN_MARKERS = (
    "/.git/",
    "/.github/",
    "/build/",
    "/dist/",
    "/.venv/",
    "/venv/",
    "/.pytest_cache/",
    "/coverage/",
    "/__pycache__/",
    "/_ba_a_out/",
)


class PrepareError(Exception):
    pass


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _run(cmd, *, cwd: Path) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, cwd=str(cwd), capture_output=True, text=True, check=False)


def assert_clean(repo: Path) -> None:
    proc = _run(["git", "status", "--porcelain=v1"], cwd=repo)
    if proc.returncode != 0:
        raise PrepareError("git status failed: {}".format(proc.stderr))
    if proc.stdout.strip():
        raise PrepareError(
            "working tree dirty; refuse publication build:\n{}".format(proc.stdout)
        )


def read_pyproject_version(repo: Path) -> str:
    path = repo / "pyproject.toml"
    in_project = False
    for line in path.read_text(encoding="utf-8").splitlines():
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
    raise PrepareError("pyproject version missing")


def _ensure_outside(repo: Path, outdir: Path) -> Path:
    outdir = outdir.resolve()
    repo = repo.resolve()
    if outdir == repo or repo in outdir.parents:
        raise PrepareError(
            "build outdir must be outside the repository checkout: {}".format(outdir)
        )
    if outdir.exists():
        shutil.rmtree(outdir)
    outdir.mkdir(parents=True)
    return outdir


def build_pair(repo: Path, outdir: Path) -> tuple[Path, Path]:
    outdir = _ensure_outside(repo, outdir)
    proc = _run(
        [sys.executable, "-m", "build", "--outdir", str(outdir)],
        cwd=repo,
    )
    if proc.returncode != 0:
        raise PrepareError(
            "build failed:\n{}\n{}".format(proc.stdout, proc.stderr)
        )
    wheels = sorted(outdir.glob("*.whl"))
    sdists = sorted(outdir.glob("*.tar.gz"))
    if len(wheels) != 1 or len(sdists) != 1:
        raise PrepareError(
            "expected one wheel and one sdist in {}; got {} / {}".format(
                outdir, [p.name for p in wheels], [p.name for p in sdists]
            )
        )
    return wheels[0], sdists[0]


def _has_prefix(names, prefix: str) -> bool:
    return any(n == prefix.rstrip("/") or n.startswith(prefix) for n in names)


def audit_wheel(wheel: Path, expected_version: str) -> None:
    if not wheel.is_file():
        raise PrepareError("missing wheel: {}".format(wheel))
    with zipfile.ZipFile(wheel) as zf:
        names = zf.namelist()
        meta_name = next(n for n in names if n.endswith(".dist-info/METADATA"))
        metadata = zf.read(meta_name).decode("utf-8")
    if any(n.startswith("ekp/tests/") for n in names):
        raise PrepareError("wheel contains forbidden ekp/tests/**")
    for prefix in WHEEL_REQUIRED_PREFIXES:
        if not _has_prefix(names, prefix):
            raise PrepareError("wheel missing required prefix {}".format(prefix))
    if "Version: {}".format(expected_version) not in metadata:
        raise PrepareError(
            "wheel METADATA version mismatch; expected {}".format(expected_version)
        )
    if expected_version not in wheel.name:
        raise PrepareError("wheel filename version mismatch: {}".format(wheel.name))


def audit_sdist(sdist: Path, expected_version: str) -> None:
    if not sdist.is_file():
        raise PrepareError("missing sdist: {}".format(sdist))
    if expected_version not in sdist.name:
        raise PrepareError("sdist filename version mismatch: {}".format(sdist.name))
    with tarfile.open(sdist, "r:gz") as tf:
        names = tf.getnames()
    relative = []
    for name in names:
        parts = name.split("/", 1)
        relative.append(parts[1] if len(parts) == 2 else name)
    for required in SDIST_REQUIRED_RELATIVE:
        if not _has_prefix(relative, required):
            raise PrepareError("sdist missing required path {}".format(required))
    rooted = ["/" + n for n in names]
    for marker in SDIST_FORBIDDEN_MARKERS:
        hits = [n for n in rooted if marker in n]
        if hits:
            raise PrepareError(
                "sdist contains forbidden {}: {}".format(marker, hits[:5])
            )


def twine_check(wheel: Path, sdist: Path) -> None:
    proc = subprocess.run(
        [sys.executable, "-m", "twine", "check", str(wheel), str(sdist)],
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        raise PrepareError(
            "twine check failed:\n{}\n{}".format(proc.stdout, proc.stderr)
        )


def write_sha256sums(directory: Path, files: list[Path]) -> Path:
    lines = []
    for path in sorted(files, key=lambda p: p.name):
        lines.append("{}  {}".format(_sha256(path), path.name))
    manifest = directory / "SHA256SUMS"
    manifest.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return manifest


def prepare(
    repo: Path,
    build_a: Path,
    build_b: Path,
    release_dist: Path,
) -> dict:
    assert_clean(repo)
    version = read_pyproject_version(repo)

    wheel_a, sdist_a = build_pair(repo, build_a)
    wheel_b, sdist_b = build_pair(repo, build_b)

    if _sha256(wheel_a) != _sha256(wheel_b):
        raise PrepareError(
            "wheel reproducibility failed: {} != {}".format(
                _sha256(wheel_a), _sha256(wheel_b)
            )
        )
    if _sha256(sdist_a) != _sha256(sdist_b):
        raise PrepareError(
            "sdist reproducibility failed: {} != {}".format(
                _sha256(sdist_a), _sha256(sdist_b)
            )
        )

    audit_wheel(wheel_a, version)
    audit_sdist(sdist_a, version)
    twine_check(wheel_a, sdist_a)

    release_dist = release_dist.resolve()
    if release_dist.exists():
        shutil.rmtree(release_dist)
    release_dist.mkdir(parents=True)

    auth_wheel = release_dist / wheel_a.name
    auth_sdist = release_dist / sdist_a.name
    shutil.copy2(wheel_a, auth_wheel)
    shutil.copy2(sdist_a, auth_sdist)
    write_sha256sums(release_dist, [auth_wheel, auth_sdist])

    return {
        "package_version": version,
        "wheel": auth_wheel.name,
        "sdist": auth_sdist.name,
        "wheel_sha256": _sha256(auth_wheel),
        "sdist_sha256": _sha256(auth_sdist),
        "wheel_size": auth_wheel.stat().st_size,
        "sdist_size": auth_sdist.stat().st_size,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", default=".", help="source checkout root")
    parser.add_argument("--build-a", required=True, help="Build A outdir (outside checkout)")
    parser.add_argument("--build-b", required=True, help="Build B outdir (outside checkout)")
    parser.add_argument(
        "--release-dist",
        required=True,
        help="authoritative publication directory (outside checkout)",
    )
    args = parser.parse_args(argv)

    repo = Path(args.repo_root).resolve()
    try:
        result = prepare(
            repo,
            Path(args.build_a),
            Path(args.build_b),
            Path(args.release_dist),
        )
    except PrepareError as exc:
        print("error: {}".format(exc), file=sys.stderr)
        return 1

    print(
        "prepared version={package_version} wheel={wheel} sdist={sdist}".format(**result)
    )
    print("wheel_sha256={wheel_sha256}".format(**result))
    print("sdist_sha256={sdist_sha256}".format(**result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
