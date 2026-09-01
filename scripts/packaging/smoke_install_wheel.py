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
    wheel = max(wheels, key=lambda path: path.stat().st_mtime)
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
        version_line = proc.stdout.splitlines()[0].strip()
        if version_line != "0.15.0":
            print("Unexpected version output", file=sys.stderr)
            return 1

        proc = subprocess.run([str(ekp), "--help"], capture_output=True, text=True, check=True)
        if "detect" not in proc.stdout:
            print("Help missing detect command", file=sys.stderr)
            return 1
        if "install" not in proc.stdout:
            print("Help missing install command", file=sys.stderr)
            return 1
        if "status" not in proc.stdout:
            print("Help missing status command", file=sys.stderr)
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

        install_script = tmp_path / "smoke_install.py"
        install_script.write_text(
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

def count_rules(root: Path) -> int:
    rules = root / ".cursor" / "rules"
    return len(list(rules.glob("*.mdc"))) if rules.is_dir() else 0

with tempfile.TemporaryDirectory() as symfony_dir:
    symfony_root = Path(symfony_dir)
    write_symfony(symfony_root)
    proc = subprocess.run([ekp, "install", "--yes", "--path", str(symfony_root)], capture_output=True, text=True)
    assert proc.returncode == 0, proc.stderr + proc.stdout
    manifest = json.loads((symfony_root / ".ekp" / "install.json").read_text(encoding="utf-8"))
    assert manifest["profile"] == "cursor-symfony", manifest
    assert count_rules(symfony_root) == 83, count_rules(symfony_root)
    assert len(manifest["managed_files"]) == 83, manifest
    proc = subprocess.run([ekp, "install", "--yes", "--path", str(symfony_root)], capture_output=True, text=True)
    assert proc.returncode == 0, proc.stderr + proc.stdout
    assert count_rules(symfony_root) == 83
    print("installed_install_symfony_ok")

with tempfile.TemporaryDirectory() as flutter_dir:
    flutter_root = Path(flutter_dir)
    write_flutter(flutter_root)
    proc = subprocess.run([ekp, "install", "--yes", "--path", str(flutter_root)], capture_output=True, text=True)
    assert proc.returncode == 0, proc.stderr + proc.stdout
    manifest = json.loads((flutter_root / ".ekp" / "install.json").read_text(encoding="utf-8"))
    assert manifest["profile"] == "cursor-flutter", manifest
    assert count_rules(flutter_root) == 75, count_rules(flutter_root)
    assert len(manifest["managed_files"]) == 75, manifest
    assert not (flutter_root / ".github").exists()
    print("installed_install_flutter_ok")

with tempfile.TemporaryDirectory() as empty_dir:
    empty_root = Path(empty_dir)
    proc = subprocess.run(
        [ekp, "install", "--yes", "--profile", "cursor-core", "--path", empty_dir],
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, proc.stderr + proc.stdout
    manifest = json.loads((empty_root / ".ekp" / "install.json").read_text(encoding="utf-8"))
    assert len(manifest["managed_files"]) == 65, manifest
    proc = subprocess.run([ekp, "install", "--yes", "--path", empty_dir], capture_output=True, text=True)
    assert proc.returncode == 2, proc.stdout
    assert not (empty_root / ".cursor").joinpath("rules").exists() or count_rules(empty_root) == 65
    print("installed_install_empty_ok")

with tempfile.TemporaryDirectory() as collision_dir:
    collision_root = Path(collision_dir)
    write_symfony(collision_root)
    assembly_probe = subprocess.run(
        [ekp, "install", "--dry-run", "--yes", "--path", str(collision_root)],
        capture_output=True,
        text=True,
    )
    assert assembly_probe.returncode == 0, assembly_probe.stderr
    # Placeholder collision file using a known EKP-style name from dry-run output
    rules_dir = collision_root / ".cursor" / "rules"
    rules_dir.mkdir(parents=True, exist_ok=True)
    rules_dir.joinpath("00-ekp-orchestrator.mdc").write_text("user", encoding="utf-8")
    proc = subprocess.run([ekp, "install", "--yes", "--path", str(collision_root)], capture_output=True, text=True)
    assert proc.returncode == 3, proc.stdout
    assert not (collision_root / ".ekp" / "install.json").exists()
    assert rules_dir.joinpath("00-ekp-orchestrator.mdc").read_text(encoding="utf-8") == "user"
    print("installed_install_collision_ok")

with tempfile.TemporaryDirectory() as dry_dir:
    dry_root = Path(dry_dir)
    before = list(dry_root.rglob("*"))
    proc = subprocess.run(
        [ekp, "install", "--profile", "cursor-flutter", "--dry-run", "--path", dry_dir],
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, proc.stderr
    after = list(dry_root.rglob("*"))
    assert before == after, (before, after)
    print("installed_install_dry_run_ok")

with tempfile.TemporaryDirectory() as status_dir:
    status_root = Path(status_dir)
    write_symfony(status_root)
    proc = subprocess.run([ekp, "install", "--yes", "--path", str(status_root)], capture_output=True, text=True)
    assert proc.returncode == 0, proc.stderr + proc.stdout
    proc = subprocess.run([ekp, "status", "--json", "--path", str(status_root)], capture_output=True, text=True)
    assert proc.returncode == 0, proc.stderr + proc.stdout
    payload = json.loads(proc.stdout)
    assert payload["installed"] is True, payload
    assert payload["state"] == "healthy", payload
    assert payload["profile"] == "cursor-symfony", payload
    assert payload["managed_files"]["total"] == 83, payload
    assert payload["managed_files"]["intact"] == 83, payload
    print("installed_status_healthy_ok")

    rule = next((status_root / ".cursor" / "rules").glob("*.mdc"))
    rule.write_text("modified", encoding="utf-8")
    proc = subprocess.run([ekp, "status", "--json", "--path", str(status_root)], capture_output=True, text=True)
    assert proc.returncode == 0, proc.stderr + proc.stdout
    payload = json.loads(proc.stdout)
    assert payload["state"] == "modified", payload
    assert len(payload["managed_files"]["modified"]) == 1, payload
    print("installed_status_modified_ok")

    rule.unlink()
    proc = subprocess.run([ekp, "status", "--json", "--path", str(status_root)], capture_output=True, text=True)
    assert proc.returncode == 0, proc.stderr + proc.stdout
    payload = json.loads(proc.stdout)
    assert payload["state"] == "incomplete", payload
    assert len(payload["managed_files"]["missing"]) == 1, payload
    print("installed_status_missing_ok")

with tempfile.TemporaryDirectory() as no_install_dir:
    proc = subprocess.run([ekp, "status", "--path", no_install_dir], capture_output=True, text=True)
    assert proc.returncode == 0, proc.stderr + proc.stdout
    assert "not installed" in proc.stdout.lower(), proc.stdout
    print("installed_status_not_installed_ok")

with tempfile.TemporaryDirectory() as invalid_dir:
    invalid_root = Path(invalid_dir)
    invalid_root.joinpath(".ekp").mkdir()
    invalid_root.joinpath(".ekp/install.json").write_text("{bad", encoding="utf-8")
    proc = subprocess.run([ekp, "status", "--path", str(invalid_root)], capture_output=True, text=True)
    assert proc.returncode == 3, proc.stdout
    print("installed_status_invalid_ok")

with tempfile.TemporaryDirectory() as mismatch_dir:
    mismatch_root = Path(mismatch_dir)
    write_symfony(mismatch_root)
    subprocess.run([ekp, "install", "--yes", "--path", str(mismatch_root)], check=True)
    manifest = json.loads((mismatch_root / ".ekp" / "install.json").read_text(encoding="utf-8"))
    manifest["ekp_version"] = "0.14.0"
    (mismatch_root / ".ekp" / "install.json").write_text(json.dumps(manifest, indent=2) + "\\n", encoding="utf-8")
    proc = subprocess.run([ekp, "status", "--json", "--path", str(mismatch_root)], capture_output=True, text=True)
    assert proc.returncode == 0, proc.stderr + proc.stdout
    payload = json.loads(proc.stdout)
    assert payload["state"] == "version_mismatch", payload
    assert payload["installed_version"] == "0.14.0", payload
    print("installed_status_version_mismatch_ok")
""",
            encoding="utf-8",
        )

        proc = subprocess.run(
            [str(python), str(install_script), str(ekp)],
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
            "installed_install_symfony_ok",
            "installed_install_flutter_ok",
            "installed_install_empty_ok",
            "installed_install_collision_ok",
            "installed_install_dry_run_ok",
            "installed_status_healthy_ok",
            "installed_status_modified_ok",
            "installed_status_missing_ok",
            "installed_status_not_installed_ok",
            "installed_status_invalid_ok",
            "installed_status_version_mismatch_ok",
        ):
            if marker not in proc.stdout:
                return 1

    print("Packaging smoke test passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
