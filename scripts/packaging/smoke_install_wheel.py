#!/usr/bin/env python3
"""
Build and smoke-test the EKP wheel from outside the repository.

Run from repository root after building:
    py -3 scripts/packaging/smoke_install_wheel.py
"""

import subprocess
import sys
import tempfile
from pathlib import Path


def main():
    repo_root = Path(__file__).resolve().parents[2]
    build_dir = repo_root / "build"
    dist_dir = repo_root / "dist"

    subprocess.run(
        [sys.executable, "-m", "pip", "install", "build", "hatchling"],
        check=True,
        cwd=str(repo_root),
    )
    subprocess.run(
        [sys.executable, "-m", "build", "--wheel", str(repo_root), "-o", str(dist_dir)],
        check=True,
        cwd=str(repo_root),
    )

    wheels = sorted(dist_dir.glob("engineering_knowledge_pack-*.whl"))
    if not wheels:
        print("No wheel produced", file=sys.stderr)
        return 1
    wheel = wheels[-1]
    print("Built wheel: {}".format(wheel.name))

    with tempfile.TemporaryDirectory(prefix="ekp-smoke-") as tmp:
        tmp_path = Path(tmp)
        venv_dir = tmp_path / "venv"
        subprocess.run([sys.executable, "-m", "venv", str(venv_dir)], check=True)

        if sys.platform == "win32":
            python = venv_dir / "Scripts" / "python.exe"
            ekp = venv_dir / "Scripts" / "ekp.exe"
        else:
            python = venv_dir / "bin" / "python"
            ekp = venv_dir / "bin" / "ekp"

        subprocess.run([str(python), "-m", "pip", "install", str(wheel)], check=True)

        proc = subprocess.run([str(ekp), "version"], capture_output=True, text=True, check=True)
        print(proc.stdout.strip())
        if "0.15.0.dev0" not in proc.stdout:
            print("Unexpected version output", file=sys.stderr)
            return 1

        proc = subprocess.run([str(ekp), "--help"], capture_output=True, text=True, check=True)
        if "version" not in proc.stdout:
            print("Help missing version command", file=sys.stderr)
            return 1

        smoke_script = tmp_path / "smoke_assemble.py"
        smoke_script.write_text(
            """
import sys
from pathlib import Path
from ekp.assembly import AssemblyRequest, AssemblyService
from ekp.paths import get_ekp_root
import tempfile

root = get_ekp_root()
assert (root / "knowledge").is_dir(), root
assert (root / "profiles").is_dir(), root
assert root.name == "_resources", "Expected installed bundled resources"

with tempfile.TemporaryDirectory() as tmp:
    tmp_path = Path(tmp)
    result = AssemblyService().assemble(
        AssemblyRequest(
            profile="cursor-core",
            verify=True,
            resource_root=root,
            workspace_dir=tmp_path / "workspace",
            output_root=tmp_path / "output",
        )
    )
    count = len(list((result.bundle_path / "cursor").glob("*.mdc")))
    assert result.rules_count == 65, result.rules_count
    assert count == 65, count
    print("installed_assembly_ok", count)
""",
            encoding="utf-8",
        )

        proc = subprocess.run(
            [str(python), str(smoke_script)],
            capture_output=True,
            text=True,
            cwd=str(tmp_path),
        )
        if proc.returncode != 0:
            print(proc.stdout, file=sys.stderr)
            print(proc.stderr, file=sys.stderr)
            return proc.returncode
        print(proc.stdout.strip())
        if "installed_assembly_ok" not in proc.stdout:
            print(proc.stderr, file=sys.stderr)
            return 1

    print("Packaging smoke test passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
