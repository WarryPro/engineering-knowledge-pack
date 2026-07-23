# Architecture

## Overview

EKP follows a **knowledge-first, adapter-second** architecture. Human-authored engineering knowledge is the canonical source. Everything else—AI rules, profiles, checklists—is derived or composed from that source.

```
┌─────────────────────────────────────────────────────────┐
│                     knowledge/                          │
│         (tool-agnostic markdown, source of truth)     │
└────────────────────────┬────────────────────────────────┘
                         │
           ┌─────────────┼─────────────┐
           ▼             ▼             ▼
    ┌──────────┐  ┌──────────┐  ┌──────────┐
    │  rules/  │  │ profiles/│  │ examples/│
    │ (per-tool│  │ (composed│  │ (reference│
    │  output) │  │  sets)   │  │  usage)  │
    └────┬─────┘  └────┬─────┘  └──────────┘
         │             │
         └──────┬──────┘
                ▼
         ┌──────────┐
         │ scripts/ │
         │(adapters)│
         └──────────┘
```

## Repository layers

### `knowledge/` — Source of truth

Contains engineering knowledge as markdown documents organized by domain:

- **Cross-cutting domains** — `engineering/`, `architecture/`, `security/`, `testing/`, `performance/`, `devops/`, `ai/`
- **Technology domains** — `php/`, `symfony/`, `flutter/`, `typescript/`, `frontend/`, `database/`

Each document follows the [knowledge document template](../templates/knowledge-document-template.md) and adheres to the [style guide](style-guide.md).

Knowledge documents must be:

- Understandable without any AI tool
- Free of tool-specific syntax (no Cursor frontmatter, no Copilot directives)
- Self-contained enough to be useful alone, with links to related documents

### `rules/` — Tool-specific outputs

Contains rules formatted for AI assistants and IDEs. These are **not** the primary authoring surface.

Rules may be:

- **Generated** — produced by scripts in `scripts/` that transform knowledge documents
- **Curated** — manually refined when automatic transformation is insufficient

A rule should always trace back to one or more knowledge documents. If a rule cannot be justified by knowledge, it should not exist.

### `profiles/` — Composed contexts

A profile defines which knowledge and rules apply to a specific context:

- A team ("backend platform team")
- A technology stack ("Symfony + PostgreSQL API")
- A role ("tech lead doing architecture reviews")
- A project type ("greenfield microservice" vs. "legacy migration")

Profiles are composition manifests—not duplicates of knowledge. They reference knowledge documents and rules by path, with optional priority and scope metadata.

Example profile concept (not yet implemented):

```yaml
name: symfony-api-backend
description: Backend API development with Symfony and PostgreSQL
knowledge:
  - knowledge/engineering/error-handling.md
  - knowledge/symfony/service-layer.md
  - knowledge/database/transaction-boundaries.md
  - knowledge/security/authentication.md
rules:
  - rules/cursor/symfony-api.mdc
```

### `templates/` — Authoring scaffolds

Reusable document structures that ensure consistency across contributions. Templates define required sections, metadata fields, and quality expectations.

### `examples/` — Reference usage

Demonstrates how knowledge, profiles, and adapters work together in practice. Populated in later phases.

### `scripts/` — Adapters and tooling

Build scripts that:

- Transform knowledge documents into tool-specific rule formats
- Validate document structure and cross-references
- Assemble profiles into deployable bundles
- Generate indexes and navigation

Scripts are the **adapter layer**. They should be idempotent, testable, and documented.

### `docs/` — Project meta-documentation

Documentation about the repository itself—not engineering knowledge. Vision, architecture, roadmap, contribution process.

## Knowledge vs. rules vs. profiles

| Aspect | Knowledge | Rules | Profiles |
|--------|-----------|-------|----------|
| **Audience** | Engineers (human and AI) | AI assistants | Both, scoped |
| **Format** | Markdown | Tool-specific (`.mdc`, `.md`, JSON) | YAML or JSON manifest |
| **Authored by** | Engineers | Generated or curated from knowledge | Composed from knowledge + rules |
| **Stability** | High — changes require review | Medium — regenerated on knowledge changes | Low — easy to recompose |
| **Contains reasoning** | Yes — trade-offs, context | No — concise directives only | No — references only |

### When to write knowledge

Write knowledge when you want to capture:

- A principle with trade-offs ("prefer explicit error types over generic exceptions")
- A pattern with constraints ("repository interfaces live in the domain layer")
- A review criterion with rationale ("every public API method must have an integration test")

### When to create a rule

Create (or generate) a rule when:

- Knowledge needs to be enforced during AI-assisted coding sessions
- The guidance can be expressed as concise, unambiguous directives
- A tool-specific format is required for the target assistant

### When to create a profile

Create a profile when:

- A team or project needs a specific subset of knowledge
- Different contexts require different rule strictness
- You want a single artifact to configure an AI assistant for a workflow

## How future adapters will consume knowledge

Adapters in `scripts/` will follow a consistent pipeline:

```
1. Parse    — Read knowledge markdown; extract metadata, sections, directives
2. Filter   — Apply profile scope; select relevant documents
3. Transform — Map knowledge sections to target format (Cursor rule, Copilot instruction, etc.)
4. Validate — Check output against tool schema and internal lint rules
5. Emit     — Write to rules/ or a deployment target
```

### Design constraints for adapters

- **Lossless where possible** — if a rule loses meaning compared to its source knowledge, flag it for human review rather than silently degrading.
- **Deterministic** — the same knowledge + profile always produces the same output.
- **Incremental** — adapters process individual documents; full rebuilds are not required for single-document changes.
- **Extensible** — adding a new tool means adding a new adapter, not restructuring knowledge.

### Metadata contract

Knowledge documents will include frontmatter (defined in the style guide) that adapters use for filtering and transformation:

```yaml
---
title: Service Layer Boundaries
domain: symfony
tags: [architecture, layering, dependency-injection]
severity: recommended  # required | recommended | advisory
applies_to: [backend, api]
related:
  - knowledge/architecture/hexagonal-architecture.md
---
```

Adapters read this metadata to decide inclusion, ordering, and formatting. The body content remains human-readable prose.

## Extension points

Future phases may add:

- **Validation CLI** — `scripts/validate` checks structure, links, and metadata
- **Index generation** — auto-generated table of contents per domain
- **Versioning** — profile versioning for teams that pin to a specific EKP release
- **Plugin adapters** — community-contributed transformers for additional AI tools
