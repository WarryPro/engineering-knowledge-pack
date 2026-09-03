#!/usr/bin/env python3
"""Import externally produced model responses into standardized run records.

No provider calls. No response rewriting.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

_SCRIPT_DIR = Path(__file__).resolve().parent
if str(_SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPT_DIR))

from eval_common import (  # noqa: E402
    EMPTY_BYTES_SHA256,
    REPO_ROOT,
    collect_forbidden_metadata_keys,
    load_json,
    load_schema_validators,
    sha256_bytes,
    sha256_file,
    validate_against,
)

FORBIDDEN_OVERRIDE_KEYS = {
    "scenario_id",
    "scenario_version",
    "profile",
    "condition",
    "ekp_commit",
    "ekp_version",
    "prompt_sha256",
    "context_sha256",
}


class ImportRunError(Exception):
    pass


def _read_exact_bytes(path: Path) -> bytes:
    return path.read_bytes()


def _verify_package(package_dir: Path) -> Dict[str, Any]:
    request_path = package_dir / "request.json"
    if not request_path.is_file():
        raise ImportRunError("missing request.json in {}".format(package_dir))
    request = load_json(request_path)
    if not isinstance(request, dict):
        raise ImportRunError("request.json must be an object")

    for name, key in (
        ("system_instruction.md", "system_instruction_sha256"),
        ("participant.md", "prompt_sha256"),
        ("context.md", "context_sha256"),
    ):
        path = package_dir / name
        if not path.is_file():
            raise ImportRunError("missing {} in package".format(name))
        actual = sha256_file(path)
        expected = request.get(key)
        if actual != expected:
            raise ImportRunError(
                "{} hash mismatch (expected {}, got {})".format(name, expected, actual)
            )

    condition = request.get("condition")
    if condition == "baseline":
        ctx = _read_exact_bytes(package_dir / "context.md")
        if ctx != b"" or request.get("context_sha256") != EMPTY_BYTES_SHA256:
            raise ImportRunError("baseline package context must be empty bytes")
    elif condition == "treatment":
        if request.get("context_bytes", 0) <= 0:
            raise ImportRunError("treatment package context must be non-empty")
    else:
        raise ImportRunError("unknown condition in request package")

    # Fixture audit hashes
    for row in request.get("fixture_files") or []:
        if not isinstance(row, dict):
            continue
        # Fixture content already embedded in participant.md; audit row integrity only.
        for required in ("path", "sha256", "bytes"):
            if required not in row:
                raise ImportRunError("fixture audit missing {}".format(required))
        if not re.fullmatch(r"[0-9a-f]{64}", str(row["sha256"])):
            raise ImportRunError("invalid fixture sha256 for {}".format(row.get("path")))

    return request


def _decode_utf8(data: bytes, label: str) -> str:
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ImportRunError("{} is not valid UTF-8: {}".format(label, exc))


def build_run_id(
    scenario_id: str,
    model_config_id: str,
    replicate_index: int,
    condition: str,
    response_sha: str,
) -> str:
    safe_model = re.sub(r"[^a-zA-Z0-9._-]+", "-", model_config_id).strip("-") or "model"
    return "{}--{}--r{:02d}--{}--{}".format(
        scenario_id,
        safe_model,
        int(replicate_index),
        condition,
        response_sha[:12],
    )


def import_run(
    package_dir: Path,
    response_path: Path,
    execution: Dict[str, Any],
    output_dir: Path,
) -> Dict[str, Any]:
    package_dir = Path(package_dir)
    response_path = Path(response_path)
    output_dir = Path(output_dir)

    request = _verify_package(package_dir)

    forbidden = collect_forbidden_metadata_keys(execution)
    if forbidden:
        raise ImportRunError(
            "forbidden execution metadata key(s): {}".format(", ".join(forbidden))
        )

    for key in FORBIDDEN_OVERRIDE_KEYS:
        if key in execution:
            raise ImportRunError(
                "execution metadata cannot override package field {!r}".format(key)
            )

    if not response_path.is_file():
        raise ImportRunError("response file not found: {}".format(response_path))
    response_bytes = _read_exact_bytes(response_path)
    if not response_bytes:
        raise ImportRunError("response must be non-empty")
    _decode_utf8(response_bytes, "response")
    response_sha = sha256_bytes(response_bytes)

    required_exec = [
        "provider",
        "model_config_id",
        "model_id_observed",
        "executed_at",
        "replicate_index",
    ]
    for key in required_exec:
        if key not in execution:
            raise ImportRunError("missing execution field {!r}".format(key))

    sampling = execution.get("sampling")
    if sampling is None:
        sampling = {
            "temperature": execution.get("temperature", None),
            "top_p": execution.get("top_p", None),
            "seed": execution.get("seed", None),
            "seed_supported": execution.get("seed_supported", None),
            "max_output": execution.get("max_output", None),
        }
    if not isinstance(sampling, dict):
        raise ImportRunError("sampling must be an object")

    run_id = build_run_id(
        request["scenario_id"],
        str(execution["model_config_id"]),
        int(execution["replicate_index"]),
        request["condition"],
        response_sha,
    )

    response_out_name = "response.txt"
    run = {
        "run_id": run_id,
        "scenario_id": request["scenario_id"],
        "scenario_version": request["scenario_version"],
        "ekp_commit": request["ekp_commit"],
        "ekp_version": request["ekp_version"],
        "profile": request["profile"],
        "condition": request["condition"],
        "provider": execution["provider"],
        "model_config_id": execution["model_config_id"],
        "model_id_observed": execution["model_id_observed"],
        "executed_at": execution["executed_at"],
        "replicate_index": int(execution["replicate_index"]),
        "sampling": {
            "temperature": sampling.get("temperature", None),
            "top_p": sampling.get("top_p", None),
            "seed": sampling.get("seed", None),
            "seed_supported": sampling.get("seed_supported", None),
            "max_output": sampling.get("max_output", None),
        },
        "tools_enabled": False,
        "session_isolation": "fresh",
        "prompt_sha256": request["prompt_sha256"],
        "context_sha256": request["context_sha256"],
        "response_sha256": response_sha,
        "response_file": response_out_name,
    }
    if "model_version_reported" in execution:
        # Not in schema; reject unknown top-level extras by keeping only schema fields.
        pass
    if "input_chars" in execution:
        run["input_chars"] = execution["input_chars"]
    if "output_chars" in execution:
        run["output_chars"] = execution["output_chars"]
    if "notes" in execution:
        run["notes"] = execution["notes"]

    validators = load_schema_validators()
    errors = validate_against(validators["run"], run, "run")
    if errors:
        raise ImportRunError("; ".join(errors))

    output_dir.mkdir(parents=True, exist_ok=True)
    response_out = output_dir / response_out_name
    response_out.write_bytes(response_bytes)
    if sha256_file(response_out) != response_sha:
        raise ImportRunError("stored response hash mismatch")

    run_path = output_dir / "run.json"
    run_path.write_text(json.dumps(run, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return run


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Import an evaluation model response")
    parser.add_argument("--package", required=True, help="Prepared condition package directory")
    parser.add_argument("--response", required=True, help="Raw response text file")
    parser.add_argument("--execution", required=True, help="Execution metadata JSON file")
    parser.add_argument("--output", required=True, help="Output directory for run artifacts")
    args = parser.parse_args(argv)

    try:
        execution = load_json(Path(args.execution))
        if not isinstance(execution, dict):
            raise ImportRunError("execution metadata must be a JSON object")
        run = import_run(
            package_dir=Path(args.package),
            response_path=Path(args.response),
            execution=execution,
            output_dir=Path(args.output),
        )
    except ImportRunError as exc:
        print("Import FAILED: {}".format(exc), file=sys.stderr)
        return 1

    print("Import passed.")
    print("run_id={}".format(run["run_id"]))
    print("response_sha256={}".format(run["response_sha256"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
