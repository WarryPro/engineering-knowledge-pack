"""Navigation README validation."""

import re
from pathlib import Path

NAVIGATION_READMES = [
    "knowledge/engineering/README.md",
    "knowledge/testing/README.md",
    "knowledge/architecture/README.md",
    "knowledge/ai/README.md",
    "knowledge/security/README.md",
    "knowledge/performance/README.md",
    "knowledge/database/README.md",
    "knowledge/php/README.md",
    "knowledge/symfony/README.md",
]

INDEX_SECTIONS = {
    "published",
    "foundation",
    "practices",
    "patterns",
    "procedures",
}

LINK_RE = re.compile(r"\[[^\]]+\]\(([^)]+)\)")


def _section_name(line):
    # type: (str) -> str
    if line.startswith("## "):
        return line[3:].strip().lower()
    return ""


def _parse_index_links(content, readme_dir, repo_root):
    # type: (str, Path, Path) -> list
    """Extract markdown link targets from navigation index sections."""
    links = []
    in_index = False

    for line in content.splitlines():
        section = _section_name(line)
        if section:
            in_index = section in INDEX_SECTIONS
            continue

        if not in_index:
            continue

        for match in LINK_RE.finditer(line):
            target = match.group(1).strip()
            if target.startswith(("http://", "https://", "mailto:", "#")):
                continue
            resolved = (readme_dir / target).resolve()
            try:
                rel = resolved.relative_to(repo_root.resolve()).as_posix()
            except ValueError:
                rel = target
            links.append(rel)

    return links


def _domain_from_readme(readme_path):
    # type: (str) -> str
    parts = Path(readme_path).parts
    if len(parts) >= 2 and parts[0] == "knowledge":
        return parts[1]
    return ""


def validate_readmes(repo_root, knowledge_doc_paths, navigation_readmes=None):
    # type: (Path, list, list) -> tuple
    """R-R1 and R-R2 for navigation READMEs. Returns (errors, warnings)."""
    errors = []
    warnings = []

    if navigation_readmes is None:
        navigation_readmes = NAVIGATION_READMES

    docs_by_domain = {}  # type: dict
    for doc_path in knowledge_doc_paths:
        domain = Path(doc_path).parts[1] if doc_path.startswith("knowledge/") else ""
        docs_by_domain.setdefault(domain, set()).add(doc_path)

    indexed_by_domain = {}  # type: dict

    for readme_rel in navigation_readmes:
        readme_path = repo_root / readme_rel
        if not readme_path.is_file():
            errors.append("[README] navigation README missing: {}".format(readme_rel))
            continue

        content = readme_path.read_text(encoding="utf-8")
        links = _parse_index_links(content, readme_path.parent, repo_root)
        domain = _domain_from_readme(readme_rel)
        indexed = set()

        for link in links:
            if not link.endswith(".md"):
                continue
            indexed.add(link)
            if not (repo_root / link).is_file():
                errors.append("[README] {}: missing target: {}".format(readme_rel, link))

        indexed_by_domain[domain] = indexed

    for domain, docs in docs_by_domain.items():
        indexed = indexed_by_domain.get(domain, set())
        for doc_path in sorted(docs):
            if doc_path not in indexed:
                warnings.append(
                    "[README] published document not indexed in domain README: {}".format(
                        doc_path
                    )
                )

    return errors, warnings
