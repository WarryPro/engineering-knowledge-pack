"""Concept namespace registry validation."""

import json
import re
from pathlib import Path

REGISTRY_PATH = Path(__file__).resolve().parents[3] / "schema" / "concept-namespaces.json"


def load_namespace_registry():
    # type: () -> dict
    with REGISTRY_PATH.open(encoding="utf-8") as handle:
        return json.load(handle)


def namespace_key_for_concept(concept_id):
    # type: (str) -> str
    if re.match(r"^EKP-P(0[1-9]|10)$", concept_id):
        return "EKP-P"
    match = re.match(r"^(EKP-[A-Z]{2})", concept_id)
    return match.group(1) if match else ""


def _concept_number(concept_id):
    # type: (str) -> int
    match = re.search(r"(\d+)$", concept_id)
    return int(match.group(1)) if match else 0


def validate_namespaces(nodes, registry=None):
    # type: (list, dict) -> tuple
    """N1-N4 namespace registry rules. Returns (errors, warnings)."""
    if registry is None:
        registry = load_namespace_registry()

    errors = []
    warnings = []

    for node in nodes:
        seen_in_doc = set()
        numbers_by_ns = {}  # type: dict

        for concept_id in node.concept_ids:
            ns_key = namespace_key_for_concept(concept_id)

            if ns_key not in registry:
                errors.append(
                    "[NAMESPACE] {}: unknown namespace for '{}'".format(node.path, concept_id)
                )
                continue

            ns_entry = registry[ns_key]
            if not re.match(ns_entry["format"], concept_id):
                errors.append(
                    "[NAMESPACE] {}: '{}' does not match format {}".format(
                        node.path, concept_id, ns_entry["format"]
                    )
                )

            if concept_id in seen_in_doc:
                errors.append(
                    "[NAMESPACE] {}: duplicate concept_id '{}' in document".format(
                        node.path, concept_id
                    )
                )
            seen_in_doc.add(concept_id)

            if ns_entry["owner"] != node.path:
                errors.append(
                    "[NAMESPACE] {}: may not own '{}' (namespace {} owned by {})".format(
                        node.path, concept_id, ns_key, ns_entry["owner"]
                    )
                )

            numbers_by_ns.setdefault(ns_key, []).append(_concept_number(concept_id))

        for ns_key, numbers in numbers_by_ns.items():
            numbers = sorted(numbers)
            if not numbers:
                continue
            if numbers[0] != 1:
                warnings.append(
                    "[NAMESPACE] {}: {} numbering should start at 01 (found {:02d})".format(
                        node.path, ns_key, numbers[0]
                    )
                )
            for index in range(1, len(numbers)):
                if numbers[index] - numbers[index - 1] > 1:
                    warnings.append(
                        "[NAMESPACE] {}: {} numbering gap between {:02d} and {:02d}".format(
                            node.path, ns_key, numbers[index - 1], numbers[index]
                        )
                    )

    ns_holders = {}  # type: dict
    for node in nodes:
        for concept_id in node.concept_ids:
            ns_key = namespace_key_for_concept(concept_id)
            if ns_key in registry:
                ns_holders.setdefault(ns_key, set()).add(node.path)

    for ns_key, entry in registry.items():
        holders = ns_holders.get(ns_key, set())
        owner = entry["owner"]
        if holders and owner not in holders:
            warnings.append(
                "[NAMESPACE] {} owner mismatch: concepts found in {}".format(
                    ns_key, ", ".join(sorted(holders))
                )
            )
        elif len(holders) > 1:
            warnings.append(
                "[NAMESPACE] {} owner mismatch: concepts spread across {}".format(
                    ns_key, ", ".join(sorted(holders))
                )
            )

    return errors, warnings
