"""Scoped project composition: root/workspace knowledge inventory (AZ-B).

Pure, assistant-neutral composition above ComponentRegistry. Scope is an outer
concern; adapters consume ScopedKnowledgeInventory later (AZ-C).
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional, Sequence, Tuple

from ekp.composition.models import ResolvedComposition
from ekp.composition.registry import ComponentRegistry, CompositionError
from ekp.composition.resolve import resolve_composition
from ekp.config.models import (
    PROJECT_SCHEMA_VERSION_1,
    PROJECT_SCHEMA_VERSION_2,
    SUPPORTED_PROJECT_SCHEMA_VERSIONS,
    ProjectConfig,
)


class KnowledgeScope(Enum):
    """Ephemeral knowledge scope for composition IR (not persisted)."""

    GLOBAL = "global"
    WORKSPACE = "workspace"


@dataclass(frozen=True)
class ScopedKnowledgeItem:
    """One canonical knowledge source reference under an explicit scope."""

    source_path: str
    scope: KnowledgeScope
    workspace_path: Optional[str] = None

    def __post_init__(self) -> None:
        if self.scope is KnowledgeScope.GLOBAL:
            if self.workspace_path is not None:
                raise CompositionError(
                    "GLOBAL ScopedKnowledgeItem must not set workspace_path"
                )
        elif self.scope is KnowledgeScope.WORKSPACE:
            if not self.workspace_path:
                raise CompositionError(
                    "WORKSPACE ScopedKnowledgeItem requires workspace_path"
                )
        else:
            raise CompositionError(
                "unsupported KnowledgeScope: {!r}".format(self.scope)
            )


@dataclass(frozen=True)
class ScopedKnowledgeInventory:
    """Deterministic ordered collection of scoped knowledge references."""

    items: Tuple[ScopedKnowledgeItem, ...]

    def global_items(self) -> Tuple[ScopedKnowledgeItem, ...]:
        return tuple(
            item for item in self.items if item.scope is KnowledgeScope.GLOBAL
        )

    def workspace_items(self, path: str) -> Tuple[ScopedKnowledgeItem, ...]:
        return tuple(
            item
            for item in self.items
            if item.scope is KnowledgeScope.WORKSPACE
            and item.workspace_path == path
        )

    def unique_source_paths(self) -> Tuple[str, ...]:
        """Canonical source paths in first-seen inventory order (cache keys)."""
        seen = set()
        ordered = []
        for item in self.items:
            if item.source_path in seen:
                continue
            seen.add(item.source_path)
            ordered.append(item.source_path)
        return tuple(ordered)


@dataclass(frozen=True)
class ResolvedWorkspaceComposition:
    """Resolved composition for one workspace path."""

    path: str
    composition: ResolvedComposition


@dataclass(frozen=True)
class ProjectCompositionResolution:
    """One project composition preparation result (ephemeral)."""

    root: Optional[ResolvedComposition]
    workspaces: Tuple[ResolvedWorkspaceComposition, ...]
    inventory: ScopedKnowledgeInventory


def _items_from_composition(
    composition: ResolvedComposition,
    *,
    scope: KnowledgeScope,
    workspace_path: Optional[str],
) -> Tuple[ScopedKnowledgeItem, ...]:
    """Build scoped items preserving ResolvedComposition.knowledge_paths order."""
    return tuple(
        ScopedKnowledgeItem(
            source_path=source_path,
            scope=scope,
            workspace_path=workspace_path,
        )
        for source_path in composition.knowledge_paths
    )


def _build_inventory(
    root: Optional[ResolvedComposition],
    workspaces: Sequence[ResolvedWorkspaceComposition],
) -> ScopedKnowledgeInventory:
    items: list = []
    if root is not None:
        items.extend(
            _items_from_composition(
                root,
                scope=KnowledgeScope.GLOBAL,
                workspace_path=None,
            )
        )
    for workspace in workspaces:
        items.extend(
            _items_from_composition(
                workspace.composition,
                scope=KnowledgeScope.WORKSPACE,
                workspace_path=workspace.path,
            )
        )
    inventory = ScopedKnowledgeInventory(items=tuple(items))
    _assert_intra_scope_uniqueness(inventory)
    return inventory


def _assert_intra_scope_uniqueness(inventory: ScopedKnowledgeInventory) -> None:
    """Refuse duplicate (source_path, scope, workspace_path) triples."""
    seen = set()
    for item in inventory.items:
        key = (item.source_path, item.scope, item.workspace_path)
        if key in seen:
            raise CompositionError(
                "duplicate scoped knowledge item within one scope: {}".format(key)
            )
        seen.add(key)


def resolve_project_composition(
    config: ProjectConfig,
    registry: ComponentRegistry,
) -> ProjectCompositionResolution:
    """
    Resolve root and workspace technology intent into one scoped inventory.

    Pure: does not touch the filesystem, adapters, or configuration hashing.
    Empty schema2 root components yield no GLOBAL items and do not call
    ``resolve_composition([])``.
    """
    if config.schema_version not in SUPPORTED_PROJECT_SCHEMA_VERSIONS:
        raise CompositionError(
            "unsupported project config schema_version: {}".format(
                config.schema_version
            )
        )

    if config.schema_version == PROJECT_SCHEMA_VERSION_1:
        if config.workspaces:
            raise CompositionError(
                "schema_version 1 project config must not declare workspaces"
            )
        if not config.components:
            raise CompositionError(
                "schema_version 1 project config requires at least one component"
            )
        root = resolve_composition(config.components, registry)
        inventory = _build_inventory(root, ())
        return ProjectCompositionResolution(
            root=root,
            workspaces=(),
            inventory=inventory,
        )

    if config.schema_version == PROJECT_SCHEMA_VERSION_2:
        if not config.workspaces:
            raise CompositionError(
                "schema_version 2 project config requires at least one workspace"
            )

        root: Optional[ResolvedComposition]
        if config.components:
            root = resolve_composition(config.components, registry)
        else:
            root = None

        # Deterministic workspace group order: canonical path ascending.
        ordered_intents = sorted(config.workspaces, key=lambda item: item.path)
        workspaces = []
        for intent in ordered_intents:
            composition = resolve_composition(intent.components, registry)
            workspaces.append(
                ResolvedWorkspaceComposition(
                    path=intent.path,
                    composition=composition,
                )
            )
        workspace_tuple = tuple(workspaces)
        inventory = _build_inventory(root, workspace_tuple)
        return ProjectCompositionResolution(
            root=root,
            workspaces=workspace_tuple,
            inventory=inventory,
        )

    raise CompositionError(
        "unsupported project config schema_version: {}".format(config.schema_version)
    )
