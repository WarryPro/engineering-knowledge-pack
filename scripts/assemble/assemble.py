#!/usr/bin/env python3
"""
Assemble EKP adapter bundles from profiles.

Usage:
    py -3 scripts/assemble/assemble.py --profile cursor-core
    py -3 scripts/assemble/assemble.py --profile cursor-core --clean --verify
"""

import argparse
import json
import re
import shutil
import sys
from datetime import datetime
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parents[1]
ADAPTERS_DIR = SCRIPT_DIR.parent / "adapters"

if str(ADAPTERS_DIR) not in sys.path:
    sys.path.insert(0, str(ADAPTERS_DIR))

from common.paths import get_dist_path, get_repo_root
from cursor.generate import generate as generate_cursor_rules
from cursor.naming import orchestrator_filename

INDEX_FILES = (
    "concept-index.json",
    "knowledge-graph.json",
    "adapter-manifest.json",
)

GENERATE_INDEX_HINT = (
    "Run: py -3 scripts/validate/validate.py --generate-index"
)

SOURCE_RE = re.compile(
    r">\s*\*\*Source:\*\*\s*`(knowledge/[^`]+\.md)`"
)
CONCEPT_FILENAME_RE = re.compile(
    r"^concept-(ekp-(?:p(?:0[1-9]|10)|[a-z]{2}\d{2}))",
    re.IGNORECASE,
)
FRONTMATTER_RE = re.compile(r"^---\s*\n.*?\n---\s*\n", re.DOTALL)


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


def _concept_ids_from_rule(filename, content):
    # type: (str, str) -> list
    """Derive concept IDs for a generated rule file."""
    match = CONCEPT_FILENAME_RE.match(filename)
    if match:
        return [match.group(1).upper()]
    return []


def _source_from_rule(content):
    # type: (str) -> str
    """Extract the knowledge source path from a generated rule file."""
    match = SOURCE_RE.search(content)
    return match.group(1) if match else ""


def build_bundle_manifest(profile_name, cursor_dir, generated_at=None):
    # type: (str, Path, str) -> dict
    """Build a deterministic bundle manifest from generated .mdc files."""
    rules = []

    for mdc_path in sorted(cursor_dir.glob("*.mdc")):
        content = mdc_path.read_text(encoding="utf-8")
        rules.append(
            {
                "filename": mdc_path.name,
                "source": _source_from_rule(content),
                "concept_ids": _concept_ids_from_rule(mdc_path.name, content),
            }
        )

    timestamp = generated_at
    if timestamp is None:
        timestamp = datetime.utcnow().replace(microsecond=0).isoformat() + "Z"

    return {
        "profile": profile_name,
        "adapter": "cursor",
        "generated_at": timestamp,
        "rules_count": len(rules),
        "rules": rules,
    }


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
    errors = []
    cursor_dir = bundle_dir / "cursor"
    manifest_path = bundle_dir / "bundle-manifest.json"

    if not cursor_dir.is_dir():
        errors.append("Missing cursor output directory: {}".format(cursor_dir))
        raise AssembleError("\n".join(errors))

    mdc_files = sorted(cursor_dir.glob("*.mdc"))
    if not mdc_files:
        errors.append("No .mdc files generated in {}".format(cursor_dir))

    orchestrator = cursor_dir / orchestrator_filename()
    if not orchestrator.is_file():
        errors.append("Missing orchestrator rule: {}".format(orchestrator.filename()))

    for mdc_path in mdc_files:
        content = mdc_path.read_text(encoding="utf-8")
        if not FRONTMATTER_RE.match(content):
            errors.append("{}: missing YAML frontmatter".format(mdc_path.name))
        if "> **Source:**" not in content:
            errors.append("{}: missing Source reference".format(mdc_path.name))

    if not manifest_path.is_file():
        errors.append("Missing bundle manifest: {}".format(manifest_path))
    else:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest_names = sorted(
            rule["filename"] for rule in manifest.get("rules", [])
        )
        disk_names = sorted(path.name for path in mdc_files)

        if manifest_names != disk_names:
            errors.append(
                "Manifest filenames do not match generated files."
            )

        if manifest.get("rules_count") != len(disk_names):
            errors.append(
                "Manifest rules_count does not match generated file count."
            )

        for rule in manifest.get("rules", []):
            if not rule.get("source"):
                errors.append(
                    "{}: manifest entry missing source".format(
                        rule.get("filename", "?")
                    )
                )

    if errors:
        raise AssembleError("\n".join(errors))


def assemble(profile_name, clean=False, verify=False, repo_root=None):
    # type: (str, bool, bool, Path) -> dict
    """
    Assemble a deployable adapter bundle for a profile.

    Returns the bundle manifest dict.
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

    bundle_dir = dist_dir / profile_name
    cursor_dir = bundle_dir / "cursor"

    if clean and bundle_dir.exists():
        shutil.rmtree(bundle_dir)

    generate_cursor_rules(
        profile_name=profile_name,
        output_dir=cursor_dir,
    )

    manifest = build_bundle_manifest(profile_name, cursor_dir)
    write_bundle_manifest(bundle_dir, manifest)

    if verify:
        verify_bundle(bundle_dir)

    return manifest


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
