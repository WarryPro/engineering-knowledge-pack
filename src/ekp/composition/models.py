"""Immutable technology-component model."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Tuple


LAYER_RANK = {
    "L0": 0,
    "L1": 1,
    "L2": 2,
    "L3": 3,
}


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
