"""BA-B1 Trusted Publishing workflow and release-ref contract tests."""

from __future__ import annotations

import re
import subprocess
import tempfile
import textwrap
import unittest
from pathlib import Path

import yaml

from ekp.paths import get_ekp_root

WORKFLOW_REL = Path(".github/workflows/publish-package.yml")

# Semantic release associated with each immutable pin (resolved 2026-09-18).
EXPECTED_ACTION_PINS = {
    "actions/checkout": (
        "3d3c42e5aac5ba805825da76410c181273ba90b1",
        "v7.0.1",
    ),
    "actions/setup-python": (
        "5fda3b95a4ea91299a34e894583c3862153e4b97",
        "v7.0.0",
    ),
    "actions/upload-artifact": (
        "043fb46d1a93c77aae656e7c1c64a875d1fc6a0a",
        "v7.0.1",
    ),
    "actions/download-artifact": (
        "3e5f45b2cfb9172054b4087a40e8e0b5a5461e7c",
        "v8.0.1",
    ),
    "pypa/gh-action-pypi-publish": (
        "dc37677b2e1c63e2034f94d8a5b11f265b73ba33",
        "v1.14.2",
    ),
}

FULL_SHA_RE = re.compile(r"^[0-9a-f]{40}$")
USES_RE = re.compile(
    r"^\s*uses:\s*(?P<owner>[^/\s]+)/(?P<repo>[^@\s]+)@(?P<ref>\S+)",
    re.MULTILINE,
)

# Forbidden credential / secret patterns in the publication workflow.
FORBIDDEN_SECRET_PATTERNS = (
    re.compile(r"PYPI_API_TOKEN", re.I),
    re.compile(r"TWINE_PASSWORD", re.I),
    re.compile(r"__token__", re.I),
    re.compile(r"secrets\.PYPI_", re.I),
    re.compile(r"password\s*:", re.I),
    re.compile(r"user(?:name)?\s*:\s*[^\n]*token", re.I),
)


def _repo_root() -> Path:
    return get_ekp_root()


def _github_safe_load(text: str):
    """Load GitHub Actions YAML without coercing ``on`` to boolean True."""
    # PyYAML 1.1 may parse bare `on:` as boolean True; quote the key first.
    fixed = re.sub(r"(?m)^on:", '"on":', text)
    return yaml.safe_load(fixed)


def _load_workflow():
    path = _repo_root() / WORKFLOW_REL
    text = path.read_text(encoding="utf-8")
    return text, _github_safe_load(text)


def _import_validate_module():
    import importlib.util

    path = _repo_root() / "scripts" / "packaging" / "validate_release_ref.py"
    spec = importlib.util.spec_from_file_location("validate_release_ref", path)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


def _import_prepare_module():
    import importlib.util

    path = _repo_root() / "scripts" / "packaging" / "prepare_publish_artifacts.py"
    spec = importlib.util.spec_from_file_location("prepare_publish_artifacts", path)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


def _import_upload_module():
    import importlib.util

    path = _repo_root() / "scripts" / "packaging" / "prepare_publish_upload.py"
    spec = importlib.util.spec_from_file_location("prepare_publish_upload", path)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


def _git(repo: Path, *args: str) -> str:
    proc = subprocess.run(
        ["git", *args],
        cwd=str(repo),
        capture_output=True,
        text=True,
        check=True,
    )
    return proc.stdout.strip()


