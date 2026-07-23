# Style Guide

Conventions for authoring content in EKP. Consistency makes knowledge discoverable, adapters predictable, and reviews efficient.

## Naming conventions

### Files and directories

| Element | Convention | Example |
|---------|------------|---------|
| Directories | lowercase kebab-case | `knowledge/error-handling/` |
| Knowledge files | lowercase kebab-case, singular topic | `service-layer-boundaries.md` |
| Profile files | lowercase kebab-case | `symfony-api.yaml` |
| Rule files | lowercase kebab-case, tool prefix in directory | `rules/cursor/symfony-api.mdc` |

### Document titles

- Use **title case** in the `title` frontmatter field
- Match the filename semantically: `service-layer-boundaries.md` → `title: Service Layer Boundaries`
- Be specific: prefer "Transaction Boundary Rules for Write Operations" over "Transactions"

### Identifiers in frontmatter

```yaml
domain: symfony          # matches knowledge/ subdirectory
tags: [layering, di]     # lowercase, no spaces
severity: recommended    # required | recommended | advisory
applies_to: [backend]    # lowercase context identifiers
```

## Markdown style

### General rules

- Use ATX-style headings (`#`, `##`, `###`) — not Setext (underlines)
- One top-level heading (`#`) per document, matching the `title` in frontmatter
- Maximum heading depth: `###` (three levels). If you need deeper nesting, split the document.
- Use fenced code blocks with language identifiers
- Use relative links for internal references: `[architecture](../architecture/hexagonal-architecture.md)`
- No HTML unless required for elements markdown cannot express

### Lists

- Use `-` for unordered lists (not `*` or `+`)
- Use numbered lists only when order matters
- Keep list items parallel in structure and tense

### Code examples

- Prefer **realistic** examples over `foo`/`bar` placeholders
- Show **good** and **bad** patterns when illustrating a principle
- Label non-obvious examples:

```markdown
<!-- Good -->
...

<!-- Avoid -->
...
```

### Tables

Use tables for structured comparisons (e.g., severity levels, tool mappings). Do not use tables for prose.

## Document structure

### Knowledge documents

Every knowledge document follows the [knowledge document template](../templates/knowledge-document-template.md):

1. **Frontmatter** — metadata for filtering and adapter consumption
2. **Summary** — one paragraph: what this document covers and when to apply it
3. **Context** — when and why this guidance matters
4. **Guidance** — the actual practices, patterns, or principles
5. **Trade-offs** — what you gain and what you sacrifice
6. **Examples** — concrete illustrations (optional but encouraged)
7. **Related** — links to related knowledge documents

### Rules

Rules are concise. They translate knowledge into directives an AI assistant can follow during coding. Follow the [cursor rule template](../templates/cursor-rule-template.md) structure.

### Decision records

Follow the [decision record template](../templates/decision-record-template.md). Place in `knowledge/architecture/decisions/adr-<number>-<topic>.md` (zero-padded four-digit number, e.g. `adr-0004-clean-code-position-in-knowledge-graph.md`). Set `type: decision-record` in frontmatter when used. One decision per record.

### Review checklists

Follow the [review checklist template](../templates/review-checklist-template.md). Place in `knowledge/<domain>/checklists/<name>.md`. Set `type: checklist` in frontmatter.

### Profiles

Follow the [profile template](../templates/profile-template.yaml). Place in `profiles/<name>.yaml`. Profiles reference knowledge paths only.

## Frontmatter schema

All knowledge documents must include:

```yaml
---
title: Document Title
domain: engineering          # required — matches knowledge/ subdirectory
tags: [tag-one, tag-two]     # required — at least one tag
severity: recommended        # required — required | recommended | advisory
applies_to: [backend, api]   # required — context identifiers
related: []                  # optional — paths to related documents
type: guide                  # optional — guide | checklist | decision-record
---
```

### Severity levels

| Level | Meaning |
|-------|---------|
| `required` | Must be followed. Violations are defects. |
| `recommended` | Should be followed unless there is a documented reason not to. |
| `advisory` | Consider during design. No enforcement expectation. |

## Quality standards

### Every document must

- [ ] Have a clear, single concern (if it covers two unrelated topics, split it)
- [ ] Explain **why**, not just **what**
- [ ] Include trade-offs — no practice is free
- [ ] Be actionable — a reader should know what to do differently after reading
- [ ] Use valid frontmatter matching the schema above
- [ ] Link to related documents where they exist

### Every document must not

- Duplicate content that exists in another document (link instead)
- Contain tool-specific syntax (Cursor directives, Copilot comments)
- Include time-sensitive references ("as of 2024…") without a maintenance plan
- Use vague language ("consider best practices") without defining what those practices are
- Exceed ~500 lines — if it does, it likely covers too much

### Writing tone

- Direct and professional
- Second person ("prefer explicit types") or imperative ("use dependency injection")
- No filler phrases ("it's worth noting that", "in today's fast-paced world")
- Assume the reader is a competent engineer, not a beginner

## Review checklist for contributors

Before submitting a knowledge document, verify:

1. Filename follows kebab-case convention
2. Frontmatter is complete and valid
3. Summary accurately describes the content in one paragraph
4. At least one trade-off is documented
5. No tool-specific syntax in knowledge documents
6. Internal links resolve correctly
7. Document length is appropriate for its scope
