"""v0.22 packaging contract: wheel/sdist content and same-tree reproducibility."""

from __future__ import annotations

import hashlib
import shutil
import subprocess
import sys
import tarfile
import tempfile
import unittest
import zipfile
from pathlib import Path

from ekp.paths import get_ekp_root

EXPECTED_VERSION = "0.22.0"
DIST_NAME = "engineering-knowledge-pack"

WHEEL_REQUIRED_PREFIXES = (
    "ekp/",
    "ekp/_resources/knowledge/",
    "ekp/_resources/profiles/",
    "ekp/_resources/components/",
    "ekp/_resources/schema/",
    "ekp/_resources/scripts/adapters/",
    "ekp/_resources/scripts/assemble/",
    "ekp/_resources/scripts/validate/",
)

WHEEL_FORBIDDEN_PREFIXES = (
    "ekp/tests/",
)

SDIST_REQUIRED_RELATIVE = (
    "pyproject.toml",
    "README.md",
    "LICENSE",
    "src/ekp/",
    "src/ekp/tests/",
    "knowledge/",
    "profiles/",
    "components/",
    "schema/",
    "scripts/adapters/",
    "scripts/assemble/",
    "scripts/validate/",
)

SDIST_FORBIDDEN_MARKERS = (
    "/.git/",
    "/.github/",
    "/build/",
    "/dist/",
    "/.venv/",
    "/venv/",
    "/.pytest_cache/",
    "/coverage/",
    "/__pycache__/",
    "/_ba_a_out/",
)


def _repo_root() -> Path:
    return get_ekp_root()


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _build_artifacts(outdir: Path) -> tuple[Path, Path]:
    """Build clean wheel + sdist into ``outdir`` (must be outside the repo).

    Hatchling packs from the project cwd; writing build products into the
    checkout can contaminate a subsequent sdist unless those paths are excluded.
    """
    repo = _repo_root()
    outdir = outdir.resolve()
    if repo in outdir.parents or outdir == repo:
        raise AssertionError(
            "packaging build outdir must be outside the repository: {}".format(outdir)
        )
    if outdir.exists():
        shutil.rmtree(outdir)
    outdir.mkdir(parents=True)
    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "build",
            "--outdir",
            str(outdir),
        ],
        cwd=str(repo),
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        raise AssertionError(
            "build failed ({})\nSTDOUT:\n{}\nSTDERR:\n{}".format(
                proc.returncode, proc.stdout, proc.stderr
            )
        )
    wheels = sorted(outdir.glob("*.whl"))
    sdists = sorted(outdir.glob("*.tar.gz"))
    if len(wheels) != 1 or len(sdists) != 1:
        raise AssertionError(
            "expected one wheel and one sdist, got wheels={} sdists={}".format(
                [p.name for p in wheels], [p.name for p in sdists]
            )
        )
    return wheels[0], sdists[0]


def _has_prefix(names, prefix: str) -> bool:
    return any(n == prefix.rstrip("/") or n.startswith(prefix) for n in names)


class PackagingContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._tmpdir = tempfile.TemporaryDirectory(prefix="ekp-packaging-contract-")
        cls.outdir = Path(cls._tmpdir.name) / "dist-a"
        cls.wheel, cls.sdist = _build_artifacts(cls.outdir)

    @classmethod
    def tearDownClass(cls):
        cls._tmpdir.cleanup()

    def test_artifact_filenames_match_development_version(self):
        self.assertIn(EXPECTED_VERSION, self.wheel.name)
        self.assertIn(EXPECTED_VERSION, self.sdist.name)
        self.assertTrue(self.wheel.name.startswith("engineering_knowledge_pack-"))
        self.assertTrue(self.sdist.name.startswith("engineering_knowledge_pack-"))

    def test_wheel_contains_required_runtime_resources(self):
        with zipfile.ZipFile(self.wheel) as zf:
            names = zf.namelist()
        for prefix in WHEEL_REQUIRED_PREFIXES:
            self.assertTrue(
                _has_prefix(names, prefix),
                "wheel missing required prefix: {}".format(prefix),
            )
        meta_dirs = [
            n
            for n in names
            if n.endswith(".dist-info/") or "/METADATA" in n or n.endswith("METADATA")
        ]
        self.assertTrue(any("METADATA" in n for n in names), "wheel missing METADATA")
        self.assertTrue(meta_dirs or any(".dist-info/" in n for n in names))

    def test_wheel_excludes_package_tests(self):
        with zipfile.ZipFile(self.wheel) as zf:
            names = zf.namelist()
        forbidden = [n for n in names if any(n.startswith(p) for p in WHEEL_FORBIDDEN_PREFIXES)]
        self.assertEqual(
            forbidden,
            [],
            "wheel must not contain ekp/tests/**; found: {}".format(forbidden[:20]),
        )

    def test_wheel_metadata_version(self):
        with zipfile.ZipFile(self.wheel) as zf:
            meta_name = next(n for n in zf.namelist() if n.endswith(".dist-info/METADATA"))
            metadata = zf.read(meta_name).decode("utf-8")
        self.assertIn("Name: {}".format(DIST_NAME), metadata)
        self.assertIn("Version: {}".format(EXPECTED_VERSION), metadata)
        self.assertIn("Requires-Python: >=3.9", metadata)

    def test_sdist_contains_required_source_and_tests(self):
        with tarfile.open(self.sdist, "r:gz") as tf:
            names = tf.getnames()
        # Strip leading package directory (engineering_knowledge_pack-VERSION/)
        relative = []
        for name in names:
            parts = name.split("/", 1)
            relative.append(parts[1] if len(parts) == 2 else name)
        for required in SDIST_REQUIRED_RELATIVE:
            self.assertTrue(
                _has_prefix(relative, required),
                "sdist missing required path: {}".format(required),
            )

    def test_sdist_excludes_repository_noise(self):
        with tarfile.open(self.sdist, "r:gz") as tf:
            names = tf.getnames()
        # Normalize to rooted paths for marker checks
        rooted = ["/" + n for n in names]
        for marker in SDIST_FORBIDDEN_MARKERS:
            hits = [n for n in rooted if marker in n]
            self.assertEqual(
                hits,
                [],
                "sdist must not contain {}; found: {}".format(marker, hits[:10]),
            )

    def test_metadata_validation_twine_check(self):
        try:
            import twine  # noqa: F401
        except ImportError:
            self.skipTest("twine not installed")
        proc = subprocess.run(
            [sys.executable, "-m", "twine", "check", str(self.wheel), str(self.sdist)],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(
            proc.returncode,
            0,
            "twine check failed:\n{}\n{}".format(proc.stdout, proc.stderr),
        )


class SameTreeReproducibilityTests(unittest.TestCase):
    def test_two_clean_builds_are_byte_identical(self):
        with tempfile.TemporaryDirectory(prefix="ekp-repro-") as tmp:
            root = Path(tmp)
            wheel_a, sdist_a = _build_artifacts(root / "a")
            wheel_b, sdist_b = _build_artifacts(root / "b")
            self.assertEqual(wheel_a.name, wheel_b.name)
            self.assertEqual(sdist_a.name, sdist_b.name)
            self.assertEqual(
                _sha256(wheel_a),
                _sha256(wheel_b),
                "same-tree wheels differ: {} vs {}".format(
                    _sha256(wheel_a), _sha256(wheel_b)
                ),
            )
            self.assertEqual(
                _sha256(sdist_a),
                _sha256(sdist_b),
                "same-tree sdists differ: {} vs {}".format(
                    _sha256(sdist_a), _sha256(sdist_b)
                ),
            )


if __name__ == "__main__":
    unittest.main()
