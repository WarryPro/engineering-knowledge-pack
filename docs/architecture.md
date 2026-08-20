# Architecture

## Overview

EKP follows a **knowledge-first, adapter-second** architecture. Human-authored engineering knowledge is the canonical source. Profiles, indexes, and tool-specific rules are derived or composed from that source through the operational pipeline (Phase 3A).

```
knowledge/
    ↓ validate
    ↓ generate-index  →  dist/*.json
    ↓ adapter         →  dist/<profile>/<tool>/
    ↓ assemble        →  bundle-manifest.json
    ↓ deploy          →  consumer project (see deployment.md)
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

See [`adapter-architecture.md`](adapter-architecture.md) for pipeline details and [`deployment.md`](deployment.md) for copying artifacts into a consumer project.

## Repository layers

### `knowledge/` — Source of truth

Contains engineering knowledge as markdown documents organized by domain:

- **Cross-cutting domains** — `engineering/`, `architecture/`, `security/`, `testing/`, `performance/`, `devops/`, `ai/`, `database/`
- **Technology domains** — `php/` (L1), `symfony/` (L2), `typescript/` (L1), `frontend/` (L2), `devops/` (L3), `flutter/` (L2 stub)

Technology knowledge **applies** foundation concepts; it must not redefine them. Layering:

```
L0 Foundation → L1 Language (php, typescript) → L2 Framework (symfony, frontend, flutter) → L3 Ops (devops)
```

Dependency direction is downward only. Graph policy for Phase 4 is **V2**: reuse existing roles (`practice`, `architecture`, …); add explicit `graph-rules.yaml` exceptions when an L2 guide must `depends_on` an L1 guide (e.g. Symfony → PHP, Frontend → TypeScript). Do not introduce a `technology` role until exceptions become costly.

**Technology namespaces:** `EKP-PH`, `EKP-SY`, `EKP-TY`, `EKP-FE`. Do not reuse `EKP-TS` (Testing) or `EKP-SF` (Security).

Each document follows the [knowledge document template](../templates/knowledge-document-template.md) or, for stack guides, the [technology knowledge template](../templates/technology-knowledge-document-template.md), and adheres to the [style guide](style-guide.md).

Knowledge documents must be:

- Understandable without any AI tool
- Free of tool-specific syntax (no Cursor frontmatter, no Copilot directives)
- Self-contained enough to be useful alone, with links to related documents

**Current scale:** 20 published guides; 187 concepts; 21 namespaces.

### `rules/` — Scaffold (not primary output)

Layout reference for tool-specific rule formats. **Deployable output is generated in `dist/`** by the assemble pipeline—not authored directly under `rules/`.

Rules trace back to knowledge documents. If a rule cannot be justified by knowledge, it should not exist.

### `profiles/` — Composed contexts

A profile defines which knowledge applies to a specific context (team, role, workflow). Profiles reference **knowledge paths only**—adapters derive rules at build time.

Operational profiles:

| Profile | Role |
|---------|------|
| `cursor-core` | Minimal L0 bundle (65 rules) — **frozen**; included by stack profiles |
| `cursor-php` | `includes: [cursor-core]` + `php-fundamentals` |
| `cursor-symfony` | `includes: [cursor-core]` + PHP + `symfony-architecture` |
| `cursor-typescript` | `includes: [cursor-core]` + `typescript-fundamentals` |
| `cursor-frontend` | `includes: [cursor-core]` + TypeScript + `frontend-architecture` |
| `cursor-devops` | `includes: [cursor-core]` + `devops-fundamentals` |
| `ekp-php` | `includes: [cursor-php]`; `outputs: [cursor, copilot]` — first stack multi-adapter profile |
| `ekp-core` | Multi-adapter **pilot** (`includes: [cursor-core]`; Cursor + Copilot + Antigravity + Claude) |

Profiles compose knowledge via **`includes`** (ADR-0008). Included profiles contribute knowledge paths only; the root profile owns `adapter`, `filters`, and `outputs`. **`extends` is not supported.**

Example stack profile (`profiles/cursor-php.yaml`):

```yaml
name: cursor-php
includes:
  - cursor-core
knowledge:
  - knowledge/php/php-fundamentals.md
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
- `dist/<profile>/` — from `assemble` (Cursor `.mdc`, optional Copilot/Antigravity/Claude trees, manifests)

Never commit `dist/`. Regenerate locally or in CI.

### `docs/` — Project meta-documentation

Vision, architecture, roadmap, contribution process, deployment—not engineering knowledge.

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
4. Transform  — registered adapters (cursor, copilot, antigravity, claude)
5. Assemble   — Profile bundle + manifests + --verify
6. Deploy     — Copy dist/<profile>/<adapter>/ artifacts (see deployment.md)
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
- Adapters: Cursor (operational `cursor-*` profiles), Copilot on `ekp-php` and `ekp-core`, Antigravity / Claude (`ekp-core` pilot)
- Assemble pipeline with `--verify` (CI verifies all six Cursor profiles, `ekp-php`, and `ekp-core`)

**Planned / deferred:**

- Flutter technology guide and profile (deferred)
- Graph role `technology` (V1) if V2 exceptions proliferate (deferred)
- Expand remaining stack multi-adapter profiles beyond `ekp-php` (deferred)
- Antigravity / Claude on stack profiles (deferred; remain `ekp-core` pilot)

## Related

- [`adapter-architecture.md`](adapter-architecture.md) — pipeline stages
- [`deployment.md`](deployment.md) — consumer copy paths per adapter
- [`folder-structure.md`](folder-structure.md) — directory layout
- [`DEVELOPMENT.md`](../DEVELOPMENT.md) — local validation and CI
