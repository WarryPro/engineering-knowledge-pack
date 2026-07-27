"""Body and frontmatter concept ID consistency (warning-only)."""

import re

HEADING_ID_RE = re.compile(
    r"^### (EKP-(?:[A-Z]{2}\d{2}|P(?:0[1-9]|10)))\b",
    re.MULTILINE,
)
INLINE_ID_RE = re.compile(r"\b(EKP-(?:[A-Z]{2}\d{2}|P(?:0[1-9]|10)))\b")


def validate_concept_body(nodes):
    # type: (list) -> list
    """B1/B2: concept_ids vs body headings. Returns warnings only."""
    warnings = []

    for node in nodes:
        frontmatter_ids = set(node.concept_ids)
        heading_ids = set(HEADING_ID_RE.findall(node.body))

        for concept_id in frontmatter_ids:
            if concept_id not in node.body:
                warnings.append(
                    "[BODY] {}: concept_id '{}' not found in document body".format(
                        node.path, concept_id
                    )
                )

        for heading_id in heading_ids:
            if heading_id not in frontmatter_ids:
                warnings.append(
                    "[BODY] {}: concept heading '{}' missing from frontmatter concept_ids".format(
                        node.path, heading_id
                    )
                )

    return warnings
