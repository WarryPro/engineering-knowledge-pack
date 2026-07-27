"""Related and extends frontmatter path validation."""

KNOWLEDGE_PREFIX = "knowledge/"
MD_SUFFIX = ".md"


def _validate_path_list(paths, repo_root, node_path, field_name):
    # type: (list, object, str, str) -> list
    errors = []
    for target in paths:
        if not isinstance(target, str):
            continue
        if not target.startswith(KNOWLEDGE_PREFIX):
            errors.append(
                "[RELATED] {}: {} '{}' must start with knowledge/".format(
                    node_path, field_name, target
                )
            )
            continue
        if not target.endswith(MD_SUFFIX):
            errors.append(
                "[RELATED] {}: {} '{}' must end with .md".format(
                    node_path, field_name, target
                )
            )
            continue
        if not (repo_root / target).is_file():
            errors.append(
                "[RELATED] {} target missing: {}".format(field_name.upper(), target)
            )
    return errors


def validate_related_paths(nodes, repo_root):
    # type: (list, object) -> list
    """R-G10-lite: related and extends paths must exist."""
    errors = []
    for node in nodes:
        errors.extend(_validate_path_list(node.related, repo_root, node.path, "related"))
        extends = node.frontmatter.get("extends")
        if isinstance(extends, list) and extends:
            errors.extend(_validate_path_list(extends, repo_root, node.path, "extends"))
    return errors
