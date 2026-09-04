"""Component registry: load, validate, and query bundled components."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List, Optional, Set

import yaml
from jsonschema import Draft202012Validator

from ekp.composition.models import Component
from ekp.install.paths import check_symlink_boundary, relative_posix_path, resolve_under_root
from ekp.paths import get_ekp_root


class CompositionError(Exception):
    """Raised when component registry or composition contracts fail."""


class ComponentRegistry:
    """Load and validate ``components/*.yaml`` from the EKP resource root."""

    def __init__(self, components: Dict[str, Component], resource_root: Path):
        self._components = dict(components)
        self._resource_root = Path(resource_root)

    @classmethod
    def load(cls, resource_root: Optional[Path] = None) -> "ComponentRegistry":
        root = Path(resource_root or get_ekp_root())
        components_dir = root / "components"
        if not components_dir.is_dir():
            raise CompositionError(
                "components directory missing under resource root: {}".format(root)
            )

        schema_path = root / "schema" / "component.schema.json"
        if not schema_path.is_file():
            raise CompositionError(
                "component schema missing: {}".format(schema_path.as_posix())
            )
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        validator = Draft202012Validator(schema)

        loaded: Dict[str, Component] = {}
        for path in sorted(components_dir.glob("*.yaml")):
            component = cls._load_file(path, validator)
            if component.id in loaded:
                raise CompositionError(
                    "duplicate component id {!r}".format(component.id)
                )
            loaded[component.id] = component

        if not loaded:
            raise CompositionError(
                "no component definitions found under {}".format(components_dir)
            )

        registry = cls(loaded, root)
        registry.validate()
        return registry

    @staticmethod
    def _load_file(path: Path, validator: Draft202012Validator) -> Component:
        try:
            payload = yaml.safe_load(path.read_text(encoding="utf-8"))
        except yaml.YAMLError as exc:
            raise CompositionError(
                "invalid YAML in {}: {}".format(path.as_posix(), exc)
            ) from exc
        if not isinstance(payload, dict):
            raise CompositionError(
                "{}: component must be a mapping".format(path.as_posix())
            )

        errors = sorted(validator.iter_errors(payload), key=lambda e: list(e.path))
        if errors:
            raise CompositionError(
                "{}: schema invalid: {}".format(path.as_posix(), errors[0].message)
            )

        component_id = str(payload["id"])
        stem = path.stem
        if component_id != stem:
            raise CompositionError(
                "{}: id {!r} must match filename stem {!r}".format(
                    path.as_posix(), component_id, stem
                )
            )

        requires = tuple(str(item) for item in payload.get("requires", []))
        knowledge = tuple(str(item) for item in payload.get("knowledge", []))
        if len(requires) != len(set(requires)):
            raise CompositionError(
                "{}: requires must contain unique ids".format(path.as_posix())
            )
        if len(knowledge) != len(set(knowledge)):
            raise CompositionError(
                "{}: knowledge must contain unique paths".format(path.as_posix())
            )

        return Component(
            id=component_id,
            layer=str(payload["layer"]),
            requires=requires,
            knowledge=knowledge,
            selectable=bool(payload["selectable"]),
            legacy_profile=(
                str(payload["legacy_profile"])
                if "legacy_profile" in payload and payload["legacy_profile"] is not None
                else None
            ),
        )

    def validate(self) -> None:
        """Validate graph, layers, knowledge ownership, and legacy profiles."""
        for component in self._components.values():
            for dep_id in component.requires:
                if dep_id not in self._components:
                    raise CompositionError(
                        "component {!r} requires unknown dependency {!r}".format(
                            component.id, dep_id
                        )
                    )
                dep = self._components[dep_id]
                if dep.layer_rank > component.layer_rank:
                    raise CompositionError(
                        "component {!r} ({}) must not require higher-layer {!r} ({})".format(
                            component.id,
                            component.layer,
                            dep.id,
                            dep.layer,
                        )
                    )

            for rel in component.knowledge:
                self._validate_knowledge_path(rel)

            if component.legacy_profile:
                profile_path = (
                    self._resource_root / "profiles" / "{}.yaml".format(component.legacy_profile)
                )
                if not profile_path.is_file():
                    raise CompositionError(
                        "component {!r} legacy_profile {!r} not found".format(
                            component.id, component.legacy_profile
                        )
                    )

        ownership: Dict[str, str] = {}
        for component in self.list_components():
            for rel in component.knowledge:
                owner = ownership.get(rel)
                if owner is not None and owner != component.id:
                    raise CompositionError(
                        "knowledge path {!r} claimed by both {!r} and {!r}".format(
                            rel, owner, component.id
                        )
                    )
                ownership[rel] = component.id

        self._assert_acyclic()

        for component in self._components.values():
            if component.id == "core":
                if component.requires:
                    raise CompositionError("core must have empty requires")
                continue
            if "core" not in self._reachable(component.id):
                raise CompositionError(
                    "component {!r} does not transitively reach core".format(component.id)
                )

    def _validate_knowledge_path(self, relative: str) -> None:
        if relative.startswith("/") or ":\\" in relative or relative.startswith("\\\\"):
            raise CompositionError("absolute knowledge path forbidden: {!r}".format(relative))
        try:
            normalized = relative_posix_path(relative)
        except ValueError as exc:
            raise CompositionError("unsafe knowledge path: {!r}".format(relative)) from exc
        if not normalized.startswith("knowledge/"):
            raise CompositionError(
                "knowledge path must remain under knowledge/: {!r}".format(relative)
            )
        boundary = check_symlink_boundary(self._resource_root, normalized)
        if boundary:
            raise CompositionError(boundary)
        try:
            target = resolve_under_root(self._resource_root, normalized)
        except ValueError as exc:
            raise CompositionError(str(exc)) from exc
        if not target.is_file():
            raise CompositionError(
                "knowledge path missing or not a file: {}".format(normalized)
            )

    def _reachable(self, start_id: str) -> Set[str]:
        seen: Set[str] = set()
        stack = [start_id]
        while stack:
            current = stack.pop()
            if current in seen:
                continue
            seen.add(current)
            stack.extend(self._components[current].requires)
        return seen

    def _assert_acyclic(self) -> None:
        visiting: Set[str] = set()
        visited: Set[str] = set()
        path: List[str] = []

        def visit(node_id: str) -> None:
            if node_id in visited:
                return
            if node_id in visiting:
                cycle_start = path.index(node_id)
                cycle = path[cycle_start:] + [node_id]
                raise CompositionError(
                    "component dependency cycle: {}".format(" -> ".join(cycle))
                )
            visiting.add(node_id)
            path.append(node_id)
            for dep in self._components[node_id].requires:
                visit(dep)
            path.pop()
            visiting.remove(node_id)
            visited.add(node_id)

        for component_id in sorted(self._components):
            visit(component_id)

    @property
    def resource_root(self) -> Path:
        return self._resource_root

    def get(self, component_id: str) -> Component:
        try:
            return self._components[component_id]
        except KeyError as exc:
            raise CompositionError(
                "unknown component: {!r}".format(component_id)
            ) from exc

    def has(self, component_id: str) -> bool:
        return component_id in self._components

    def list_components(self) -> List[Component]:
        return [self._components[key] for key in sorted(self._components)]

    def list_ids(self) -> List[str]:
        return sorted(self._components)

    def as_mapping(self) -> Dict[str, Component]:
        return dict(self._components)
