"""AW-F product validation matrix (disposable fixtures, real CLI/API)."""

from __future__ import annotations

import hashlib
import io
import json
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

from ekp.cli import main
from ekp.composition import ComponentRegistry, resolve_composition
from ekp.config import PROJECT_CONFIG_RELATIVE, ProjectConfig, ProjectConfigStore
from ekp.config.project import render_project_config_yaml
from ekp.install.errors import EXIT_CONFLICT, EXIT_SELECTION
from ekp.install.manifest import INSTALL_MODE_COMPOSITION, ManifestStore
from ekp.lifecycle.apply import TransactionApplier
from ekp.lifecycle.update import UpdateRequest, UpdateService
from ekp.status.models import StatusState
from ekp.status.service import StatusRequest, StatusService
from ekp.tests.fixtures import (
    devops_fixture,
    flutter_fixture,
    frontend_fixture,
    nativescript_fixture,
    symfony_fixture,
)
from ekp.version import get_version


def _rules(project: Path) -> int:
    rules = project / ".cursor" / "rules"
    return len(list(rules.glob("*.mdc"))) if rules.is_dir() else 0


def _fp(project: Path):
    out = {}
    for path in sorted(project.rglob("*")):
        if path.is_file():
            out[path.relative_to(project).as_posix()] = hashlib.sha256(
                path.read_bytes()
            ).hexdigest()
    return out


def _run(argv):
    out = io.StringIO()
    err = io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        code = main(argv)
    return code, out.getvalue(), err.getvalue()


