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


def write_bundle_manifest(bundle_dir, manifest):
    # type: (Path, dict) -> Path
    """Write bundle-manifest.json to the bundle directory."""
    manifest_path = bundle_dir / "bundle-manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return manifest_path


def verify_bundle(bundle_dir):
    # type: (Path) -> None
    """Verify generated bundle integrity. Raises AssembleError on failure."""
    try:
        verify_cursor_bundle(bundle_dir)
    except CursorVerifyError as exc:
        raise AssembleError(str(exc))


def assemble(profile_name, clean=False, verify=False, repo_root=None, registry=None):
    # type: (str, bool, bool, Path, object) -> dict
    """
    Assemble deployable adapter bundles for a profile.

    Dispatches to registered adapters based on profile ``outputs``.
    Returns the primary bundle manifest dict (last adapter assembled).
    """
    root = repo_root or get_repo_root()
    profile_path = root / "profiles" / "{}.yaml".format(profile_name)
    if not profile_path.is_file():
        raise AssembleError("Profile not found: {}".format(profile_path))

    dist_dir = root / "dist"
    missing = verify_indexes(dist_dir)
    if missing:
        raise AssembleError(
            "Missing required indexes in dist/: {}\n{}".format(
                ", ".join(missing), GENERATE_INDEX_HINT
            )
        )

    profile = load_profile_by_name(profile_name, repo_root=root)
    adapter_registry = registry or build_default_registry()
    bundle_dir = dist_dir / profile_name

    if clean and bundle_dir.exists():
        shutil.rmtree(bundle_dir)

    primary_manifest = None
    for adapter_name in profile["outputs"]:
        try:
            adapter = adapter_registry.get(adapter_name)
        except AdapterNotImplementedError as exc:
            raise AssembleError(str(exc))

        adapter_dir = bundle_dir / adapter_name
        adapter["generate"](
            profile_name=profile_name,
            output_dir=adapter_dir,
            profile=profile,
            repo_root=root,
        )

        manifest = adapter["build_manifest"](profile_name, adapter_dir)
        write_bundle_manifest(bundle_dir, manifest)
        primary_manifest = manifest

        if verify:
            try:
                adapter["verify"](bundle_dir)
            except CursorVerifyError as exc:
                raise AssembleError(str(exc))

    if primary_manifest is None:
        raise AssembleError(
            "Profile '{}' declared no adapter outputs.".format(profile_name)
        )

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
    print("  rules: {}".format(manifest["rules_count"]))
    print("  manifest: {}".format(bundle_dir / "bundle-manifest.json"))
    if args.verify:
        print("Verification passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
