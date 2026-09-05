"""Reusable assembly service for consumer CLI workflows."""

from __future__ import annotations

import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, List, Optional

from ekp.paths import get_ekp_root

if TYPE_CHECKING:
    from ekp.composition import ResolvedComposition


@dataclass
class AssemblyRequest:
    """Structured input for profile assembly."""

    profile: str
    verify: bool = True
    clean: bool = True
    resource_root: Optional[Path] = None
    workspace_dir: Optional[Path] = None
    output_root: Optional[Path] = None


@dataclass
class CompositionAssemblyRequest:
    """Structured input for component-based composition assembly."""

    components: List[str]
    outputs: Optional[List[str]] = None
    verify: bool = True
    clean: bool = True
    resource_root: Optional[Path] = None
    workspace_dir: Optional[Path] = None
    output_root: Optional[Path] = None

    def __post_init__(self) -> None:
        if self.outputs is None:
            self.outputs = ["cursor"]
        else:
            self.outputs = list(self.outputs)


@dataclass
class AssemblyResult:
    """Structured output from profile or composition assembly."""

    profile: str
    adapters: List[str] = field(default_factory=list)
    bundle_path: Optional[Path] = None
    rules_count: Optional[int] = None
    manifest: Optional[dict] = None
    resource_root: Optional[Path] = None
    workspace_dir: Optional[Path] = None
    output_root: Optional[Path] = None
    composition: Optional["ResolvedComposition"] = None
    _temp_ctx: object = field(default=None, repr=False, compare=False)


