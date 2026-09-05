#!/usr/bin/env python3
"""
Build and smoke-test the EKP wheel from outside the repository.

Run from repository root after building:
    py -3 scripts/packaging/smoke_install_wheel.py
"""

import hashlib
import json
import subprocess
import sys
import tempfile
from pathlib import Path


REQUIRED_COMMANDS = (
    "detect",
    "version",
    "install",
    "status",
    "update",
    "uninstall",
)


def write_symfony(root):
    root.joinpath("composer.json").write_text(
        '{"require":{"php":"^8.2","symfony/framework-bundle":"^7.0"}}',
        encoding="utf-8",
    )
    root.joinpath("symfony.lock").write_text("{}", encoding="utf-8")
    root.joinpath("config").mkdir(exist_ok=True)
    root.joinpath("config/bundles.php").write_text("<?php", encoding="utf-8")


def file_inventory(root):
    items = {}
    for path in sorted(root.rglob("*")):
        if path.is_file():
            rel = path.relative_to(root).as_posix()
            items[rel] = hashlib.sha256(path.read_bytes()).hexdigest()
    return items


def run_ekp(ekp, args, path):
    return subprocess.run(
        [str(ekp)] + args + ["--path", str(path)],
        capture_output=True,
        text=True,
    )


def load_manifest(root):
    return json.loads((root / ".ekp" / "install.json").read_text(encoding="utf-8"))


def load_status(ekp, root):
    proc = run_ekp(ekp, ["status", "--json"], root)
    assert proc.returncode == 0, proc.stderr + proc.stdout
    return json.loads(proc.stdout)


def count_rules(root):
    rules = root / ".cursor" / "rules"
    return len(list(rules.glob("*.mdc"))) if rules.is_dir() else 0


def expected_version_from_wheel(wheel):
    name = wheel.name
    prefix = "engineering_knowledge_pack-"
    suffix = "-py3-none-any.whl"
    if not (name.startswith(prefix) and name.endswith(suffix)):
        raise SystemExit("Unexpected wheel filename: {}".format(name))
    return name[len(prefix) : -len(suffix)]


def main():
    repo_root = Path(__file__).resolve().parents[2]
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
    wheel_version = expected_version_from_wheel(wheel)

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

        meta = subprocess.run(
            [
                str(python),
                "-c",
                "from importlib.metadata import version; print(version('engineering-knowledge-pack'))",
            ],
            capture_output=True,
            text=True,
            check=True,
        )
        installed_version = meta.stdout.strip()
        if installed_version != wheel_version:
            print(
                "Wheel/package version mismatch: {} vs {}".format(
                    wheel_version, installed_version
                ),
                file=sys.stderr,
            )
            return 1

        proc = subprocess.run([str(ekp), "version"], capture_output=True, text=True, check=True)
        print(proc.stdout.strip())
        version_line = proc.stdout.splitlines()[0].strip()
        if version_line != installed_version:
            print("Unexpected version output", file=sys.stderr)
            return 1

        proc = subprocess.run([str(ekp), "--help"], capture_output=True, text=True, check=True)
        for command in REQUIRED_COMMANDS:
            if command not in proc.stdout:
                print("Help missing {} command".format(command), file=sys.stderr)
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
assert (root / "schema").is_dir(), root
assert (root / "scripts").is_dir(), root
assert root.name == "_resources", "Expected installed bundled resources"
assert root.parent.name == "ekp", root
posix = root.as_posix()
assert "/site-packages/ekp/_resources" in posix or posix.endswith("site-packages/ekp/_resources"), posix
print("resource_root", root)

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
        if repo_root.as_posix() in proc.stdout.replace("\\", "/"):
            print("resource_root resolved to repository checkout", file=sys.stderr)
            return 1

        config_script = tmp_path / "smoke_project_config.py"
        config_script.write_text(
            """
import tempfile
from pathlib import Path
from ekp.composition import ComponentRegistry
from ekp.config import ProjectConfig, ProjectConfigStore, configuration_sha256
from ekp.paths import get_ekp_root

root = get_ekp_root()
schema = root / "schema" / "project-config.schema.json"
assert schema.is_file(), schema
assert root.name == "_resources", root
registry = ComponentRegistry.load(root)
assert registry.has("symfony")

with tempfile.TemporaryDirectory() as tmp:
    project = Path(tmp)
    store = ProjectConfigStore(project, registry=registry, resource_root=root)
    created = store.create(
        ProjectConfig(
            schema_version=1,
            components=("symfony", "frontend"),
            assistants=("cursor",),
        )
    )
    loaded = store.load()
    assert loaded == created
    digest = configuration_sha256(created, registry)
    assert len(digest) == 64
    assert store.load_snapshot().configuration_sha256 == digest
print("installed_project_config_ok", digest)
""",
            encoding="utf-8",
        )

        proc = subprocess.run(
            [str(python), str(config_script)],
            capture_output=True,
            text=True,
            cwd=str(tmp_path),
        )
        if proc.returncode != 0:
            print(proc.stdout, file=sys.stderr)
            print(proc.stderr, file=sys.stderr)
            return proc.returncode
        print(proc.stdout.strip())
        if "installed_project_config_ok" not in proc.stdout:
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

