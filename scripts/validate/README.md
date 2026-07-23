# Validation

Checks knowledge document structure, frontmatter, and internal links.

## Usage

Run from repository root:

```bash
py -3 scripts/validate/validate.py
```

## What it validates

- Knowledge documents have required frontmatter (`title`, `domain`, `tags`, `severity`, `applies_to`)
- `domain` matches the parent directory under `knowledge/`
- Internal markdown links resolve to existing files
- Profiles reference `knowledge/` paths only (not `rules/`)

## Planned (Phase 5)

- JSON Schema validation against `schema/knowledge-frontmatter.schema.json`
- Profile validation against `schema/profile.schema.json`
- Cross-reference integrity for `related:` frontmatter fields
