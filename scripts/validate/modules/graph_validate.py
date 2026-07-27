"""Knowledge graph validation (ADR-0004)."""

from pathlib import Path

from .graph_rules import get_allowed_exceptions, get_role_rules, load_graph_rules
from .models import FOUNDATION_PATH, DocumentNode

KNOWLEDGE_PATH_PATTERN = "knowledge/"
DEPENDS_ON_SUFFIX = ".md"


def _is_valid_knowledge_path(path):
    # type: (str) -> bool
    return path.startswith(KNOWLEDGE_PATH_PATTERN) and path.endswith(DEPENDS_ON_SUFFIX)


def _dependency_kind(dep, by_path):
    # type: (str, dict) -> str
    """Classify a depends_on target for layer rule checks."""
    if dep == FOUNDATION_PATH:
        return "foundation"
    dep_node = by_path.get(dep)
    if dep_node is None:
        return ""
    return dep_node.role


def validate_depends_on_paths(nodes, repo_root):
    # type: (list, Path) -> list
    """R-G1: depends_on paths must exist and use canonical knowledge/*.md form."""
    errors = []
    for node in nodes:
        for dep in node.depends_on:
            if not _is_valid_knowledge_path(dep):
                errors.append(
                    "[GRAPH] {}: depends_on '{}' must match knowledge/*.md".format(
                        node.path, dep
                    )
                )
                continue
            if not (repo_root / dep).is_file():
                errors.append(
                    "[GRAPH] {}: depends_on '{}' does not exist".format(node.path, dep)
                )
    return errors


def detect_cycles(nodes):
    # type: (list) -> list
    """R-G2: depends_on graph must be acyclic."""
    by_path = {node.path: node for node in nodes}
    errors = []
    visiting = set()  # type: set
    visited = set()  # type: set
    stack = []  # type: list

    def dfs(path):
        # type: (str) -> None
        if path in visited:
            return
        if path in visiting:
            cycle_start = stack.index(path)
            cycle = stack[cycle_start:] + [path]
            chain = " -> ".join(cycle)
            errors.append("[GRAPH] dependency cycle detected: {}".format(chain))
            return

        visiting.add(path)
        stack.append(path)
        node = by_path.get(path)
        if node:
            for dep in node.depends_on:
                if dep in by_path:
                    dfs(dep)
        stack.pop()
        visiting.remove(path)
        visited.add(path)

    for node in nodes:
        dfs(node.path)

    return list(dict.fromkeys(errors)) if hasattr(dict, "fromkeys") else list(set(errors))


def validate_reachability(nodes):
    # type: (list) -> list
    """R-G3: every non-foundation document must reach foundation via depends_on."""
    by_path = {node.path: node for node in nodes}
    errors = []

    if by_path.get(FOUNDATION_PATH) is None:
        return ["[GRAPH] foundation document missing: {}".format(FOUNDATION_PATH)]

    def reaches_foundation(path, seen):
        # type: (str, set) -> bool
        if path == FOUNDATION_PATH:
            return True
        if path in seen:
            return False
        seen.add(path)
        node = by_path.get(path)
        if node is None:
            return False
        return any(reaches_foundation(dep, seen) for dep in node.depends_on)

    for node in nodes:
        if node.is_foundation:
            continue
        if not reaches_foundation(node.path, set()):
            errors.append(
                "[GRAPH] {}: not reachable from {} via depends_on".format(
                    node.path, FOUNDATION_PATH
                )
            )

    return errors


def validate_dependency_directions(nodes, rules=None):
    # type: (list, dict) -> list
    """R-G4: depends_on edges must follow role layer rules from graph-rules.yaml."""
    if rules is None:
        rules = load_graph_rules()

    by_path = {node.path: node for node in nodes}
    exceptions = get_allowed_exceptions(rules)
    errors = []

    for node in nodes:
        role_rules = get_role_rules(rules, node.role)
        allowed = role_rules.get("allowed_dependencies", [])
        required = role_rules.get("required_dependencies", [])

        if "foundation" in required and FOUNDATION_PATH not in node.depends_on:
            if not node.is_foundation:
                errors.append(
                    "[GRAPH] {}: role '{}' requires depends_on {}".format(
                        node.path, node.role, FOUNDATION_PATH
                    )
                )

        for dep in node.depends_on:
            if (node.path, dep) in exceptions:
                continue

            dep_kind = _dependency_kind(dep, by_path)
            if not dep_kind:
                continue

            if dep_kind not in allowed:
                errors.append(
                    "[GRAPH] {}: role '{}' may not depend on '{}' (role '{}')".format(
                        node.path, node.role, dep, dep_kind
                    )
                )

    return errors


