"""Selection-equivalent, adapter-neutral evaluation context renderer.

Renderer version 1. Reuses profile resolution + select_manifest_rules + extract_*.
Does not import Cursor writers or activation metadata.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from eval_common import EMPTY_BYTES_SHA256, REPO_ROOT, sha256_bytes

RENDERER_VERSION = 1

ORCHESTRATOR_PATH = "knowledge/ai/ai-assisted-development.md"
FOUNDATION_PATH = "knowledge/engineering/engineering-principles.md"

PRINCIPLE_ORDER = [
    "EKP-P01",
    "EKP-P02",
    "EKP-P03",
    "EKP-P04",
    "EKP-P05",
    "EKP-P06",
    "EKP-P07",
    "EKP-P08",
    "EKP-P09",
    "EKP-P10",
]

BLOCKING_TOKENS = ("block", "hard block")


class ContextRenderError(Exception):
    """Deterministic preparation/render failure."""


@dataclass
class SemanticUnit:
    unit_id: str
    unit_type: str  # foundation-summary | foundation-principle | decision-flow | selected-concept
    source_document: str
    concept_id: Optional[str] = None
    title: str = ""
    body: str = ""
    audit: Dict[str, Any] = field(default_factory=dict)

    def to_manifest(self) -> Dict[str, Any]:
        row = {
            "unit_id": self.unit_id,
            "unit_type": self.unit_type,
            "source_document": self.source_document.replace("\\", "/"),
            "title": self.title,
        }
        if self.concept_id:
            row["concept_id"] = self.concept_id
        if self.audit:
            row["audit"] = self.audit
        return row


def _ensure_adapters_importable() -> None:
    adapters = str(REPO_ROOT / "scripts" / "adapters")
    if adapters not in sys.path:
        sys.path.insert(0, adapters)


def _load_adapters():
    _ensure_adapters_importable()
    from common.extract import (  # type: ignore
        CONCEPT_HEADING_RE,
        extract_concepts,
        extract_decision_flow,
    )
    from common.profile_loader import load_profile_by_name  # type: ignore
    from common.selection import (  # type: ignore
        load_generation_indexes,
        markdown_cache_for_profile,
        select_manifest_rules,
    )

    return {
        "CONCEPT_HEADING_RE": CONCEPT_HEADING_RE,
        "extract_concepts": extract_concepts,
        "extract_decision_flow": extract_decision_flow,
        "load_profile_by_name": load_profile_by_name,
        "load_generation_indexes": load_generation_indexes,
        "markdown_cache_for_profile": markdown_cache_for_profile,
        "select_manifest_rules": select_manifest_rules,
    }


def normalize_newlines(text: str) -> str:
    return text.replace("\r\n", "\n").replace("\r", "\n")


def require_indexes(dist_dir: Path) -> Tuple[dict, dict]:
    concept_path = dist_dir / "concept-index.json"
    manifest_path = dist_dir / "adapter-manifest.json"
    missing = [p.name for p in (concept_path, manifest_path) if not p.is_file()]
    if missing:
        raise ContextRenderError(
            "Missing generation indexes: {}. Run: python scripts/validate/validate.py --generate-index".format(
                ", ".join(missing)
            )
        )
    concept_index = json.loads(concept_path.read_text(encoding="utf-8"))
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    return concept_index, manifest


def _extract_summary_paragraph(markdown: str) -> str:
    match = re.search(r"^## Summary\s*$", markdown, re.MULTILINE)
    if not match:
        raise ContextRenderError("Foundation document missing ## Summary")
    rest = markdown[match.end() :]
    next_h2 = re.search(r"^##\s+", rest, re.MULTILINE)
    section = rest[: next_h2.start()] if next_h2 else rest
    for line in section.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("|"):
            continue
        if stripped.startswith("#"):
            continue
        return stripped
    raise ContextRenderError("Foundation Summary has no usable paragraph")


def _extract_principle_parts(markdown: str, concept_id: str, heading_re) -> Tuple[str, str]:
    for match in heading_re.finditer(markdown):
        if match.group(1) != concept_id:
            continue
        title = match.group(2).strip()
        body_start = match.end()
        next_match = heading_re.search(markdown, body_start)
        body_end = next_match.start() if next_match else len(markdown)
        body = markdown[body_start:body_end].strip()
        first_paragraph = ""
        for line in body.splitlines():
            stripped = line.strip()
            if not stripped:
                continue
            if stripped.startswith("- ") or stripped.startswith("**"):
                break
            first_paragraph = stripped
            break
        return title, first_paragraph
    raise ContextRenderError(
        "Foundation principle {} not found in {}".format(concept_id, FOUNDATION_PATH)
    )


def _blocking_rows(enforcement_rules: Optional[list]) -> List[Dict[str, str]]:
    rows = []
    for row in enforcement_rules or []:
        auto_apply = str(row.get("auto_apply", "")).lower()
        if not any(token in auto_apply for token in BLOCKING_TOKENS):
            continue
        rows.append(
            {
                "step": str(row.get("step", "")).strip(),
                "auto_apply": str(row.get("auto_apply", "")).strip(),
                "notes": str(row.get("notes", "")).strip(),
            }
        )
    return rows


def _format_flow_body(flow_text: str, blocking: List[Dict[str, str]]) -> str:
    lines = [line.rstrip() for line in normalize_newlines(flow_text).splitlines()]
    while lines and not lines[0].strip():
        lines.pop(0)
    while lines and not lines[-1].strip():
        lines.pop()
    parts = ["\n".join(lines)]
    if blocking:
        parts.append("")
        parts.append("Blocking constraints:")
        for row in blocking:
            note = row["notes"]
            if note:
                parts.append(
                    "- Step {} — {}. {}".format(row["step"], row["auto_apply"], note)
                )
            else:
                parts.append("- Step {} — {}.".format(row["step"], row["auto_apply"]))
    return "\n".join(parts).rstrip() + "\n"


def _format_concept_body(concept) -> str:
    chunks = []
    intent = (concept.intent or "").strip()
    if intent:
        chunks.append("Intent: {}".format(intent))
    rules = list(concept.rules or [])
    if rules:
        chunks.append("Rules:")
        for rule in rules:
            chunks.append("- {}".format(rule.strip()))
    good = (concept.good_examples or "").strip()
    if good:
        chunks.append("Good example: {}".format(good))
    bad = (concept.bad_examples or "").strip()
    if bad:
        chunks.append("Bad example: {}".format(bad))
    return "\n".join(chunks).rstrip() + ("\n" if chunks else "")


def build_treatment_units(
    repo_root: Path,
    profile_name: str,
    dist_dir: Optional[Path] = None,
) -> List[SemanticUnit]:
    """Build ordered, deduplicated semantic units for a profile."""
    api = _load_adapters()
    root = Path(repo_root)
    dist = Path(dist_dir) if dist_dir is not None else root / "dist"
    concept_index, manifest = require_indexes(dist)

    profile = api["load_profile_by_name"](profile_name, repo_root=root)
    knowledge_paths = list(profile.get("knowledge") or [])
    if not knowledge_paths:
        raise ContextRenderError("Profile {!r} resolved to empty knowledge".format(profile_name))
    if ORCHESTRATOR_PATH not in knowledge_paths:
        raise ContextRenderError(
            "Profile {!r} must include orchestrator document".format(profile_name)
        )

    get_markdown = api["markdown_cache_for_profile"](root, knowledge_paths)
    manifest_rules = api["select_manifest_rules"](
        manifest,
        knowledge_paths,
        profile.get("adapter_priorities") or ["high"],
    )

    # Extract per document once.
    docs: Dict[str, Dict[str, Any]] = {}
    for source_path in knowledge_paths:
        markdown = normalize_newlines(get_markdown(source_path))
        flow = api["extract_decision_flow"](markdown, source_path)
        concepts = api["extract_concepts"](markdown, source_path)
        by_id = {c.concept_id: c for c in concepts}
        docs[source_path] = {
            "markdown": markdown,
            "flow": flow,
            "by_id": by_id,
        }

    # Hard-fail if a selected concept is missing from extraction.
    selected_ids_by_source: Dict[str, List[str]] = {}
    selected_order: List[Tuple[str, str]] = []  # (source, concept_id) in manifest order
    for entry in manifest_rules:
        source_path = entry.get("source")
        concept_id = entry.get("concept")
        if not source_path or not concept_id:
            continue
        if source_path not in docs:
            raise ContextRenderError(
                "Selected concept {} references source not in profile knowledge: {}".format(
                    concept_id, source_path
                )
            )
        if concept_id not in docs[source_path]["by_id"]:
            raise ContextRenderError(
                "Selected concept {} missing from extract_concepts({})".format(
                    concept_id, source_path
                )
            )
        selected_ids_by_source.setdefault(source_path, []).append(concept_id)
        selected_order.append((source_path, concept_id))

    units: List[SemanticUnit] = []
    emitted_concepts = set()
    emitted_flows = set()

    # 1. Orchestrator decision flow
    orch = docs[ORCHESTRATOR_PATH]
    if orch["flow"] is None:
        raise ContextRenderError("Orchestrator document missing AI Decision Flow")
    blocking = _blocking_rows(orch["flow"].enforcement_rules)
    units.append(
        SemanticUnit(
            unit_id="flow:{}".format(ORCHESTRATOR_PATH),
            unit_type="decision-flow",
            source_document=ORCHESTRATOR_PATH,
            title=orch["flow"].title or "AI Decision Flow",
            body=_format_flow_body(orch["flow"].decision_flow, blocking),
            audit={"blocking_constraint_count": len(blocking), "role": "orchestrator"},
        )
    )
    emitted_flows.add(ORCHESTRATOR_PATH)

    # 2–3. Foundation summary + principles P01..P10
    if FOUNDATION_PATH in docs:
        foundation_md = docs[FOUNDATION_PATH]["markdown"]
        summary = _extract_summary_paragraph(foundation_md)
        units.append(
            SemanticUnit(
                unit_id="foundation:summary",
                unit_type="foundation-summary",
                source_document=FOUNDATION_PATH,
                title="Engineering Principles Summary",
                body=summary + "\n",
            )
        )
        for principle_id in PRINCIPLE_ORDER:
            title, paragraph = _extract_principle_parts(
                foundation_md, principle_id, api["CONCEPT_HEADING_RE"]
            )
            body_parts = [paragraph] if paragraph else []
            # Merge selected-concept detail if present and non-empty.
            selected = docs[FOUNDATION_PATH]["by_id"].get(principle_id)
            if selected is not None and principle_id in selected_ids_by_source.get(
                FOUNDATION_PATH, []
            ):
                detail = _format_concept_body(selected).strip()
                if detail:
                    body_parts.append(detail)
            body = "\n\n".join([p for p in body_parts if p]).rstrip() + "\n"
            units.append(
                SemanticUnit(
                    unit_id="principle:{}".format(principle_id),
                    unit_type="foundation-principle",
                    source_document=FOUNDATION_PATH,
                    concept_id=principle_id,
                    title=title,
                    body=body,
                )
            )
            emitted_concepts.add(principle_id)

    # 4. Remaining document decision flows in resolved knowledge order
    for source_path in knowledge_paths:
        if source_path in emitted_flows:
            continue
        flow = docs[source_path]["flow"]
        if flow is None:
            continue
        blocking = _blocking_rows(flow.enforcement_rules)
        units.append(
            SemanticUnit(
                unit_id="flow:{}".format(source_path),
                unit_type="decision-flow",
                source_document=source_path,
                title=flow.title or Path(source_path).stem,
                body=_format_flow_body(flow.decision_flow, blocking),
                audit={"blocking_constraint_count": len(blocking)},
            )
        )
        emitted_flows.add(source_path)

    # 5. Remaining selected concepts in select_manifest_rules order
    for source_path, concept_id in selected_order:
        if concept_id in emitted_concepts:
            continue
        concept = docs[source_path]["by_id"][concept_id]
        units.append(
            SemanticUnit(
                unit_id="concept:{}".format(concept_id),
                unit_type="selected-concept",
                source_document=source_path,
                concept_id=concept_id,
                title=concept.title,
                body=_format_concept_body(concept),
                audit={
                    "has_intent": bool((concept.intent or "").strip()),
                    "rule_count": len(concept.rules or []),
                },
            )
        )
        emitted_concepts.add(concept_id)

    # concept_index presence already enforced via require_indexes
    _ = concept_index
    return units


def render_context_markdown(units: List[SemanticUnit]) -> str:
    """Render model-visible Engineering Context from semantic units."""
    if not units:
        return ""
    parts = ["# Engineering Context", ""]
    for unit in units:
        parts.append("## {}".format(unit.title.strip() or unit.unit_id))
        parts.append("")
        body = unit.body.rstrip("\n")
        if body:
            parts.append(body)
            parts.append("")
    text = "\n".join(parts).rstrip() + "\n"
    return normalize_newlines(text)


def units_manifest(units: List[SemanticUnit]) -> Dict[str, Any]:
    return {
        "renderer_version": RENDERER_VERSION,
        "semantic_unit_count": len(units),
        "units": [u.to_manifest() for u in units],
    }


def context_sha256_from_bytes(data: bytes) -> str:
    return sha256_bytes(data)


def empty_context_bytes() -> bytes:
    return b""


def empty_context_sha256() -> str:
    return EMPTY_BYTES_SHA256
