"""Shared fixture builders for detection tests."""

from __future__ import annotations

import json
from pathlib import Path


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def symfony_fixture(root: Path) -> None:
    write_json(
        root / "composer.json",
        {
            "require": {
                "php": "^8.2",
                "symfony/framework-bundle": "^7.0",
            }
        },
    )
    (root / "symfony.lock").write_text("{}\n", encoding="utf-8")
    (root / "config").mkdir(exist_ok=True)
    (root / "config" / "bundles.php").write_text("<?php\n", encoding="utf-8")
    (root / "bin").mkdir(exist_ok=True)
    (root / "bin" / "console").write_text("#!/usr/bin/env php\n", encoding="utf-8")


def flutter_fixture(root: Path) -> None:
    (root / "lib").mkdir(exist_ok=True)
    (root / "lib" / "main.dart").write_text("void main() {}\n", encoding="utf-8")
    (root / "pubspec.yaml").write_text(
        "name: demo\nenvironment:\n  sdk: '>=3.0.0 <4.0.0'\nflutter:\n  sdk: flutter\n",
        encoding="utf-8",
    )


def frontend_fixture(root: Path) -> None:
    write_json(
        root / "package.json",
        {
            "dependencies": {
                "react": "^18.0.0",
                "typescript": "^5.0.0",
            }
        },
    )
    (root / "tsconfig.json").write_text("{}", encoding="utf-8")
    (root / "src" / "components").mkdir(parents=True, exist_ok=True)


def nativescript_fixture(root: Path) -> None:
    write_json(
        root / "package.json",
        {"dependencies": {"@nativescript/core": "^8.0.0", "typescript": "^5.0.0"}},
    )
    (root / "nativescript.config.ts").write_text("export default {};\n", encoding="utf-8")
    (root / "App_Resources").mkdir(exist_ok=True)
    (root / "tsconfig.json").write_text("{}", encoding="utf-8")


def php_fixture(root: Path) -> None:
    write_json(root / "composer.json", {"require": {"php": "^8.2"}})
    (root / "src").mkdir(exist_ok=True)
    for index in range(3):
        (root / "src" / "Example{}.php".format(index)).write_text(
            "<?php\n", encoding="utf-8"
        )


def typescript_fixture(root: Path) -> None:
    write_json(root / "package.json", {"devDependencies": {"typescript": "^5.0.0"}})
    (root / "tsconfig.json").write_text("{}", encoding="utf-8")
    (root / "src").mkdir(exist_ok=True)
    (root / "src" / "app.ts").write_text("export {};\n", encoding="utf-8")


def devops_fixture(root: Path) -> None:
    (root / "Dockerfile").write_text("FROM alpine\n", encoding="utf-8")
    (root / ".github" / "workflows").mkdir(parents=True, exist_ok=True)
    (root / ".github" / "workflows" / "ci.yml").write_text("name: ci\n", encoding="utf-8")
