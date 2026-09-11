#!/usr/bin/env python3
"""
AZ-E: build/install the local wheel and smoke public workspace CLI outside the repo.

Run from repository root:
    py -3 scripts/packaging/smoke_workspace_wheel.py
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

GOLDEN_A = "09cf2e9312aa182a2fc6438080bc4a9c687838077e4e7aeffe56c448e8655b14"
GOLDEN_C = "2320ef8549f08599beb643f9bb1d04de9304cda1531ec11d44d033fb44dae1de"
EXPECTED_VERSION = "0.21.0.dev0"
REF_COUNTS = {"cursor": 105, "copilot": 16, "claude": 37, "antigravity": 38}


def run(cmd, *, cwd=None, check=True, env=None):
    proc = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, env=env)
    if check and proc.returncode != 0:
        sys.stderr.write(proc.stdout)
        sys.stderr.write(proc.stderr)
        raise SystemExit(proc.returncode or 1)
    return proc


def isolated_env():
    """Drop checkout PYTHONPATH so the venv wheel is the only import source."""
    import os

    env = os.environ.copy()
    env.pop("PYTHONPATH", None)
    env.pop("PYTHONHOME", None)
    return env


def run_ekp(ekp, args, project, *, env=None):
    return subprocess.run(
        [str(ekp)] + args + ["--path", str(project)],
        capture_output=True,
        text=True,
        env=env,
        cwd=str(Path(project).resolve().parent),
    )


def make_monorepo(root: Path) -> Path:
    project = root / "monorepo"
    project.mkdir()
    for relative in ("apps/api", "apps/web", "apps/mobile", "packages/shared"):
        path = project / relative
        path.mkdir(parents=True)
        (path / "SENTINEL").write_text("ok\n", encoding="utf-8")
    return project


def load_status(ekp, project, *, env=None):
    proc = run_ekp(ekp, ["status", "--json"], project, env=env)
    assert proc.returncode == 0, proc.stderr + proc.stdout
    return json.loads(proc.stdout)


def adapter_counts(project: Path) -> dict:
    manifest = json.loads((project / ".ekp" / "install.json").read_text(encoding="utf-8"))
    counts = {}
    for item in manifest.get("managed_files", []):
        adapter = item.get("adapter")
        counts[adapter] = counts.get(adapter, 0) + 1
    return counts


def main() -> int:
    repo_root = Path(__file__).resolve().parents[2]
    dist_dir = repo_root / "dist"
    dist_dir.mkdir(exist_ok=True)

    run([sys.executable, "-m", "pip", "install", "build", "hatchling"], cwd=str(repo_root))
    run(
        [sys.executable, "-m", "build", "--wheel", str(repo_root), "-o", str(dist_dir)],
        cwd=str(repo_root),
    )
    wheels = sorted(dist_dir.glob("engineering_knowledge_pack-*.whl"))
    if not wheels:
        print("No wheel produced", file=sys.stderr)
        return 1
    wheel = max(wheels, key=lambda path: path.stat().st_mtime)
    print("Built wheel:", wheel.name)
    if EXPECTED_VERSION not in wheel.name:
        print("Unexpected wheel version:", wheel.name, file=sys.stderr)
        return 1

    with tempfile.TemporaryDirectory(prefix="ekp-aze-wheel-") as tmp:
        tmp_path = Path(tmp)
        venv_dir = tmp_path / "venv"
        run([sys.executable, "-m", "venv", str(venv_dir)])
        if sys.platform == "win32":
            python = venv_dir / "Scripts" / "python.exe"
            ekp = venv_dir / "Scripts" / "ekp.exe"
        else:
            python = venv_dir / "bin" / "python"
            ekp = venv_dir / "bin" / "ekp"

        env = isolated_env()
        run([str(python), "-m", "pip", "install", str(wheel)], env=env)

        ver = run(
            [
                str(python),
                "-c",
                "from importlib.metadata import version; print(version('engineering-knowledge-pack'))",
            ],
            env=env,
            cwd=str(tmp_path),
        )
        print("installed_version", ver.stdout.strip())
        assert ver.stdout.strip() == EXPECTED_VERSION

        # Packaging audit: critical modules importable without checkout.
        audit = run(
            [
                str(python),
                "-c",
                "import ekp.cli_workspace, ekp.workspace_identity, ekp.config.workspaces; "
                "from ekp.cli import main; from ekp.paths import get_ekp_root; "
                "root=get_ekp_root(); "
                "assert '_resources' in root.as_posix(), root; "
                "print('modules_ok', root)",
            ],
            cwd=str(tmp_path),
            env=env,
        )
        assert "modules_ok" in audit.stdout
        print(audit.stdout.strip())

        proc = run([str(ekp), "version"], check=False, env=env, cwd=str(tmp_path))
        assert proc.returncode == 0, proc.stderr
        print("ekp_version", proc.stdout.strip() or proc.stderr.strip())
        assert "site-packages" in proc.stdout.replace("\\", "/") or "_resources" in proc.stdout

        # Schema1 smoke
        schema1 = tmp_path / "schema1"
        schema1.mkdir()
        (schema1 / "package.json").write_text('{"name":"demo"}', encoding="utf-8")
        proc = run_ekp(
            ekp,
            ["install", "--component", "frontend", "--assistant", "cursor", "--yes"],
            schema1,
            env=env,
        )
        assert proc.returncode == 0, proc.stderr + proc.stdout
        status = load_status(ekp, schema1, env=env)
        assert str(status["state"]).upper() == "HEALTHY", status
        print("schema1_ok")

        # Schema2 reference install
        project = make_monorepo(tmp_path)
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
        assert proc.returncode == 0, proc.stderr + proc.stdout
        status = load_status(ekp, project, env=env)
        assert str(status["state"]).upper() == "HEALTHY"
        assert status.get("configuration_sha256") == GOLDEN_C
        counts = adapter_counts(project)
        for name, expected in REF_COUNTS.items():
            assert counts.get(name) == expected, (name, counts)
        print("schema2_install_ok", counts)

        proc = run_ekp(ekp, ["status"], project, env=env)
        assert proc.returncode == 0, proc.stderr + proc.stdout
        assert "Workspaces:" in proc.stdout
        print("status_ok")

        before = (project / ".ekp" / "project.yaml").read_bytes()
        proc = run_ekp(ekp, ["update", "--yes"], project, env=env)
        assert proc.returncode == 0, proc.stderr + proc.stdout
        assert (project / ".ekp" / "project.yaml").read_bytes() == before
        assert str(load_status(ekp, project, env=env)["state"]).upper() == "HEALTHY"
        print("update_ok")

        proc = run_ekp(
            ekp,
            [
                "configure",
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
                "frontend",
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
        assert proc.returncode == 0, proc.stderr + proc.stdout
        assert str(load_status(ekp, project, env=env)["state"]).upper() == "HEALTHY"
        print("configure_ok")

        # Empty-root install golden A
        empty = tmp_path / "empty_root"
        empty.mkdir()
        (empty / "apps" / "api").mkdir(parents=True)
        proc = run_ekp(
            ekp,
            [
                "install",
                "--workspace",
                "apps/api",
                "symfony",
                "--assistant",
                "cursor",
                "--yes",
            ],
            empty,
            env=env,
        )
        assert proc.returncode == 0, proc.stderr + proc.stdout
        assert load_status(ekp, empty, env=env)["configuration_sha256"] == GOLDEN_A
        print("empty_root_ok")

        proc = run_ekp(ekp, ["uninstall", "--yes"], project, env=env)
        assert proc.returncode == 0, proc.stderr + proc.stdout
        status = load_status(ekp, project, env=env)
        assert str(status["state"]).upper() in {"NOT_INSTALLED", "HEALTHY"} or not status.get(
            "installed"
        ) or status.get("managed_files", {}).get("total", 1) == 0
        # Composition uninstall keeps project.yaml; managed assistant outputs are removed.
        assert not (project / ".cursor" / "rules").exists() or not list(
            (project / ".cursor" / "rules").glob("*.mdc")
        )
        print("uninstall_ok")

    print("AZ-E wheel smoke PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
