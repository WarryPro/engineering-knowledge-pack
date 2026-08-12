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

`scripts/adapters/common/` provides shared logic used by all tool adapters:

| Module | Purpose |
|--------|---------|
| `models.py` | Data structures including `GeneratedRule` (in-memory IR) |
| `extract.py` | Parses knowledge markdown into concept blocks and decision flows |
| `paths.py` | Repository path resolution for knowledge and output targets |
| `profile_resolve.py` | Profile `includes` resolution |
| `profile_loader.py` | Profile loading; canonical `outputs` resolution |
| `selection.py` | Shared adapter-manifest concept selection |
| `registry.py` | Adapter dispatch registry (Cursor operational; others deferred) |

### 5. Cursor adapter

`scripts/adapters/cursor/` transforms extracted and normalized knowledge into Cursor Rules (`.mdc`):

| Module | Purpose |
|--------|---------|
| `generate.py` | Orchestrates extract → selection → normalization → writer |
| `normalize.py` | Builds `GeneratedRule` objects for Cursor |
| `mdc_writer.py` | Writes `.mdc` files with Cursor frontmatter |
| `naming.py` | Deterministic rule file naming from concept metadata |
| `manifest.py` | Cursor bundle manifest generation |
| `verify.py` | Cursor bundle verification |

The adapter reads profile knowledge paths and `adapter.include.adapter_priority` filters to select which concepts become rules.

**Only Cursor is implemented.** Copilot, Antigravity, and Claude are registered as future adapters (ADR-0009).

### 6. Assemble pipeline

`scripts/assemble/assemble.py` composes deployable bundles for a profile by dispatching to registered adapters based on profile `outputs`:

```bash
py -3 scripts/assemble/assemble.py --profile cursor-core --clean --verify
```

| Flag | Purpose |
|------|---------|
| `--profile` | Profile YAML to assemble (e.g. `cursor-core`) |
| `--clean` | Remove existing output before generation |
| `--verify` | Run per-adapter verification after assembly |

Profiles declare requested adapters with `outputs` (canonical). Legacy profiles may still use `adapter.target` as a fallback when `outputs` is omitted.

Output structure (Cursor today):

```
dist/<profile>/
├── bundle-manifest.json    # adapter: "cursor"
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
