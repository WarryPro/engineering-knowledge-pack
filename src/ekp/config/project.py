"""Safe load, exclusive create, and transactional replace for .ekp/project.yaml."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Optional, Sequence, Tuple

import yaml
from jsonschema import Draft202012Validator

from ekp.composition import ComponentRegistry, CompositionError
from ekp.config.models import (
    PROJECT_CONFIG_RELATIVE,
    SUPPORTED_PROJECT_SCHEMA_VERSION,
    ProjectConfig,
    ProjectConfigError,
    ProjectConfigFileSnapshot,
    ProjectConfigReplaceHandle,
    ProjectConfigRollbackError,
    ProjectConfigSnapshot,
)
from ekp.config.normalization import configuration_sha256, normalize_project_config
from ekp.install.atomic import ExclusiveTempFile, exclusive_create_from_temp
from ekp.install.paths import check_symlink_boundary, resolve_under_root
from ekp.paths import get_ekp_root


def project_config_content_sha256(raw_bytes: bytes) -> str:
    """SHA-256 of exact project.yaml bytes (physical fingerprint, not semantic)."""
    return hashlib.sha256(raw_bytes).hexdigest()


def _production_supported_assistants() -> Tuple[str, ...]:
    """
    Lazy capability lookup from DeployRegistry (authoritative Consumer SoT).

    Dependency direction: config.project → install.deploy.registry (lazy).
    Deploy modules do not import config validation, avoiding an import cycle.
    """
    from ekp.install.deploy.registry import build_default_deploy_registry

    return build_default_deploy_registry().supported_assistants()


def _load_project_config_schema(resource_root: Optional[Path] = None) -> dict:
    root = Path(resource_root or get_ekp_root())
    schema_path = root / "schema" / "project-config.schema.json"
    if not schema_path.is_file():
        raise ProjectConfigError(
            "project-config schema missing: {}".format(schema_path.as_posix())
        )
    try:
        return json.loads(schema_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ProjectConfigError(
            "unable to load project-config schema: {}".format(exc)
        ) from exc


def render_project_config_yaml(config: ProjectConfig) -> str:
    """Deterministic YAML for initial project config creation (UTF-8 / LF)."""
    lines = ["schema_version: {}".format(int(config.schema_version))]
    lines.append("components:")
    for component_id in config.components:
        lines.append("  - {}".format(component_id))
    lines.append("assistants:")
    for assistant_id in config.assistants:
        lines.append("  - {}".format(assistant_id))
    return "\n".join(lines) + "\n"


def validate_project_config_payload(
    payload: Any,
    registry: ComponentRegistry,
    *,
    schema: Optional[dict] = None,
    supported_assistants: Optional[Sequence[str]] = None,
) -> ProjectConfig:
    """
    Structurally and semantically validate a project-config mapping.

    ``supported_assistants`` defaults to DeployRegistry production capability
    (injected when provided). Raises ProjectConfigError for invalid configuration.
    """
    if not isinstance(payload, dict):
        raise ProjectConfigError("project config root must be a mapping/object")

    schema_doc = schema if schema is not None else _load_project_config_schema(
        registry.resource_root
    )
    validator = Draft202012Validator(schema_doc)
    errors = sorted(validator.iter_errors(payload), key=lambda e: list(e.path))
    if errors:
        raise ProjectConfigError(
            "project config schema invalid: {}".format(errors[0].message)
        )

    schema_version = payload["schema_version"]
    if schema_version != SUPPORTED_PROJECT_SCHEMA_VERSION:
        raise ProjectConfigError(
            "unsupported project config schema_version: {}".format(schema_version)
        )

    components = tuple(str(item) for item in payload["components"])
    assistants = tuple(str(item) for item in payload["assistants"])
    if not assistants:
        raise ProjectConfigError("project config requires at least one assistant")

    for component_id in components:
        if not registry.has(component_id):
            raise ProjectConfigError(
                "unknown component in project config: {!r}".format(component_id)
            )
        component = registry.get(component_id)
        if not component.selectable:
            raise ProjectConfigError(
                "component is not selectable in project config: {!r}".format(
                    component_id
                )
            )

    # Ensure the requested set forms a valid graph (unknown deps already covered).
    try:
        for component_id in components:
            registry.get(component_id)
    except CompositionError as exc:
        raise ProjectConfigError(str(exc)) from exc

    if supported_assistants is None:
        supported = set(_production_supported_assistants())
    else:
        supported = set(str(item) for item in supported_assistants)
    for assistant_id in assistants:
        if assistant_id not in supported:
            raise ProjectConfigError(
                "unsupported assistant in project config for this EKP version: {!r}".format(
                    assistant_id
                )
            )

    return ProjectConfig(
        schema_version=int(schema_version),
        components=components,
        assistants=assistants,
    )


class ProjectConfigStore:
    """Load, exclusively create, and transactionally replace project intent configuration."""

    def __init__(
        self,
        project_root: Path,
        *,
        registry: Optional[ComponentRegistry] = None,
        resource_root: Optional[Path] = None,
    ):
        self.project_root = Path(project_root).resolve()
        self._registry = registry
        self._resource_root = Path(resource_root) if resource_root is not None else None
        self.config_path = self._safe_config_path()

    def _registry_or_load(self) -> ComponentRegistry:
        if self._registry is not None:
            return self._registry
        return ComponentRegistry.load(self._resource_root)

    def _schema(self) -> dict:
        root = self._resource_root
        if root is None and self._registry is not None:
            root = self._registry.resource_root
        return _load_project_config_schema(root)

    def _safe_config_path(self) -> Path:
        """
        Locate project.yaml without resolving the final path component.

        Parent components (``.ekp``) are validated against the project root.
        """
        parts = Path(PROJECT_CONFIG_RELATIVE).parts
        if not parts or any(part in (".", "..") for part in parts):
            raise ProjectConfigError(
                "Unsafe project config path: {}".format(PROJECT_CONFIG_RELATIVE)
            )

        parent_parts = parts[:-1]
        if parent_parts:
            parent_rel = "/".join(parent_parts)
            boundary = check_symlink_boundary(self.project_root, parent_rel)
            if boundary:
                raise ProjectConfigError(boundary)
            try:
                parent = resolve_under_root(self.project_root, parent_rel)
            except ValueError as exc:
                raise ProjectConfigError(
                    "Project config path escapes project root: {}".format(
                        PROJECT_CONFIG_RELATIVE
                    )
                ) from exc
        else:
            parent = self.project_root

        return parent / parts[-1]

    def exists(self) -> bool:
        return self.config_path.is_file() or self.config_path.is_symlink()

    def _reject_symlinked_config(self) -> None:
        if self.config_path.is_symlink():
            raise ProjectConfigError(
                "Refusing to use symlinked project config: {}".format(
                    PROJECT_CONFIG_RELATIVE
                )
            )

    def _ensure_config_path_safe(self) -> None:
        self._reject_symlinked_config()
        boundary = check_symlink_boundary(self.project_root, PROJECT_CONFIG_RELATIVE)
        if boundary:
            raise ProjectConfigError(boundary)

    def _read_raw_bytes(self) -> bytes:
        """Read exact project.yaml bytes after safety checks. Raises on races."""
        if not self.config_path.exists() and not self.config_path.is_symlink():
            raise ProjectConfigError(
                "project config missing: {}".format(PROJECT_CONFIG_RELATIVE)
            )
        self._ensure_config_path_safe()
        if not self.config_path.is_file() or self.config_path.is_symlink():
            raise ProjectConfigError(
                "project config path is not a regular file: {}".format(
                    PROJECT_CONFIG_RELATIVE
                )
            )
        try:
            return self.config_path.read_bytes()
        except OSError as exc:
            raise ProjectConfigError(
                "unable to read project config: {}".format(exc)
            ) from exc

    def _parse_config_bytes(self, raw: bytes) -> ProjectConfig:
        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise ProjectConfigError(
                "project config is not valid UTF-8: {}".format(exc)
            ) from exc
        try:
            payload = yaml.safe_load(text)
        except yaml.YAMLError as exc:
            raise ProjectConfigError(
                "invalid YAML in project config: {}".format(exc)
            ) from exc
        if payload is None:
            raise ProjectConfigError("project config root must be a mapping/object")
        return validate_project_config_payload(
            payload,
            self._registry_or_load(),
            schema=self._schema(),
        )

    def load(self) -> Optional[ProjectConfig]:
        """Return None when missing; raise ProjectConfigError when invalid."""
        if not self.config_path.exists() and not self.config_path.is_symlink():
            return None

        self._ensure_config_path_safe()
        if not self.config_path.is_file():
            raise ProjectConfigError(
                "project config path is not a regular file: {}".format(
                    PROJECT_CONFIG_RELATIVE
                )
            )

        try:
            raw = self.config_path.read_text(encoding="utf-8")
        except OSError as exc:
            raise ProjectConfigError(
                "unable to read project config: {}".format(exc)
            ) from exc

        try:
            payload = yaml.safe_load(raw)
        except yaml.YAMLError as exc:
            raise ProjectConfigError(
                "invalid YAML in project config: {}".format(exc)
            ) from exc

        if payload is None:
            raise ProjectConfigError("project config root must be a mapping/object")

        return validate_project_config_payload(
            payload,
            self._registry_or_load(),
            schema=self._schema(),
        )

    def load_snapshot(self) -> Optional[ProjectConfigSnapshot]:
        config = self.load()
        if config is None:
            return None
        registry = self._registry_or_load()
        normalized = normalize_project_config(config, registry)
        digest = configuration_sha256(config, registry)
        return ProjectConfigSnapshot(
            config=config,
            normalized=normalized,
            configuration_sha256=digest,
        )

    def load_file_snapshot(self) -> Optional[ProjectConfigFileSnapshot]:
        """Load semantic snapshot plus exact file bytes / physical fingerprint."""
        if not self.config_path.exists() and not self.config_path.is_symlink():
            return None
        raw = self._read_raw_bytes()
        config = self._parse_config_bytes(raw)
        registry = self._registry_or_load()
        normalized = normalize_project_config(config, registry)
        return ProjectConfigFileSnapshot(
            config=config,
            normalized=normalized,
            configuration_sha256=configuration_sha256(config, registry),
            raw_bytes=raw,
            content_sha256=project_config_content_sha256(raw),
        )

    def create(self, config: ProjectConfig) -> ProjectConfig:
        """
        Atomically create project.yaml when missing.

        Refuses if the file (or a symlink at that path) already exists.
        """
        registry = self._registry_or_load()
        # Re-validate through the same semantic path used for load.
        validated = validate_project_config_payload(
            {
                "schema_version": config.schema_version,
                "components": list(config.components),
                "assistants": list(config.assistants),
            },
            registry,
            schema=self._schema(),
        )

        parent = self.config_path.parent
        if self.config_path.exists() or self.config_path.is_symlink():
            raise ProjectConfigError(
                "project config already exists: {}".format(PROJECT_CONFIG_RELATIVE)
            )

        try:
            parent.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            raise ProjectConfigError(
                "unable to create project config parent directory: {}".format(exc)
            ) from exc

        text = render_project_config_yaml(validated)
        tmp = ExclusiveTempFile.create(parent)
        try:
            tmp.write_text(text, encoding="utf-8")
            tmp.close_fd()
            self._exclusive_commit(tmp.path, self.config_path)
            tmp.path = None
        except Exception:
            tmp.cleanup()
            raise

        if self.config_path.is_symlink():
            raise ProjectConfigError(
                "Refusing to use symlinked project config: {}".format(
                    PROJECT_CONFIG_RELATIVE
                )
            )

        return validated

    def replace(
        self,
        new_config: ProjectConfig,
        *,
        expected_content_sha256: str,
    ) -> ProjectConfigReplaceHandle:
        """
        Atomically replace project.yaml when current exact bytes match CAS fingerprint.

        Compare-and-swap uses physical content SHA-256, never semantic configuration_sha256.
        """
        registry = self._registry_or_load()
        validated = validate_project_config_payload(
            {
                "schema_version": new_config.schema_version,
                "components": list(new_config.components),
                "assistants": list(new_config.assistants),
            },
            registry,
            schema=self._schema(),
        )
        new_text = render_project_config_yaml(validated)
        new_bytes = new_text.encode("utf-8")
        new_content = project_config_content_sha256(new_bytes)
        new_semantic = configuration_sha256(validated, registry)

        old_raw = self._read_raw_bytes()
        old_content = project_config_content_sha256(old_raw)
        if old_content != expected_content_sha256:
            raise ProjectConfigError(
                "project config changed before replacement; refusing overwrite"
            )
        old_config = self._parse_config_bytes(old_raw)
        old_semantic = configuration_sha256(old_config, registry)

        parent = self.config_path.parent
        tmp = ExclusiveTempFile.create(parent)
        try:
            tmp.write_bytes(new_bytes)
            # Immediate pre-commit revalidation (TOCTOU).
            current = self._read_raw_bytes()
            if project_config_content_sha256(current) != expected_content_sha256:
                raise ProjectConfigError(
                    "project config changed before replacement; refusing overwrite"
                )
            tmp.commit(self.config_path)
        except Exception:
            tmp.cleanup()
            raise

        # Post-replace verification.
        try:
            actual = self._read_raw_bytes()
        except ProjectConfigError as exc:
            raise ProjectConfigError(
                "project config unverifiable after replacement: {}".format(exc)
            ) from exc
        if project_config_content_sha256(actual) != new_content:
            raise ProjectConfigError(
                "project config bytes mismatch after replacement"
            )
        loaded = self._parse_config_bytes(actual)
        if configuration_sha256(loaded, registry) != new_semantic:
            raise ProjectConfigError(
                "project config semantic hash mismatch after replacement"
            )

        return ProjectConfigReplaceHandle(
            old_bytes=old_raw,
            old_content_sha256=old_content,
            old_configuration_sha256=old_semantic,
            new_bytes=new_bytes,
            new_content_sha256=new_content,
            new_configuration_sha256=new_semantic,
            config=validated,
        )

    def rollback_replace(
        self,
        *,
        expected_current_content_sha256: str,
        old_bytes: bytes,
    ) -> None:
        """
        Restore exact prior project.yaml bytes after a successful replace.

        Refuses if current bytes no longer match what this store committed, or if
        the path is missing / symlink / non-regular (no blind recreation).
        """
        try:
            current = self._read_raw_bytes()
        except ProjectConfigError as exc:
            raise ProjectConfigRollbackError(
                "cannot rollback project config: {}".format(exc)
            ) from exc

        current_sha = project_config_content_sha256(current)
        if current_sha != expected_current_content_sha256:
            raise ProjectConfigRollbackError(
                "project config changed after replacement; refusing rollback overwrite"
            )

        parent = self.config_path.parent
        tmp = ExclusiveTempFile.create(parent)
        try:
            tmp.write_bytes(old_bytes)
            # Immediate pre-commit revalidation.
            try:
                recheck = self._read_raw_bytes()
            except ProjectConfigError as exc:
                raise ProjectConfigRollbackError(
                    "cannot rollback project config: {}".format(exc)
                ) from exc
            if project_config_content_sha256(recheck) != expected_current_content_sha256:
                raise ProjectConfigRollbackError(
                    "project config changed after replacement; refusing rollback overwrite"
                )
            tmp.commit(self.config_path)
        except ProjectConfigRollbackError:
            tmp.cleanup()
            raise
        except Exception:
            tmp.cleanup()
            raise

        try:
            restored = self._read_raw_bytes()
        except ProjectConfigError as exc:
            raise ProjectConfigRollbackError(
                "project config unverifiable after rollback: {}".format(exc)
            ) from exc
        if restored != old_bytes:
            raise ProjectConfigRollbackError(
                "project config bytes mismatch after rollback"
            )

    def _exclusive_commit(self, temp_path: Path, target: Path) -> None:
        """Commit temp content to target without overwriting an existing file."""
        try:
            exclusive_create_from_temp(temp_path, target)
        except FileExistsError as exc:
            raise ProjectConfigError(
                "project config already exists: {}".format(PROJECT_CONFIG_RELATIVE)
            ) from exc
        except OSError as exc:
            raise ProjectConfigError(
                "unable to create project config: {}".format(exc)
            ) from exc