def _init_synthetic_repo(root: Path) -> Path:
    """Create a minimal git repo with master/staging identity for gate tests."""
    repo = root / "repo"
    repo.mkdir()
    _git(repo, "init")
    _git(repo, "config", "user.email", "ba-b1@example.test")
    _git(repo, "config", "user.name", "BA-B1 Tests")
    (repo / "pyproject.toml").write_text(
        textwrap.dedent(
            """\
            [build-system]
            requires = ["hatchling"]
            build-backend = "hatchling.build"

            [project]
            name = "engineering-knowledge-pack"
            version = "0.22.0.dev0"
            description = "test"
            requires-python = ">=3.9"
            """
        ),
        encoding="utf-8",
    )
    (repo / "README.md").write_text("test\n", encoding="utf-8")
    _git(repo, "add", "pyproject.toml", "README.md")
    _git(repo, "commit", "-m", "init")
    # Ensure branch names master/staging
    current = _git(repo, "branch", "--show-current")
    if current != "master":
        _git(repo, "branch", "-M", "master")
    _git(repo, "branch", "staging")
    # Simulate origin remotes via local remote
    bare = root / "origin.git"
    _git(root, "init", "--bare", str(bare))
    _git(repo, "remote", "add", "origin", str(bare))
    _git(repo, "push", "-u", "origin", "master")
    _git(repo, "push", "-u", "origin", "staging")
    _git(repo, "fetch", "origin")
    return repo


class PublishWorkflowContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text, cls.data = _load_workflow()

    def test_workflow_dispatch_only_trigger(self):
        on = self.data["on"]
        self.assertIsInstance(on, dict)
        self.assertIn("workflow_dispatch", on)
        self.assertEqual(set(on.keys()), {"workflow_dispatch"})

    def test_required_inputs_target_and_ref(self):
        inputs = self.data["on"]["workflow_dispatch"]["inputs"]
        self.assertIn("target", inputs)
        self.assertIn("ref", inputs)
        self.assertTrue(inputs["target"]["required"])
        self.assertTrue(inputs["ref"]["required"])
        self.assertEqual(inputs["target"]["type"], "choice")
        self.assertEqual(set(inputs["target"]["options"]), {"testpypi", "pypi"})

    def test_default_permissions_contents_read_only(self):
        perms = self.data.get("permissions", {})
        self.assertEqual(perms.get("contents"), "read")
        self.assertNotIn("id-token", perms)

    def test_build_job_has_no_id_token_write(self):
        build = self.data["jobs"]["build"]
        perms = build.get("permissions", {})
        self.assertNotEqual(perms.get("id-token"), "write")
        # Build must not escalate beyond contents read
        self.assertEqual(perms.get("contents"), "read")

    def test_publish_jobs_oidc_and_environments(self):
        test = self.data["jobs"]["publish-testpypi"]
        prod = self.data["jobs"]["publish-pypi"]
        self.assertEqual(test["environment"], "testpypi")
        self.assertEqual(prod["environment"], "pypi")
        self.assertEqual(test["permissions"]["id-token"], "write")
        self.assertEqual(prod["permissions"]["id-token"], "write")
        self.assertIn("build", test["needs"] if isinstance(test["needs"], list) else [test["needs"]])
        self.assertIn("build", prod["needs"] if isinstance(prod["needs"], list) else [prod["needs"]])

    def test_publish_jobs_are_target_gated(self):
        test_if = str(self.data["jobs"]["publish-testpypi"]["if"])
        prod_if = str(self.data["jobs"]["publish-pypi"]["if"])
        self.assertIn("testpypi", test_if)
        self.assertIn("'pypi'", prod_if.replace('"', "'"))
        self.assertNotIn("testpypi", prod_if)
        self.assertNotIn("pypi", test_if.replace("testpypi", ""))

    def test_testpypi_repository_url_and_pypi_default(self):
        test_steps = self.data["jobs"]["publish-testpypi"]["steps"]
        prod_steps = self.data["jobs"]["publish-pypi"]["steps"]
        test_publish = [s for s in test_steps if "gh-action-pypi-publish" in s.get("uses", "")][0]
        prod_publish = [s for s in prod_steps if "gh-action-pypi-publish" in s.get("uses", "")][0]
        self.assertEqual(
            test_publish["with"]["repository-url"],
            "https://test.pypi.org/legacy/",
        )
        self.assertNotIn("repository-url", prod_publish.get("with", {}))
        self.assertNotIn("skip-existing", test_publish.get("with", {}))
        self.assertNotIn("skip-existing", prod_publish.get("with", {}))

    def test_publish_jobs_consume_build_artifact_without_rebuild(self):
        for job_name in ("publish-testpypi", "publish-pypi"):
            steps = self.data["jobs"][job_name]["steps"]
            uses = [s.get("uses", "") for s in steps]
            self.assertTrue(any("download-artifact" in u for u in uses))
            # Sparse checkout of the upload-prep helper only — never rebuild.
            self.assertTrue(any("checkout" in u for u in uses))
            run_blocks = "\n".join(s.get("run", "") for s in steps)
            self.assertNotIn("python -m build", run_blocks)
            self.assertNotIn("prepare_publish_artifacts", run_blocks)
            self.assertIn("prepare_publish_upload.py", run_blocks)

    def test_publish_jobs_isolate_verified_upload_payload(self):
        for job_name in ("publish-testpypi", "publish-pypi"):
            steps = self.data["jobs"][job_name]["steps"]
            publish = [s for s in steps if "gh-action-pypi-publish" in s.get("uses", "")][0]
            packages_dir = publish["with"]["packages-dir"]
            self.assertIn("upload-dist", packages_dir)
            self.assertNotIn("publish-dist", packages_dir)
            run_blocks = "\n".join(s.get("run", "") for s in steps)
            self.assertIn("--artifact-dir", run_blocks)
            self.assertIn("publish-dist", run_blocks)
            self.assertIn("--upload-dir", run_blocks)
            self.assertIn("upload-dist", run_blocks)
            self.assertIn("SHA256SUMS", run_blocks)
            self.assertIn('test ! -e "${RUNNER_TEMP}/upload-dist/SHA256SUMS"', run_blocks)

    def test_no_static_credential_references(self):
        for pattern in FORBIDDEN_SECRET_PATTERNS:
            self.assertIsNone(
                pattern.search(self.text),
                "forbidden credential pattern found: {}".format(pattern.pattern),
            )

    def test_third_party_actions_are_full_sha_pinned(self):
        for match in USES_RE.finditer(self.text):
            owner = match.group("owner")
            repo = match.group("repo")
            ref = match.group("ref").split("#", 1)[0].strip()
            key = "{}/{}".format(owner, repo)
            self.assertRegex(ref, FULL_SHA_RE, "mutable action ref: {}@{}".format(key, ref))
            self.assertIn(key, EXPECTED_ACTION_PINS)
            expected_sha, expected_tag = EXPECTED_ACTION_PINS[key]
            self.assertEqual(ref, expected_sha)
            # Comment documents semantic version
            line = match.group(0)
            # Find original line with comment
            for raw in self.text.splitlines():
                if key in raw and expected_sha in raw:
                    self.assertIn(expected_tag, raw)
                    break
            else:
                self.fail("missing semantic version comment for {}".format(key))

    def test_build_uses_runner_temp_not_repo_dist(self):
        build_runs = "\n".join(
            s.get("run", "") for s in self.data["jobs"]["build"]["steps"] if "run" in s
        )
        self.assertIn("RUNNER_TEMP", build_runs)
        self.assertIn("build-a", build_runs)
        self.assertIn("build-b", build_runs)
        self.assertIn("release-dist", build_runs)
        self.assertIn("prepare_publish_artifacts.py", build_runs)
        self.assertIn("validate_release_ref.py", build_runs)


class ReleaseRefValidationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.mod = _import_validate_module()

    def test_unknown_target_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = _init_synthetic_repo(Path(tmp))
            with self.assertRaises(self.mod.ReleaseRefError):
                self.mod.validate(repo, "prod", _git(repo, "rev-parse", "HEAD"))

    def test_empty_ref_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = _init_synthetic_repo(Path(tmp))
            with self.assertRaises(self.mod.ReleaseRefError):
                self.mod.validate(repo, "testpypi", "")

    def test_testpypi_rejects_branch_name(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = _init_synthetic_repo(Path(tmp))
            with self.assertRaises(self.mod.ReleaseRefError):
                self.mod.validate(repo, "testpypi", "staging")

    def test_testpypi_accepts_exact_dev_commit(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = _init_synthetic_repo(Path(tmp))
            sha = _git(repo, "rev-parse", "HEAD")
            # Place on feature branch (authorized)
            _git(repo, "checkout", "-b", "feature/distribution-product-ux")
            payload = self.mod.validate(repo, "testpypi", sha)
            self.assertEqual(payload["target"], "testpypi")
            self.assertEqual(payload["resolved_sha"], sha)
            self.assertEqual(payload["package_version"], "0.22.0.dev0")

    def test_testpypi_rejects_final_version(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = _init_synthetic_repo(Path(tmp))
            text = (repo / "pyproject.toml").read_text(encoding="utf-8")
            (repo / "pyproject.toml").write_text(
                text.replace("0.22.0.dev0", "0.22.0"), encoding="utf-8"
            )
            _git(repo, "add", "pyproject.toml")
            _git(repo, "commit", "-m", "final")
            _git(repo, "checkout", "-b", "feature/x")
            sha = _git(repo, "rev-parse", "HEAD")
            with self.assertRaises(self.mod.ReleaseRefError):
                self.mod.validate(repo, "testpypi", sha)

    def test_pypi_rejects_raw_sha(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = _init_synthetic_repo(Path(tmp))
            sha = _git(repo, "rev-parse", "HEAD")
            with self.assertRaises(self.mod.ReleaseRefError):
                self.mod.validate(repo, "pypi", sha)

    def test_pypi_rejects_lightweight_tag(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = _init_synthetic_repo(Path(tmp))
            # Make final version matching tag
            text = (repo / "pyproject.toml").read_text(encoding="utf-8")
            (repo / "pyproject.toml").write_text(
                text.replace("0.22.0.dev0", "0.22.0"), encoding="utf-8"
            )
            _git(repo, "add", "pyproject.toml")
            _git(repo, "commit", "-m", "release")
            sha = _git(repo, "rev-parse", "HEAD")
            _git(repo, "checkout", "staging")
            _git(repo, "merge", "--ff-only", "master")
            _git(repo, "push", "origin", "master")
            _git(repo, "push", "origin", "staging")
            _git(repo, "tag", "v0.22.0")  # lightweight
            with self.assertRaises(self.mod.ReleaseRefError) as ctx:
                self.mod.validate(repo, "pypi", "v0.22.0")
            self.assertIn("annotated", str(ctx.exception).lower())

    def test_pypi_rejects_tag_version_mismatch(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = _init_synthetic_repo(Path(tmp))
            # version stays 0.22.0.dev0 but tag is v0.22.0
            _git(repo, "tag", "-a", "v0.22.0", "-m", "bad")
            with self.assertRaises(self.mod.ReleaseRefError):
                self.mod.validate(repo, "pypi", "v0.22.0")

    def test_pypi_rejects_when_master_staging_diverge(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = _init_synthetic_repo(Path(tmp))
            text = (repo / "pyproject.toml").read_text(encoding="utf-8")
            (repo / "pyproject.toml").write_text(
                text.replace("0.22.0.dev0", "0.22.0"), encoding="utf-8"
            )
            _git(repo, "add", "pyproject.toml")
            _git(repo, "commit", "-m", "release")
            _git(repo, "tag", "-a", "v0.22.0", "-m", "v0.22.0")
            # diverge staging
            _git(repo, "checkout", "staging")
            (repo / "README.md").write_text("diverged\n", encoding="utf-8")
            _git(repo, "add", "README.md")
            _git(repo, "commit", "-m", "diverge staging")
            _git(repo, "push", "origin", "master")
            _git(repo, "push", "origin", "staging", "--force")
            _git(repo, "fetch", "origin")
            _git(repo, "checkout", "master")
            with self.assertRaises(self.mod.ReleaseRefError):
                self.mod.validate(repo, "pypi", "v0.22.0")

    def test_pypi_accepts_annotated_tag_aligned_master_staging(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = _init_synthetic_repo(Path(tmp))
            text = (repo / "pyproject.toml").read_text(encoding="utf-8")
            (repo / "pyproject.toml").write_text(
                text.replace("0.22.0.dev0", "0.22.0"), encoding="utf-8"
            )
            _git(repo, "add", "pyproject.toml")
            _git(repo, "commit", "-m", "release")
            sha = _git(repo, "rev-parse", "HEAD")
            _git(repo, "checkout", "staging")
            _git(repo, "merge", "--ff-only", "master")
            _git(repo, "push", "origin", "master")
            _git(repo, "push", "origin", "staging")
            _git(repo, "fetch", "origin")
            _git(repo, "checkout", "master")
            _git(repo, "tag", "-a", "v0.22.0", "-m", "v0.22.0")
            payload = self.mod.validate(repo, "pypi", "v0.22.0")
            self.assertEqual(payload["resolved_sha"], sha)
            self.assertEqual(payload["package_version"], "0.22.0")
            self.assertEqual(payload["tag_name"], "v0.22.0")

    def test_pypi_rejects_dev_version_even_with_tag_shape(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = _init_synthetic_repo(Path(tmp))
            # Impossible combo: tag v0.22.0 but version .dev — mismatch path
            _git(repo, "tag", "-a", "v0.22.0", "-m", "v0.22.0")
            with self.assertRaises(self.mod.ReleaseRefError):
                self.mod.validate(repo, "pypi", "v0.22.0")

    def test_dirty_tree_gate(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = _init_synthetic_repo(Path(tmp))
            (repo / "dirt.txt").write_text("x", encoding="utf-8")
            with self.assertRaises(self.mod.ReleaseRefError):
                self.mod.assert_clean_worktree(repo)


class PrepareArtifactsNegativeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.mod = _import_prepare_module()

    def test_missing_wheel_fails_build_pair_contract(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            # empty outdir simulation via audit helpers
            with self.assertRaises(self.mod.PrepareError):
                self.mod.audit_wheel(root / "missing.whl", "0.22.0.dev0")

    def test_non_reproducible_hashes_detected(self):
        # Direct comparison path in prepare()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            a = root / "a.whl"
            b = root / "b.whl"
            a.write_bytes(b"one")
            b.write_bytes(b"two")
            self.assertNotEqual(self.mod._sha256(a), self.mod._sha256(b))

    def test_dirty_source_tree_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = _init_synthetic_repo(Path(tmp))
            (repo / "dirt.txt").write_text("x", encoding="utf-8")
            with self.assertRaises(self.mod.PrepareError):
                self.mod.assert_clean(repo)


def _write_artifact_fixture(
    root: Path,
    *,
    wheel_bytes: bytes = b"wheel-bytes",
    sdist_bytes: bytes = b"sdist-bytes",
    mutate_manifest: str | None = None,
    extra_file: str | None = None,
    omit: str | None = None,
) -> Path:
    """Create a release-dist shaped directory for upload-prep tests."""
    artifact = root / "artifact"
    artifact.mkdir()
    wheel = artifact / "engineering_knowledge_pack-0.22.0.dev0-py3-none-any.whl"
    sdist = artifact / "engineering_knowledge_pack-0.22.0.dev0.tar.gz"
    if omit != "wheel":
        wheel.write_bytes(wheel_bytes)
    if omit != "sdist":
        sdist.write_bytes(sdist_bytes)
    if omit != "SHA256SUMS":
        entries = []
        if omit != "wheel":
            entries.append(
                "{}  {}".format(
                    __import__("hashlib").sha256(wheel_bytes).hexdigest(),
                    wheel.name,
                )
            )
        if omit != "sdist":
            entries.append(
                "{}  {}".format(
                    __import__("hashlib").sha256(sdist_bytes).hexdigest(),
                    sdist.name,
                )
            )
        text = "\n".join(entries) + ("\n" if entries else "")
        if mutate_manifest is not None:
            text = mutate_manifest
        (artifact / "SHA256SUMS").write_text(text, encoding="utf-8")
    if extra_file:
        (artifact / extra_file).write_text("extra\n", encoding="utf-8")
    return artifact


class PreparePublishUploadTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.mod = _import_upload_module()

    def test_successful_preparation_exact_upload_contents(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            artifact = _write_artifact_fixture(root)
            upload = root / "upload"
            result = self.mod.prepare_upload(
                artifact_dir=artifact, upload_dir=upload
            )
            names = sorted(p.name for p in upload.iterdir())
            self.assertEqual(
                names,
                [
                    "engineering_knowledge_pack-0.22.0.dev0-py3-none-any.whl",
                    "engineering_knowledge_pack-0.22.0.dev0.tar.gz",
                ],
            )
            self.assertNotIn("SHA256SUMS", names)
            self.assertEqual(result["upload_files"], names)
            self.assertTrue((artifact / "SHA256SUMS").is_file())
            # Bytes must be unchanged copies
            self.assertEqual(
                (upload / names[0]).read_bytes(),
                (artifact / names[0]).read_bytes(),
            )
            self.assertEqual(
                (upload / names[1]).read_bytes(),
                (artifact / names[1]).read_bytes(),
            )

    def test_checksum_mismatch_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            artifact = _write_artifact_fixture(root, wheel_bytes=b"wheel-bytes")
            wheel = next(artifact.glob("*.whl"))
            wheel.write_bytes(b"tampered-wheel")
            with self.assertRaises(self.mod.UploadPrepareError) as ctx:
                self.mod.prepare_upload(
                    artifact_dir=artifact, upload_dir=root / "upload"
                )
            self.assertIn("checksum mismatch", str(ctx.exception).lower())

    def test_missing_wheel_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            artifact = _write_artifact_fixture(root, omit="wheel")
            with self.assertRaises(self.mod.UploadPrepareError):
                self.mod.prepare_upload(
                    artifact_dir=artifact, upload_dir=root / "upload"
                )

    def test_unexpected_file_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            artifact = _write_artifact_fixture(root, extra_file="NOTES.txt")
            with self.assertRaises(self.mod.UploadPrepareError) as ctx:
                self.mod.prepare_upload(
                    artifact_dir=artifact, upload_dir=root / "upload"
                )
            self.assertIn("unexpected", str(ctx.exception).lower())

    def test_invalid_manifest_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            artifact = _write_artifact_fixture(
                root, mutate_manifest="not-a-valid-manifest-line\n"
            )
            with self.assertRaises(self.mod.UploadPrepareError) as ctx:
                self.mod.prepare_upload(
                    artifact_dir=artifact, upload_dir=root / "upload"
                )
            self.assertIn("malformed", str(ctx.exception).lower())

    def test_missing_manifest_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            artifact = _write_artifact_fixture(root, omit="SHA256SUMS")
            with self.assertRaises(self.mod.UploadPrepareError):
                self.mod.prepare_upload(
                    artifact_dir=artifact, upload_dir=root / "upload"
                )


class MutableActionRefNegativeTests(unittest.TestCase):
    def test_mutable_tag_ref_rejected_by_contract_regex(self):
        bad = "uses: actions/checkout@v4"
        match = USES_RE.search(bad)
        self.assertIsNotNone(match)
        ref = match.group("ref")
        self.assertIsNone(FULL_SHA_RE.match(ref))


if __name__ == "__main__":
    unittest.main()
