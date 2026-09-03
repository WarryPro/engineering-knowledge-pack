#!/usr/bin/env python3
"""Prepare deterministic baseline/treatment evaluation request packages.

No model execution. Generated packages default to dist/evals/prepared/ (gitignored).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

_SCRIPT_DIR = Path(__file__).resolve().parent
if str(_SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPT_DIR))

from context import (  # noqa: E402
    RENDERER_VERSION,
    ContextRenderError,
    build_treatment_units,
    empty_context_bytes,
    empty_context_sha256,
    normalize_newlines,
    render_context_markdown,
    units_manifest,
)
from eval_common import (  # noqa: E402
    EVALS_ROOT,
    REPO_ROOT,
    SCENARIOS_DIR,
    SYSTEM_INSTRUCTION_PATH,
    iter_scenario_dirs,
    load_yaml,
    resolve_under,
    sha256_bytes,
    sha256_file,
)


class PrepareError(Exception):
    pass


def resolve_ekp_commit(repo_root: Path) -> str:
    try:
        out = subprocess.check_output(
            ["git", "rev-parse", "HEAD"],
            cwd=str(repo_root),
            stderr=subprocess.STDOUT,
            text=True,
        ).strip()
    except (subprocess.CalledProcessError, FileNotFoundError) as exc:
        raise PrepareError("Cannot determine repository commit identity: {}".format(exc))
    if len(out) != 40 or any(c not in "0123456789abcdef" for c in out):
        raise PrepareError("Unexpected git HEAD identity: {!r}".format(out))
    return out


def resolve_ekp_version(repo_root: Path) -> str:
    # Prefer installed/source package mechanism when available.
    try:
        sys.path.insert(0, str(repo_root / "src"))
        from ekp.version import get_version  # type: ignore

        return get_version()
    except Exception:
        text = (repo_root / "pyproject.toml").read_text(encoding="utf-8")
        for line in text.splitlines():
            if line.strip().startswith("version"):
                return line.split("=", 1)[1].strip().strip('"').strip("'")
        raise PrepareError("Cannot determine EKP version from pyproject.toml")


def serialize_participant(prompt_text: str, fixture_files: List[Tuple[str, str]]) -> str:
    parts = ["# Task", "", normalize_newlines(prompt_text).rstrip(), "", "# Project Fixture", ""]
    if not fixture_files:
        parts.append("(no fixture files)")
        parts.append("")
    for rel, content in fixture_files:
        parts.append("===== BEGIN FILE: {} =====".format(rel))
        parts.append(normalize_newlines(content).rstrip("\n"))
        parts.append("===== END FILE: {} =====".format(rel))
        parts.append("")
    return "\n".join(parts).rstrip() + "\n"


def load_fixture_files(scenario_dir: Path, fixture_rel: Optional[str]) -> Tuple[List[Tuple[str, str]], List[Dict[str, Any]]]:
    if fixture_rel is None:
        return [], []
    fixture_root, err = resolve_under(scenario_dir, fixture_rel, "fixture")
    if err:
        raise PrepareError(err)
    if fixture_root is None or not fixture_root.exists():
        raise PrepareError("fixture path not found: {}".format(fixture_rel))
    if not fixture_root.is_dir():
        raise PrepareError("fixture must be a directory: {}".format(fixture_rel))

    files: List[Tuple[str, str]] = []
    audits: List[Dict[str, Any]] = []
    for path in sorted(fixture_root.rglob("*"), key=lambda p: p.relative_to(fixture_root).as_posix()):
        if not path.is_file():
            continue
        if path.is_symlink():
            target = path.resolve()
            try:
                target.relative_to(fixture_root.resolve())
            except ValueError:
                raise PrepareError("fixture symlink escapes fixture root: {}".format(path))
        rel = path.relative_to(fixture_root).as_posix()
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError as exc:
            raise PrepareError("non-UTF-8 fixture file {}: {}".format(rel, exc))
        text = normalize_newlines(text)
        data = text.encode("utf-8")
        files.append((rel, text))
        audits.append(
            {
                "path": rel,
                "sha256": sha256_bytes(data),
                "bytes": len(data),
            }
        )
    return files, audits


def load_active_scenarios(scenarios_dir: Path = SCENARIOS_DIR) -> List[Dict[str, Any]]:
    scenarios = []
    for scenario_dir in iter_scenario_dirs(scenarios_dir):
        data = load_yaml(scenario_dir / "scenario.yaml")
        if not isinstance(data, dict):
            raise PrepareError("invalid scenario.yaml in {}".format(scenario_dir.name))
        data["_dir"] = scenario_dir
        if data.get("status") == "active":
            scenarios.append(data)
    return scenarios


def write_bytes(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)


def write_text(path: Path, text: str) -> None:
    write_bytes(path, normalize_newlines(text).encode("utf-8"))


def prepare_scenario(
    scenario: Dict[str, Any],
    output_root: Path,
    repo_root: Path,
    ekp_commit: str,
    ekp_version: str,
    dist_dir: Optional[Path] = None,
) -> Dict[str, Any]:
    scenario_dir = Path(scenario["_dir"])
    scenario_id = scenario["id"]
    profile = scenario["profile"]
    prompt_rel = scenario["prompt_file"]
    prompt_path, err = resolve_under(scenario_dir, prompt_rel, "prompt_file")
    if err or prompt_path is None or not prompt_path.is_file():
        raise PrepareError("{}: prompt not found".format(scenario_id))
    prompt_text = normalize_newlines(prompt_path.read_text(encoding="utf-8"))

    fixture_files, fixture_audits = load_fixture_files(scenario_dir, scenario.get("fixture"))
    participant = serialize_participant(prompt_text, fixture_files)
    participant_bytes = participant.encode("utf-8")
    prompt_sha = sha256_bytes(participant_bytes)

    system_text = normalize_newlines(SYSTEM_INSTRUCTION_PATH.read_text(encoding="utf-8"))
    if not system_text.endswith("\n"):
        system_text += "\n"
    system_bytes = system_text.encode("utf-8")
    system_sha = sha256_bytes(system_bytes)

    treatment_units = build_treatment_units(repo_root, profile, dist_dir=dist_dir)
    treatment_context = render_context_markdown(treatment_units)
    treatment_bytes = treatment_context.encode("utf-8")
    treatment_sha = sha256_bytes(treatment_bytes)
    treatment_manifest = units_manifest(treatment_units)

    baseline_bytes = empty_context_bytes()
    baseline_sha = empty_context_sha256()
    baseline_manifest = units_manifest([])

    summary = {
        "scenario_id": scenario_id,
        "profile": profile,
        "prompt_sha256": prompt_sha,
        "system_instruction_sha256": system_sha,
        "baseline_context_sha256": baseline_sha,
        "treatment_context_sha256": treatment_sha,
        "participant_bytes": len(participant_bytes),
        "participant_chars": len(participant),
        "context_bytes": len(treatment_bytes),
        "context_chars": len(treatment_context),
        "semantic_unit_count": treatment_manifest["semantic_unit_count"],
    }

    for condition, ctx_bytes, ctx_sha, manifest in (
        ("baseline", baseline_bytes, baseline_sha, baseline_manifest),
        ("treatment", treatment_bytes, treatment_sha, treatment_manifest),
    ):
        package_dir = output_root / scenario_id / condition
        write_bytes(package_dir / "system_instruction.md", system_bytes)
        write_bytes(package_dir / "participant.md", participant_bytes)
        write_bytes(package_dir / "context.md", ctx_bytes)
        write_text(package_dir / "units.json", json.dumps(manifest, indent=2, sort_keys=True) + "\n")

        request = {
            "format_version": 1,
            "scenario_id": scenario_id,
            "scenario_version": scenario["version"],
            "profile": profile,
            "condition": condition,
            "ekp_version": ekp_version,
            "ekp_commit": ekp_commit,
            "renderer_version": RENDERER_VERSION,
            "system_instruction_sha256": system_sha,
            "prompt_sha256": prompt_sha,
            "context_sha256": ctx_sha,
            "system_instruction_bytes": len(system_bytes),
            "system_instruction_chars": len(system_text),
            "participant_bytes": len(participant_bytes),
            "participant_chars": len(participant),
            "context_bytes": len(ctx_bytes),
            "context_chars": 0 if not ctx_bytes else len(ctx_bytes.decode("utf-8")),
            "semantic_unit_count": manifest["semantic_unit_count"],
            "fixture_files": fixture_audits,
            "tools_enabled": False,
            "session_isolation": "fresh",
        }
        write_text(
            package_dir / "request.json",
            json.dumps(request, indent=2, sort_keys=True) + "\n",
        )

        # Pair fairness local check
        if condition == "treatment":
            if request["prompt_sha256"] != prompt_sha:
                raise PrepareError("internal prompt hash mismatch")
            if len(ctx_bytes) == 0:
                raise PrepareError("treatment context unexpectedly empty for {}".format(scenario_id))

    return summary


def prepare_all(
    output_root: Path,
    repo_root: Path = REPO_ROOT,
    scenario_id: Optional[str] = None,
    ekp_commit: Optional[str] = None,
    ekp_version: Optional[str] = None,
    dist_dir: Optional[Path] = None,
) -> List[Dict[str, Any]]:
    commit = ekp_commit or resolve_ekp_commit(repo_root)
    version = ekp_version or resolve_ekp_version(repo_root)
    scenarios = load_active_scenarios(repo_root / "evals" / "scenarios")
    if scenario_id:
        scenarios = [s for s in scenarios if s["id"] == scenario_id]
        if not scenarios:
            raise PrepareError("active scenario not found: {}".format(scenario_id))

    summaries = []
    for scenario in scenarios:
        summaries.append(
            prepare_scenario(
                scenario,
                output_root=output_root,
                repo_root=repo_root,
                ekp_commit=commit,
                ekp_version=version,
                dist_dir=dist_dir,
            )
        )
    return summaries


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Prepare EKP evaluation request packages")
    parser.add_argument("--all", action="store_true", help="Prepare all active scenarios")
    parser.add_argument("--scenario", help="Prepare one scenario id")
    parser.add_argument(
        "--output",
        default=str(REPO_ROOT / "dist" / "evals" / "prepared"),
        help="Output directory (default: dist/evals/prepared)",
    )
    parser.add_argument("--repo-root", default=str(REPO_ROOT))
    args = parser.parse_args(argv)

    if not args.all and not args.scenario:
        parser.error("specify --all or --scenario <id>")

    try:
        summaries = prepare_all(
            output_root=Path(args.output),
            repo_root=Path(args.repo_root),
            scenario_id=None if args.all else args.scenario,
        )
    except (PrepareError, ContextRenderError) as exc:
        print("Preparation FAILED: {}".format(exc), file=sys.stderr)
        return 1

    print("Evaluation preparation passed.")
    print("Scenarios: {}".format(len(summaries)))
    print("Packages: {}".format(len(summaries) * 2))
    for row in summaries:
        print(
            "- {scenario_id} profile={profile} context_bytes={context_bytes} units={semantic_unit_count}".format(
                **row
            )
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
