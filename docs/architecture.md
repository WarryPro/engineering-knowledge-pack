# Architecture

## Overview

EKP follows a **knowledge-first, adapter-second** architecture. Human-authored engineering knowledge is the canonical source. Profiles, indexes, and tool-specific rules are derived or composed from that source through the operational pipeline (Phase 3A).

```
knowledge/
    ↓ validate
    ↓ generate-index  →  dist/*.json
    ↓ adapter         →  dist/<profile>/<tool>/
    ↓ assemble        →  bundle-manifest.json
    ↓ deploy          →  consumer project (e.g. .cursor/rules/)
```

```
┌─────────────────────────────────────────────────────────┐
│                     knowledge/                          │
│         (tool-agnostic markdown, source of truth)       │
└────────────────────────┬────────────────────────────────┘
                         │
           ┌─────────────┼─────────────┐
           ▼             ▼             ▼
    ┌──────────┐  ┌──────────┐  ┌──────────┐
    │ profiles/│  │ examples/│  │ templates│
    │ (compose │  │ (educational│ │ (authoring│
    │  sets)   │  │  samples) │  │ scaffolds)│
    └────┬─────┘  └──────────┘  └──────────┘
         │
         ▼
    ┌──────────┐     ┌──────────┐
    │ scripts/ │ ──► │  dist/   │  (gitignored, generated)
    │ validate │     │ bundles  │
    │ adapters │     └──────────┘
    │ assemble │
    └──────────┘
```

See [`adapter-architecture.md`](adapter-architecture.md) for pipeline details.

## Repository layers

### `knowledge/` — Source of truth

Contains engineering knowledge as markdown documents organized by domain:

- **Cross-cutting domains** — `engineering/`, `architecture/`, `security/`, `testing/`, `performance/`, `devops/`, `ai/`, `database/`
- **Technology domains** — `php/`, `symfony/`, `flutter/`, `typescript/`, `frontend/` (Phase 4 — stubs today)

Each document follows the [knowledge document template](../templates/knowledge-document-template.md) and adheres to the [style guide](style-guide.md).

Knowledge documents must be:

- Understandable without any AI tool
- Free of tool-specific syntax (no Cursor frontmatter, no Copilot directives)
- Self-contained enough to be useful alone, with links to related documents

**Current scale:** 16 published guides, 155 concepts, 17 namespaces.

### `rules/` — Scaffold (not primary output)

Layout reference for tool-specific rule formats. **Deployable output is generated in `dist/`** by the assemble pipeline—not authored directly under `rules/`.

Rules trace back to knowledge documents. If a rule cannot be justified by knowledge, it should not exist.

### `profiles/` — Composed contexts

A profile defines which knowledge applies to a specific context (team, role, workflow). Profiles reference **knowledge paths only**—adapters derive rules at build time.

Operational example (`profiles/cursor-core.yaml`):

```yaml
name: cursor-core
description: Minimal EKP knowledge bundle for Cursor AI-assisted development.
knowledge:
  - knowledge/engineering/engineering-principles.md
  - knowledge/ai/ai-assisted-development.md
  - knowledge/engineering/refactoring.md
  - knowledge/testing/testing.md
  - knowledge/engineering/error-handling.md
  - knowledge/architecture/layering-and-boundaries.md
adapter:
  target:
    - cursor
  include:
    adapter_priority:
      - high
outputs:
  - cursor
```

See `templates/profile-template.yaml` and `schema/profile.schema.json`.

### `templates/` — Authoring scaffolds

Reusable document structures for knowledge, ADRs, checklists, profiles, and rules.

### `examples/` — Educational samples

Demonstrates ADR format and review checklists. **Not** production decisions—see [`examples/README.md`](../examples/README.md).

### `scripts/` — Operational pipeline

| Component | Path | Role |
|-----------|------|------|
| Validator | `scripts/validate/` | Structure, graph, concepts, links |
| Adapters | `scripts/adapters/` | Knowledge → tool formats (Cursor operational) |
| Assemble | `scripts/assemble/` | Profile → deployable bundle + manifest |

Scripts are idempotent, testable, and documented. See [`DEVELOPMENT.md`](../DEVELOPMENT.md).

### `dist/` — Generated artifacts (gitignored)

- `dist/concept-index.json`, `knowledge-graph.json`, `adapter-manifest.json` — from `validate --generate-index`
- `dist/<profile>/cursor/*.mdc` + `bundle-manifest.json` — from `assemble`

Never commit `dist/`. Regenerate locally or in CI.

### `docs/` — Project meta-documentation

Vision, architecture, roadmap, contribution process—not engineering knowledge.

## Knowledge vs. rules vs. profiles

| Aspect | Knowledge | Rules (generated) | Profiles |
|--------|-----------|-------------------|----------|
| **Audience** | Engineers (human and AI) | AI assistants | Both, scoped |
| **Format** | Markdown | Tool-specific (`.mdc`, etc.) | YAML manifest |
| **Authored by** | Engineers | Adapters from knowledge | Composed from knowledge paths |
| **Stability** | High — changes require review | Regenerated on knowledge changes | Low — easy to recompose |
| **Contains reasoning** | Yes — trade-offs, context | No — concise directives only | No — references only |

## Adapter pipeline (operational)

```
1. Validate   — Frontmatter, graph, concepts, links
2. Index      — dist/*.json for adapter consumption
3. Extract    — scripts/adapters/common/ parses knowledge
4. Transform  — scripts/adapters/cursor/ → .mdc rules
5. Assemble   — Profile bundle + bundle-manifest.json + --verify
6. Deploy     — Copy dist/<profile>/cursor/ to consumer .cursor/rules/
```

### Design constraints

- **Deterministic** — same knowledge + profile → same output
- **Incremental** — changed-only validation for CI efficiency
- **Explicit contract** — `adapter_priority`, concept IDs, Decision Flows

### Metadata contract

Knowledge frontmatter is validated against `schema/knowledge-frontmatter.schema.json`. Adapters filter on `adapter_priority`, `severity`, and profile `knowledge` paths.

## Extension points

**Operational today:**

- Validator v2.3 with graph rules, namespaces, index generation, reports
- Cursor adapter and `cursor-core` profile (65 rules)
- Assemble pipeline with `--verify`

**Planned (Phase 4–5):**

- Additional technology domains and profiles
- Copilot and Claude adapters
- Profile versioning for pinned releases

## Related

- [`adapter-architecture.md`](adapter-architecture.md) — pipeline stages
- [`folder-structure.md`](folder-structure.md) — directory layout
- [`DEVELOPMENT.md`](../DEVELOPMENT.md) — local validation and CI
