"""Adapter metadata consistency validation."""

OPERATIONAL_ROLES = {"practice", "pattern", "procedure", "architecture"}
VALID_PRIORITIES = {"high", "medium", "low"}


def validate_adapter_metadata(nodes, strict_adapters=False):
    # type: (list, bool) -> tuple
    """Adapter priority rules. Returns (errors, warnings)."""
    errors = []
    warnings = []

    for node in nodes:
        priority = node.frontmatter.get("adapter_priority")

        if node.is_foundation:
            if priority is not None:
                errors.append(
                    "[ADAPTER] {}: foundation document cannot define adapter_priority".format(
                        node.path
                    )
                )
            continue

        if node.role in OPERATIONAL_ROLES:
            if priority is None:
                message = (
                    "[ADAPTER] {}: role '{}' should define adapter_priority "
                    "(high, medium, or low)".format(node.path, node.role)
                )
                if strict_adapters:
                    errors.append(message)
                else:
                    warnings.append(message)
            elif priority not in VALID_PRIORITIES:
                errors.append(
                    "[ADAPTER] {}: invalid adapter_priority '{}'".format(node.path, priority)
                )

    return errors, warnings
