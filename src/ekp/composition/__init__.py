"""Technology-component composition primitives for EKP v0.18+."""

from ekp.composition.closure import (
    reduce_requested_components,
    resolve_component_closure,
    resolve_knowledge_paths,
)
from ekp.composition.models import (
    COMPOSITION_ADAPTER_PRIORITIES,
    PROJECT_COMPOSITION_PROFILE,
    Component,
    ResolvedComposition,
)
from ekp.composition.registry import ComponentRegistry, CompositionError
from ekp.composition.resolve import (
    build_ephemeral_composition_profile,
    resolve_composition,
)

__all__ = [
    "COMPOSITION_ADAPTER_PRIORITIES",
    "PROJECT_COMPOSITION_PROFILE",
    "Component",
    "ComponentRegistry",
    "CompositionError",
    "ResolvedComposition",
    "build_ephemeral_composition_profile",
    "reduce_requested_components",
    "resolve_component_closure",
    "resolve_composition",
    "resolve_knowledge_paths",
]