class ProductMatrixTests(unittest.TestCase):
    def test_01_symfony_full_lifecycle(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            symfony_fixture(project)
            code, out, err = _run(["detect", "--path", str(project), "--json"])
            self.assertEqual(code, 0, err)
            detect = json.loads(out)
            self.assertEqual(detect["proposed_components"], ["symfony"])
            self.assertEqual(
                detect["resolved_components"], ["core", "php", "symfony"]
            )
            code, _, err = _run(["install", "--path", str(project), "--yes"])
            self.assertEqual(code, 0, err)
            self.assertEqual(_rules(project), 83)
            status = StatusService().inspect(StatusRequest(path=str(project)))
            self.assertEqual(status.state, StatusState.HEALTHY)
            self.assertEqual(status.mode, INSTALL_MODE_COMPOSITION)
            self.assertEqual(status.requested_components, ["symfony"])
            config_bytes = (project / PROJECT_CONFIG_RELATIVE).read_bytes()
            code, _, err = _run(["update", "--path", str(project), "--dry-run"])
            self.assertEqual(code, 0, err)
            code, _, err = _run(["update", "--path", str(project), "--yes"])
            self.assertEqual(code, 0, err)
            code, _, err = _run(["uninstall", "--path", str(project), "--yes"])
            self.assertEqual(code, 0, err)
            self.assertEqual((project / PROJECT_CONFIG_RELATIVE).read_bytes(), config_bytes)
            self.assertFalse((project / ".ekp" / "install.json").exists())
            status = StatusService().inspect(StatusRequest(path=str(project)))
            self.assertEqual(status.state, StatusState.NOT_INSTALLED)

    def test_02_frontend_install(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            frontend_fixture(project)
            code, _, err = _run(["install", "--path", str(project), "--yes"])
            self.assertEqual(code, 0, err)
            status = StatusService().inspect(StatusRequest(path=str(project)))
            self.assertEqual(status.state, StatusState.HEALTHY)
            self.assertEqual(status.requested_components, ["frontend"])
            self.assertEqual(
                status.resolved_components, ["core", "typescript", "frontend"]
            )
            self.assertEqual(_rules(project), 92)

    def test_03_flutter_install(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            flutter_fixture(project)
            code, _, err = _run(["install", "--path", str(project), "--yes"])
            self.assertEqual(code, 0, err)
            status = StatusService().inspect(StatusRequest(path=str(project)))
            self.assertEqual(status.requested_components, ["flutter"])
            self.assertEqual(status.resolved_components, ["core", "flutter"])
            self.assertEqual(_rules(project), 75)
            self.assertEqual(status.state, StatusState.HEALTHY)

    def test_04_nativescript_install(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            nativescript_fixture(project)
            code, _, err = _run(["install", "--path", str(project), "--yes"])
            self.assertEqual(code, 0, err)
            status = StatusService().inspect(StatusRequest(path=str(project)))
            self.assertEqual(status.requested_components, ["nativescript"])
            self.assertEqual(
                status.resolved_components, ["core", "typescript", "nativescript"]
            )
            self.assertEqual(_rules(project), 84)
            self.assertEqual(status.state, StatusState.HEALTHY)

    def test_05_symfony_frontend(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            symfony_fixture(project)
            frontend_fixture(project)
            code, _, err = _run(["install", "--path", str(project), "--yes"])
            self.assertEqual(code, 0, err)
            status = StatusService().inspect(StatusRequest(path=str(project)))
            self.assertEqual(status.requested_components, ["frontend", "symfony"])
            self.assertEqual(
                status.resolved_components,
                ["core", "php", "symfony", "typescript", "frontend"],
            )
            self.assertEqual(_rules(project), 110)
            self.assertFalse(
                (Path("profiles") / "cursor-symfony-frontend.yaml").exists()
            )

    def test_06_symfony_devops(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            symfony_fixture(project)
            devops_fixture(project)
            code, _, err = _run(["install", "--path", str(project), "--yes"])
            self.assertEqual(code, 0, err)
            status = StatusService().inspect(StatusRequest(path=str(project)))
            self.assertEqual(status.requested_components, ["devops", "symfony"])
            registry = ComponentRegistry.load()
            composition = resolve_composition(["devops", "symfony"], registry)
            self.assertEqual(
                list(composition.resolved_components),
                ["core", "devops", "php", "symfony"],
            )
            knowledge_count = len(composition.knowledge_paths)
            rules = _rules(project)
            self.assertGreater(knowledge_count, 0)
            self.assertGreater(rules, 83)  # devops adds rules beyond symfony-only
            self.assertEqual(status.state, StatusState.HEALTHY)
            self.assertEqual(
                status.resolved_components,
                ["core", "devops", "php", "symfony"],
            )
            print(
                "AWF_SYMFONY_DEVOPS knowledge={} rules={}".format(
                    knowledge_count, rules
                )
            )

    def test_07_symfony_frontend_devops(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            symfony_fixture(project)
            frontend_fixture(project)
            devops_fixture(project)
            code, _, err = _run(["install", "--path", str(project), "--yes"])
            self.assertEqual(code, 0, err)
            self.assertEqual(_rules(project), 119)
            paths = [
                m.relative_path
                for m in ManifestStore(project).load().managed_files
            ]
            self.assertEqual(len(paths), len(set(paths)))

    def test_08_empty_explicit(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            code, _, err = _run(
                [
                    "install",
                    "--path",
                    str(project),
                    "--component",
                    "symfony",
                    "--component",
                    "frontend",
                    "--yes",
                ]
            )
            self.assertEqual(code, 0, err)
            self.assertEqual(_rules(project), 110)
            self.assertTrue((project / PROJECT_CONFIG_RELATIVE).is_file())
            self.assertEqual(
                StatusService().inspect(StatusRequest(path=str(project))).state,
                StatusState.HEALTHY,
            )

    def test_09_empty_interactive(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            registry = ComponentRegistry.load()
            selectable = [c.id for c in registry.list_components() if c.selectable]
            indexes = [
                str(selectable.index("symfony") + 1),
                str(selectable.index("frontend") + 1),
            ]
            selection = ",".join(indexes)
            calls = {"n": 0}

            def input_fn(prompt=""):
                calls["n"] += 1
                if calls["n"] == 1:
                    return selection
                return "y"

            from ekp.install.service import InstallRequest, InstallService

            result = InstallService(input_fn=input_fn, output_fn=lambda _s: None).install(
                InstallRequest(path=str(project), assume_yes=False)
            )
            self.assertEqual(result.exit_code, 0, result.message)
            self.assertEqual(_rules(project), 110)
            raw = (project / PROJECT_CONFIG_RELATIVE).read_text(encoding="utf-8")
            self.assertIn("- symfony", raw)
            self.assertIn("- frontend", raw)
            self.assertNotRegex(raw, r"(?m)^\s*-\s*php\s*$")
            self.assertNotRegex(raw, r"(?m)^\s*-\s*typescript\s*$")
            self.assertNotRegex(raw, r"(?m)^\s*-\s*core\s*$")

    def test_10_empty_yes_refusal(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            before = _fp(project)
            code, _, _ = _run(["install", "--path", str(project), "--yes"])
            self.assertEqual(code, EXIT_SELECTION)
            self.assertEqual(_fp(project), before)
            self.assertFalse((project / PROJECT_CONFIG_RELATIVE).exists())
            self.assertFalse((project / ".ekp" / "install.json").exists())
            self.assertEqual(_rules(project), 0)

    def test_11_explicit_legacy(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            symfony_fixture(project)
            code, _, err = _run(
                [
                    "install",
                    "--path",
                    str(project),
                    "--profile",
                    "cursor-symfony",
                    "--yes",
                ]
            )
            self.assertEqual(code, 0, err)
            raw = json.loads((project / ".ekp" / "install.json").read_text(encoding="utf-8"))
            self.assertEqual(raw["profile"], "cursor-symfony")
            self.assertNotIn("mode", raw)
            self.assertFalse((project / PROJECT_CONFIG_RELATIVE).exists())
            self.assertEqual(_rules(project), 83)
            status = StatusService().inspect(StatusRequest(path=str(project)))
            self.assertEqual(status.mode, "legacy-profile")
            self.assertEqual(status.state, StatusState.HEALTHY)

    def test_12_mutual_exclusion(self):
        with tempfile.TemporaryDirectory() as tmp:
            before = _fp(Path(tmp))
            code, _, _ = _run(
                [
                    "install",
                    "--path",
                    tmp,
                    "--profile",
                    "cursor-symfony",
                    "--component",
                    "frontend",
                ]
            )
            self.assertEqual(code, EXIT_SELECTION)
            self.assertEqual(_fp(Path(tmp)), before)

    def test_13_update_toctou_mid_apply_rollback(self):
        """Hard gate: config change after some file writes must fully roll back."""
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            symfony_fixture(project)
            code, _, err = _run(["install", "--path", str(project), "--yes"])
            self.assertEqual(code, 0, err)
            # Force repair writes: delete one managed rule.
            rules = sorted((project / ".cursor" / "rules").glob("*.mdc"))
            deleted = rules[0]
            deleted_name = deleted.name
            deleted.unlink()
            inventory_before = {
                p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                for p in (project / ".cursor" / "rules").glob("*.mdc")
            }
            manifest_before = (project / ".ekp" / "install.json").read_bytes()
            bound = json.loads(manifest_before)["configuration_sha256"]

            applier = TransactionApplier()
            real_create = applier._apply_create
            created_count = {"n": 0}

            def create_and_mutate(plan, operation, created):
                real_create(plan, operation, created)
                created_count["n"] += 1
                if created_count["n"] == 1:
                    (project / PROJECT_CONFIG_RELATIVE).write_text(
                        render_project_config_yaml(
                            ProjectConfig(
                                schema_version=1,
                                components=("symfony", "frontend"),
                                assistants=("cursor",),
                            )
                        ),
                        encoding="utf-8",
                    )

            applier._apply_create = create_and_mutate
            service = UpdateService(applier=applier)
            result = service.update(UpdateRequest(path=str(project), assume_yes=True))
            self.assertEqual(result.exit_code, EXIT_CONFLICT, result.message)
            # Deleted rule must remain deleted (CREATE rolled back).
            self.assertFalse(
                (project / ".cursor" / "rules" / deleted_name).exists()
            )
            # No extra/partial new managed files beyond pre-apply inventory.
            after_names = {
                p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                for p in (project / ".cursor" / "rules").glob("*.mdc")
            }
            self.assertEqual(after_names, inventory_before)
            self.assertEqual(
                (project / ".ekp" / "install.json").read_bytes(), manifest_before
            )
            raw = json.loads(manifest_before)
            self.assertEqual(raw["configuration_sha256"], bound)
            status = StatusService().inspect(StatusRequest(path=str(project)))
            self.assertEqual(status.state, StatusState.CONFIGURATION_DRIFT)

    def test_14_status_precedence_drift_over_version(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            symfony_fixture(project)
            self.assertEqual(_run(["install", "--path", str(project), "--yes"])[0], 0)
            (project / PROJECT_CONFIG_RELATIVE).write_text(
                render_project_config_yaml(
                    ProjectConfig(
                        schema_version=1,
                        components=("symfony", "frontend"),
                        assistants=("cursor",),
                    )
                ),
                encoding="utf-8",
            )
            store = ManifestStore(project)
            manifest = store.load()
            manifest.ekp_version = "0.0.0"
            store.save(manifest)
            # Also delete a rule — drift still wins.
            next((project / ".cursor" / "rules").glob("*.mdc")).unlink()
            status = StatusService().inspect(StatusRequest(path=str(project)))
            self.assertEqual(status.state, StatusState.CONFIGURATION_DRIFT)

    def test_15_cross_version_composition_update(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            symfony_fixture(project)
            self.assertEqual(_run(["install", "--path", str(project), "--yes"])[0], 0)
            config_bytes = (project / PROJECT_CONFIG_RELATIVE).read_bytes()
            store = ManifestStore(project)
            snapshot = store.load_with_fingerprint()
            manifest = snapshot.manifest
            installed_at = manifest.installed_at
            bound = manifest.configuration_sha256
            manifest.ekp_version = "0.17.0"
            store.save(manifest)
            result = UpdateService().update(
                UpdateRequest(path=str(project), assume_yes=True)
            )
            self.assertEqual(result.exit_code, 0, result.message)
            after = ManifestStore(project).load()
            self.assertEqual(after.ekp_version, get_version())
            self.assertEqual(after.mode, INSTALL_MODE_COMPOSITION)
            self.assertEqual(after.profile, "project-composition")
            self.assertEqual(after.configuration_sha256, bound)
            self.assertEqual(after.installed_at, installed_at)
            self.assertEqual((project / PROJECT_CONFIG_RELATIVE).read_bytes(), config_bytes)
            self.assertEqual(
                StatusService().inspect(StatusRequest(path=str(project))).state,
                StatusState.HEALTHY,
            )


if __name__ == "__main__":
    unittest.main()
