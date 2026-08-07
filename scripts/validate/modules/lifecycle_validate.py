"""Knowledge document lifecycle status validation."""

VALID_STATUSES = frozenset(
    ("draft", "review", "validated", "published", "deprecated", "retired")
)
DEFAULT_STATUS = "published"


def resolve_status(frontmatter):
    # type: (dict) -> str
    """Return effective lifecycle status; missing status means published."""
    raw = frontmatter.get("status")
    if raw is None:
        return DEFAULT_STATUS
    if isinstance(raw, str):
        return raw.strip().lower()
    return raw


def validate_lifecycle(nodes):
    # type: (list) -> tuple
    """Validate optional status frontmatter. Returns (errors, warnings)."""
    errors = []
    warnings = []

    for node in nodes:
        raw = node.frontmatter.get("status")
        if raw is None:
            continue

        if not isinstance(raw, str):
            errors.append(
                "[LIFECYCLE] {}: status must be a string".format(node.path)
            )
            continue

        status = raw.strip().lower()
        if status not in VALID_STATUSES:
            errors.append(
                "[LIFECYCLE] {}: invalid status '{}' (allowed: {})".format(
                    node.path,
                    raw,
                    ", ".join(sorted(VALID_STATUSES)),
                )
            )

    return errors, warnings
