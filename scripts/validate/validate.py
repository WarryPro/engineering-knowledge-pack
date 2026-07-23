#!/usr/bin/env python3
"""
EKP validation CLI (skeleton).

Validates knowledge document frontmatter, domain alignment, and internal links.
Run from repository root: py -3 scripts/validate/validate.py
"""

import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
KNOWLEDGE_DIR = REPO_ROOT / "knowledge"
PROFILES_DIR = REPO_ROOT / "profiles"

REQUIRED_FIELDS = {"title", "domain", "tags", "severity", "applies_to"}
VALID_SEVERITIES = {"required", "recommended", "advisory"}
VALID_DOMAINS = {
    "engineering", "architecture", "php", "symfony", "flutter",
    "typescript", "frontend", "database", "security", "testing",
    "performance", "devops", "ai",
}

FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---", re.DOTALL)
LINK_RE = re.compile(r"\[[^\]]+\]\(([^)]+)\)")
SKIP_LINK_PREFIXES = ("http://", "https://", "mailto:", "#")


def parse_frontmatter(content):
    """Parse a minimal YAML subset (scalars and inline lists)."""
    match = FRONTMATTER_RE.match(content)
    if not match:
        return {}

    data = {}
    for line in match.group(1).splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if ":" not in line:
            continue
        key, _, value = line.partition(":")
        key = key.strip()
        value = value.strip()
        if value.startswith("[") and value.endswith("]"):
            items = [v.strip().strip("'\"") for v in value[1:-1].split(",") if v.strip()]
            data[key] = items
        else:
            data[key] = value.strip("'\"")
    return data


def collect_knowledge_files():
    return sorted(
        p for p in KNOWLEDGE_DIR.rglob("*.md")
        if p.name != "README.md"
    )


def validate_knowledge_file(path):
    errors = []
    rel = path.relative_to(REPO_ROOT).as_posix()
    content = path.read_text(encoding="utf-8")
    fm = parse_frontmatter(content)

    if not fm:
        return [f"{rel}: missing YAML frontmatter"]

    missing = REQUIRED_FIELDS - fm.keys()
    if missing:
        errors.append(f"{rel}: missing frontmatter fields: {', '.join(sorted(missing))}")

    domain = fm.get("domain")
    if isinstance(domain, str):
        if domain not in VALID_DOMAINS:
            errors.append(f"{rel}: invalid domain '{domain}'")
        expected = path.relative_to(KNOWLEDGE_DIR).parts[0]
        if domain != expected and not (domain == "architecture" and "decisions" in path.parts):
            errors.append(f"{rel}: domain '{domain}' does not match directory '{expected}'")

    severity = fm.get("severity")
    if isinstance(severity, str) and severity not in VALID_SEVERITIES:
        errors.append(f"{rel}: invalid severity '{severity}'")

    tags = fm.get("tags")
    if isinstance(tags, list) and len(tags) == 0:
        errors.append(f"{rel}: tags must contain at least one item")

    applies_to = fm.get("applies_to")
    if isinstance(applies_to, list) and len(applies_to) == 0:
        errors.append(f"{rel}: applies_to must contain at least one item")

    for link_match in LINK_RE.finditer(content):
        target = link_match.group(1).strip()
        if target.startswith(SKIP_LINK_PREFIXES):
            continue
        resolved = (path.parent / target).resolve()
        if not resolved.exists():
            errors.append(f"{rel}: broken link to '{target}'")

    return errors


def validate_profiles():
    errors = []
    if not PROFILES_DIR.exists():
        return errors

    for profile in sorted(PROFILES_DIR.glob("*.yaml")):
        rel = profile.relative_to(REPO_ROOT).as_posix()
        text = profile.read_text(encoding="utf-8")
        if "rules:" in text:
            errors.append(f"{rel}: profiles must reference knowledge only; remove 'rules:' entries")
        for line in text.splitlines():
            if line.strip().startswith("- knowledge/"):
                doc_path = REPO_ROOT / line.strip().removeprefix("- ").strip()
                if not doc_path.exists():
                    errors.append(f"{rel}: references missing document '{doc_path.relative_to(REPO_ROOT).as_posix()}'")
    return errors


def main():
    if not KNOWLEDGE_DIR.exists():
        print("No knowledge/ directory found.", file=sys.stderr)
        return 1

    knowledge_files = collect_knowledge_files()
    errors = []

    if not knowledge_files:
        print("No knowledge documents to validate (foundation phase).")
    else:
        for path in knowledge_files:
            errors.extend(validate_knowledge_file(path))

    errors.extend(validate_profiles())

    if errors:
        print(f"Validation failed with {len(errors)} error(s):\n", file=sys.stderr)
        for error in errors:
            print(f"  - {error}", file=sys.stderr)
        return 1

    print("Validation passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
