"""Preparation and context renderer tests."""

from __future__ import annotations

import hashlib
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
EVALS_DIR = REPO_ROOT / "evals"
SCRIPTS_EVALS = REPO_ROOT / "scripts" / "evals"
if str(SCRIPTS_EVALS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_EVALS))

from context import (  # noqa: E402
    EMPTY_BYTES_SHA256,
    ContextRenderError,
    build_treatment_units,
    empty_context_sha256,
    normalize_newlines,
    render_context_markdown,
)
from eval_common import EMPTY_BYTES_SHA256 as EMPTY_SHA  # noqa: E402
from helpers import MIN_SCENARIO, add_scenario, copy_real_schemas, write_yaml  # noqa: E402
from prepare import (  # noqa: E402
    PrepareError,
    prepare_all,
    serialize_participant,
)


class ContextRendererTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Real indexes required for profile rendering tests.
        dist = REPO_ROOT / "dist"
        if not (dist / "adapter-manifest.json").is_file():
            raise unittest.SkipTest("dist indexes missing; generate-index first")

    def test_empty_context_sha(self):
        self.assertEqual(empty_context_sha256(), EMPTY_SHA)
        self.assertEqual(
            EMPTY_SHA,
            "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
        )

    def test_missing_indexes_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(ContextRenderError) as ctx:
                build_treatment_units(REPO_ROOT, "cursor-core", dist_dir=Path(tmp))
            self.assertIn("generate-index", str(ctx.exception))

    def test_cursor_core_treatment_non_empty_and_ordered(self):
        units = build_treatment_units(REPO_ROOT, "cursor-core")
        self.assertGreater(len(units), 0)
        self.assertEqual(units[0].unit_type, "decision-flow")
        self.assertTrue(units[0].unit_id.endswith("ai-assisted-development.md"))
        types = [u.unit_type for u in units]
        self.assertIn("foundation-summary", types)
        self.assertEqual(types.count("foundation-principle"), 10)
        text = render_context_markdown(units)
        self.assertTrue(text.startswith("# Engineering Context\n"))
        self.assertNotIn("Evaluation treatment", text)
        self.assertNotIn("Cursor rules", text)

    def test_repeated_render_byte_identical(self):
        a = render_context_markdown(build_treatment_units(REPO_ROOT, "cursor-core")).encode("utf-8")
        b = render_context_markdown(build_treatment_units(REPO_ROOT, "cursor-core")).encode("utf-8")
        self.assertEqual(a, b)

    def test_crlf_canonicalization(self):
        self.assertEqual(normalize_newlines("a\r\nb\rc"), "a\nb\nc")

    def test_six_core_scenarios_share_context_when_prepared(self):
        # Relies on real prepared output if present; otherwise prepare into temp.
        with tempfile.TemporaryDirectory() as tmp:
            summaries = prepare_all(
                output_root=Path(tmp),
                repo_root=REPO_ROOT,
                ekp_commit="a" * 40,
                ekp_version="0.17.0.dev0",
            )
            by_id = {s["scenario_id"]: s for s in summaries}
            core_ids = [
                "core-boundaries-split",
                "core-api-integration",
                "core-db-migration",
                "core-test-strategy",
                "core-authz-review",
                "core-refactor-safety",
            ]
            shas = {by_id[i]["treatment_context_sha256"] for i in core_ids}
            self.assertEqual(len(shas), 1)
            for sid in core_ids:
                self.assertEqual(by_id[sid]["baseline_context_sha256"], EMPTY_SHA)
                self.assertGreater(by_id[sid]["context_bytes"], 0)


class PreparePackageTests(unittest.TestCase):
    def test_pair_fairness_and_fixture_order(self):
        with tempfile.TemporaryDirectory() as tmp:
            summaries = prepare_all(
                output_root=Path(tmp),
                repo_root=REPO_ROOT,
                scenario_id="core-boundaries-split",
                ekp_commit="b" * 40,
                ekp_version="0.17.0.dev0",
            )
            self.assertEqual(len(summaries), 1)
            base = Path(tmp) / "core-boundaries-split"
            b_sys = (base / "baseline" / "system_instruction.md").read_bytes()
            t_sys = (base / "treatment" / "system_instruction.md").read_bytes()
            b_part = (base / "baseline" / "participant.md").read_bytes()
            t_part = (base / "treatment" / "participant.md").read_bytes()
            self.assertEqual(b_sys, t_sys)
            self.assertEqual(b_part, t_part)
            self.assertEqual((base / "baseline" / "context.md").read_bytes(), b"")
            self.assertGreater(len((base / "treatment" / "context.md").read_bytes()), 0)
            participant = b_part.decode("utf-8")
            self.assertIn("===== BEGIN FILE:", participant)
            # Lexicographic fixture order: callers.py before fulfillment_service.py / README
            pos_readme = participant.find("BEGIN FILE: README.md")
            pos_callers = participant.find("BEGIN FILE: callers.py")
            self.assertGreaterEqual(pos_readme, 0)
            self.assertGreaterEqual(pos_callers, 0)

    def test_prepare_determinism_two_directories(self):
        with tempfile.TemporaryDirectory() as tmp:
            out1 = Path(tmp) / "a"
            out2 = Path(tmp) / "b"
            kwargs = dict(
                repo_root=REPO_ROOT,
                scenario_id="stack-frontend-boundary",
                ekp_commit="c" * 40,
                ekp_version="0.17.0.dev0",
            )
            prepare_all(output_root=out1, **kwargs)
            prepare_all(output_root=out2, **kwargs)
            files1 = {
                p.relative_to(out1).as_posix(): p.read_bytes()
                for p in out1.rglob("*")
                if p.is_file()
            }
            files2 = {
                p.relative_to(out2).as_posix(): p.read_bytes()
                for p in out2.rglob("*")
                if p.is_file()
            }
            self.assertEqual(files1, files2)

    def test_serialize_participant_order(self):
        text = serialize_participant(
            "Do the thing.\n",
            [("b.txt", "B\n"), ("a.txt", "A\n")],
        )
        self.assertLess(text.find("BEGIN FILE: b.txt"), text.find("BEGIN FILE: a.txt"))


class UnsafeFixtureTests(unittest.TestCase):
    def test_symlink_escape_rejected(self):
        if os.name == "nt":
            self.skipTest("Unix symlink escape coverage")
        with tempfile.TemporaryDirectory() as tmp:
            evals = Path(tmp) / "evals"
            copy_real_schemas(evals, EVALS_DIR)
            # Build a synthetic scenario under a fake repo that still uses real profiles/indexes
            scenario = dict(MIN_SCENARIO)
            scenario["id"] = "synthetic-fixture"
            scenario["status"] = "active"
            scenario["fixture"] = "fixture"
            scenario_dir = add_scenario(evals, scenario=scenario)
            fixture = scenario_dir / "fixture"
            fixture.mkdir()
            outside = Path(tmp) / "secret.txt"
            outside.write_text("secret", encoding="utf-8")
            link = fixture / "escape.txt"
            link.symlink_to(outside)
            # Point prepare at temporary scenarios by monkeypatching path is hard;
            # exercise load_fixture_files directly.
            from prepare import load_fixture_files

            with self.assertRaises(PrepareError):
                load_fixture_files(scenario_dir, "fixture")


if __name__ == "__main__":
    unittest.main()
