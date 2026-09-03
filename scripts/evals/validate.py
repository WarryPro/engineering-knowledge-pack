#!/usr/bin/env python3
"""Offline structural validator for EKP evaluation artifacts.

No model execution. No network calls. Exit nonzero on failure.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

_SCRIPT_DIR = Path(__file__).resolve().parent
if str(_SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPT_DIR))

from eval_common import (  # noqa: E402
    CORE_DIMENSIONS,
    EMPTY_BYTES_SHA256,
    REPO_ROOT,
    SCHEMA_FILES,
    collect_forbidden_metadata_keys,
    find_concept_ids,
    iter_scenario_dirs,
    load_json,
    load_schema_validators,
    load_yaml,
    profile_exists_and_resolves,
    resolve_under,
    sha256_file,
    validate_against,
)


class EvalValidator(object):
    def __init__(
        self,
        repo_root: Path = REPO_ROOT,
        evals_root: Optional[Path] = None,
    ) -> None:
        self.repo_root = Path(repo_root)
        self.evals_root = (
            Path(evals_root) if evals_root is not None else self.repo_root / "evals"
        )
        self.schema_dir = self.evals_root / "schema"
        self.scenarios_dir = self.evals_root / "scenarios"
        self.shared_dir = self.evals_root / "shared"
        self.system_instruction = self.shared_dir / "system_instruction.md"
        self.evidence_dir = self.evals_root / "evidence"
        self.errors: List[str] = []
        self.validators = None
        self.scenario_count = 0

    def error(self, message: str) -> None:
        self.errors.append(message)

    def validate(self) -> int:
        self.errors = []
        self.scenario_count = 0
        self._validate_foundation()
        self._validate_scenarios()
        self._validate_optional_evidence()
        return 1 if self.errors else 0

    def _validate_foundation(self) -> None:
        if not self.evals_root.is_dir():
            self.error("missing evals/ directory")
            return
        if not self.schema_dir.is_dir():
            self.error("missing evals/schema/ directory")
            return
        for name in SCHEMA_FILES:
            path = self.schema_dir / name
            if not path.is_file():
                try:
                    rel = path.relative_to(self.repo_root)
                except ValueError:
                    rel = path
                self.error("missing schema: {}".format(rel))
        try:
            self.validators = load_schema_validators(self.schema_dir)
        except Exception as exc:
            self.error("schema load failed: {}".format(exc))
            self.validators = None

        if not self.system_instruction.is_file():
            self.error(
                "missing shared system instruction: {}".format(self.system_instruction)
            )
        else:
            text = self.system_instruction.read_text(encoding="utf-8").strip()
            if not text:
                self.error("shared system instruction is empty")
            leaked = find_concept_ids(text)
            if leaked:
                self.error(
                    "shared system instruction must not contain EKP concept IDs: {}".format(
                        ", ".join(leaked)
                    )
                )

        if not self.scenarios_dir.is_dir():
            self.error("missing evals/scenarios/ directory")

    def _validate_scenarios(self) -> None:
        if self.validators is None or not self.scenarios_dir.is_dir():
            return

        seen_ids: Set[str] = set()
        for scenario_dir in iter_scenario_dirs(self.scenarios_dir):
            self.scenario_count += 1
            self._validate_one_scenario(scenario_dir, seen_ids)

    def _validate_one_scenario(self, scenario_dir: Path, seen_ids: Set[str]) -> None:
        scenario_file = scenario_dir / "scenario.yaml"
        label = "scenario {}".format(scenario_dir.name)
        if not scenario_file.is_file():
            self.error("{}: missing scenario.yaml".format(label))
            return

        try:
            data = load_yaml(scenario_file)
        except Exception as exc:
            self.error("{}: invalid YAML: {}".format(label, exc))
            return

        if not isinstance(data, dict):
            self.error("{}: scenario.yaml must be a mapping".format(label))
            return

        self.errors.extend(validate_against(self.validators["scenario"], data, label))

        scenario_id = data.get("id")
        if isinstance(scenario_id, str):
            if scenario_id != scenario_dir.name:
                self.error(
                    "{}: directory name {!r} must equal scenario id {!r}".format(
                        label, scenario_dir.name, scenario_id
                    )
                )
            if scenario_id in seen_ids:
                self.error("duplicate scenario id: {!r}".format(scenario_id))
            seen_ids.add(scenario_id)

        profile = data.get("profile")
        if isinstance(profile, str):
            profile_error = profile_exists_and_resolves(profile, self.repo_root)
            if profile_error:
                self.error("{}: {}".format(label, profile_error))

        prompt_rel = data.get("prompt_file")
        rubric_rel = data.get("rubric_file")

        if isinstance(prompt_rel, str):
            prompt_path, err = resolve_under(scenario_dir, prompt_rel, "prompt_file")
            if err:
                self.error("{}: {}".format(label, err))
            elif prompt_path is not None and not prompt_path.is_file():
                self.error("{}: prompt file not found: {}".format(label, prompt_rel))
            elif prompt_path is not None:
                prompt_text = prompt_path.read_text(encoding="utf-8")
                leaked = find_concept_ids(prompt_text)
                if leaked:
                    self.error(
                        "{}: participant prompt contains EKP concept ID(s): {}".format(
                            label, ", ".join(sorted(set(leaked)))
                        )
                    )

        if isinstance(rubric_rel, str):
            rubric_path, err = resolve_under(scenario_dir, rubric_rel, "rubric_file")
            if err:
                self.error("{}: {}".format(label, err))
            elif rubric_path is not None and not rubric_path.is_file():
                self.error("{}: rubric file not found: {}".format(label, rubric_rel))
            elif rubric_path is not None:
                self._validate_rubric(label, data, rubric_path)

        fixture = data.get("fixture", None)
        if fixture is not None:
            if not isinstance(fixture, str):
                self.error("{}: fixture must be a string path or null".format(label))
            else:
                fixture_path, err = resolve_under(scenario_dir, fixture, "fixture")
                if err:
                    self.error("{}: {}".format(label, err))
                elif fixture_path is not None and not fixture_path.exists():
                    self.error(
                        "{}: fixture path not found: {}".format(label, fixture)
                    )

        shared_ref = data.get("shared_system_instruction_ref")
        if isinstance(shared_ref, str):
            shared_path, err = resolve_under(
                self.evals_root, shared_ref, "shared_system_instruction_ref"
            )
            if err:
                self.error("{}: {}".format(label, err))
            elif shared_path is not None:
                try:
                    shared_path.relative_to(self.shared_dir.resolve())
                except ValueError:
                    self.error(
                        "{}: shared_system_instruction_ref must resolve under evals/shared/".format(
                            label
                        )
                    )
                if not shared_path.is_file():
                    self.error(
                        "{}: shared system instruction not found: {}".format(
                            label, shared_ref
                        )
                    )

    def _validate_rubric(
        self, label: str, scenario: Dict[str, Any], rubric_path: Path
    ) -> None:
        try:
            rubric = load_yaml(rubric_path)
        except Exception as exc:
            self.error("{}: invalid rubric YAML: {}".format(label, exc))
            return
        if not isinstance(rubric, dict):
            self.error("{}: rubric must be a mapping".format(label))
            return

        self.errors.extend(
            validate_against(self.validators["rubric"], rubric, "{} rubric".format(label))
        )

        if rubric.get("scenario_id") != scenario.get("id"):
            self.error(
                "{}: rubric scenario_id {!r} does not match scenario id {!r}".format(
                    label, rubric.get("scenario_id"), scenario.get("id")
                )
            )
        if rubric.get("scenario_version") != scenario.get("version"):
            self.error(
                "{}: rubric scenario_version {!r} does not match scenario version {!r}".format(
                    label, rubric.get("scenario_version"), scenario.get("version")
                )
            )

        dimensions = rubric.get("dimensions") or []
        if isinstance(dimensions, list):
            for dim in dimensions:
                if dim not in CORE_DIMENSIONS:
                    self.error("{}: unknown rubric dimension {!r}".format(label, dim))

        cf_ids = []
        for item in rubric.get("critical_failures") or []:
            if isinstance(item, dict) and "id" in item:
                cf_ids.append(item["id"])
        if len(cf_ids) != len(set(cf_ids)):
            self.error("{}: duplicate critical-failure IDs".format(label))

    def _validate_optional_evidence(self) -> None:
        if self.validators is None or not self.evidence_dir.is_dir():
            return

        for path in sorted(self.evidence_dir.rglob("*")):
            if not path.is_file():
                continue
            if path.suffix not in {".json", ".yaml", ".yml"}:
                continue
            rel = path.relative_to(self.evals_root).as_posix()
            try:
                if path.suffix == ".json":
                    data = load_json(path)
                else:
                    data = load_yaml(path)
            except Exception as exc:
                self.error("evidence {}: invalid document: {}".format(rel, exc))
                continue
            if not isinstance(data, dict):
                continue

            if "response_file" in data and "condition" in data:
                self._validate_run_record(rel, data, path)
            elif "pairwise_preference" in data and "response_a" in data:
                self._validate_score_sheet(rel, data)
            elif "outcomes" in data and "evaluation_id" in data:
                self._validate_report_summary(rel, data)

    def _safe_response_path(
        self, label: str, base: Path, response_file: str
    ) -> Optional[Path]:
        from pathlib import Path as _Path

        if _Path(response_file).is_absolute() or ".." in _Path(response_file).parts:
            self.error("{}: response_file must be a safe relative path".format(label))
            return None
        for root in (base, self.evidence_dir):
            resolved_path, err = resolve_under(root, response_file, "response_file")
            if err is None and resolved_path is not None and resolved_path.is_file():
                return resolved_path
        self.error("{}: response_file not found: {}".format(label, response_file))
        return None

    def _validate_run_record(self, label: str, data: Any, path: Path) -> None:
        if not isinstance(data, dict):
            self.error("{}: run record must be a mapping".format(label))
            return
        self.errors.extend(validate_against(self.validators["run"], data, label))

        for key_path in collect_forbidden_metadata_keys(data):
            self.error("{}: forbidden metadata key: {}".format(label, key_path))

        condition = data.get("condition")
        context_hash = data.get("context_sha256")
        if condition == "baseline" and context_hash != EMPTY_BYTES_SHA256:
            self.error(
                "{}: baseline context_sha256 must be SHA-256 of empty bytes ({})".format(
                    label, EMPTY_BYTES_SHA256
                )
            )

        response_file = data.get("response_file")
        response_sha = data.get("response_sha256")
        if isinstance(response_file, str):
            resolved = self._safe_response_path(label, path.parent, response_file)
            if resolved is not None and isinstance(response_sha, str):
                actual = sha256_file(resolved)
                if actual != response_sha:
                    self.error(
                        "{}: response_sha256 mismatch (expected {}, got {})".format(
                            label, response_sha, actual
                        )
                    )

    def _validate_score_sheet(self, label: str, data: Any) -> None:
        if not isinstance(data, dict):
            self.error("{}: score sheet must be a mapping".format(label))
            return

        for key in data.keys():
            if str(key).lower() in {
                "baseline",
                "treatment",
                "condition",
                "ekp-enabled",
                "ekp_enabled",
            }:
                self.error(
                    "{}: score sheet must not contain condition key {!r}".format(
                        label, key
                    )
                )

        self.errors.extend(validate_against(self.validators["score-sheet"], data, label))

        for side in ("response_a", "response_b"):
            response = data.get(side)
            if not isinstance(response, dict):
                continue
            scores = response.get("dimension_scores") or {}
            if isinstance(scores, dict):
                for dim, value in scores.items():
                    if dim not in CORE_DIMENSIONS:
                        self.error("{}: unknown dimension {!r}".format(label, dim))
                    if value is not None and value not in (0, 1, 2, 3):
                        self.error(
                            "{}: dimension {!r} score must be 0..3, got {!r}".format(
                                label, dim, value
                            )
                        )

    def _validate_report_summary(self, label: str, data: Any) -> None:
        if not isinstance(data, dict):
            self.error("{}: report summary must be a mapping".format(label))
            return
        self.errors.extend(
            validate_against(self.validators["report-summary"], data, label)
        )


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Validate EKP evaluation artifacts")
    parser.add_argument(
        "--repo-root",
        default=str(REPO_ROOT),
        help="Repository root (default: detected from script location)",
    )
    args = parser.parse_args(argv)

    validator = EvalValidator(repo_root=Path(args.repo_root))
    status = validator.validate()

    if validator.errors:
        print("Evaluation validation FAILED.")
        for message in validator.errors:
            print("  ERROR: {}".format(message))
        print("Scenarios: {}".format(validator.scenario_count))
        return 1

    print("Evaluation validation passed.")
    print("Scenarios: {}".format(validator.scenario_count))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
