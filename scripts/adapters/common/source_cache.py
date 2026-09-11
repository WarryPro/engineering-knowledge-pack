"""Assistant-neutral canonical source loading keyed by source_path."""

from __future__ import annotations

from common.selection import markdown_cache_for_profile


def build_source_markdown_cache(repo_root, source_paths):
    # type: (object, object) -> object
    """
    Return ``get_markdown(source_path)`` caching by canonical path.

    Same source appearing in multiple scopes is read/parsed once per invocation.
    """
    unique = []
    seen = set()
    for path in source_paths:
        if path in seen:
            continue
        seen.add(path)
        unique.append(path)
    return markdown_cache_for_profile(repo_root, unique)
