"""Install manifest mode / composition metadata tests (AW-E1)."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from ekp.composition import PROJECT_COMPOSITION_PROFILE
from ekp.install.errors import InstallConflictError
from ekp.install.manifest import (
    INSTALL_MODE_COMPOSITION,
    INSTALL_MODE_LEGACY_PROFILE,
    InstallManifest,
    ManagedFile,
    ManifestStore,
)


def _legacy_payload(**overrides):
    payload = {
        "schema_version": 1,
        "ekp_version": "0.17.0",
        "profile": "cursor-symfony",
        "adapters": ["cursor"],
        "installed_at": "2026-01-01T00:00:00Z",
        "install_root": ".",
        "managed_files": [
            {
                "relative_path": ".cursor/rules/demo.mdc",
                "adapter": "cursor",
                "sha256": "a" * 64,
            }
        ],
        "created_directories": [".cursor/rules"],
    }
    payload.update(overrides)
    return payload


def _composition_hash():
    return "b" * 64


class ManifestModeTests(unittest.TestCase):
    def test_legacy_without_mode_loads(self):
        manifest = InstallManifest.from_dict(_legacy_payload())
        self.assertIsNone(manifest.mode)
        self.assertIsNone(manifest.configuration_sha256)
        self.assertEqual(manifest.effective_mode, INSTALL_MODE_LEGACY_PROFILE)

    def test_legacy_explicit_mode(self):
        manifest = InstallManifest.from_dict(
            _legacy_payload(mode=INSTALL_MODE_LEGACY_PROFILE)
        )
        self.assertEqual(manifest.effective_mode, INSTALL_MODE_LEGACY_PROFILE)

    def test_composition_manifest_valid(self):
        digest = _composition_hash()
        manifest = InstallManifest.from_dict(
            _legacy_payload(
                profile=PROJECT_COMPOSITION_PROFILE,
                mode=INSTALL_MODE_COMPOSITION,
                configuration_sha256=digest,
            )
        )
        self.assertEqual(manifest.effective_mode, INSTALL_MODE_COMPOSITION)
        self.assertEqual(manifest.configuration_sha256, digest)

    def test_composition_missing_hash_rejected(self):
        with self.assertRaises(InstallConflictError):
            InstallManifest.from_dict(
                _legacy_payload(
                    profile=PROJECT_COMPOSITION_PROFILE,
                    mode=INSTALL_MODE_COMPOSITION,
                )
            )

    def test_composition_invalid_hash_rejected(self):
        with self.assertRaises(InstallConflictError):
            InstallManifest.from_dict(
                _legacy_payload(
                    profile=PROJECT_COMPOSITION_PROFILE,
                    mode=INSTALL_MODE_COMPOSITION,
                    configuration_sha256="abc",
                )
            )

    def test_composition_wrong_profile_rejected(self):
        with self.assertRaises(InstallConflictError):
            InstallManifest.from_dict(
                _legacy_payload(
                    profile="cursor-symfony",
                    mode=INSTALL_MODE_COMPOSITION,
                    configuration_sha256=_composition_hash(),
                )
            )

    def test_unknown_mode_rejected(self):
        with self.assertRaises(InstallConflictError):
            InstallManifest.from_dict(_legacy_payload(mode="weird"))

    def test_legacy_serialization_omits_optional_nulls(self):
        manifest = InstallManifest(
            schema_version=1,
            ekp_version="0.17.0",
            profile="cursor-core",
            adapters=["cursor"],
            installed_at="2026-01-01T00:00:00Z",
            install_root=".",
            managed_files=[],
            mode=None,
            configuration_sha256=None,
        )
        payload = manifest.to_dict()
        self.assertNotIn("mode", payload)
        self.assertNotIn("configuration_sha256", payload)

    def test_composition_serialization_includes_fields(self):
        digest = _composition_hash()
        manifest = InstallManifest(
            schema_version=1,
            ekp_version="0.18.0.dev0",
            profile=PROJECT_COMPOSITION_PROFILE,
            adapters=["cursor"],
            installed_at="2026-01-01T00:00:00Z",
            install_root=".",
            managed_files=[],
            mode=INSTALL_MODE_COMPOSITION,
            configuration_sha256=digest,
        )
        payload = manifest.to_dict()
        self.assertEqual(payload["mode"], INSTALL_MODE_COMPOSITION)
        self.assertEqual(payload["configuration_sha256"], digest)

    def test_round_trip_legacy(self):
        original = InstallManifest.from_dict(_legacy_payload())
        restored = InstallManifest.from_dict(original.to_dict())
        self.assertEqual(restored.effective_mode, INSTALL_MODE_LEGACY_PROFILE)
        self.assertIsNone(restored.mode)

    def test_round_trip_composition(self):
        digest = _composition_hash()
        original = InstallManifest.from_dict(
            _legacy_payload(
                profile=PROJECT_COMPOSITION_PROFILE,
                mode=INSTALL_MODE_COMPOSITION,
                configuration_sha256=digest,
            )
        )
        restored = InstallManifest.from_dict(original.to_dict())
        self.assertEqual(restored.effective_mode, INSTALL_MODE_COMPOSITION)
        self.assertEqual(restored.configuration_sha256, digest)

    def test_exclusive_create_refuses_existing(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = ManifestStore(Path(tmp))
            manifest = InstallManifest(
                schema_version=1,
                ekp_version="0.18.0.dev0",
                profile="cursor-core",
                adapters=["cursor"],
                installed_at="2026-01-01T00:00:00Z",
                install_root=".",
                managed_files=[
                    ManagedFile(
                        relative_path=".cursor/rules/demo.mdc",
                        adapter="cursor",
                        sha256="c" * 64,
                    )
                ],
            )
            store.create(manifest)
            with self.assertRaises(InstallConflictError):
                store.create(manifest)

    def test_v017_fixture_shape(self):
        """v0.17-style fixture without mode fields remains readable."""
        raw = json.dumps(_legacy_payload(), indent=2)
        payload = json.loads(raw)
        self.assertNotIn("mode", payload)
        self.assertNotIn("configuration_sha256", payload)
        manifest = InstallManifest.from_dict(payload)
        self.assertEqual(manifest.effective_mode, INSTALL_MODE_LEGACY_PROFILE)


if __name__ == "__main__":
    unittest.main()
