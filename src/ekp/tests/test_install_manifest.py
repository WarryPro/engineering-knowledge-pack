"""Install manifest tests."""

import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from ekp.install.errors import InstallConflictError
from ekp.install.manifest import InstallManifest, ManagedFile, ManifestStore


class ManifestTests(unittest.TestCase):
    def test_round_trip(self):
        manifest = InstallManifest(
            schema_version=1,
            ekp_version="0.15.0.dev0",
            profile="cursor-core",
            adapters=["cursor"],
            installed_at="2026-01-01T00:00:00Z",
            install_root=".",
            managed_files=[
                ManagedFile(
                    relative_path=".cursor/rules/demo.mdc",
                    adapter="cursor",
                    sha256="abc",
                )
            ],
            created_directories=[".cursor/rules"],
        )
        restored = InstallManifest.from_dict(manifest.to_dict())
        self.assertEqual(restored.profile, "cursor-core")
        self.assertEqual(len(restored.managed_files), 1)

    def test_invalid_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            store = ManifestStore(root)
            store.manifest_path.parent.mkdir(parents=True, exist_ok=True)
            store.manifest_path.write_text("{bad", encoding="utf-8")
            with self.assertRaises(InstallConflictError):
                store.load()

    def test_unsupported_schema(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            store = ManifestStore(root)
            store.manifest_path.parent.mkdir(parents=True, exist_ok=True)
            store.manifest_path.write_text(
                json.dumps({"schema_version": 99, "ekp_version": "x"}),
                encoding="utf-8",
            )
            with self.assertRaises(InstallConflictError):
                store.load()

    def test_atomic_save(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            store = ManifestStore(root)
            manifest = InstallManifest(
                schema_version=1,
                ekp_version="0.15.0.dev0",
                profile="cursor-core",
                adapters=["cursor"],
                installed_at="2026-01-01T00:00:00Z",
                install_root=".",
                managed_files=[],
            )
            store.save(manifest)
            self.assertTrue(store.manifest_path.is_file())
            self.assertTrue(store.exists())

    def test_load_with_fingerprint_round_trip(self):
        manifest = InstallManifest(
            schema_version=1,
            ekp_version="0.15.0.dev0",
            profile="cursor-core",
            adapters=["cursor"],
            installed_at="2026-01-01T00:00:00Z",
            install_root=".",
            managed_files=[
                ManagedFile(
                    relative_path=".cursor/rules/demo.mdc",
                    adapter="cursor",
                    sha256="abc",
                )
            ],
            created_directories=[".cursor/rules"],
        )
        with tempfile.TemporaryDirectory() as tmp:
            store = ManifestStore(Path(tmp))
            store.save(manifest)
            snapshot = store.load_with_fingerprint()
            self.assertIsNotNone(snapshot)
            self.assertEqual(snapshot.manifest.profile, "cursor-core")
            self.assertEqual(
                snapshot.sha256,
                hashlib.sha256(store.manifest_path.read_bytes()).hexdigest(),
            )

    def test_snapshot_invalid_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = ManifestStore(Path(tmp))
            store.manifest_path.parent.mkdir(parents=True, exist_ok=True)
            store.manifest_path.write_text("{bad", encoding="utf-8")
            with self.assertRaises(InstallConflictError):
                store.load_with_fingerprint()

    def test_snapshot_unsupported_schema(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = ManifestStore(Path(tmp))
            store.manifest_path.parent.mkdir(parents=True, exist_ok=True)
            store.manifest_path.write_text(
                json.dumps({"schema_version": 99, "ekp_version": "x"}),
                encoding="utf-8",
            )
            with self.assertRaises(InstallConflictError):
                store.load_with_fingerprint()
