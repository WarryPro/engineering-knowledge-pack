#!/usr/bin/env python3
"""Deterministic evaluation report generation (no product claims)."""

from __future__ import annotations

import argparse
import json
import re
import statistics
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

_SCRIPT_DIR = Path(__file__).resolve().parent
if str(_SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPT_DIR))

from eval_common import load_json, load_schema_validators, validate_against  # noqa: E402
from scoring_common import (  # noqa: E402
    MANDATORY_LIMITATIONS,
    ScoringError,
    dump_json_bytes,
    write_bytes,
    write_text,
)


class ReportError(ScoringError):
    pass


FORBIDDEN_CLAIM_PHRASES = (
    "ekp improves ai engineering",
    "ekp improves",
    "treatment is better overall",
)


def _contains_forbidden_claim(text: str) -> Optional[str]:
    lowered = text.lower()
    for phrase in FORBIDDEN_CLAIM_PHRASES:
        if phrase in lowered:
            return phrase
    # Ban affirmative universal-improvement headlines, not the explicit disclaimer.
    if re.search(r"\buniversal improvement\b(?! percentage)", lowered):
        return "universal improvement"
    return None


def load_consensus_artifacts(consensus_dir: Path) -> List[Dict[str, Any]]:
    if not consensus_dir.is_dir():
        raise ReportError("consensus directory missing: {}".format(consensus_dir))
    rows = []
    for path in sorted(consensus_dir.glob("*.json"), key=lambda p: p.name):
        data = load_json(path)
        if isinstance(data, dict) and data.get("pair_id"):
            rows.append(data)
    rows.sort(
        key=lambda r: (
            r.get("scenario_id") or "",
            int(r.get("replicate_index") or 0),
            r.get("pair_id") or "",
        )
    )
    return rows


def outcome_counts(rows: Sequence[Dict[str, Any]]) -> Dict[str, int]:
    counts = {"improved": 0, "tied": 0, "regressed": 0, "disputed": 0}
    for row in rows:
        outcome = row.get("outcome")
        if outcome not in counts:
            raise ReportError("unknown outcome {!r}".format(outcome))
        counts[outcome] += 1
    return counts