class AssemblyService:
    """Thin service boundary over validate/index/assemble pipeline."""

    def assemble(self, request: AssemblyRequest) -> AssemblyResult:
        resource_root = Path(request.resource_root or get_ekp_root())
        workspace_dir, output_root, temp_ctx = self._prepare_workspace(
            request.workspace_dir,
            request.output_root,
            resource_root,
        )

        self._generate_indexes(resource_root, workspace_dir)
        manifest, adapters = self._run_assemble(
            profile=request.profile,
            resource_root=resource_root,
            workspace_dir=workspace_dir,
            output_root=output_root,
            clean=request.clean,
            verify=request.verify,
        )

        bundle_path = output_root / request.profile
        rules_count = manifest.get("rules_count") if isinstance(manifest, dict) else None

        return AssemblyResult(
            profile=request.profile,
            adapters=adapters,
            bundle_path=bundle_path,
            rules_count=rules_count,
            manifest=manifest,
            resource_root=resource_root,
            workspace_dir=workspace_dir,
            output_root=output_root,
            composition=None,
            _temp_ctx=temp_ctx,
        )

    def assemble_composition(
        self, request: CompositionAssemblyRequest
    ) -> AssemblyResult:
        from ekp.composition import (
            PROJECT_COMPOSITION_PROFILE,
            ComponentRegistry,
            CompositionError,
            build_ephemeral_composition_profile,
            resolve_composition,
        )

        resource_root = Path(request.resource_root or get_ekp_root())
        workspace_dir, output_root, temp_ctx = self._prepare_workspace(
            request.workspace_dir,
            request.output_root,
            resource_root,
        )

        try:
            registry = ComponentRegistry.load(resource_root)
            composition = resolve_composition(request.components, registry)
            ephemeral = build_ephemeral_composition_profile(
                composition, request.outputs or []
            )
        except CompositionError as exc:
            raise RuntimeError(str(exc)) from exc

        self._generate_indexes(resource_root, workspace_dir)
        manifest, adapters = self._run_assemble_resolved(
            profile_name=PROJECT_COMPOSITION_PROFILE,
            profile=ephemeral,
            resource_root=resource_root,
            workspace_dir=workspace_dir,
            output_root=output_root,
            clean=request.clean,
            verify=request.verify,
        )

        bundle_path = output_root / PROJECT_COMPOSITION_PROFILE
        rules_count = manifest.get("rules_count") if isinstance(manifest, dict) else None

        return AssemblyResult(
            profile=PROJECT_COMPOSITION_PROFILE,
            adapters=adapters,
            bundle_path=bundle_path,
            rules_count=rules_count,
            manifest=manifest,
            resource_root=resource_root,
            workspace_dir=workspace_dir,
            output_root=output_root,
            composition=composition,
            _temp_ctx=temp_ctx,
        )

    def _prepare_workspace(
        self,
        workspace_dir: Optional[Path],
        output_root: Optional[Path],
        resource_root: Path,
    ):
        owns_temp = workspace_dir is None and output_root is None
        if owns_temp:
            temp_ctx = tempfile.TemporaryDirectory(prefix="ekp-assembly-")
            temp_root = Path(temp_ctx.name)
            workspace = temp_root / "workspace"
            output = temp_root / "output"
        else:
            temp_ctx = None
            workspace = Path(workspace_dir or (resource_root / "dist"))
            output = Path(output_root or workspace)

        workspace.mkdir(parents=True, exist_ok=True)
        output.mkdir(parents=True, exist_ok=True)
        return workspace, output, temp_ctx

    def _scripts_paths(self, resource_root: Path):
        scripts = resource_root / "scripts"
        return (
            scripts / "adapters",
            scripts / "assemble",
            scripts / "validate",
        )

    def _ensure_import_paths(self, resource_root: Path) -> None:
        for path in self._scripts_paths(resource_root):
            entry = str(path)
            if entry not in sys.path:
                sys.path.insert(0, entry)

    def _generate_indexes(self, resource_root: Path, workspace_dir: Path) -> None:
        adapters_dir, assemble_dir, validate_dir = self._scripts_paths(resource_root)
        self._ensure_import_paths(resource_root)

        if str(validate_dir) not in sys.path:
            sys.path.insert(0, str(validate_dir))

        from validate import run_generate_index

        exit_code = run_generate_index(output_dir=workspace_dir, repo_root=resource_root)
        if exit_code != 0:
            raise RuntimeError("Index generation failed with exit code {}".format(exit_code))

    def _run_assemble(
        self,
        profile: str,
        resource_root: Path,
        workspace_dir: Path,
        output_root: Path,
        clean: bool,
        verify: bool,
    ):
        self._ensure_import_paths(resource_root)

        from assemble import AssembleError, assemble
        from common.paths import clear_path_context, set_path_context
        from common.profile_loader import load_profile_by_name

        set_path_context(repo_root=resource_root, dist_dir=workspace_dir)
        try:
            manifest = assemble(
                profile_name=profile,
                clean=clean,
                verify=verify,
                repo_root=resource_root,
                dist_dir=workspace_dir,
                bundle_root=output_root,
            )
        except AssembleError as exc:
            raise RuntimeError(str(exc)) from exc
        finally:
            clear_path_context()

        profile_data = load_profile_by_name(profile, repo_root=resource_root)
        adapters = list(profile_data.get("outputs") or [])
        return manifest, adapters

    def _run_assemble_resolved(
        self,
        profile_name: str,
        profile: dict,
        resource_root: Path,
        workspace_dir: Path,
        output_root: Path,
        clean: bool,
        verify: bool,
    ):
        self._ensure_import_paths(resource_root)

        from assemble import AssembleError, assemble_resolved_profile
        from common.paths import clear_path_context, set_path_context

        set_path_context(repo_root=resource_root, dist_dir=workspace_dir)
        try:
            manifest = assemble_resolved_profile(
                profile_name=profile_name,
                profile=profile,
                clean=clean,
                verify=verify,
                repo_root=resource_root,
                dist_dir=workspace_dir,
                bundle_root=output_root,
            )
        except AssembleError as exc:
            raise RuntimeError(str(exc)) from exc
        finally:
            clear_path_context()

        adapters = list(profile.get("outputs") or [])
        return manifest, adapters
