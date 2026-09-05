"""Immutable technology-component and composition models."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Tuple


LAYER_RANK = {
    "L0": 0,
    "L1": 1,
    "L2": 2,
    "L3": 3,
}

PROJECT_COMPOSITION_PROFILE = "project-composition"
COMPOSITION_ADAPTER_PRIORITIES = ("high",)


@dataclass(frozen=True)
class Component:
    """Canonical technology component for project composition."""

    id: str
    layer: str
    requires: Tuple[str, ...]
    knowledge: Tuple[str, ...]
    selectable: bool
    legacy_profile: Optional[str] = None

    @property
    def layer_rank(self) -> int:
        return LAYER_RANK[self.layer]


@dataclass(frozen=True)
class ResolvedComposition:
    """Canonical composition after request reduction and dependency closure."""

    requested_components: Tuple[str, ...]
    resolved_components: Tuple[str, ...]
    knowledge_paths: Tuple[str, ...]
