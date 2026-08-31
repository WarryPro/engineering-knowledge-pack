"""Profile resolution tests."""

import tempfile
import unittest
from pathlib import Path

from ekp.detection.service import DetectionService
from ekp.detection.models import DetectionResult
from ekp.resolution.resolver import resolve_profile
from ekp.tests.fixtures import (
    devops_fixture,
    flutter_fixture,
    frontend_fixture,
    nativescript_fixture,
    php_fixture,
    symfony_fixture,
    typescript_fixture,
)


class ResolverTests(unittest.TestCase):
    def test_php_recommends_cursor_php(self):
        profile, candidates, additional, ambiguous, _ = resolve_profile(
            [DetectionResult("php", "high", ["composer.json"])]
        )
        self.assertEqual(profile, "cursor-php")
        self.assertFalse(ambiguous)

    def test_symfony_subsumes_php(self):
        profile, _, _, ambiguous, _ = resolve_profile(
            [
                DetectionResult("symfony", "high", ["symfony.lock"]),
                DetectionResult("php", "high", ["composer.json"]),
            ]
        )
        self.assertEqual(profile, "cursor-symfony")
        self.assertFalse(ambiguous)

    def test_typescript_recommends_cursor_typescript(self):
        profile, _, _, ambiguous, _ = resolve_profile(
            [DetectionResult("typescript", "high", ["tsconfig.json"])]
        )
        self.assertEqual(profile, "cursor-typescript")
        self.assertFalse(ambiguous)

    def test_frontend_subsumes_typescript(self):
        profile, _, _, ambiguous, _ = resolve_profile(
            [
                DetectionResult("frontend", "high", ["package.json: react"]),
                DetectionResult("typescript", "high", ["tsconfig.json"]),
            ]
        )
        self.assertEqual(profile, "cursor-frontend")
        self.assertFalse(ambiguous)

    def test_nativescript_subsumes_typescript(self):
        profile, _, _, ambiguous, _ = resolve_profile(
            [
                DetectionResult("nativescript", "high", ["nativescript.config.ts"]),
                DetectionResult("typescript", "high", ["tsconfig.json"]),
            ]
        )
        self.assertEqual(profile, "cursor-nativescript")
        self.assertFalse(ambiguous)

    def test_flutter_recommends_cursor_flutter(self):
        profile, _, _, ambiguous, _ = resolve_profile(
            [DetectionResult("flutter", "high", ["pubspec.yaml"])]
        )
        self.assertEqual(profile, "cursor-flutter")
        self.assertFalse(ambiguous)

    def test_devops_only(self):
        profile, _, _, ambiguous, _ = resolve_profile(
            [DetectionResult("devops", "medium", ["Dockerfile"])]
        )
        self.assertEqual(profile, "cursor-devops")
        self.assertFalse(ambiguous)

    def test_symfony_with_devops_additional_concern(self):
        profile, _, additional, ambiguous, _ = resolve_profile(
            [
                DetectionResult("symfony", "high", ["symfony.lock"]),
                DetectionResult("php", "high", ["composer.json"]),
                DetectionResult("devops", "medium", ["Dockerfile"]),
            ]
        )
        self.assertEqual(profile, "cursor-symfony")
        self.assertIn("devops", additional)
        self.assertFalse(ambiguous)

    def test_symfony_and_frontend_ambiguous(self):
        profile, candidates, _, ambiguous, reason = resolve_profile(
            [
                DetectionResult("symfony", "high", ["symfony.lock"]),
                DetectionResult("frontend", "high", ["package.json: react"]),
            ]
        )
        self.assertIsNone(profile)
        self.assertTrue(ambiguous)
        self.assertIn("cursor-symfony", candidates)
        self.assertIn("cursor-frontend", candidates)
        self.assertEqual(reason, "multiple independent primary stacks")

    def test_empty_no_recommendation(self):
        profile, candidates, _, ambiguous, _ = resolve_profile([])
        self.assertIsNone(profile)
        self.assertEqual(candidates, [])
        self.assertFalse(ambiguous)

    def test_integration_symfony_fixture(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            symfony_fixture(root)
            devops_fixture(root)
            report = DetectionService().detect(str(root))
            self.assertEqual(report.recommended_profile, "cursor-symfony")
            self.assertIn("devops", report.additional_concerns)

    def test_integration_empty_fixture(self):
        with tempfile.TemporaryDirectory() as tmp:
            report = DetectionService().detect(str(Path(tmp)))
            self.assertIsNone(report.recommended_profile)
            self.assertEqual(report.technologies, [])
