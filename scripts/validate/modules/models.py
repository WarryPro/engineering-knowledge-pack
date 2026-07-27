"""Document model for the EKP knowledge graph."""

from pathlib import Path
from typing import Dict, List, Tuple

from .parse import normalize_list, parse_document

FOUNDATION_PATH = "knowledge/engineering/engineering-principles.md"


class DocumentNode(object):
    """A parsed knowledge document and its graph metadata."""

    def __init__(
        self,
        path,
        frontmatter,
        body,
        title="",
        domain="",
        role="",
        depends_on=None,
        implements=None,
        related=None,
        concept_ids=None,
    ):
        # type: (...) -> None
        self.path = path
        self.frontmatter = frontmatter
        self.body = body
        self.title = title
        self.domain = domain
        self.role = role
        self.depends_on = depends_on or []
        self.implements = implements or []
        self.related = related or []
        self.concept_ids = concept_ids or []

    @classmethod
    def from_path(cls, path, repo_root):
        # type: (Path, Path) -> Tuple[DocumentNode, List[str]]
        """Build a DocumentNode from a file path."""
        rel = path.relative_to(repo_root).as_posix()
        frontmatter, body, errors = parse_document(path)
        if errors:
            return None, errors
        if frontmatter is None:
            return None, ["{}: missing frontmatter".format(rel)]

        node = cls(
            path=rel,
            frontmatter=frontmatter,
            body=body,
            title=str(frontmatter.get("title", "")),
            domain=str(frontmatter.get("domain", "")),
            role=str(frontmatter.get("role", "")),
            depends_on=normalize_list(frontmatter.get("depends_on")),
            implements=normalize_list(frontmatter.get("implements")),
            related=normalize_list(frontmatter.get("related")),
            concept_ids=normalize_list(frontmatter.get("concept_ids")),
        )
        return node, []

    @property
    def is_foundation(self):
        # type: () -> bool
        return self.role == "foundation"
