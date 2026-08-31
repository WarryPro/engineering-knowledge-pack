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
        if "detect" not in proc.stdout:
            print("Help missing detect command", file=sys.stderr)
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

        detect_script = tmp_path / "smoke_detect.py"
        detect_script.write_text(
            """
import json
import subprocess
import sys
import tempfile
from pathlib import Path

ekp = sys.argv[1]

def write_symfony(root: Path):
    root.joinpath("composer.json").write_text(
        '{"require":{"php":"^8.2","symfony/framework-bundle":"^7.0"}}',
        encoding="utf-8",
    )
    root.joinpath("symfony.lock").write_text("{}", encoding="utf-8")
    root.joinpath("config").mkdir(exist_ok=True)
    root.joinpath("config/bundles.php").write_text("<?php", encoding="utf-8")

def write_flutter(root: Path):
    root.joinpath("lib").mkdir(exist_ok=True)
    root.joinpath("lib/main.dart").write_text("void main() {}", encoding="utf-8")
    root.joinpath("pubspec.yaml").write_text(
        "name: demo\\nflutter:\\n  sdk: flutter\\n",
        encoding="utf-8",
    )

with tempfile.TemporaryDirectory() as symfony_dir:
    symfony_root = Path(symfony_dir)
    write_symfony(symfony_root)
    proc = subprocess.run([ekp, "detect", "--json", "--path", str(symfony_root)], capture_output=True, text=True, check=True)
    payload = json.loads(proc.stdout)
    assert payload["recommended_profile"] == "cursor-symfony", payload
    assert any(item["technology"] == "symfony" for item in payload["technologies"]), payload
    print("installed_detect_symfony_ok")

with tempfile.TemporaryDirectory() as flutter_dir:
    flutter_root = Path(flutter_dir)
    write_flutter(flutter_root)
    proc = subprocess.run([ekp, "detect", "--json", "--path", str(flutter_root)], capture_output=True, text=True, check=True)
    payload = json.loads(proc.stdout)
    assert payload["recommended_profile"] == "cursor-flutter", payload
    print("installed_detect_flutter_ok")

with tempfile.TemporaryDirectory() as empty_dir:
    proc = subprocess.run([ekp, "detect", "--json", "--path", empty_dir], capture_output=True, text=True, check=True)
    payload = json.loads(proc.stdout)
    assert payload["recommended_profile"] is None, payload
    assert payload["technologies"] == [], payload
    print("installed_detect_empty_ok")
""",
            encoding="utf-8",
        )

        proc = subprocess.run(
            [str(python), str(detect_script), str(ekp)],
            capture_output=True,
            text=True,
            cwd=str(tmp_path),
        )
        if proc.returncode != 0:
            print(proc.stdout, file=sys.stderr)
            print(proc.stderr, file=sys.stderr)
            return proc.returncode
        print(proc.stdout.strip())
        for marker in (
            "installed_detect_symfony_ok",
            "installed_detect_flutter_ok",
            "installed_detect_empty_ok",
        ):
            if marker not in proc.stdout:
                return 1

    print("Packaging smoke test passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
