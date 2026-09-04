#!/usr/bin/env python3
"""Import and validate completed blind score sheets (byte-preserving)."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

import yaml

_SCRIPT_DIR = Path(__file__).resolve().parent
if str(_SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPT_DIR))

from eval_common import (  # noqa: E402
    load_json,
    load_schema_validators,
    sha256_bytes,
    validate_against,
)
from scoring_common import (  # noqa: E402
    ScoringError,
    load_rubric_for_scenario,
    load_synthetic_rubric,
    rubric_cf_ids,
    rubric_dimensions,
    validate_preference_against_critical_failures,
    write_bytes,
    write_json,
)


class ScoreImportError(ScoringError):
    pass


def load_mapping(path: Path) -> Dict[str, Any]:
    data = load_json(path)
    if not isinstance(data, dict) or "pairs" not in data:
        raise ScoreImportError("invalid mapping document")
    return data


def mapping_pair_by_id(mapping: Dict[str, Any], pair_id: str) -> Dict[str, Any]:
    for pair in mapping.get("pairs") or []:
        if pair.get("pair_id") == pair_id:
            return pair
    raise ScoreImportError("pair_id {!r} not found in mapping".format(pair_id))


def load_score_document(path: Path) -> tuple[Dict[str, Any], bytes]:
    raw = path.read_bytes()
    text = raw.decode("utf-8")
    if path.suffix.lower() in (".yaml", ".yml"):
        data = yaml.safe_load(text)
    else:
        data = json.loads(text)
    if not isinstance(data, dict):
        raise ScoreImportError("score sheet must be an object")
    if data.get("_template") is True:
        raise ScoreImportError("refusing to import unfinished score template")
    return data, raw


def _validate_response_block(
    label: str,
    block: Dict[str, Any],
    expected_sha: str,
    expected_dims: Sequence[str],
    allowed_cf: Sequence[str],
) -> List[str]:
    errors: List[str] = []
    if not isinstance(block, dict):
        return ["{} must be an object".format(label)]
    if block.get("response_sha256") != expected_sha:
        errors.append(
            "{} response_sha256 mismatch (expected {}, got {})".format(
                label, expected_sha, block.get("response_sha256")
            )
        )
    dims = block.get("dimension_scores")
    if not isinstance(dims, dict):
        errors.append("{} dimension_scores must be an object".format(label))
        return errors
    expected = set(expected_dims)
    actual = set(dims.keys())
    missing = sorted(expected - actual)
    extra = sorted(actual - expected)
    if missing:
        errors.append("{} missing dimensions: {}".format(label, ", ".join(missing)))
    if extra:
        errors.append("{} extra dimensions: {}".format(label, ", ".join(extra)))
    for key, value in dims.items():
        if value is None or not isinstance(value, int) or value < 0 or value > 3:
            errors.append("{} dimension {} must be integer 0..3".format(label, key))
    cfs = block.get("critical_failures") or []
    if not isinstance(cfs, list):
        errors.append("{} critical_failures must be an array".format(label))
    else:
        allowed = set(allowed_cf)
        for cf in cfs:
            if cf not in allowed:
                errors.append("{} unknown critical failure id {!r}".format(label, cf))
    return errors


def validate_score_sheet(
    sheet: Dict[str, Any],
    mapping: Dict[str, Any],
    rubric: Dict[str, Any],
    rubric_sha: str,
    validators=None,
) -> List[str]:
    errors: List[str] = []
    validators = validators or load_schema_validators()
    errors.extend(validate_against(validators["score-sheet"], sheet, "score-sheet"))

    if sheet.get("blinded") is not True:
        errors.append("blinded must be true for reference workflow")

    # Condition leakage keys rejected by schema additionalProperties, but guard nested.
    for leak in ("condition", "baseline", "treatment"):
        if leak in sheet:
            errors.append("score sheet must not contain {!r}".format(leak))

    try:
        pair = mapping_pair_by_id(mapping, sheet.get("pair_id"))
    except ScoreImportError as exc:
        errors.append(exc.message)
        return errors

    if sheet.get("scenario_id") != pair.get("scenario_id"):
        errors.append("scenario_id does not match mapping pair")
    if sheet.get("scenario_version") != pair.get("scenario_version"):
        errors.append("scenario_version does not match mapping pair")
    if int(sheet.get("replicate_index") or -1) != int(pair.get("replicate_index")):
        errors.append("replicate_index does not match mapping pair")
    if sheet.get("rubric_sha256") != rubric_sha:
        errors.append(
            "rubric_sha256 mismatch (expected {}, got {})".format(
                rubric_sha, sheet.get("rubric_sha256")
            )
        )
    if sheet.get("rubric_version") != rubric.get("version"):
        errors.append("rubric_version does not match rubric artifact")

    dims = rubric_dimensions(rubric)
    allowed_cf = rubric_cf_ids(rubric)
    assignment = pair.get("assignment") or {}
    expected_a = (assignment.get("A") or {}).get("response_sha256")
    expected_b = (assignment.get("B") or {}).get("response_sha256")
    errors.extend(
        _validate_response_block(
            "response_a", sheet.get("response_a") or {}, expected_a, dims, allowed_cf
        )
    )
    errors.extend(
        _validate_response_block(
            "response_b", sheet.get("response_b") or {}, expected_b, dims, allowed_cf
        )
    )

    pref = sheet.get("pairwise_preference")
    cf_a = (sheet.get("response_a") or {}).get("critical_failures") or []
    cf_b = (sheet.get("response_b") or {}).get("critical_failures") or []
    pref_err = validate_preference_against_critical_failures(pref, cf_a, cf_b)
    if pref_err:
        errors.append(pref_err)
    return errors


def import_score_sheet(
    score_path: Path,
    mapping_path: Path,
    output_dir: Path,
    scenarios_dir: Optional[Path] = None,
    rubric_path: Optional[Path] = None,
) -> Dict[str, Any]:
    mapping = load_mapping(mapping_path)
    sheet, raw = load_score_document(score_path)
    pair = mapping_pair_by_id(mapping, sheet.get("pair_id"))
    scenario_id = pair["scenario_id"]

    if rubric_path is not None:
        rubric, _, rubric_sha = load_synthetic_rubric(rubric_path)
    else:
        from eval_common import SCENARIOS_DIR as DEFAULT_SCENARIOS

        rubric, _, rubric_sha = load_rubric_for_scenario(
            scenario_id, scenarios_dir=scenarios_dir or DEFAULT_SCENARIOS
        )

    errors = validate_score_sheet(sheet, mapping, rubric, rubric_sha)
    if errors:
        raise ScoreImportError("; ".join(errors))

    pair_dir = output_dir / "scores" / pair["pair_id"]
    pair_dir.mkdir(parents=True, exist_ok=True)
    alias = sheet["rater_alias"]
    dest = pair_dir / "{}{}".format(alias, score_path.suffix.lower() or ".yaml")
    index_path = pair_dir / "index.json"
    index = {"pair_id": pair["pair_id"], "scores": {}}
    if index_path.is_file():
        index = load_json(index_path)
    if alias in (index.get("scores") or {}):
        raise ScoreImportError(
            "duplicate rater alias {!r} already imported for pair {}".format(
                alias, pair["pair_id"]
            )
        )

    write_bytes(dest, raw)
    sheet_sha = sha256_bytes(raw)
    index.setdefault("scores", {})[alias] = {
        "score_id": sheet["score_id"],
        "path": dest.name,
        "score_sheet_sha256": sheet_sha,
        "rater_alias": alias,
    }
    write_json(index_path, index)
    return {
        "pair_id": pair["pair_id"],
        "rater_alias": alias,
        "score_id": sheet["score_id"],
        "score_sheet_sha256": sheet_sha,
        "path": str(dest),
    }


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Import a completed blind score sheet")
    parser.add_argument("--score", required=True, help="Completed score sheet YAML/JSON")
    parser.add_argument("--mapping", required=True, help="Operator-private mapping.json")
    parser.add_argument("--output", required=True, help="Imported scores output directory")
    parser.add_argument("--scenarios-dir", default=None)
    parser.add_argument("--rubric", default=None, help="Override rubric path (synthetic tests)")
    args = parser.parse_args(list(argv) if argv is not None else None)
    try:
        result = import_score_sheet(
            score_path=Path(args.score),
            mapping_path=Path(args.mapping),
            output_dir=Path(args.output),
            scenarios_dir=Path(args.scenarios_dir) if args.scenarios_dir else None,
            rubric_path=Path(args.rubric) if args.rubric else None,
        )
    except ScoreImportError as exc:
        print("Score import failed: {}".format(exc.message), file=sys.stderr)
        return 1
    print("Imported score {} ({})".format(result["score_id"], result["score_sheet_sha256"][:12]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
