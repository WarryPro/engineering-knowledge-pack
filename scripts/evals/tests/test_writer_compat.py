"""Python 3.9-compatible text writer byte-contract tests."""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPTS_EVALS = REPO_ROOT / "scripts" / "evals"
if str(SCRIPTS_EVALS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_EVALS))

from scoring_common import write_json, write_text  # noqa: E402


class WriterCompatTests(unittest.TestCase):
    def test_write_text_preserves_lf_bytes(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "out.txt"
            write_text(path, "alpha\nbeta\n")
            self.assertEqual(path.read_bytes(), b"alpha\nbeta\n")

    def test_write_json_is_utf8_lf(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "out.json"
            write_json(path, {"b": 2, "a": 1})
            raw = path.read_bytes()
            self.assertFalse(raw.startswith(b"\xef\xbb\xbf"))
            self.assertNotIn(b"\r", raw)
            self.assertEqual(raw, json.dumps({"a": 1, "b": 2}, indent=2, sort_keys=True).encode("utf-8") + b"\n")


if __name__ == "__main__":
    unittest.main()
