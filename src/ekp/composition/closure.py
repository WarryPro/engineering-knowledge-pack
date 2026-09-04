"""Deterministic dependency closure and knowledge path composition."""

from __future__ import annotations

from typing import Dict, Iterable, List, Sequence, Set

from ekp.composition.models import Component
from ekp.composition.registry import CompositionError, ComponentRegistry


def resolve_component_closure(
    requested: Sequence[str],
    registry: ComponentRegistry,
) -> List[str]:
    """
    Resolve requested component ids to a dependency-first deterministic list.

    Dependencies always precede dependants. Ready-node ties break by lexical id.
    """
    if not isinstance(requested, (list, tuple)):
        raise CompositionError("requested components must be a sequence of ids")

    requested_unique: List[str] = []
    seen_request: Set[str] = set()
    for raw in requested:
        component_id = str(raw)
        if component_id in seen_request:
            continue
        seen_request.add(component_id)
        if not registry.has(component_id):
            raise CompositionError("unknown component: {!r}".format(component_id))
        requested_unique.append(component_id)

    needed: Set[str] = set()

    def add_with_deps(component_id: str, stack: List[str]) -> None:
        if component_id in needed:
            return
        if component_id in stack:
            cycle = stack[stack.index(component_id) :] + [component_id]
            raise CompositionError(
                "component dependency cycle: {}".format(" -> ".join(cycle))
            )
        component = registry.get(component_id)
        next_stack = stack + [component_id]
        for dep in component.requires:
            add_with_deps(dep, next_stack)
        needed.add(component_id)

    for component_id in requested_unique:
        add_with_deps(component_id, [])

    # Kahn topological sort over the needed subgraph.
    incoming: Dict[str, int] = {component_id: 0 for component_id in needed}
    dependents: Dict[str, List[str]] = {component_id: [] for component_id in needed}
    for component_id in needed:
        for dep in registry.get(component_id).requires:
            if dep not in needed:
                continue
            incoming[component_id] += 1
            dependents[dep].append(component_id)

    ready = sorted(component_id for component_id, count in incoming.items() if count == 0)
    ordered: List[str] = []
    while ready:
        current = ready.pop(0)
        ordered.append(current)
        for child in sorted(dependents[current]):
            incoming[child] -= 1
            if incoming[child] == 0:
                ready.append(child)
                ready.sort()

    if len(ordered) != len(needed):
        raise CompositionError(
            "component dependency cycle detected among: {}".format(
                ", ".join(sorted(needed))
            )
        )
    return ordered


def resolve_knowledge_paths(
    resolved_component_ids: Sequence[str],
    registry: ComponentRegistry,
) -> List[str]:
    """
    Derive ordered unique knowledge paths from a resolved component list.

    Order: resolved component order, then each component's declared knowledge order.
    """
    paths: List[str] = []
    seen: Set[str] = set()
    for component_id in resolved_component_ids:
        component = registry.get(component_id)
        for relative in component.knowledge:
            if relative in seen:
                continue
            seen.add(relative)
            paths.append(relative)
    return paths
