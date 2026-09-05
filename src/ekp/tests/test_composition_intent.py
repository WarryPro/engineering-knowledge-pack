"""Composition-aware detection and install intent tests (AW-D)."""

from __future__ import annotations

import hashlib
import io
import json
import tempfile
import unittest
from pathlib import Path

from ekp.assembly import AssemblyService, CompositionAssemblyRequest
from ekp.composition import Component, ComponentRegistry
from ekp.config import ProjectConfig, configuration_sha256
from ekp.detection.models import DetectionReport, DetectionResult
from ekp.detection.render import render_human, report_to_dict
from ekp.detection.service import DetectionService
from ekp.install.errors import InstallSelectionError
from ekp.install.intent import (
    MODE_COMPOSITION,
    MODE_LEGACY_PROFILE,
    build_composition_intent,
    intent_to_project_config,
    select_install_intent,
)
from ekp.paths import get_ekp_root
from ekp.resolution.composition_proposal import resolve_detected_components
from ekp.resolution.resolver import apply_resolution, resolve_profile
from ekp.tests.fixtures import (
    devops_fixture,
    flutter_fixture,
    frontend_fixture,
    nativescript_fixture,
    symfony_fixture,
)


def _file_fingerprint(root: Path):
    items = {}
    for path in sorted(root.rglob("*")):
        if path.is_file():
            rel = path.relative_to(root).as_posix()
            items[rel] = hashlib.sha256(path.read_bytes()).hexdigest()
    return items


class CompositionProposalTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.registry = ComponentRegistry.load()

    def test_symfony_php_reduces(self):
        composition, diags = resolve_detected_components(
            [
                DetectionResult("symfony", "high", ["symfony.lock"]),
                DetectionResult("php", "high", ["composer.json"]),
            ],
            self.registry,
        )
        self.assertEqual(diags, [])
        self.assertEqual(composition.requested_components, ("symfony",))
        self.assertEqual(
            composition.resolved_components, ("core", "php", "symfony")
        )

    def test_frontend_typescript_reduces(self):
        composition, _ = resolve_detected_components(
            [
                DetectionResult("frontend", "high", ["package.json"]),
                DetectionResult("typescript", "high", ["tsconfig.json"]),
            ],
            self.registry,
        )
        self.assertEqual(composition.requested_components, ("frontend",))
        self.assertEqual(
            composition.resolved_components,
            ("core", "typescript", "frontend"),
        )

    def test_nativescript_typescript(self):
        composition, _ = resolve_detected_components(
            [
                DetectionResult("nativescript", "high", ["nativescript.config.ts"]),
                DetectionResult("typescript", "high", ["tsconfig.json"]),
            ],
            self.registry,
        )
        self.assertEqual(composition.requested_components, ("nativescript",))
        self.assertEqual(
            composition.resolved_components,
            ("core", "typescript", "nativescript"),
        )

    def test_symfony_frontend_valid_composition(self):
        composition, _ = resolve_detected_components(
            [
                DetectionResult("symfony", "high", ["a"]),
                DetectionResult("php", "high", ["b"]),
                DetectionResult("frontend", "high", ["c"]),
                DetectionResult("typescript", "high", ["d"]),
            ],
            self.registry,
        )
        self.assertEqual(
            composition.requested_components, ("frontend", "symfony")
        )
        self.assertEqual(
            composition.resolved_components,
            ("core", "php", "symfony", "typescript", "frontend"),
        )

    def test_devops_first_class_with_symfony(self):
        composition, _ = resolve_detected_components(
            [
                DetectionResult("symfony", "high", ["a"]),
                DetectionResult("devops", "medium", ["Dockerfile"]),
            ],
            self.registry,
        )
        self.assertEqual(
            composition.requested_components, ("devops", "symfony")
        )
        self.assertEqual(
            composition.resolved_components,
            ("core", "devops", "php", "symfony"),
        )

    def test_symfony_frontend_devops(self):
        composition, _ = resolve_detected_components(
            [
                DetectionResult("symfony", "high", ["a"]),
                DetectionResult("frontend", "high", ["b"]),
                DetectionResult("devops", "medium", ["c"]),
            ],
            self.registry,
        )
        self.assertEqual(
            composition.requested_components,
            ("devops", "frontend", "symfony"),
        )
        self.assertEqual(
            composition.resolved_components,
            ("core", "devops", "php", "symfony", "typescript", "frontend"),
        )

    def test_flutter_symfony_valid(self):
        composition, _ = resolve_detected_components(
            [
                DetectionResult("flutter", "high", ["pubspec.yaml"]),
                DetectionResult("symfony", "high", ["symfony.lock"]),
            ],
            self.registry,
        )
        self.assertEqual(
            composition.requested_components, ("flutter", "symfony")
        )
        self.assertIn("flutter", composition.resolved_components)
        self.assertIn("symfony", composition.resolved_components)
        self.assertIn("core", composition.resolved_components)

    def test_low_confidence_excluded(self):
        composition, _ = resolve_detected_components(
            [DetectionResult("symfony", "low", ["maybe"])],
            self.registry,
        )
        self.assertIsNone(composition)

    def test_unknown_technology_diagnostic(self):
        composition, diags = resolve_detected_components(
            [
                DetectionResult("symfony", "high", ["a"]),
                DetectionResult("unknown-component-id", "high", ["x"]),
            ],
            self.registry,
        )
        self.assertEqual(composition.requested_components, ("symfony",))
        self.assertTrue(any("unknown technology" in item for item in diags))

    def test_empty_detections(self):
        composition, diags = resolve_detected_components([], self.registry)
        self.assertIsNone(composition)
        self.assertEqual(diags, [])