def write_symfony(root):
    root.joinpath("composer.json").write_text(
        '{"require":{"php":"^8.2","symfony/framework-bundle":"^7.0"}}',
        encoding="utf-8",
    )
    root.joinpath("symfony.lock").write_text("{}", encoding="utf-8")
    root.joinpath("config").mkdir(exist_ok=True)
    root.joinpath("config/bundles.php").write_text("<?php", encoding="utf-8")

def write_flutter(root):
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
expected_version = sys.argv[2]

def write_symfony(root):
    root.joinpath("composer.json").write_text(
        '{"require":{"php":"^8.2","symfony/framework-bundle":"^7.0"}}',
        encoding="utf-8",
    )
    root.joinpath("symfony.lock").write_text("{}", encoding="utf-8")
    root.joinpath("config").mkdir(exist_ok=True)
    root.joinpath("config/bundles.php").write_text("<?php", encoding="utf-8")

def write_flutter(root):
    root.joinpath("lib").mkdir(exist_ok=True)
    root.joinpath("lib/main.dart").write_text("void main() {}", encoding="utf-8")
    root.joinpath("pubspec.yaml").write_text(
        "name: demo\\nflutter:\\n  sdk: flutter\\n",
        encoding="utf-8",
    )

def count_rules(root):
    rules = root / ".cursor" / "rules"
    return len(list(rules.glob("*.mdc"))) if rules.is_dir() else 0

