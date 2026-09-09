"""Public ``ekp configure`` CLI tests (AY-C)."""

from __future__ import annotations

import hashlib
import io
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from ekp import cli
from ekp.assembly import AssemblyService
from ekp.composition import ComponentRegistry
from ekp.config.project import ProjectConfigStore
from ekp.install.composition_install import CompositionInstallService
from ekp.install.errors import EXIT_CONFLICT, EXIT_SELECTION, EXIT_SUCCESS
from ekp.install.intent import build_composition_intent
from ekp.install.manifest import ManifestStore
from ekp.install.service import InstallRequest, InstallService
from ekp.lifecycle.configure import ConfigureService
from ekp.lifecycle.configure_cli import run_configure_cli
from ekp.lifecycle.update import UpdateRequest, UpdateService
from ekp.paths import get_ekp_root
from ekp.status.models import StatusState
from ekp.status.service import StatusRequest, StatusService
from ekp.version import get_version


def _fingerprint(root: Path):
    items = {}
    for path in sorted(root.rglob("*")):
        if path.is_file():
            items[path.relative_to(root).as_posix()] = hashlib.sha256(
                path.read_bytes()
            ).hexdigest()
    return items


class ConfigureCliHelpers(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.registry = ComponentRegistry.load()
        cls.resource_root = get_ekp_root()
        cls.version = get_version()

    def _install(self, project: Path, components, assistants):
        intent = build_composition_intent(
            components, self.registry, assistants=assistants
        )
        result = CompositionInstallService(
            registry=self.registry,
            resource_root=self.resource_root,
        ).install(project, intent)
        self.assertEqual(result.exit_code, EXIT_SUCCESS, result.message)
        return intent

    def _status(self, project: Path):
        return StatusService().inspect(StatusRequest(path=str(project)))

    def _service(self) -> ConfigureService:
        return ConfigureService(
            registry=self.registry,
            resource_root=self.resource_root,
        )

    def _run(
        self,
        project: Path,
        *,
        components=None,
        assistants=None,
        assume_yes=False,
        dry_run=False,
        answers=None,
        outputs=None,
    ):
        answers = list(answers or [])
        outputs = outputs if outputs is not None else []

        def input_fn(_prompt=""):
            if not answers:
                return ""
            return answers.pop(0)

        def output_fn(text):
            outputs.append(text)

        return run_configure_cli(
            path=str(project),
            components=components,
            assistants=assistants,
            assume_yes=assume_yes,
            dry_run=dry_run,
            input_fn=input_fn,
            output_fn=output_fn,
            service=self._service(),
        )


class ConfigureCliHelpTests(unittest.TestCase):
    def test_top_level_help_lists_configure(self):
        buf = io.StringIO()
        with mock.patch("sys.stdout", buf):
            with self.assertRaises(SystemExit) as raised:
                cli.main(["--help"])
        self.assertEqual(raised.exception.code, 0)
        text = buf.getvalue()
        self.assertIn("configure", text)
        self.assertIn("Change the managed project configuration", text)

    def test_configure_help_desired_state_contract(self):
        buf = io.StringIO()
        with mock.patch("sys.stdout", buf):
            with self.assertRaises(SystemExit) as raised:
                cli.main(["configure", "--help"])
        self.assertEqual(raised.exception.code, 0)
        text = buf.getvalue()
        self.assertIn("--component", text)
        self.assertIn("--assistant", text)
        self.assertIn("--yes", text)
        self.assertIn("--dry-run", text)
        self.assertIn("exact desired", text.lower())
        self.assertIn(
            "With --yes or --dry-run, both component and assistant sets must",
            text,
        )


class ConfigureCliNoninteractiveTests(ConfigureCliHelpers):
    def test_yes_requires_both_dimensions(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            project.mkdir()
            self._install(project, ["core"], ["cursor"])
            for kwargs in (
                {"assume_yes": True},
                {"assume_yes": True, "components": ["core"]},
                {"assume_yes": True, "assistants": ["cursor"]},
                {"dry_run": True},
                {"dry_run": True, "components": ["core"]},
                {"dry_run": True, "assistants": ["cursor"]},
            ):
                result = self._run(project, **kwargs)
                self.assertEqual(result.exit_code, EXIT_SELECTION, kwargs)
                self.assertIn("both component and assistant", result.message)

    def test_yes_and_dry_run_together_allowed(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            project.mkdir()
            self._install(project, ["core"], ["cursor"])
            before = _fingerprint(project)
            result = self._run(
                project,
                components=["core"],
                assistants=["cursor", "copilot"],
                assume_yes=True,
                dry_run=True,
            )
            self.assertEqual(result.exit_code, EXIT_SUCCESS, result.message)
            self.assertIn("Dry run", result.message)
            self.assertEqual(_fingerprint(project), before)

    def test_noninteractive_complete_assistant_add(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            project.mkdir()
            self._install(project, ["core"], ["cursor"])
            result = self._run(
                project,
                components=["core"],
                assistants=["cursor", "copilot"],
                assume_yes=True,
            )
            self.assertEqual(result.exit_code, EXIT_SUCCESS, result.message)
            self.assertIn("EKP configuration updated", result.message)
            status = self._status(project)
            self.assertEqual(status.state, StatusState.HEALTHY)
            self.assertEqual(status.managed_total, 67)

    def test_assistant_remove(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            project.mkdir()
            self._install(
                project,
                ["core"],
                ["cursor", "copilot", "claude", "antigravity"],
            )
            self.assertEqual(self._status(project).managed_total, 78)
            result = self._run(
                project,
                components=["core"],
                assistants=["cursor"],
                assume_yes=True,
            )
            self.assertEqual(result.exit_code, EXIT_SUCCESS, result.message)
            self.assertEqual(self._status(project).managed_total, 65)

    def test_component_add_and_remove(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            project.mkdir()
            self._install(project, ["symfony"], ["cursor"])
            self.assertEqual(self._status(project).managed_total, 83)
            result = self._run(
                project,
                components=["symfony", "frontend"],
                assistants=["cursor"],
                assume_yes=True,
            )
            self.assertEqual(result.exit_code, EXIT_SUCCESS, result.message)
            self.assertEqual(self._status(project).managed_total, 110)
            result = self._run(
                project,
                components=["symfony"],
                assistants=["cursor"],
                assume_yes=True,
            )
            self.assertEqual(result.exit_code, EXIT_SUCCESS, result.message)
            self.assertEqual(self._status(project).managed_total, 83)

    def test_multi_dimension_and_all_four(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            project.mkdir()
            self._install(project, ["symfony"], ["cursor"])
            result = self._run(
                project,
                components=["symfony", "frontend"],
                assistants=["copilot", "claude"],
                assume_yes=True,
            )
            self.assertEqual(result.exit_code, EXIT_SUCCESS, result.message)
            status = self._status(project)
            self.assertEqual(status.managed_total, 16)
            self.assertEqual(status.adapters, ["claude", "copilot"])
            result = self._run(
                project,
                components=["symfony", "frontend"],
                assistants=["cursor", "copilot", "claude", "antigravity"],
                assume_yes=True,
            )
            self.assertEqual(result.exit_code, EXIT_SUCCESS, result.message)
            self.assertEqual(self._status(project).managed_total, 137)

    def test_duplicates_and_ordering(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            project.mkdir()
            self._install(project, ["core"], ["cursor"])
            r1 = self._run(
                project,
                components=["core", "core"],
                assistants=["cursor", "claude", "cursor"],
                assume_yes=True,
            )
            self.assertEqual(r1.exit_code, EXIT_SUCCESS, r1.message)
            hash1 = ProjectConfigStore(
                project, registry=self.registry
            ).load_file_snapshot().configuration_sha256
            adapters1 = ManifestStore(project).load().adapters
            # Reconfigure to cursor-only then back with reverse order.
            self._run(
                project,
                components=["core"],
                assistants=["cursor"],
                assume_yes=True,
            )
            r2 = self._run(
                project,
                components=["core"],
                assistants=["claude", "cursor"],
                assume_yes=True,
            )
            self.assertEqual(r2.exit_code, EXIT_SUCCESS, r2.message)
            hash2 = ProjectConfigStore(
                project, registry=self.registry
            ).load_file_snapshot().configuration_sha256
            adapters2 = ManifestStore(project).load().adapters
            self.assertEqual(hash1, hash2)
            self.assertEqual(adapters1, adapters2)
            self.assertEqual(adapters1, ["claude", "cursor"])

    def test_unknown_ids(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            project.mkdir()
            self._install(project, ["core"], ["cursor"])
            before = _fingerprint(project)
            bad_a = self._run(
                project,
                components=["core"],
                assistants=["unknown"],
                assume_yes=True,
            )
            self.assertEqual(bad_a.exit_code, EXIT_SELECTION)
            self.assertRegex(bad_a.message.lower(), r"assistant|supported")
            bad_c = self._run(
                project,
                components=["nope"],
                assistants=["cursor"],
                assume_yes=True,
            )
            self.assertEqual(bad_c.exit_code, EXIT_SELECTION)
            self.assertEqual(_fingerprint(project), before)


class ConfigureCliDryRunAndNoopTests(ConfigureCliHelpers):
    def test_noop_no_prompt_preserves_bytes(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            project.mkdir()
            self._install(project, ["core"], ["cursor"])
            before = _fingerprint(project)
            outputs = []
            result = self._run(
                project,
                components=["core"],
                assistants=["cursor"],
                assume_yes=False,
                answers=["should-not-be-read"],
                outputs=outputs,
            )
            self.assertEqual(result.exit_code, EXIT_SUCCESS, result.message)
            self.assertTrue(result.noop)
            self.assertIn("already matches", result.message)
            self.assertEqual(outputs, [])
            self.assertEqual(_fingerprint(project), before)

    def test_dry_run_renders_plan_zero_writes(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            project.mkdir()
            self._install(project, ["symfony"], ["cursor"])
            before = _fingerprint(project)
            result = self._run(
                project,
                components=["symfony", "frontend"],
                assistants=["cursor", "claude"],
                dry_run=True,
            )
            self.assertEqual(result.exit_code, EXIT_SUCCESS, result.message)
            self.assertIn("EKP configure plan", result.message)
            self.assertIn("Configuration action: UPDATE", result.message)
            self.assertIn("CREATE:", result.message)
            self.assertIn("DELETE:", result.message)
            self.assertIn("Dry run — no files changed.", result.message)
            self.assertEqual(_fingerprint(project), before)

    def test_dry_run_collision_nonzero(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            project.mkdir()
            self._install(project, ["core"], ["cursor"])
            (project / "CLAUDE.md").write_text("# foreign\n", encoding="utf-8")
            before = _fingerprint(project)
            result = self._run(
                project,
                components=["core"],
                assistants=["cursor", "claude"],
                dry_run=True,
            )
            self.assertEqual(result.exit_code, EXIT_CONFLICT, result.message)
            self.assertEqual(_fingerprint(project), before)


class ConfigureCliInteractiveTests(ConfigureCliHelpers):
    def test_interactive_blank_noop_zero_assembly(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            project.mkdir()
            self._install(project, ["symfony"], ["cursor"])
            before = _fingerprint(project)
            with mock.patch.object(
                AssemblyService,
                "assemble_composition",
                wraps=AssemblyService().assemble_composition,
            ) as assemble:
                result = self._run(
                    project,
                    answers=["", ""],
                )
            self.assertEqual(result.exit_code, EXIT_SUCCESS, result.message)
            self.assertTrue(result.noop)
            self.assertEqual(assemble.call_count, 0)
            self.assertEqual(_fingerprint(project), before)

    def test_interactive_both_explicit_confirm_yes(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            project.mkdir()
            self._install(project, ["core"], ["cursor"])
            outputs = []
            result = self._run(
                project,
                components=["core"],
                assistants=["cursor", "copilot"],
                answers=["y"],
                outputs=outputs,
            )
            self.assertEqual(result.exit_code, EXIT_SUCCESS, result.message)
            self.assertTrue(any("Continue?" in chunk for chunk in outputs))
            self.assertEqual(self._status(project).managed_total, 67)

    def test_interactive_confirm_blank_and_cancel(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            project.mkdir()
            self._install(project, ["core"], ["cursor"])
            ok = self._run(
                project,
                components=["core"],
                assistants=["cursor", "copilot"],
                answers=[""],
            )
            self.assertEqual(ok.exit_code, EXIT_SUCCESS, ok.message)
            self.assertEqual(self._status(project).managed_total, 67)

            project2 = Path(tmp) / "project2"
            project2.mkdir()
            self._install(project2, ["core"], ["cursor"])
            before = _fingerprint(project2)
            cancelled = self._run(
                project2,
                components=["core"],
                assistants=["cursor", "copilot"],
                answers=["n"],
            )
            self.assertEqual(cancelled.exit_code, EXIT_SUCCESS)
            self.assertIn("cancelled", cancelled.message.lower())
            self.assertEqual(_fingerprint(project2), before)

    def test_interactive_component_only_flags(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            project.mkdir()
            self._install(project, ["core"], ["cursor"])
            outputs = []
            result = self._run(
                project,
                components=["symfony"],
                answers=["cursor,claude", "y"],
                outputs=outputs,
            )
            self.assertEqual(result.exit_code, EXIT_SUCCESS, result.message)
            joined = "\n".join(outputs)
            self.assertIn("Select exact desired AI assistants", joined)
            self.assertNotIn("Select exact desired project components", joined)
            cfg = ProjectConfigStore(project, registry=self.registry).load()
            self.assertEqual(list(cfg.components), ["symfony"])
            self.assertEqual(list(cfg.assistants), ["claude", "cursor"])

    def test_interactive_assistant_only_flags(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            project.mkdir()
            self._install(project, ["core"], ["cursor"])
            outputs = []
            result = self._run(
                project,
                assistants=["cursor"],
                answers=["symfony", "y"],
                outputs=outputs,
            )
            self.assertEqual(result.exit_code, EXIT_SUCCESS, result.message)
            joined = "\n".join(outputs)
            self.assertIn("Select exact desired project components", joined)
            self.assertNotIn("Select exact desired AI assistants", joined)
            self.assertEqual(self._status(project).managed_total, 83)

    def test_interactive_change_one_dimension(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            project.mkdir()
            self._install(project, ["symfony"], ["cursor"])
            result = self._run(
                project,
                answers=["", "cursor,claude", "yes"],
            )
            self.assertEqual(result.exit_code, EXIT_SUCCESS, result.message)
            cfg = ProjectConfigStore(project, registry=self.registry).load()
            self.assertEqual(list(cfg.components), ["symfony"])
            self.assertEqual(list(cfg.assistants), ["claude", "cursor"])

    def test_empty_selection_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            project.mkdir()
            self._install(project, ["core"], ["cursor"])
            before = _fingerprint(project)
            bad_c = self._run(project, answers=["-", ""])
            self.assertEqual(bad_c.exit_code, EXIT_SELECTION)
            bad_a = self._run(project, answers=["", "clear"])
            self.assertEqual(bad_a.exit_code, EXIT_SELECTION)
            self.assertEqual(_fingerprint(project), before)

    def test_pre_prompt_eligibility_not_installed(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            project.mkdir()
            outputs = []
            result = self._run(project, answers=["core", "cursor"], outputs=outputs)
            self.assertEqual(result.exit_code, EXIT_SELECTION)
            self.assertIn("not installed", result.message.lower())
            self.assertEqual(outputs, [])


class ConfigureCliEligibilityTests(ConfigureCliHelpers):
    def test_legacy_version_incomplete_modified_drift(self):
        with tempfile.TemporaryDirectory() as tmp:
            # Legacy
            legacy = Path(tmp) / "legacy"
            legacy.mkdir()
            outcome = InstallService().install(
                InstallRequest(
                    path=str(legacy), profile="cursor-core", assume_yes=True
                )
            )
            self.assertEqual(outcome.exit_code, EXIT_SUCCESS, outcome.message)
            before = _fingerprint(legacy)
            result = self._run(
                legacy,
                components=["core"],
                assistants=["cursor"],
                assume_yes=True,
            )
            self.assertEqual(result.exit_code, EXIT_SELECTION)
            self.assertIn("legacy-profile", result.message)
            self.assertEqual(_fingerprint(legacy), before)

            # Version mismatch
            project = Path(tmp) / "mismatch"
            project.mkdir()
            self._install(project, ["core"], ["cursor"])
            store = ManifestStore(project)
            snap = store.load_with_fingerprint()
            manifest = snap.manifest
            mutated = type(manifest)(
                schema_version=manifest.schema_version,
                ekp_version="0.19.0",
                profile=manifest.profile,
                adapters=list(manifest.adapters),
                installed_at=manifest.installed_at,
                install_root=manifest.install_root,
                managed_files=list(manifest.managed_files),
                created_directories=list(manifest.created_directories),
                mode=manifest.mode,
                configuration_sha256=manifest.configuration_sha256,
            )
            store.replace(mutated, expected_sha256=snap.sha256)
            before = _fingerprint(project)
            result = self._run(
                project,
                components=["core"],
                assistants=["cursor", "copilot"],
                assume_yes=True,
            )
            self.assertEqual(result.exit_code, EXIT_SELECTION)
            self.assertIn("ekp update", result.message.lower())
            self.assertEqual(_fingerprint(project), before)

            # Incomplete
            incomplete = Path(tmp) / "incomplete"
            incomplete.mkdir()
            self._install(incomplete, ["core"], ["cursor"])
            managed = ManifestStore(incomplete).load().managed_files[0]
            target = incomplete / Path(managed.relative_path.replace("/", os.sep))
            target.unlink()
            before = _fingerprint(incomplete)
            result = self._run(
                incomplete,
                components=["core"],
                assistants=["cursor", "copilot"],
                assume_yes=True,
            )
            self.assertEqual(result.exit_code, EXIT_SELECTION)
            self.assertIn("incomplete", result.message.lower())
            self.assertEqual(_fingerprint(incomplete), before)

            # Modified
            modified = Path(tmp) / "modified"
            modified.mkdir()
            self._install(modified, ["core"], ["cursor"])
            managed = ManifestStore(modified).load().managed_files[0]
            target = modified / Path(managed.relative_path.replace("/", os.sep))
            target.write_text(
                target.read_text(encoding="utf-8") + "\n# edited\n", encoding="utf-8"
            )
            before = _fingerprint(modified)
            result = self._run(
                modified,
                components=["core"],
                assistants=["cursor", "copilot"],
                assume_yes=True,
            )
            self.assertEqual(result.exit_code, EXIT_SELECTION)
            self.assertIn("modified", result.message.lower())
            self.assertEqual(_fingerprint(modified), before)

            # Drift
            drift = Path(tmp) / "drift"
            drift.mkdir()
            self._install(drift, ["core"], ["cursor"])
            (drift / ".ekp" / "project.yaml").write_text(
                "schema_version: 1\ncomponents:\n  - symfony\nassistants:\n  - cursor\n",
                encoding="utf-8",
            )
            before = _fingerprint(drift)
            result = self._run(
                drift,
                components=["core"],
                assistants=["cursor"],
                assume_yes=True,
            )
            self.assertEqual(result.exit_code, EXIT_SELECTION)
            self.assertIn("outside EKP", result.message)
            self.assertEqual(_fingerprint(drift), before)

    def test_v019_mismatch_then_update_then_configure(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            project.mkdir()
            self._install(project, ["core"], ["cursor"])
            store = ManifestStore(project)
            snap = store.load_with_fingerprint()
            manifest = snap.manifest
            mutated = type(manifest)(
                schema_version=manifest.schema_version,
                ekp_version="0.19.0",
                profile=manifest.profile,
                adapters=list(manifest.adapters),
                installed_at=manifest.installed_at,
                install_root=manifest.install_root,
                managed_files=list(manifest.managed_files),
                created_directories=list(manifest.created_directories),
                mode=manifest.mode,
                configuration_sha256=manifest.configuration_sha256,
            )
            store.replace(mutated, expected_sha256=snap.sha256)
            refused = self._run(
                project,
                components=["core"],
                assistants=["cursor", "copilot"],
                assume_yes=True,
            )
            self.assertEqual(refused.exit_code, EXIT_SELECTION)
            updated = UpdateService().update(
                UpdateRequest(path=str(project), assume_yes=True)
            )
            self.assertEqual(updated.exit_code, EXIT_SUCCESS, updated.message)
            self.assertEqual(self._status(project).state, StatusState.HEALTHY)
            ok = self._run(
                project,
                components=["core"],
                assistants=["cursor", "copilot"],
                assume_yes=True,
            )
            self.assertEqual(ok.exit_code, EXIT_SUCCESS, ok.message)
            self.assertEqual(self._status(project).managed_total, 67)

    def test_modified_delete_and_collision(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            project.mkdir()
            self._install(project, ["core"], ["cursor", "claude"])
            claude = project / "CLAUDE.md"
            claude.write_text(
                claude.read_text(encoding="utf-8") + "\n# user\n", encoding="utf-8"
            )
            before = _fingerprint(project)
            result = self._run(
                project,
                components=["core"],
                assistants=["cursor"],
                assume_yes=True,
            )
            self.assertEqual(result.exit_code, EXIT_SELECTION)
            self.assertEqual(_fingerprint(project), before)

            conflict = Path(tmp) / "conflict"
            conflict.mkdir()
            self._install(conflict, ["core"], ["cursor"])
            (conflict / "CLAUDE.md").write_text("# foreign\n", encoding="utf-8")
            before = _fingerprint(conflict)
            result = self._run(
                conflict,
                components=["core"],
                assistants=["cursor", "claude"],
                assume_yes=True,
            )
            self.assertEqual(result.exit_code, EXIT_CONFLICT)
            self.assertEqual(_fingerprint(conflict), before)


class ConfigureCliRaceAndAssemblyTests(ConfigureCliHelpers):
    def test_one_assembly_on_real_change(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            project.mkdir()
            self._install(project, ["core"], ["cursor"])
            with mock.patch(
                "ekp.lifecycle.configure.AssemblyService.assemble_composition",
                wraps=AssemblyService().assemble_composition,
            ) as assemble:
                result = self._run(
                    project,
                    components=["core"],
                    assistants=["cursor", "copilot"],
                    assume_yes=True,
                )
            self.assertEqual(result.exit_code, EXIT_SUCCESS, result.message)
            self.assertEqual(assemble.call_count, 1)

    def test_dry_run_one_assembly_then_cleanup(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            project.mkdir()
            self._install(project, ["core"], ["cursor"])
            with mock.patch(
                "ekp.lifecycle.configure.AssemblyService.assemble_composition",
                wraps=AssemblyService().assemble_composition,
            ) as assemble:
                result = self._run(
                    project,
                    components=["core"],
                    assistants=["cursor", "copilot"],
                    dry_run=True,
                )
            self.assertEqual(result.exit_code, EXIT_SUCCESS, result.message)
            self.assertEqual(assemble.call_count, 1)

    def test_config_and_manifest_race_after_render(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            project.mkdir()
            self._install(project, ["core"], ["cursor"])
            yaml_path = project / ".ekp" / "project.yaml"

            def mutate_then_yes(_prompt=""):
                yaml_path.write_bytes(yaml_path.read_bytes() + b"\n")
                return "y"

            before = _fingerprint(project)
            # Fingerprint before mutation inside confirm — capture after refuse.
            result = run_configure_cli(
                path=str(project),
                components=["core"],
                assistants=["cursor", "copilot"],
                assume_yes=False,
                dry_run=False,
                input_fn=mutate_then_yes,
                output_fn=lambda _s: None,
                service=self._service(),
            )
            self.assertNotEqual(result.exit_code, EXIT_SUCCESS)
            # Bytes include the race mutation; managed inventory otherwise unchanged.
            self.assertTrue(yaml_path.read_bytes().endswith(b"\n"))
            self.assertEqual(self._status(project).managed_total, 65)

            project2 = Path(tmp) / "manifest-race"
            project2.mkdir()
            self._install(project2, ["core"], ["cursor"])

            def mutate_manifest_then_yes(_prompt=""):
                store = ManifestStore(project2)
                snap = store.load_with_fingerprint()
                manifest = snap.manifest
                # Touch installed_at to change manifest bytes while keeping ownership.
                mutated = type(manifest)(
                    schema_version=manifest.schema_version,
                    ekp_version=manifest.ekp_version,
                    profile=manifest.profile,
                    adapters=list(manifest.adapters),
                    installed_at=manifest.installed_at + "Z",
                    install_root=manifest.install_root,
                    managed_files=list(manifest.managed_files),
                    created_directories=list(manifest.created_directories),
                    mode=manifest.mode,
                    configuration_sha256=manifest.configuration_sha256,
                )
                store.replace(mutated, expected_sha256=snap.sha256)
                return "yes"

            result = run_configure_cli(
                path=str(project2),
                components=["core"],
                assistants=["cursor", "copilot"],
                assume_yes=False,
                dry_run=False,
                input_fn=mutate_manifest_then_yes,
                output_fn=lambda _s: None,
                service=self._service(),
            )
            self.assertNotEqual(result.exit_code, EXIT_SUCCESS)
            self.assertEqual(self._status(project2).managed_total, 65)

    def test_cancel_cleans_prepared_temps(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            project.mkdir()
            self._install(project, ["core"], ["cursor"])
            closed = {"value": False}
            real_prepare = ConfigureService.prepare

            def prepare_wrapper(self_svc, request):
                result = real_prepare(self_svc, request)
                if result.prepared is not None:
                    real_close = result.prepared.close

                    def close_wrapper():
                        closed["value"] = True
                        return real_close()

                    result.prepared.close = close_wrapper
                return result

            with mock.patch.object(ConfigureService, "prepare", prepare_wrapper):
                result = self._run(
                    project,
                    components=["core"],
                    assistants=["cursor", "copilot"],
                    answers=["n"],
                )
            self.assertEqual(result.exit_code, EXIT_SUCCESS)
            self.assertTrue(closed["value"])


class ConfigureCliMainDispatchTests(ConfigureCliHelpers):
    def test_cli_main_configure_dispatch(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            project.mkdir()
            self._install(project, ["core"], ["cursor"])
            code = cli.main(
                [
                    "configure",
                    "--path",
                    str(project),
                    "--component",
                    "core",
                    "--assistant",
                    "cursor",
                    "--assistant",
                    "copilot",
                    "--yes",
                ]
            )
            self.assertEqual(code, EXIT_SUCCESS)
            self.assertEqual(self._status(project).managed_total, 67)


if __name__ == "__main__":
    unittest.main()