def compute_dependency_depth(node, by_path, cache=None, stack=None):
    # type: (DocumentNode, dict, dict, set) -> int
    """Return longest depends_on path length to foundation (R-G8)."""
    if cache is None:
        cache = {}
    if stack is None:
        stack = set()

    if node.path in cache:
        return cache[node.path]

    if node.is_foundation or node.path == FOUNDATION_PATH:
        cache[node.path] = 0
        return 0

    if node.path in stack:
        return 0

    stack.add(node.path)
    child_depths = []
    for dep in node.depends_on:
        dep_node = by_path.get(dep)
        if dep_node is not None:
            child_depths.append(compute_dependency_depth(dep_node, by_path, cache, stack))

    stack.discard(node.path)
    depth = 1 + max(child_depths) if child_depths else 0
    cache[node.path] = depth
    return depth


def validate_dependency_depth(nodes, rules=None):
    # type: (list, dict) -> tuple
    """R-G8: warn at depth 3, error at depth 4+."""
    if rules is None:
        rules = load_graph_rules()

    depth_rules = rules.get("depth", {})
    warn_at = depth_rules.get("warn_at", 3)
    error_at = depth_rules.get("error_at", 4)

    by_path = {node.path: node for node in nodes}
    cache = {}
    errors = []
    warnings = []

    for node in nodes:
        depth = compute_dependency_depth(node, by_path, cache)
        if depth >= error_at:
            errors.append(
                "[GRAPH] {} dependency depth is {} (maximum allowed is {})".format(
                    node.path, depth, error_at - 1
                )
            )
        elif depth >= warn_at:
            warnings.append(
                "[GRAPH] {} dependency depth is {} (expected maximum depth is {})".format(
                    node.path, depth, warn_at - 1
                )
            )

    return errors, warnings


def validate_foundation_singleton(nodes):
    # type: (list) -> list
    """R-G5: exactly one foundation document with correct invariants."""
    errors = []
    foundations = [node for node in nodes if node.role == "foundation"]

    if len(foundations) == 0:
        errors.append(
            "[GRAPH] no document with role: foundation (expected {})".format(
                FOUNDATION_PATH
            )
        )
        return errors

    if len(foundations) > 1:
        paths = ", ".join(node.path for node in foundations)
        errors.append("[GRAPH] multiple foundation documents: {}".format(paths))

    foundation = foundations[0]
    if foundation.path != FOUNDATION_PATH:
        errors.append(
            "[GRAPH] foundation must be {}, found {}".format(
                FOUNDATION_PATH, foundation.path
            )
        )

    if foundation.depends_on:
        errors.append("[GRAPH] {}: foundation depends_on must be []".format(foundation.path))

    if foundation.implements:
        errors.append(
            "[GRAPH] {}: foundation must not have implements".format(foundation.path)
        )

    return errors


def validate_downstream_metadata(nodes):
    # type: (list) -> list
    """R-G6: non-foundation documents require graph metadata."""
    errors = []
    for node in nodes:
        if node.is_foundation:
            continue
        if not node.depends_on:
            errors.append(
                "[GRAPH] {}: depends_on must contain at least one entry".format(node.path)
            )
        if not node.implements:
            errors.append(
                "[GRAPH] {}: implements must contain at least one entry".format(node.path)
            )
        if not node.concept_ids:
            errors.append(
                "[GRAPH] {}: concept_ids must contain at least one entry".format(node.path)
            )
    return errors


def get_max_depth(nodes):
    # type: (list) -> int
    by_path = {node.path: node for node in nodes}
    cache = {}
    return max(compute_dependency_depth(node, by_path, cache) for node in nodes)


def get_direct_dependents(nodes, target_path):
    # type: (list, str) -> list
    dependents = []
    for node in nodes:
        if target_path in node.depends_on:
            dependents.append(node.path)
    return sorted(dependents)


def validate_graph(nodes, repo_root, rules=None):
    # type: (list, Path, dict) -> tuple
    """Run all graph validation rules."""
    if rules is None:
        rules = load_graph_rules()

    errors = []
    warnings = []

    errors.extend(validate_depends_on_paths(nodes, repo_root))
    errors.extend(detect_cycles(nodes))
    errors.extend(validate_foundation_singleton(nodes))
    errors.extend(validate_downstream_metadata(nodes))
    errors.extend(validate_reachability(nodes))
    errors.extend(validate_dependency_directions(nodes, rules))

    depth_errors, depth_warnings = validate_dependency_depth(nodes, rules)
    errors.extend(depth_errors)
    warnings.extend(depth_warnings)

    return errors, warnings
