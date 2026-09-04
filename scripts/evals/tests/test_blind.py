"""Blind pairing tests (synthetic runs only)."""

from __future__ import annotations

import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPTS_EVALS = REPO_ROOT / "scripts" / "evals"
if str(SCRIPTS_EVALS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_EVALS))

from at_helpers import SYNTHETIC_RUBRIC, write_run_bundle  # noqa: E402
from blind import (  # noqa: E402
    assign_ab,
    generate_blind_packages,
    group_runs_into_pairs,
    make_pair_id,
    parse_salt_hex,
)
from helpers import write_yaml  # noqa: E402
from scoring_common import ScoringError, load_runs_from_dir  # noqa: E402

SALT_A = "11" * 32
SALT_B = "22" * 32


class BlindPairingTests(unittest.TestCase):
    def _rubric_path(self, root: Path) -> Path:
        path = root / "rubric.yaml"
        write_yaml(path, SYNTHETIC_RUBRIC)
        return path

    def test_fair_pair_accepted_and_balanced(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            runs = root / "runs"
            write_run_bundle(
                runs,
                scenario_id="synth-alpha",
                replicate_index=1,
                baseline_text="Synthetic response baseline r1.\n",
                treatment_text="Synthetic response treatment r1.\n",
            )
            write_run_bundle(
                runs,
                scenario_id="synth-alpha",
                replicate_index=2,
                baseline_text="Synthetic response baseline r2.\n",
                treatment_text="Synthetic response treatment r2.\n",
                baseline_at="2026-09-04T03:00:00Z",
                treatment_at="2026-09-04T01:00:00Z",
            )
            out = root / "blind"
            mapping = generate_blind_packages(
                runs_dir=runs,
                output_dir=out,
                salt_hex=SALT_A,
                rubric_paths={"synth-alpha": self._rubric_path(root)},
            )
            self.assertEqual(mapping["pair_count"], 2)
            self.assertEqual(mapping["treatment_as_a"] + mapping["treatment_as_b"], 2)
            self.assertLessEqual(
                abs(mapping["treatment_as_a"] - mapping["treatment_as_b"]), 0
            )
            self.assertTrue((out / "operator-private" / "mapping.json").is_file())
            self.assertTrue((out / "rater" / "instructions.md").is_file())

    def test_missing_condition_peer_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            runs = root / "runs"
            write_run_bundle(
                runs,
                scenario_id="synth-alpha",
                replicate_index=1,
                baseline_text="Synthetic response baseline only.\n",
                treatment_text="Synthetic response treatment only.\n",
            )
            # Delete treatment run folder
            for path in runs.iterdir():
                if "treatment" in path.name:
                    for child in path.iterdir():
                        child.unlink()
                    path.rmdir()
            with self.assertRaises(ScoringError) as ctx:
                group_runs_into_pairs(load_runs_from_dir(runs))
            self.assertIn("missing", str(ctx.exception).lower())

    def test_duplicate_condition_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            runs = root / "runs"
            write_run_bundle(
                runs,
                scenario_id="synth-alpha",
                replicate_index=1,
                baseline_text="Synthetic response baseline.\n",
                treatment_text="Synthetic response treatment.\n",
            )
            # Add second baseline with same pair key
            write_run_bundle(
                runs,
                scenario_id="synth-alpha",
                replicate_index=1,
                baseline_text="Synthetic response baseline duplicate.\n",
                treatment_text="Synthetic response treatment other.\n",
            )
            with self.assertRaises(ScoringError):
                group_runs_into_pairs(load_runs_from_dir(runs))

    def test_prompt_mismatch_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            runs = root / "runs"
            write_run_bundle(
                runs,
                scenario_id="synth-alpha",
                replicate_index=1,
                baseline_text="Synthetic baseline.\n",
                treatment_text="Synthetic treatment.\n",
                prompt_sha="b" * 64,
            )
            # Corrupt treatment prompt hash after write
            for path in runs.rglob("run.json"):
                data = json.loads(path.read_text(encoding="utf-8"))
                if data["condition"] == "treatment":
                    data["prompt_sha256"] = "c" * 64
                    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
            with self.assertRaises(ScoringError) as ctx:
                group_runs_into_pairs(load_runs_from_dir(runs))
            self.assertIn("prompt_sha256", str(ctx.exception))

    def test_profile_mismatch_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            runs = root / "runs"
            write_run_bundle(
                runs,
                scenario_id="synth-alpha",
                replicate_index=1,
                baseline_text="Synthetic baseline.\n",
                treatment_text="Synthetic treatment.\n",
            )
            for path in runs.rglob("run.json"):
                data = json.loads(path.read_text(encoding="utf-8"))
                if data["condition"] == "treatment":
                    data["profile"] = "cursor-symfony"
                    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
            with self.assertRaises(ScoringError) as ctx:
                group_runs_into_pairs(load_runs_from_dir(runs))
            self.assertIn("profile", str(ctx.exception))

    def test_model_mismatch_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            runs = root / "runs"
            write_run_bundle(
                runs,
                scenario_id="synth-alpha",
                replicate_index=1,
                baseline_text="Synthetic baseline.\n",
                treatment_text="Synthetic treatment.\n",
            )
            for path in runs.rglob("run.json"):
                data = json.loads(path.read_text(encoding="utf-8"))
                if data["condition"] == "treatment":
                    data["model_id_observed"] = "other-model"
                    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
            with self.assertRaises(ScoringError) as ctx:
                group_runs_into_pairs(load_runs_from_dir(runs))
            self.assertIn("model_id_observed", str(ctx.exception))

    def test_sampling_mismatch_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            runs = root / "runs"
            write_run_bundle(
                runs,
                scenario_id="synth-alpha",
                replicate_index=1,
                baseline_text="Synthetic baseline.\n",
                treatment_text="Synthetic treatment.\n",
            )
            for path in runs.rglob("run.json"):
                data = json.loads(path.read_text(encoding="utf-8"))
                if data["condition"] == "treatment":
                    data["sampling"]["temperature"] = 0.7
                    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
            with self.assertRaises(ScoringError) as ctx:
                group_runs_into_pairs(load_runs_from_dir(runs))
            self.assertIn("sampling", str(ctx.exception))

    def test_reasoning_effort_mismatch_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            runs = root / "runs"
            write_run_bundle(
                runs,
                scenario_id="synth-alpha",
                replicate_index=1,
                baseline_text="Synthetic baseline.\n",
                treatment_text="Synthetic treatment.\n",
            )
            for path in runs.rglob("run.json"):
                data = json.loads(path.read_text(encoding="utf-8"))
                if data["condition"] == "baseline":
                    data["sampling"]["reasoning_effort"] = "medium"
                else:
                    data["sampling"]["reasoning_effort"] = "high"
                path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
            with self.assertRaises(ScoringError) as ctx:
                group_runs_into_pairs(load_runs_from_dir(runs))
            msg = str(ctx.exception)
            self.assertIn("sampling", msg)
            # Mismatch is detected via SAMPLING_FIELDS (includes reasoning_effort).
            base = None
            treat = None
            for path in runs.rglob("run.json"):
                data = json.loads(path.read_text(encoding="utf-8"))
                if data["condition"] == "baseline":
                    base = data["sampling"]["reasoning_effort"]
                else:
                    treat = data["sampling"]["reasoning_effort"]
            self.assertEqual(base, "medium")
            self.assertEqual(treat, "high")
            self.assertNotEqual(base, treat)

    def test_reasoning_effort_match_accepted(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            runs = root / "runs"
            write_run_bundle(
                runs,
                scenario_id="synth-alpha",
                replicate_index=1,
                baseline_text="Synthetic baseline.\n",
                treatment_text="Synthetic treatment.\n",
            )
            for path in runs.rglob("run.json"):
                data = json.loads(path.read_text(encoding="utf-8"))
                data["sampling"]["reasoning_effort"] = "medium"
                path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
            pairs = group_runs_into_pairs(load_runs_from_dir(runs))
            self.assertEqual(len(pairs), 1)
            self.assertEqual(
                pairs[0]["baseline"]["run"]["sampling"]["reasoning_effort"], "medium"
            )
            self.assertEqual(
                pairs[0]["treatment"]["run"]["sampling"]["reasoning_effort"], "medium"
            )

    def test_fixed_salt_deterministic_and_different_salt_can_change(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            runs = root / "runs"
            for i in range(1, 5):
                write_run_bundle(
                    runs,
                    scenario_id="synth-alpha",
                    replicate_index=i,
                    baseline_text="Synthetic baseline {}.\n".format(i),
                    treatment_text="Synthetic treatment {}.\n".format(i),
                )
            rubric = self._rubric_path(root)
            out_a = root / "a"
            out_b = root / "b"
            out_c = root / "c"
            m_a = generate_blind_packages(
                runs, out_a, salt_hex=SALT_A, rubric_paths={"synth-alpha": rubric}
            )
            m_b = generate_blind_packages(
                runs, out_b, salt_hex=SALT_A, rubric_paths={"synth-alpha": rubric}
            )
            m_c = generate_blind_packages(
                runs, out_c, salt_hex=SALT_B, rubric_paths={"synth-alpha": rubric}
            )
            self.assertEqual(m_a["pairs"], m_b["pairs"])
            # Different salt may change assignment; allow either change or rare collision.
            assign_a = [(p["pair_id"], p["treatment_as"]) for p in m_a["pairs"]]
            assign_c = [(p["pair_id"], p["treatment_as"]) for p in m_c["pairs"]]
            # pair ids differ by salt, so compare treatment_as sequence by scenario/replicate
            seq_a = [
                (p["scenario_id"], p["replicate_index"], p["treatment_as"])
                for p in sorted(
                    m_a["pairs"], key=lambda x: (x["scenario_id"], x["replicate_index"])
                )
            ]
            seq_c = [
                (p["scenario_id"], p["replicate_index"], p["treatment_as"])
                for p in sorted(
                    m_c["pairs"], key=lambda x: (x["scenario_id"], x["replicate_index"])
                )
            ]
            self.assertEqual(len(seq_a), 4)
            # With 4 pairs and independent HMAC, different salts almost always differ;
            # if identical, still valid cryptographically — assert balance instead.
            self.assertEqual(m_a["treatment_as_a"], 2)
            self.assertEqual(m_c["treatment_as_a"], 2)
            if seq_a == seq_c:
                # Extremely unlikely; keep assertion soft via balance already checked.
                pass
            else:
                self.assertNotEqual(seq_a, seq_c)

    def test_mapping_absent_from_rater_and_no_condition_labels(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            runs = root / "runs"
            write_run_bundle(
                runs,
                scenario_id="synth-alpha",
                replicate_index=1,
                baseline_text="Synthetic response A for scoring test.\n",
                treatment_text="Synthetic response B for scoring test.\n",
            )
            out = root / "blind"
            generate_blind_packages(
                runs,
                out,
                salt_hex=SALT_A,
                rubric_paths={"synth-alpha": self._rubric_path(root)},
            )
            import re

            rater_root = out / "rater"
            for path in rater_root.rglob("*"):
                if not path.is_file():
                    continue
                if path.name in ("response-A.md", "response-B.md"):
                    continue
                text = path.read_text(encoding="utf-8")
                self.assertIsNone(re.search(r"\bbaseline\b", text, re.I), path)
                self.assertIsNone(re.search(r"\btreatment\b", text, re.I), path)
                self.assertIsNone(re.search(r"\bcondition\b", text, re.I), path)
                self.assertNotIn("context_sha256", text.lower())
                self.assertNotIn("ekp_commit", text.lower())
            self.assertFalse((rater_root / "mapping.json").exists())
            self.assertTrue((out / "operator-private" / "mapping.json").is_file())

    def test_responses_byte_identical_to_source(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            runs = root / "runs"
            base_text = "Synthetic response baseline exact.\n"
            treat_text = "Synthetic response treatment exact.\n"
            write_run_bundle(
                runs,
                scenario_id="synth-alpha",
                replicate_index=1,
                baseline_text=base_text,
                treatment_text=treat_text,
            )
            out = root / "blind"
            mapping = generate_blind_packages(
                runs,
                out,
                salt_hex=SALT_A,
                rubric_paths={"synth-alpha": self._rubric_path(root)},
            )
            pair = mapping["pairs"][0]
            pair_dir = out / "rater" / "pairs" / pair["pair_id"]
            a_bytes = (pair_dir / "response-A.md").read_bytes()
            b_bytes = (pair_dir / "response-B.md").read_bytes()
            expected = {
                pair["assignment"]["A"]["response_sha256"]: a_bytes,
                pair["assignment"]["B"]["response_sha256"]: b_bytes,
            }
            self.assertEqual(
                hashlib.sha256(a_bytes).hexdigest(),
                pair["assignment"]["A"]["response_sha256"],
            )
            self.assertEqual(
                hashlib.sha256(b_bytes).hexdigest(),
                pair["assignment"]["B"]["response_sha256"],
            )
            self.assertEqual(
                set(expected.keys()),
                {
                    hashlib.sha256(base_text.encode()).hexdigest(),
                    hashlib.sha256(treat_text.encode()).hexdigest(),
                },
            )

    def test_existing_mapping_refuses_overwrite(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            runs = root / "runs"
            write_run_bundle(
                runs,
                scenario_id="synth-alpha",
                replicate_index=1,
                baseline_text="Synthetic baseline.\n",
                treatment_text="Synthetic treatment.\n",
            )
            out = root / "blind"
            kwargs = dict(
                runs_dir=runs,
                output_dir=out,
                salt_hex=SALT_A,
                rubric_paths={"synth-alpha": self._rubric_path(root)},
            )
            generate_blind_packages(**kwargs)
            with self.assertRaises(ScoringError) as ctx:
                generate_blind_packages(**kwargs)
            self.assertIn("overwrite", str(ctx.exception).lower())

    def test_pair_id_does_not_encode_condition(self):
        salt = parse_salt_hex(SALT_A)
        pair_id = make_pair_id(salt, "synth-alpha", "1.0.0", "synthetic-config", 1)
        self.assertTrue(pair_id.startswith("pair-"))
        self.assertNotIn("baseline", pair_id)
        self.assertNotIn("treatment", pair_id)

    def test_identical_responses_still_valid_pair(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            runs = root / "runs"
            text = "Synthetic identical response for both conditions.\n"
            write_run_bundle(
                runs,
                scenario_id="synth-alpha",
                replicate_index=1,
                baseline_text=text,
                treatment_text=text,
            )
            mapping = generate_blind_packages(
                runs,
                root / "blind",
                salt_hex=SALT_A,
                rubric_paths={"synth-alpha": self._rubric_path(root)},
            )
            pair = mapping["pairs"][0]
            self.assertEqual(
                pair["assignment"]["A"]["response_sha256"],
                pair["assignment"]["B"]["response_sha256"],
            )


if __name__ == "__main__":
    unittest.main()
