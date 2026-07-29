# Adapter Architecture

This document describes how EKP knowledge flows from authored markdown to deployable AI assistant artifacts.

## Pipeline overview

```
knowledge/
    ↓
validate
    ↓
generate-index
    ↓
adapter generation
    ↓
assemble
    ↓
deploy artifact
```

## Stages

### 1. Knowledge markdown

Authors maintain guides under `knowledge/` with YAML frontmatter. Graph metadata (`depends_on`, `role`, `concept_ids`, `adapter_priority`) is validated by the EKP validator.

### 2. Validator

`scripts/validate/validate.py` enforces structural, graph, and registry rules. In v2.3 it also supports:

- `--changed-only` for incremental CI validation
- `--tier` for scoped validation passes
- `--generate-index` for adapter artifacts
- `--report adapters` and `--report scale` for readiness metrics

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

Adapters consume these JSON files instead of parsing markdown at runtime.

### 4. Adapter common extraction layer

`scripts/adapters/common/` provides shared extraction logic used by all tool adapters:

| Module | Purpose |
|--------|---------|
| `models.py` | Data structures for concepts, sections, and extraction results |
| `extract.py` | Parses knowledge markdown into adapter-ready concept blocks |
| `paths.py` | Repository path resolution for knowledge and output targets |

### 5. Cursor adapter

`scripts/adapters/cursor/` transforms extracted concepts into Cursor Rules (`.mdc`):

| Module | Purpose |
|--------|---------|
| `generate.py` | Orchestrates extraction and rule file generation |
| `mdc_writer.py` | Writes `.mdc` files with Cursor frontmatter |
| `naming.py` | Deterministic rule file naming from concept metadata |

The adapter reads profile knowledge paths and `adapter.include.adapter_priority` filters to select which concepts become rules.

### 6. Assemble pipeline

`scripts/assemble/assemble.py` composes a deployable bundle for a profile:

```bash
py -3 scripts/assemble/assemble.py --profile cursor-core --clean --verify
```

| Flag | Purpose |
|------|---------|
| `--profile` | Profile YAML to assemble (e.g. `cursor-core`) |
| `--clean` | Remove existing output before generation |
| `--verify` | Validate bundle integrity after assembly |

Output structure:

```
dist/<profile>/
├── bundle-manifest.json    # Rule inventory, source refs, verification metadata
└── cursor/
    └── *.mdc               # Generated Cursor rules
```

### 7. Bundle manifest

`dist/<profile>/bundle-manifest.json` records:

- Profile name and generation timestamp
- Rule inventory with source knowledge paths
- Concept IDs and adapter priorities included
- Verification status when `--verify` is used

Consumers can use the manifest to audit bundle contents without parsing individual rule files.

### 8. Profiles

Stack-specific profiles under `profiles/` reference **knowledge paths only**. Adapters derive rules at build time based on profile `adapter` settings:

```yaml
adapter:
  target:
    - cursor
  include:
    adapter_priority:
      - high
```

See `profiles/cursor-core.yaml` for the first operational profile.

## Output locations

| Path | Role |
|------|------|
| `dist/<profile>/cursor/*.mdc` | **Deployable artifact** — copy to consumer `.cursor/rules/` |
| `dist/*.json` | Generated indexes for adapter consumption |
| `rules/` | Scaffold only — **not** the primary bundle source |

## Design principles

- **Single source of truth:** Markdown remains authoritative; indexes and rules are generated outputs.
- **Fail closed:** Validation must pass before indexes are published.
- **Incremental scale:** Changed-only and tiered validation keep CI fast at 100–500 documents.
- **Explicit adapter contract:** `adapter_priority` and manifest JSON define what adapters prioritize.
- **Reproducible bundles:** `assemble --verify` ensures generated output matches profile and source refs.

## Related documents

- `scripts/validate/README.md` — validator usage and tiers
- `docs/folder-structure.md` — directory layout and content flow
- `schema/concept-namespaces.json` — namespace ownership registry
- `schema/vocabularies.json` — controlled vocabulary (not enforced yet)
