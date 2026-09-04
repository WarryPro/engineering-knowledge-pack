"""Technology-component composition primitives for EKP v0.18+."""

from ekp.composition.closure import resolve_component_closure, resolve_knowledge_paths
from ekp.composition.models import Component
from ekp.composition.registry import ComponentRegistry, CompositionError

__all__ = [
    "Component",
    "ComponentRegistry",
    "CompositionError",
    "resolve_component_closure",
    "resolve_knowledge_paths",
]