def scenario_distributions(rows: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    by_scenario: Dict[str, Dict[str, int]] = {}
    for row in rows:
        sid = row["scenario_id"]
        bucket = by_scenario.setdefault(
            sid, {"improved": 0, "tied": 0, "regressed": 0, "disputed": 0}
        )
        bucket[row["outcome"]] += 1
    out = []
    for sid in sorted(by_scenario):
        item = {"scenario_id": sid}
        item.update(by_scenario[sid])
        out.append(item)
    return out


def _collect_cf_occurrences(
    rows: Sequence[Dict[str, Any]],
) -> Tuple[Dict[str, int], Dict[str, int], int]:
    baseline: Dict[str, int] = defaultdict(int)
    treatment: Dict[str, int] = defaultdict(int)
    disagreements = 0
    for row in rows:
        assignment = row.get("assignment") or {}
        cfs = row.get("critical_failures") or {}
        if not row.get("critical_failure_agreement", True):
            disagreements += 1
        for side in ("A", "B"):
            condition = (assignment.get(side) or {}).get("condition")
            per_rater = cfs.get(side) or {}
            # Use union of CF IDs across raters for occurrence accounting.
            ids = set()
            for values in per_rater.values():
                ids.update(values or [])
            for cf_id in sorted(ids):
                if condition == "baseline":
                    baseline[cf_id] += 1
                elif condition == "treatment":
                    treatment[cf_id] += 1
    return dict(sorted(baseline.items())), dict(sorted(treatment.items())), disagreements


def dimension_summaries(rows: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    values: Dict[str, List[int]] = defaultdict(list)
    for row in rows:
        for rater_block in row.get("dimension_deltas") or []:
            for dim, delta in sorted((rater_block.get("deltas") or {}).items()):
                values[dim].append(int(delta))
    summaries = []
    for dim in sorted(values):
        series = values[dim]
        dist: Dict[str, int] = defaultdict(int)
        for v in series:
            dist[str(v)] += 1
        summaries.append(
            {
                "dimension": dim,
                "observations": len(series),
                "median_delta": statistics.median(series) if series else None,
                "delta_distribution": dict(sorted(dist.items(), key=lambda kv: int(kv[0]))),
            }
        )
    return summaries


def execution_order_audit(rows: Sequence[Dict[str, Any]]) -> Dict[str, int]:
    counts = {
        "baseline-first": 0,
        "treatment-first": 0,
        "same": 0,
        "unknown": 0,
    }
    for row in rows:
        order = row.get("executed_at_order") or "unknown"
        if order not in counts:
            order = "unknown"
        counts[order] += 1
    return counts


def build_report_summary(
    rows: Sequence[Dict[str, Any]],
    evaluation_id: str,
    ekp_version: str,
    ekp_commit: str,
    model_config_id: str,
    extra_limitations: Optional[Sequence[str]] = None,
) -> Dict[str, Any]:
    outcomes = outcome_counts(rows)
    limitations = list(MANDATORY_LIMITATIONS)
    if extra_limitations:
        for item in extra_limitations:
            if item not in limitations:
                limitations.append(item)
    scenarios = sorted({r["scenario_id"] for r in rows})
    summary = {
        "evaluation_id": evaluation_id,
        "ekp_version": ekp_version,
        "ekp_commit": ekp_commit,
        "model_config_id": model_config_id,
        "scenario_count": len(scenarios),
        "pair_count": len(rows),
        "outcomes": outcomes,
        "limitations": limitations,
        "scenario_distributions": scenario_distributions(rows),
    }
    return summary


def render_report_markdown(
    rows: Sequence[Dict[str, Any]],
    summary: Dict[str, Any],
) -> str:
    outcomes = summary["outcomes"]
    lines: List[str] = []
    lines.append("# Evaluation report")
    lines.append("")
    lines.append("Evaluation ID: {}".format(summary["evaluation_id"]))
    lines.append("EKP version: {}".format(summary["ekp_version"]))
    lines.append("EKP commit: {}".format(summary["ekp_commit"]))
    lines.append("Model config: {}".format(summary["model_config_id"]))
    lines.append("")
    lines.append("## Primary paired outcomes")
    lines.append("")
    lines.append(
        "- improved: {improved}\n- tied: {tied}\n- regressed: {regressed}\n- disputed: {disputed}".format(
            **outcomes
        )
    )
    lines.append("")
    lines.append("No universal improvement percentage is reported.")
    lines.append("No scenario-level winner is derived from majority voting.")
    lines.append("")
    lines.append("## Per-scenario replicate distribution")
    lines.append("")
    by_scenario: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for row in rows:
        by_scenario[row["scenario_id"]].append(row)
    for sid in sorted(by_scenario):
        lines.append("### {}".format(sid))
        lines.append("")
        for row in sorted(by_scenario[sid], key=lambda r: int(r["replicate_index"])):
            lines.append(
                "- replicate {}: **{}**".format(row["replicate_index"], row["outcome"])
            )
        dist = next(
            d for d in summary["scenario_distributions"] if d["scenario_id"] == sid
        )
        lines.append(
            "- distribution: I={improved} T={tied} R={regressed} D={disputed}".format(
                **dist
            )
        )
        lines.append("")

    lines.append("## Regressions")
    lines.append("")
    regs = [r for r in rows if r["outcome"] == "regressed"]
    if not regs:
        lines.append("None.")
        lines.append("")
    else:
        for row in regs:
            lines.append(
                "- {scenario_id} replicate {replicate_index} pair `{pair_id}`".format(
                    **row
                )
            )
            lines.append(
                "  - A={}/{} B={}/{}".format(
                    row["assignment"]["A"]["condition"],
                    row["assignment"]["A"]["response_sha256"][:12],
                    row["assignment"]["B"]["condition"],
                    row["assignment"]["B"]["response_sha256"][:12],
                )
            )
            for pref in row.get("revealed_preferences") or []:
                lines.append(
                    "  - {}: blind {} → {}".format(
                        pref["rater_alias"],
                        pref["blind_preference"],
                        pref["revealed_preference"],
                    )
                )
            for block in row.get("dimension_deltas") or []:
                lines.append(
                    "  - deltas {}: {}".format(block["rater_alias"], block.get("deltas"))
                )
            lines.append(
                "  - critical failures: {}".format(row.get("critical_failures"))
            )
        lines.append("")

    lines.append("## Disputes")
    lines.append("")
    disputes = [r for r in rows if r["outcome"] == "disputed"]
    if not disputes:
        lines.append("None.")
        lines.append("")
    else:
        for row in disputes:
            lines.append(
                "- {scenario_id} replicate {replicate_index} pair `{pair_id}` "
                "reason={dispute_reason}".format(**row)
            )
            for pref in row.get("revealed_preferences") or []:
                lines.append(
                    "  - {}: blind {} → {}".format(
                        pref["rater_alias"],
                        pref["blind_preference"],
                        pref["revealed_preference"],
                    )
                )
        lines.append("")

    base_cf, treat_cf, cf_disagreements = _collect_cf_occurrences(rows)
    lines.append("## Critical failures")
    lines.append("")
    lines.append("Baseline occurrences: {}".format(base_cf or "{}"))
    lines.append("Treatment occurrences: {}".format(treat_cf or "{}"))
    lines.append("Pairs with CF rater disagreement: {}".format(cf_disagreements))
    lines.append("")

    lines.append("## Dimension summaries (treatment − baseline)")
    lines.append("")
    for item in dimension_summaries(rows):
        lines.append(
            "- {dimension}: n={observations}, median_delta={median_delta}, "
            "distribution={delta_distribution}".format(**item)
        )
    lines.append("")

    lines.append("## Execution-order audit")
    lines.append("")
    for key, value in sorted(execution_order_audit(rows).items()):
        lines.append("- {}: {}".format(key, value))
    lines.append("")
    lines.append(
        "Execution order is independent of A/B display assignment."
    )
    lines.append("")

    lines.append("## Limitations")
    lines.append("")
    for item in summary["limitations"]:
        lines.append("- {}".format(item))
    lines.append("")
    lines.append(
        "This report presents evidence counts only. "
        "It does not authorize product improvement claims."
    )
    lines.append("")
    text = "\n".join(lines)
    bad = _contains_forbidden_claim(text)
    if bad:
        raise ReportError("forbidden auto-claim phrase detected: {!r}".format(bad))
    if "scenario winner" in text.lower() and "no scenario-level winner" not in text.lower():
        raise ReportError("report must not invent scenario winners")
    return text


def generate_report(
    consensus_dir: Path,
    output_dir: Path,
    evaluation_id: str,
    ekp_version: str,
    ekp_commit: str,
    model_config_id: str,
    require_complete: bool = False,
    expected_pair_count: Optional[int] = None,
    extra_limitations: Optional[Sequence[str]] = None,
) -> Tuple[bytes, bytes, Dict[str, Any]]:
    rows = load_consensus_artifacts(consensus_dir)
    if require_complete and expected_pair_count is not None:
        if len(rows) != expected_pair_count:
            raise ReportError(
                "evidence-grade report requires {} pairs, found {}".format(
                    expected_pair_count, len(rows)
                )
            )
    if not rows:
        raise ReportError("no consensus artifacts found")

    summary = build_report_summary(
        rows,
        evaluation_id=evaluation_id,
        ekp_version=ekp_version,
        ekp_commit=ekp_commit,
        model_config_id=model_config_id,
        extra_limitations=extra_limitations,
    )
    validators = load_schema_validators()
    schema_errors = validate_against(
        validators["report-summary"], summary, "report-summary"
    )
    if schema_errors:
        raise ReportError("; ".join(schema_errors))

    md = render_report_markdown(rows, summary)
    md_bytes = md.encode("utf-8")
    json_bytes = dump_json_bytes(summary)
    write_bytes(output_dir / "report.md", md_bytes)
    write_bytes(output_dir / "report-summary.json", json_bytes)
    return md_bytes, json_bytes, summary


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Generate deterministic evaluation report")
    parser.add_argument("--consensus", required=True, help="Directory of consensus JSON files")
    parser.add_argument("--output", required=True)
    parser.add_argument("--evaluation-id", required=True)
    parser.add_argument("--ekp-version", required=True)
    parser.add_argument("--ekp-commit", required=True)
    parser.add_argument("--model-config-id", required=True)
    parser.add_argument(
        "--require-complete",
        action="store_true",
        help="Evidence-grade gate: require expected pair inventory",
    )
    parser.add_argument(
        "--expected-pairs",
        type=int,
        default=None,
        help="When --require-complete, exact pair count required",
    )
    args = parser.parse_args(list(argv) if argv is not None else None)
    try:
        md_bytes, json_bytes, summary = generate_report(
            consensus_dir=Path(args.consensus),
            output_dir=Path(args.output),
            evaluation_id=args.evaluation_id,
            ekp_version=args.ekp_version,
            ekp_commit=args.ekp_commit,
            model_config_id=args.model_config_id,
            require_complete=args.require_complete,
            expected_pair_count=args.expected_pairs,
        )
    except ReportError as exc:
        print("Report failed: {}".format(exc.message), file=sys.stderr)
        return 1
    print("Report written (md={} bytes, json={} bytes)".format(len(md_bytes), len(json_bytes)))
    print(
        "outcomes improved={improved} tied={tied} regressed={regressed} disputed={disputed}".format(
            **summary["outcomes"]
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