class DetectionCompositionIntegrationTests(unittest.TestCase):
    def test_symfony_fixture_composition(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            symfony_fixture(root)
            report = DetectionService().detect(str(root))
            self.assertEqual(report.proposed_components, ["symfony"])
            self.assertEqual(
                report.resolved_components, ["core", "php", "symfony"]
            )
            self.assertEqual(report.recommended_profile, "cursor-symfony")
            self.assertFalse(report.ambiguous)

    def test_frontend_fixture_composition(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            frontend_fixture(root)
            report = DetectionService().detect(str(root))
            self.assertEqual(report.proposed_components, ["frontend"])
            self.assertEqual(
                report.resolved_components,
                ["core", "typescript", "frontend"],
            )
            self.assertEqual(report.recommended_profile, "cursor-frontend")

    def test_nativescript_fixture_composition(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            nativescript_fixture(root)
            report = DetectionService().detect(str(root))
            self.assertEqual(report.proposed_components, ["nativescript"])
            self.assertEqual(
                report.resolved_components,
                ["core", "typescript", "nativescript"],
            )

    def test_symfony_frontend_not_composition_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            symfony_fixture(root)
            frontend_fixture(root)
            report = DetectionService().detect(str(root))
            self.assertEqual(
                report.proposed_components, ["frontend", "symfony"]
            )
            self.assertEqual(
                report.resolved_components,
                ["core", "php", "symfony", "typescript", "frontend"],
            )
            # Legacy single-profile path remains ambiguous.
            self.assertTrue(report.ambiguous)
            self.assertIsNone(report.recommended_profile)
            human = render_human(report)
            self.assertIn("Project composition:", human)
            self.assertIn("frontend", human)
            self.assertIn("symfony", human)
            self.assertIn("ambiguous", human)
            payload = report_to_dict(report)
            self.assertEqual(
                payload["proposed_components"], ["frontend", "symfony"]
            )
            self.assertEqual(
                payload["resolved_components"],
                ["core", "php", "symfony", "typescript", "frontend"],
            )

    def test_symfony_devops_composition_first_class(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            symfony_fixture(root)
            devops_fixture(root)
            report = DetectionService().detect(str(root))
            self.assertEqual(
                report.proposed_components, ["devops", "symfony"]
            )
            self.assertEqual(
                report.resolved_components,
                ["core", "devops", "php", "symfony"],
            )
            # Legacy still treats devops as additional concern with singleton profile.
            self.assertEqual(report.recommended_profile, "cursor-symfony")
            self.assertIn("devops", report.additional_concerns)

    def test_symfony_frontend_devops_and_assembly_freeze(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            symfony_fixture(root)
            frontend_fixture(root)
            devops_fixture(root)
            report = DetectionService().detect(str(root))
            self.assertEqual(
                report.proposed_components,
                ["devops", "frontend", "symfony"],
            )
            self.assertEqual(
                report.resolved_components,
                ["core", "devops", "php", "symfony", "typescript", "frontend"],
            )
            assembled = AssemblyService().assemble_composition(
                CompositionAssemblyRequest(
                    components=list(report.proposed_components),
                    outputs=["cursor"],
                    verify=True,
                    resource_root=get_ekp_root(),
                    workspace_dir=Path(tmp) / "workspace",
                    output_root=Path(tmp) / "output",
                )
            )
            self.assertEqual(assembled.rules_count, 119)

    def test_flutter_symfony_fixture(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            flutter_fixture(root)
            symfony_fixture(root)
            report = DetectionService().detect(str(root))
            self.assertEqual(
                report.proposed_components, ["flutter", "symfony"]
            )
            self.assertTrue(report.ambiguous)
            self.assertIsNone(report.recommended_profile)

    def test_empty_detection_composition_fields(self):
        with tempfile.TemporaryDirectory() as tmp:
            report = DetectionService().detect(str(Path(tmp)))
            self.assertEqual(report.proposed_components, [])
            self.assertEqual(report.resolved_components, [])

    def test_json_determinism(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            symfony_fixture(root)
            frontend_fixture(root)
            a = report_to_dict(DetectionService().detect(str(root)))
            b = report_to_dict(DetectionService().detect(str(root)))
            self.assertEqual(a["proposed_components"], b["proposed_components"])
            self.assertEqual(a["resolved_components"], b["resolved_components"])
            self.assertEqual(
                json.dumps(a, sort_keys=True),
                json.dumps(b, sort_keys=True),
            )


class InstallIntentTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.registry = ComponentRegistry.load()
        cls.root = get_ekp_root()

    def test_explicit_profile_legacy_intent(self):
        report = DetectionReport(path=".")
        intent = select_install_intent(
            report,
            explicit_profile="cursor-symfony",
            registry=self.registry,
            resource_root=self.root,
        )
        self.assertEqual(intent.mode, MODE_LEGACY_PROFILE)
        self.assertEqual(intent.profile, "cursor-symfony")
        self.assertIsNone(intent.composition)

    def test_explicit_components_composition_intent(self):
        report = DetectionReport(path=".")
        intent = select_install_intent(
            report,
            explicit_components=["symfony", "frontend"],
            registry=self.registry,
        )
        self.assertEqual(intent.mode, MODE_COMPOSITION)
        self.assertEqual(intent.components, ("frontend", "symfony"))
        self.assertEqual(
            intent.composition.resolved_components,
            ("core", "php", "symfony", "typescript", "frontend"),
        )
        self.assertEqual(intent.assistants, ("cursor",))
        self.assertIsNotNone(intent.configuration_sha256)

    def test_profile_plus_components_error(self):
        with self.assertRaises(InstallSelectionError):
            select_install_intent(
                DetectionReport(path="."),
                explicit_profile="cursor-symfony",
                explicit_components=["frontend"],
                registry=self.registry,
            )

    def test_detected_symfony_composition_intent(self):
        with tempfile.TemporaryDirectory() as tmp:
            symfony_fixture(Path(tmp))
            report = DetectionService().detect(str(Path(tmp)))
            intent = select_install_intent(report, registry=self.registry)
            self.assertEqual(intent.mode, MODE_COMPOSITION)
            self.assertEqual(intent.components, ("symfony",))

    def test_symfony_frontend_composition_intent(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            symfony_fixture(root)
            frontend_fixture(root)
            report = DetectionService().detect(str(root))
            intent = select_install_intent(
                report, assume_yes=True, registry=self.registry
            )
            self.assertEqual(intent.mode, MODE_COMPOSITION)
            self.assertEqual(intent.components, ("frontend", "symfony"))

    def test_empty_yes_fails(self):
        report = DetectionReport(path=".")
        with self.assertRaises(InstallSelectionError):
            select_install_intent(
                report, assume_yes=True, registry=self.registry
            )

    def test_low_only_yes_fails(self):
        report = apply_resolution(
            DetectionReport(
                path=".",
                technologies=[DetectionResult("symfony", "low", ["weak"])],
            ),
            registry=self.registry,
        )
        self.assertEqual(report.proposed_components, [])
        with self.assertRaises(InstallSelectionError):
            select_install_intent(
                report, assume_yes=True, registry=self.registry
            )

    def test_empty_interactive_multi_select(self):
        report = DetectionReport(path=".")
        outputs = []
        selectable_ids = [
            c.id for c in self.registry.list_components() if c.selectable
        ]
        # Choose Symfony + Frontend by index in lexical selectable list.
        symfony_idx = selectable_ids.index("symfony") + 1
        frontend_idx = selectable_ids.index("frontend") + 1
        intent = select_install_intent(
            report,
            assume_yes=False,
            registry=self.registry,
            input_fn=lambda _prompt: "{},{}".format(symfony_idx, frontend_idx),
            output_fn=outputs.append,
        )
        self.assertEqual(intent.mode, MODE_COMPOSITION)
        self.assertEqual(intent.components, ("frontend", "symfony"))
        joined = "\n".join(outputs)
        self.assertIn("Select project components", joined)
        self.assertIn("Core engineering knowledge only", joined)

    def test_unknown_explicit_component(self):
        with self.assertRaises(InstallSelectionError):
            build_composition_intent(["nope"], self.registry)

    def test_non_selectable_explicit_component(self):
        registry = ComponentRegistry(
            {
                "core": Component(
                    id="core",
                    layer="L0",
                    requires=(),
                    knowledge=(),
                    selectable=True,
                ),
                "hidden": Component(
                    id="hidden",
                    layer="L1",
                    requires=("core",),
                    knowledge=(),
                    selectable=False,
                ),
            },
            Path(tempfile.gettempdir()),
        )
        with self.assertRaises(InstallSelectionError):
            build_composition_intent(["hidden"], registry)

    def test_project_config_draft_and_hash(self):
        intent = build_composition_intent(
            ["symfony", "frontend"], self.registry
        )
        config = intent_to_project_config(intent)
        self.assertEqual(config.schema_version, 1)
        self.assertEqual(config.components, ("frontend", "symfony"))
        self.assertEqual(config.assistants, ("cursor",))
        expected = configuration_sha256(
            ProjectConfig(
                schema_version=1,
                components=("frontend", "symfony"),
                assistants=("cursor",),
            ),
            self.registry,
        )
        self.assertEqual(intent.configuration_sha256, expected)

    def test_composition_selection_zero_writes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            symfony_fixture(root)
            frontend_fixture(root)
            before = _file_fingerprint(root)
            report = DetectionService().detect(str(root))
            intent = select_install_intent(
                report, assume_yes=True, registry=self.registry
            )
            self.assertEqual(intent.mode, MODE_COMPOSITION)
            self.assertEqual(_file_fingerprint(root), before)
            self.assertFalse((root / ".ekp" / "project.yaml").exists())
            self.assertFalse((root / ".ekp" / "install.json").exists())
            self.assertFalse((root / ".cursor").exists())


class LegacyResolverShimTests(unittest.TestCase):
    """Legacy profile tables remain for install compatibility only."""

    def test_multi_stack_still_ambiguous_for_legacy(self):
        profile, candidates, _, ambiguous, reason = resolve_profile(
            [
                DetectionResult("symfony", "high", ["a"]),
                DetectionResult("frontend", "high", ["b"]),
            ]
        )
        self.assertIsNone(profile)
        self.assertTrue(ambiguous)
        self.assertEqual(reason, "multiple independent primary stacks")
        self.assertIn("cursor-symfony", candidates)


if __name__ == "__main__":
    unittest.main()
