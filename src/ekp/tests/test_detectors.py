"""Technology detector tests."""

import json
import tempfile
import unittest
from pathlib import Path

from ekp.detection.technology.devops import DevOpsDetector
from ekp.detection.technology.flutter import FlutterDetector
from ekp.detection.technology.frontend import FrontendDetector
from ekp.detection.technology.nativescript import NativeScriptDetector
from ekp.detection.technology.php import PHPDetector
from ekp.detection.technology.symfony import SymfonyDetector
from ekp.detection.technology.typescript import TypeScriptDetector
from ekp.tests.fixtures import (
    devops_fixture,
    flutter_fixture,
    frontend_fixture,
    nativescript_fixture,
    php_fixture,
    symfony_fixture,
    typescript_fixture,
)


class DetectorTests(unittest.TestCase):
    def test_symfony_detector(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            symfony_fixture(root)
            result = SymfonyDetector().detect(root, [])
            self.assertIsNotNone(result)
            self.assertEqual(result.technology, "symfony")
            self.assertEqual(result.confidence, "high")

    def test_php_detector(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            php_fixture(root)
            result = PHPDetector().detect(root, [])
            self.assertIsNotNone(result)
            self.assertEqual(result.technology, "php")

    def test_typescript_detector(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            typescript_fixture(root)
            result = TypeScriptDetector().detect(root, [])
            self.assertIsNotNone(result)
            self.assertEqual(result.technology, "typescript")

    def test_frontend_detector(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            frontend_fixture(root)
            result = FrontendDetector().detect(root, [])
            self.assertIsNotNone(result)
            self.assertEqual(result.technology, "frontend")

    def test_nativescript_detector(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            nativescript_fixture(root)
            result = NativeScriptDetector().detect(root, [])
            self.assertIsNotNone(result)
            self.assertEqual(result.technology, "nativescript")
            self.assertEqual(result.confidence, "high")

    def test_flutter_detector(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            flutter_fixture(root)
            result = FlutterDetector().detect(root, [])
            self.assertIsNotNone(result)
            self.assertEqual(result.technology, "flutter")
            self.assertEqual(result.confidence, "high")

    def test_devops_detector(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            devops_fixture(root)
            result = DevOpsDetector().detect(root, [])
            self.assertIsNotNone(result)
            self.assertEqual(result.technology, "devops")

    def test_malformed_composer_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "composer.json").write_text("{invalid", encoding="utf-8")
            diagnostics = []
            result = PHPDetector().detect(root, diagnostics)
            self.assertIsNone(result)
            self.assertTrue(any("composer.json" in item for item in diagnostics))

    def test_malformed_package_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "package.json").write_text("{invalid", encoding="utf-8")
            diagnostics = []
            result = TypeScriptDetector().detect(root, diagnostics)
            self.assertIsNone(result)
            self.assertTrue(any("package.json" in item for item in diagnostics))

    def test_malformed_pubspec_yaml(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "pubspec.yaml").write_text("name: [\n", encoding="utf-8")
            diagnostics = []
            result = FlutterDetector().detect(root, diagnostics)
            self.assertIsNone(result)

    def test_ignored_vendor_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_composer = root / "composer.json"
            write_composer.write_text(json.dumps({"require": {"php": "^8.2"}}), encoding="utf-8")
            (root / "vendor" / "autoload.php").parent.mkdir(parents=True, exist_ok=True)
            (root / "vendor" / "autoload.php").write_text("<?php\n", encoding="utf-8")
            result = PHPDetector().detect(root, [])
            self.assertIsNotNone(result)
            self.assertFalse(any("vendor" in item for item in result.evidence))

    def test_ignored_node_modules(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            frontend_fixture(root)
            (root / "node_modules" / "react" / "index.js").parent.mkdir(parents=True, exist_ok=True)
            (root / "node_modules" / "react" / "index.js").write_text("", encoding="utf-8")
            result = FrontendDetector().detect(root, [])
            self.assertIsNotNone(result)

    def test_empty_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            diagnostics = []
            self.assertIsNone(PHPDetector().detect(root, diagnostics))
            self.assertIsNone(SymfonyDetector().detect(root, diagnostics))
            self.assertIsNone(FlutterDetector().detect(root, diagnostics))
