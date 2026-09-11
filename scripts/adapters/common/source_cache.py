"""Assistant-neutral canonical source loading keyed by source_path."""

from __future__ import annotations

from common.selection import markdown_cache_for_profile, read_knowledge_document


def build_source_markdown_cache(repo_root, source_paths, reader=None):
    # type: (object, object, object) -> object
    """
    Return ``get_markdown(source_path)`` caching by canonical path only.

    Same source appearing in GLOBAL and multiple WORKSPACE scopes is read
    from disk once per adapter invocation. Scope/assistant are not part of
    the cache key.

    ``reader`` defaults to :func:`read_knowledge_document` and is the
    instrumentable filesystem boundary for tests.
    """
    unique = []
    seen = set()
    for path in source_paths:
        if path in seen:
            continue
        seen.add(path)
        unique.append(path)

    if reader is None:
        return markdown_cache_for_profile(repo_root, unique)

    cache = {}

    def get_markdown(path):
        # type: (str) -> str
        if path not in cache:
            cache[path] = reader(repo_root, path)
        return cache[path]

    return get_markdown
