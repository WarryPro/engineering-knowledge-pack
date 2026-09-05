"""Pure composition resolution for assembly and Consumer integration."""

from __future__ import annotations

from typing import Any, Dict, List, Sequence

from ekp.composition.closure import (
    reduce_requested_components,
    resolve_component_closure,
    resolve_knowledge_paths,
)
from ekp.composition.models import (
    COMPOSITION_ADAPTER_PRIORITIES,
    PROJECT_COMPOSITION_PROFILE,
    ResolvedComposition,
)
from ekp.composition.registry import ComponentRegistry, CompositionError


def resolve_composition(
    requested_components: Sequence[str],
    registry: ComponentRegistry,
) -> ResolvedComposition:
    """
    Resolve requested component ids to a canonical composition.

    Applies semantic request reduction, dependency-first closure, and knowledge
    inventory derivation using AW-A primitives.
    """
    if not isinstance(requested_components, (list, tuple)):
        raise CompositionError("requested components must be a sequence of ids")
    if len(requested_components) == 0:
        raise CompositionError("requested components must not be empty")

    reduced = reduce_requested_components(requested_components, registry)
    if not reduced:
        raise CompositionError("requested components must not be empty")

    closed = resolve_component_closure(reduced, registry)
    knowledge = resolve_knowledge_paths(closed, registry)
    return ResolvedComposition(
        requested_components=tuple(reduced),
        resolved_components=tuple(closed),
        knowledge_paths=tuple(knowledge),
    )


def build_ephemeral_composition_profile(
    composition: ResolvedComposition,
    outputs: Sequence[str],
) -> Dict[str, Any]:
    """
    Build the in-memory profile-like contract consumed by existing adapters.

    Adapters remain unaware of composition; they only see this normalized dict.
    """
    if not isinstance(outputs, (list, tuple)) or len(outputs) == 0:
        raise CompositionError("composition outputs must be a non-empty sequence")

    adapter_outputs = [str(item) for item in outputs]
    description = "Ephemeral composition of: {}".format(
        ", ".join(composition.requested_components)
    )
    return {
        "name": PROJECT_COMPOSITION_PROFILE,
        "description": description,
        "knowledge": list(composition.knowledge_paths),
        "adapter_priorities": list(COMPOSITION_ADAPTER_PRIORITIES),
        "outputs": adapter_outputs,
    }
