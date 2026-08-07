# Development Guide

How to validate, test, and assemble EKP locally. For repository overview and phase status, see [README.md](README.md). For knowledge authoring, see [docs/contribution-guide.md](docs/contribution-guide.md).

## Prerequisites

- **Python 3.6+** (3.9+ recommended; matches CI)
- **Git**
- pip packages from `scripts/validate/requirements.txt` (PyYAML, jsonschema)

```bash
py -3 -m pip install -r scripts/validate/requirements.txt
```

On Linux/macOS CI uses `python`; on Windows use `py -3` if configured.

## Repository structure (development-relevant)

| Path | Role |
|------|------|
| `knowledge/` | Source of truth — validated on every change |
| `profiles/` | Bundle composition (`cursor-core`, `cursor-php`, `cursor-symfony`, `cursor-typescript`, `cursor-frontend`) |
| `scripts/validate/` | Validator CLI |
| `scripts/adapters/` | Knowledge → tool format transformers |
| `scripts/assemble/` | Profile → deployable bundle |
| `schema/` | JSON Schema and graph rules |
| `dist/` | **Generated** — gitignored |

## Validation pipeline

Run from repository root:

### 1. Validate knowledge

```bash
py -3 scripts/validate/validate.py
```

Checks frontmatter, graph, concepts, namespaces, links, README indexes, profiles, optional lifecycle `status` (default: published).

Optional flags: `--strict`, `--changed-only`, `--tier`, `--report scale|adapters|graph`.

### 2. Generate indexes

```bash
py -3 scripts/validate/validate.py --generate-index
```

Writes to `dist/`:

- `concept-index.json`
- `knowledge-graph.json`
- `adapter-manifest.json`

Required before assemble uses adapter metadata.

### 3. Adapter tests

```bash
py -3 -m unittest discover -s scripts/adapters/tests -v
```

### 4. Assemble tests

```bash
py -3 -m unittest discover -s scripts/assemble/tests -v
```

### 5. Assemble and verify bundles

```bash
py -3 scripts/assemble/assemble.py --profile cursor-core --clean --verify
py -3 scripts/assemble/assemble.py --profile cursor-php --clean --verify
py -3 scripts/assemble/assemble.py --profile cursor-symfony --clean --verify
py -3 scripts/assemble/assemble.py --profile cursor-typescript --clean --verify
py -3 scripts/assemble/assemble.py --profile cursor-frontend --clean --verify
```

Output: `dist/<profile>/cursor/*.mdc` + `bundle-manifest.json`.

**Expected:** 65 rules for `cursor-core` (do not change without explicit profile work). Tech profiles add PHP/Symfony rules on top of the same L0 subset.

### Deploy to a consumer project

Copy generated rules:

```
dist/cursor-core/cursor/        →  <project>/.cursor/rules/
dist/cursor-php/cursor/         →  <project>/.cursor/rules/
dist/cursor-symfony/cursor/     →  <project>/.cursor/rules/
dist/cursor-typescript/cursor/  →  <project>/.cursor/rules/
dist/cursor-frontend/cursor/    →  <project>/.cursor/rules/
```

Regenerate after any knowledge or profile change.

## `dist/` policy

- **Never commit** `dist/` — it is in `.gitignore`.
- Regenerate locally after knowledge changes.
- CI regenerates on every run; artifacts are not uploaded.
- `dist/` is the deployable output; `rules/` is scaffold only.

## Continuous integration

Workflow: [`.github/workflows/ekp-validation.yml`](.github/workflows/ekp-validation.yml)

Triggers: `push` and `pull_request` to `master` and `staging`.

Steps mirror local validation: validate → generate-index → adapter tests → assemble tests → `assemble --verify` for all five Cursor profiles.

## Before opening a PR

1. `py -3 scripts/validate/validate.py`
2. Adapter and assemble tests (above)
3. `assemble --verify` if you touched knowledge, profiles, adapters, or assemble

## Related

- [scripts/validate/README.md](scripts/validate/README.md) — validator tiers and rules
- [docs/adapter-architecture.md](docs/adapter-architecture.md) — pipeline design
- [CONTRIBUTING.md](CONTRIBUTING.md) — contribution workflow