with tempfile.TemporaryDirectory() as symfony_dir:
    symfony_root = Path(symfony_dir)
    write_symfony(symfony_root)
    proc = subprocess.run([ekp, "install", "--yes", "--path", str(symfony_root)], capture_output=True, text=True)
    assert proc.returncode == 0, proc.stderr + proc.stdout
    manifest = json.loads((symfony_root / ".ekp" / "install.json").read_text(encoding="utf-8"))
    assert manifest["profile"] == "cursor-symfony", manifest
    assert manifest["ekp_version"] == expected_version, manifest
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
            [str(python), str(install_script), str(ekp), installed_version],
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

        fixture = tmp_path / "lifecycle-fixture"
        fixture.mkdir()
        write_symfony(fixture)

        proc = run_ekp(ekp, ["install", "--yes"], fixture)
        assert proc.returncode == 0, proc.stderr + proc.stdout
        manifest = load_manifest(fixture)
        assert manifest["profile"] == "cursor-symfony", manifest
        assert manifest["ekp_version"] == installed_version, manifest
        assert len(manifest["managed_files"]) == 83, len(manifest["managed_files"])
        assert count_rules(fixture) == 83
        payload = load_status(ekp, fixture)
        assert payload["state"] == "healthy", payload
        print("lifecycle_fresh_install_ok")

        manifest_bytes = (fixture / ".ekp" / "install.json").read_bytes()
        proc = run_ekp(ekp, ["update", "--yes"], fixture)
        assert proc.returncode == 0, proc.stderr + proc.stdout
        after_manifest = load_manifest(fixture)
        assert after_manifest["profile"] == "cursor-symfony", after_manifest
        assert after_manifest["ekp_version"] == installed_version, after_manifest
        assert len(after_manifest["managed_files"]) == 83
        assert (fixture / ".ekp" / "install.json").read_bytes() == manifest_bytes
        payload = load_status(ekp, fixture)
        assert payload["state"] == "healthy", payload
        print("lifecycle_same_version_update_ok")

        repair_root = tmp_path / "lifecycle-repair"
        repair_root.mkdir()
        write_symfony(repair_root)
        proc = run_ekp(ekp, ["install", "--yes"], repair_root)
        assert proc.returncode == 0, proc.stderr + proc.stdout
        repair_manifest = load_manifest(repair_root)
        installed_at = repair_manifest["installed_at"]
        deleted = next((repair_root / ".cursor" / "rules").glob("*.mdc"))
        deleted_name = deleted.name
        deleted.unlink()
        proc = run_ekp(ekp, ["update", "--yes"], repair_root)
        assert proc.returncode == 0, proc.stderr + proc.stdout
        restored = repair_root / ".cursor" / "rules" / deleted_name
        assert restored.is_file(), restored
        after_repair = load_manifest(repair_root)
        assert after_repair["ekp_version"] == installed_version, after_repair
        assert after_repair["installed_at"] == installed_at, after_repair
        assert after_repair["profile"] == "cursor-symfony", after_repair
        payload = load_status(ekp, repair_root)
        assert payload["state"] == "healthy", payload
        print("lifecycle_same_version_repair_ok")

        user_rule = fixture / ".cursor" / "rules" / "user-rule.mdc"
        user_rule.write_text("sentinel-user-rule\n", encoding="utf-8")
        before_update_dry = file_inventory(fixture)
        proc = run_ekp(ekp, ["update", "--dry-run"], fixture)
        assert proc.returncode == 0, proc.stderr + proc.stdout
        assert file_inventory(fixture) == before_update_dry
        before_uninstall_dry = file_inventory(fixture)
        proc = run_ekp(ekp, ["uninstall", "--dry-run"], fixture)
        assert proc.returncode == 0, proc.stderr + proc.stdout
        assert file_inventory(fixture) == before_uninstall_dry
        print("lifecycle_dry_run_ok")

        proc = run_ekp(ekp, ["uninstall", "--yes"], fixture)
        assert proc.returncode == 0, proc.stderr + proc.stdout
        assert not (fixture / ".ekp" / "install.json").exists()
        remaining = list((fixture / ".cursor" / "rules").glob("*.mdc"))
        assert remaining == [user_rule] or remaining[0].name == "user-rule.mdc", remaining
        assert user_rule.read_text(encoding="utf-8") == "sentinel-user-rule\n"
        assert (fixture / ".cursor" / "rules").is_dir()
        payload = load_status(ekp, fixture)
        assert payload["state"] == "not_installed", payload
        print("lifecycle_uninstall_ok")

        proc = run_ekp(ekp, ["uninstall", "--yes"], fixture)
        assert proc.returncode == 0, proc.stderr + proc.stdout
        combined = (proc.stdout + proc.stderr).lower()
        assert "not installed" in combined, proc.stdout + proc.stderr
        assert user_rule.read_text(encoding="utf-8") == "sentinel-user-rule\n"
        print("lifecycle_uninstall_idempotent_ok")

    print("Packaging smoke test passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
