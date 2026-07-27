# Validation

Checks knowledge document structure, frontmatter, graph integrity, concept IDs, namespace registry, adapter metadata, README indexes, profiles, and links.

## Usage

Run from repository root:

```bash
py -3 scripts/validate/validate.py
```

Install dependencies first:

```bash
py -3 -m pip install -r scripts/validate/requirements.txt
```

Requires **Python 3.6+**, **PyYAML**, and **jsonschema**.

### CLI options (v2.3)

| Flag | Description |
|------|-------------|
| `--strict` | Treat warnings as errors (exit code 1) |
| `--strict-adapters` | Treat missing `adapter_priority` as error |
| `--changed-only` | Validate only git-changed files; full graph when graph-affecting paths change |
| `--tier structural` | YAML parsing, schema, markdown links only |
| `--tier graph` | Dependency graph rules + namespace registry |
| `--tier registry` | Concepts, namespaces, adapter metadata, README, profiles, ADR |
| `--tier all` | Full validation (default) |
| `--generate-index` | Write `dist/` indexes and exit |
| `--report scale` | Scale and adapter readiness summary |

Other reports:

- `--report principles` — principle ownership coverage
- `--report graph` — knowledge graph summary
- `--report concepts` — concept namespace registry summary
- `--report adapters` — adapter readiness summary

### Incremental validation

```bash
py -3 scripts/validate/validate.py --changed-only
```

Uses `git diff --name-only HEAD` plus untracked files. For changed knowledge guides, runs schema, concept, body consistency, and related checks. When frontmatter, schema, graph rules, or namespace registry change, full graph validation runs because dependency impact is global.

### Generated artifacts

```bash
py -3 scripts/validate/validate.py --generate-index
```

Produces:

```
dist/
 ├── concept-index.json      # concept ID → document metadata
 ├── knowledge-graph.json    # nodes + depends_on/related edges
 └── adapter-manifest.json   # principles + adapter rule priorities
```

See `docs/adapter-architecture.md` for the adapter workflow.

## Governance manifests

- `schema/graph-rules.yaml` — role-based `depends_on` layer rules and depth thresholds
- `schema/principle-exceptions.json` — documented gaps in principle ownership
- `schema/concept-namespaces.json` — concept namespace ownership registry
- `schema/vocabularies.json` — controlled vocabulary (optional; not enforced yet)

## What it validates

### Structural (v2.0)

- Required frontmatter and JSON Schema validation
- `domain` matches directory
- Markdown link resolution
- Profile YAML parsing and JSON Schema validation

### Graph (v2.0 + v2.1)

- `depends_on` path existence and `knowledge/*.md` form
- Acyclic `depends_on` graph
- Foundation singleton invariants
- Non-foundation metadata requirements
- Reachability from `engineering-principles.md`
- **R-G4** Allowed dependency directions (`schema/graph-rules.yaml`)
- **R-G8** Dependency depth (warn at 3, error at 4+)
- **R-G10-lite** `related` and `extends` path existence

### Concepts (v2.0 + v2.2)

- Global `concept_ids` uniqueness
- Concept ID format and per-document namespace consistency
- `implements` must be `EKP-P01`–`EKP-P10`
- **N1–N4** Namespace registry validation (`schema/concept-namespaces.json`)
- **B1–B2** Body ↔ `concept_ids` consistency (warning only)

### Adapter readiness (v2.2 + v2.3)

- Foundation must not define `adapter_priority` (error)
- Operational roles should define `adapter_priority` (warning; error with `--strict-adapters`)

### Principles (v2.1)

- **R-P2** Principle ownership coverage (warnings; `principle-exceptions.json`)
- **R-P3** Foundation `related` completeness (warning)

### README (v2.1)

Navigation READMEs only:

- `knowledge/engineering/README.md`
- `knowledge/testing/README.md`
- `knowledge/architecture/README.md`

Rules:

- **R-R1** Published/Foundation/Practices/Patterns/Procedures links must resolve (error)
- **R-R2** Published domain documents should appear in domain README (warning)
- **R-R3** Planned entries are not validated

### ADR index (v2.2)

- Every `adr-*.md` in `knowledge/architecture/decisions/` must appear in `decisions/README.md` (error)

### Profiles (v2.1)

- YAML must parse
- Must validate against `schema/profile.schema.json`
- Referenced `knowledge/` paths must exist
- `rules:` entries are rejected

ADRs (`adr-*.md`) are excluded from knowledge frontmatter checks.

## Tests

```bash
py -3 -m unittest discover -s scripts/validate/tests -v
```

## Planned (v2.4+)

- Controlled vocabulary enforcement for `tags` / `applies_to`
- Automatic metadata fixes
- NLP quality checks and embeddings (adapter layer)
