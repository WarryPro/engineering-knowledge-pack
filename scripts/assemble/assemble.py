#!/usr/bin/env python3
"""
Assemble EKP adapter bundles from profiles.

Usage:
    py -3 scripts/assemble/assemble.py --profile cursor-core
    py -3 scripts/assemble/assemble.py --profile cursor-core --clean --verify
"""

import argparse
import json
import shutil
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parents[1]
ADAPTERS_DIR = SCRIPT_DIR.parent / "adapters"

if str(ADAPTERS_DIR) not in sys.path:
    sys.path.insert(0, str(ADAPTERS_DIR))

from common.paths import get_dist_path, get_repo_root
from common.profile_loader import load_profile_by_name
from common.registry import AdapterNotImplementedError, build_default_registry
from antigravity.verify import AntigravityVerifyError
from claude.verify import ClaudeVerifyError
from copilot.verify import CopilotVerifyError
from cursor.manifest import build_bundle_manifest
from cursor.verify import CursorVerifyError, verify_cursor_bundle

INDEX_FILES = (
    "concept-index.json",
    "knowledge-graph.json",
    "adapter-manifest.json",
)

GENERATE_INDEX_HINT = (
    "Run: py -3 scripts/validate/validate.py --generate-index"
)

CURSOR_ADAPTER = "cursor"
CURSOR_BUNDLE_MANIFEST = "bundle-manifest.json"
ADAPTER_MANIFEST_NAME = "adapter-manifest.json"
ASSEMBLE_MANIFEST_NAME = "assemble-manifest.json"


class AssembleError(Exception):
    """Raised when assembly or verification fails."""


def verify_indexes(dist_dir=None):
    # type: (Path) -> list
    """Return missing required index filenames under dist/."""
    target = dist_dir or get_dist_path()
    missing = []
    for name in INDEX_FILES:
        if not (target / name).is_file():
            missing.append(name)
    return missing


