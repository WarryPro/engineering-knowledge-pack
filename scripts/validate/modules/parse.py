"""YAML frontmatter parsing for knowledge documents."""

import re
from pathlib import Path
from typing import Dict, List, Tuple, Union

import yaml

FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---", re.DOTALL)


def parse_document(path):
    # type: (Path) -> Tuple[Union[Dict, None], str, List[str]]
    """
    Parse a knowledge document into frontmatter and body.

    Returns (frontmatter, body, errors). frontmatter is None when parsing fails.
    """
    rel = path.as_posix()
    try:
        content = path.read_text(encoding="utf-8")
    except OSError as exc:
        return None, "", ["{}: cannot read file: {}".format(rel, exc)]

    match = FRONTMATTER_RE.match(content)
    if not match:
        return None, content, ["{}: missing YAML frontmatter".format(rel)]

    body = content[match.end():]
    raw_yaml = match.group(1)

    try:
        frontmatter = yaml.safe_load(raw_yaml)
    except yaml.YAMLError as exc:
        return None, body, ["{}: invalid YAML frontmatter: {}".format(rel, exc)]

    if frontmatter is None:
        return None, body, ["{}: frontmatter is empty".format(rel)]

    if not isinstance(frontmatter, dict):
        return None, body, ["{}: frontmatter must be a mapping".format(rel)]

    return frontmatter, body, []


def normalize_list(value):
    # type: (object) -> list
    """Return a list for graph metadata fields; missing values become []."""
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]
