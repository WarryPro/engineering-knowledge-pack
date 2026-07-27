"""Concept ID and implements validation."""

import re
from typing import List

from .models import DocumentNode

CONCEPT_ID_PATTERN = re.compile(r"^EKP-([A-Z]{2}[0-9]{2}|P(0[1-9]|10))$")
PRINCIPLE_IMPLEMENTS_PATTERN = re.compile(r"^EKP-P(0[1-9]|10)$")


def _concept_prefix(concept_id):
    # type: (str) -> str
    """Return namespace prefix for a concept ID (e.g. CC, P, TS)."""
    match = CONCEPT_ID_PATTERN.match(concept_id)
    if not match:
        return ""
    if match.group(2):
        return "P"
    return match.group(1)[:2]


def validate_concept_format(nodes):
    # type: (List[DocumentNode]) -> List[str]
    """C2: concept_ids must match allowed formats."""
    errors = []
    for node in nodes:
        for concept_id in node.concept_ids:
            if not CONCEPT_ID_PATTERN.match(concept_id):
                errors.append(
                    "[CONCEPT] {}: invalid concept_id format '{}'".format(
                        node.path, concept_id
                    )
                )
    return errors


def validate_concept_uniqueness(nodes):
    # type: (List[DocumentNode]) -> List[str]
    """C1: concept IDs must be globally unique."""
    errors = []
    owners = {}  # type: dict

    for node in nodes:
        for concept_id in node.concept_ids:
            owners.setdefault(concept_id, []).append(node.path)

    for concept_id, paths in sorted(owners.items()):
        if len(paths) > 1:
            doc_list = ", ".join(paths)
            errors.append(
                "[CONCEPT] {} defined in multiple documents: {}".format(
                    concept_id, doc_list
                )
            )

    return errors


def validate_namespace_consistency(nodes):
    # type: (List[DocumentNode]) -> List[str]
    """C3: all concept_ids in a document must share one namespace prefix."""
    errors = []
    for node in nodes:
        if not node.concept_ids:
            continue

        prefixes = set(_concept_prefix(cid) for cid in node.concept_ids)
        prefixes.discard("")

        if len(prefixes) > 1:
            errors.append(
                "[CONCEPT] {}: mixed concept_id namespaces {}".format(
                    node.path, sorted(prefixes)
                )
            )

        if node.is_foundation and prefixes != {"P"}:
            errors.append(
                "[CONCEPT] {}: foundation must own only EKP-P** concept_ids".format(
                    node.path
                )
            )

        if not node.is_foundation and "P" in prefixes:
            errors.append(
                "[CONCEPT] {}: only foundation may own EKP-P** concept_ids".format(
                    node.path
                )
            )

    return errors


def validate_implements(nodes):
    # type: (List[DocumentNode]) -> List[str]
    """Every implements value must be EKP-P01 through EKP-P10."""
    errors = []
    for node in nodes:
        for principle_id in node.implements:
            if not PRINCIPLE_IMPLEMENTS_PATTERN.match(principle_id):
                errors.append(
                    "[CONCEPT] {}: invalid implements value '{}' "
                    "(must be EKP-P01 through EKP-P10)".format(node.path, principle_id)
                )
    return errors


def validate_concepts(nodes):
    # type: (List[DocumentNode]) -> List[str]
    """Run all concept validation rules."""
    errors = []
    errors.extend(validate_implements(nodes))
    errors.extend(validate_concept_format(nodes))
    errors.extend(validate_concept_uniqueness(nodes))
    errors.extend(validate_namespace_consistency(nodes))
    return errors
