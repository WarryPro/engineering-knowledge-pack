# Adapter Architecture

This document describes how EKP knowledge flows from authored markdown to machine-readable artifacts consumed by future AI adapters.

## Flow

```
Knowledge markdown
        |
        v
    Validator
        |
        v
Generated indexes (dist/)
        |
        v
    AI Adapter
        |
        v
Profiles / Rules
```

## Stages

### 1. Knowledge markdown

Authors maintain guides under `knowledge/` with YAML frontmatter. Graph metadata (`depends_on`, `role`, `concept_ids`, `adapter_priority`) is validated by the EKP validator.

### 2. Validator

`scripts/validate/validate.py` enforces structural, graph, and registry rules. In v2.3 it also supports:

- `--changed-only` for incremental CI validation
- `--tier` for scoped validation passes
- `--generate-index` for adapter artifacts

### 3. Generated indexes

Running:

```bash
py -3 scripts/validate/validate.py --generate-index
```

writes:

| File | Purpose |
|------|---------|
| `dist/concept-index.json` | Concept ID → document metadata lookup |
| `dist/knowledge-graph.json` | Nodes and `depends_on` / `related` edges |
| `dist/adapter-manifest.json` | Principles and adapter rule priorities |

Adapters should consume these JSON files instead of parsing markdown at runtime.

### 4. AI Adapter (future)

A future adapter layer will:

- Read `adapter-manifest.json` to select high-priority concepts
- Resolve concept metadata from `concept-index.json`
- Traverse `knowledge-graph.json` for dependency context
- Emit profile rules or lint guidance

### 5. Profiles / Rules

Stack-specific profiles under `profiles/` reference knowledge paths. Adapters translate governed concepts into enforceable rules for tools (linters, CI checks, IDE hints).

## Design principles

- **Single source of truth:** Markdown remains authoritative; indexes are generated outputs.
- **Fail closed:** Validation must pass before indexes are published.
- **Incremental scale:** Changed-only and tiered validation keep CI fast at 100–500 documents.
- **Explicit adapter contract:** `adapter_priority` and manifest JSON define what adapters should prioritize.

## Related documents

- `scripts/validate/README.md` — validator usage and tiers
- `schema/concept-namespaces.json` — namespace ownership registry
- `schema/vocabularies.json` — controlled vocabulary (not enforced yet)
