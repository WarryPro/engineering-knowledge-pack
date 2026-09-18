#!/usr/bin/env python3
"""Install an authoritative sdist outside the checkout and smoke Consumer CLI.

Release-only validation. Requires --sdist PATH.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
import venv
from pathlib import Path

GOLDEN_C = "2320ef8549f08599beb643f9bb1d04de9304cda1531ec11d44d033fb44dae1de"
REF_COUNTS = {"cursor": 105, "copilot": 16, "claude": 37, "antigravity": 38}


def isolated_env():
    env = os.environ.copy()
    env.pop("PYTHONPATH", None)
    env.pop("PYTHONHOME", None)
    return env


def run_ekp(ekp, args, project, *, env):
    return subprocess.run(
        [str(ekp)] + args + ["--path", str(project)],
        capture_output=True,
        text=True,
        env=env,
        cwd=str(Path(project).resolve().parent),
    )


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sdist", required=True, help="Path to authoritative .tar.gz")
    parser.add_argument(
        "--expected-version",
        required=True,
        help="Expected installed package version",
    )
    args = parser.parse_args(argv)

    sdist = Path(args.sdist).resolve()
    if not sdist.is_file():
        print("sdist not found:", sdist, file=sys.stderr)
        return 1

    with tempfile.TemporaryDirectory(prefix="ekp-sdist-smoke-") as tmp:
        base = Path(tmp)
        venv_dir = base / "venv"
        venv.create(venv_dir, with_pip=True)
        if sys.platform == "win32":
            python = venv_dir / "Scripts" / "python.exe"
            ekp = venv_dir / "Scripts" / "ekp.exe"
        else:
            python = venv_dir / "bin" / "python"
            ekp = venv_dir / "bin" / "ekp"

        env = isolated_env()
        subprocess.run(
            [str(python), "-m", "pip", "install", "--upgrade", "pip"],
            check=True,
            env=env,
            cwd=str(base),
        )
        subprocess.run(
            [str(python), "-m", "pip", "install", str(sdist)],
            check=True,
            env=env,
            cwd=str(base),
        )

        ver = subprocess.run(
            [str(ekp), "version"],
            capture_output=True,
            text=True,
            check=True,
            env=env,
            cwd=str(base),
        )
        version_line = ver.stdout.splitlines()[0].strip()
        print("installed_version", version_line)
        if version_line != args.expected_version:
            print(
                "version mismatch:",
                version_line,
                "!=",
                args.expected_version,
                file=sys.stderr,
            )
            return 1

        # schema1
        schema1 = base / "schema1"
        schema1.mkdir()
        (schema1 / "package.json").write_text('{"name":"demo"}', encoding="utf-8")
        proc = run_ekp(
            ekp,
            ["install", "--component", "frontend", "--assistant", "cursor", "--yes"],
            schema1,
            env=env,
        )
        if proc.returncode != 0:
            sys.stderr.write(proc.stdout + proc.stderr)
            return proc.returncode or 1
        status = json.loads(
            run_ekp(ekp, ["status", "--json"], schema1, env=env).stdout
        )
        assert str(status["state"]).upper() == "HEALTHY", status
        print("schema1_ok")

        # schema2 reference install (same shape as smoke_workspace_wheel)
        project = base / "monorepo"
        project.mkdir()
        for relative in ("apps/api", "apps/web", "apps/mobile", "packages/shared"):
            path = project / relative
            path.mkdir(parents=True)
            (path / "SENTINEL").write_text("ok\n", encoding="utf-8")
        proc = run_ekp(
            ekp,
            [
                "install",
                "--component",
                "devops",
                "--workspace",
                "apps/api",
                "symfony",
                "--workspace",
                "apps/web",
                "frontend",
                "--workspace",
                "apps/mobile",
                "flutter",
                "--workspace",
                "packages/shared",
                "typescript",
                "--assistant",
                "cursor",
                "--assistant",
                "copilot",
                "--assistant",
                "claude",
                "--assistant",
                "antigravity",
                "--yes",
            ],
            project,
            env=env,
        )
        if proc.returncode != 0:
            sys.stderr.write(proc.stdout + proc.stderr)
            return proc.returncode or 1
        status = json.loads(
            run_ekp(ekp, ["status", "--json"], project, env=env).stdout
        )
        assert str(status["state"]).upper() == "HEALTHY", status
        assert status.get("configuration_sha256") == GOLDEN_C, status
        manifest = json.loads(
            (project / ".ekp" / "install.json").read_text(encoding="utf-8")
        )
        counts = {}
        for item in manifest.get("managed_files", []):
            adapter = item.get("adapter")
            counts[adapter] = counts.get(adapter, 0) + 1
        for name, expected in REF_COUNTS.items():
            assert counts.get(name) == expected, (name, counts)
        print("schema2_ok", counts)
        print("sdist_consumer_smoke_PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