def write_json(path, payload):
    # type: (Path, dict) -> Path
    """Write a deterministic JSON document with a trailing newline."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return path


def write_bundle_manifest(bundle_dir, manifest):
    # type: (Path, dict) -> Path
    """Write Cursor-compatible bundle-manifest.json to the profile root."""
    return write_json(bundle_dir / CURSOR_BUNDLE_MANIFEST, manifest)


def adapter_manifest_relpath(adapter_name):
    # type: (str) -> str
    """Return the profile-relative manifest path for an assembled adapter."""
    if adapter_name == CURSOR_ADAPTER:
        return CURSOR_BUNDLE_MANIFEST
    return "{}/{}".format(adapter_name, ADAPTER_MANIFEST_NAME)


def build_assemble_manifest(profile_name, adapter_names):
    # type: (str, list) -> dict
    """
    Build a deterministic profile-level assembly manifest.

    Adapter order matches the resolved profile ``outputs`` list.
    """
    outputs = []
    for adapter_name in adapter_names:
        outputs.append(
            {
                "adapter": adapter_name,
                "directory": adapter_name,
                "manifest": adapter_manifest_relpath(adapter_name),
                "status": "assembled",
            }
        )
    return {
        "profile": profile_name,
        "adapters": list(adapter_names),
        "outputs": outputs,
    }


def resolve_requested_adapters(profile, adapter_registry):
    # type: (dict, object) -> list
    """
    Resolve profile outputs to implemented adapters.

    Fails before generation if any requested adapter is unimplemented.
    """
    adapter_names = list(profile.get("outputs") or [])
    if not adapter_names:
        raise AssembleError(
            "Profile '{}' declared no adapter outputs.".format(profile.get("name"))
        )

    resolved = []
    for adapter_name in adapter_names:
        try:
            resolved.append((adapter_name, adapter_registry.get(adapter_name)))
        except AdapterNotImplementedError as exc:
            raise AssembleError(str(exc))
    return resolved


def verify_bundle(bundle_dir):
    # type: (Path) -> None
    """Verify generated Cursor bundle integrity. Raises AssembleError on failure."""
    try:
        verify_cursor_bundle(bundle_dir)
    except CursorVerifyError as exc:
        raise AssembleError(str(exc))


def assemble(
    profile_name,
    clean=False,
    verify=False,
    repo_root=None,
    dist_dir=None,
    bundle_root=None,
    registry=None,
):
    # type: (str, bool, bool, Path, Path, Path, object) -> dict
    """
    Assemble deployable adapter bundles for a profile.

    Dispatches to registered adapters based on profile ``outputs``.
    Unimplemented adapters fail before any generation.

    Cursor keeps ``bundle-manifest.json`` at the profile root. Other adapters
    write ``<adapter>/adapter-manifest.json``. ``assemble-manifest.json``
    describes the full assembly.

    Returns the Cursor bundle manifest when Cursor was assembled; otherwise
    the last adapter manifest.
    """
    root = repo_root or get_repo_root()
    profile_path = root / "profiles" / "{}.yaml".format(profile_name)
    if not profile_path.is_file():
        raise AssembleError("Profile not found: {}".format(profile_path))

    indexes_dir = dist_dir or (root / "dist")
    bundles_dir = bundle_root or indexes_dir
    missing = verify_indexes(indexes_dir)
    if missing:
        raise AssembleError(
            "Missing required indexes in dist/: {}\n{}".format(
                ", ".join(missing), GENERATE_INDEX_HINT
            )
        )

    profile = load_profile_by_name(profile_name, repo_root=root)
    adapter_registry = registry or build_default_registry()
    requested = resolve_requested_adapters(profile, adapter_registry)
    bundle_dir = bundles_dir / profile_name

    if clean and bundle_dir.exists():
        shutil.rmtree(bundle_dir)

    primary_manifest = None
    cursor_manifest = None
    assembled_names = []

    for adapter_name, adapter in requested:
        adapter_dir = bundle_dir / adapter_name
        adapter["generate"](
            profile_name=profile_name,
            output_dir=adapter_dir,
            profile=profile,
            repo_root=root,
        )

        manifest = adapter["build_manifest"](profile_name, adapter_dir)
        if adapter_name == CURSOR_ADAPTER:
            write_bundle_manifest(bundle_dir, manifest)
            cursor_manifest = manifest
        else:
            write_json(adapter_dir / ADAPTER_MANIFEST_NAME, manifest)
        primary_manifest = manifest
        assembled_names.append(adapter_name)

        if verify:
            try:
                adapter["verify"](bundle_dir)
            except (
                CursorVerifyError,
                CopilotVerifyError,
                AntigravityVerifyError,
                ClaudeVerifyError,
            ) as exc:
                raise AssembleError(str(exc))
            except AssembleError:
                raise
            except Exception as exc:
                raise AssembleError(str(exc))

    assemble_manifest = build_assemble_manifest(profile_name, assembled_names)
    write_json(bundle_dir / ASSEMBLE_MANIFEST_NAME, assemble_manifest)

    if cursor_manifest is not None:
        return cursor_manifest
    return primary_manifest


def main(argv=None):
    # type: (list) -> int
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Assemble EKP adapter bundles from profiles"
    )
    parser.add_argument(
        "--profile",
        required=True,
        help="Profile name (profiles/<name>.yaml)",
    )
    parser.add_argument(
        "--clean",
        action="store_true",
        help="Remove previous bundle output before generation",
    )
    parser.add_argument(
        "--verify",
        action="store_true",
        help="Verify generated bundle integrity",
    )
    args = parser.parse_args(argv)

    try:
        manifest = assemble(
            profile_name=args.profile,
            clean=args.clean,
            verify=args.verify,
        )
    except AssembleError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    bundle_dir = get_dist_path() / args.profile
    print("Assembled bundle:")
    print("  {}".format(bundle_dir))
    if "rules_count" in manifest:
        print("  rules: {}".format(manifest["rules_count"]))
    if manifest.get("adapter") == CURSOR_ADAPTER:
        print("  manifest: {}".format(bundle_dir / CURSOR_BUNDLE_MANIFEST))
    print("  assemble-manifest: {}".format(bundle_dir / ASSEMBLE_MANIFEST_NAME))
    if args.verify:
        print("Verification passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
