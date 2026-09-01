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
| `profiles/` | Bundle composition (seven operational `cursor-*` profiles + `ekp-php` + `ekp-typescript` + `ekp-symfony` + `ekp-frontend` + `ekp-core` pilot) |
| `scripts/validate/` | Validator CLI |
| `scripts/adapters/` | Knowledge → tool format transformers |
| `scripts/assemble/` | Profile → deployable bundle |
| `src/ekp/` | Consumer CLI package (installed distribution) |
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

### 4b. Consumer CLI tests

```bash
py -3 -m pip install -e .
py -3 -m unittest discover -s src/ekp/tests -v
```

On Windows, two Unix symlink safety tests are expected to skip. Ubuntu runs all 91 tests.

### 4c. Package build and packaging smoke

```bash
py -3 -m pip install build hatchling
py -3 scripts/packaging/smoke_install_wheel.py
```

Builds a wheel outside the repository checkout, installs it in a temporary venv, and exercises `ekp version`, `detect`, `install`, and `status`.

Cross-platform validation: [`.github/workflows/consumer-cli.yml`](.github/workflows/consumer-cli.yml) (Windows + Ubuntu).

### 5. Assemble and verify bundles

Operational Cursor profiles:

```bash
py -3 scripts/assemble/assemble.py --profile cursor-core --clean --verify
py -3 scripts/assemble/assemble.py --profile cursor-php --clean --verify
py -3 scripts/assemble/assemble.py --profile cursor-symfony --clean --verify
py -3 scripts/assemble/assemble.py --profile cursor-typescript --clean --verify
py -3 scripts/assemble/assemble.py --profile cursor-frontend --clean --verify
py -3 scripts/assemble/assemble.py --profile cursor-devops --clean --verify
```

Multi-adapter profiles:

```bash
py -3 scripts/assemble/assemble.py --profile ekp-php --clean --verify
py -3 scripts/assemble/assemble.py --profile ekp-typescript --clean --verify
py -3 scripts/assemble/assemble.py --profile ekp-symfony --clean --verify
py -3 scripts/assemble/assemble.py --profile ekp-frontend --clean --verify
py -3 scripts/assemble/assemble.py --profile ekp-core --clean --verify
```

- `ekp-php` — Cursor + Copilot for PHP (`includes: [cursor-php]`); first stack-specific multi-adapter profile
- `ekp-typescript` — Cursor + Copilot for TypeScript (`includes: [cursor-typescript]`); second stack-specific multi-adapter profile
- `ekp-symfony` — Cursor + Copilot for Symfony (`includes: [cursor-symfony]`); third stack-specific multi-adapter profile
- `ekp-frontend` — Cursor + Copilot for frontend architecture (`includes: [cursor-frontend]`); fourth stack-specific multi-adapter profile (current EKP-FE knowledge; CSS/HTML/styling expansion deferred)
- `ekp-core` — Cursor + Copilot + Antigravity + Claude foundation pilot (`includes: [cursor-core]`)

Cursor output: `dist/<profile>/cursor/*.mdc` + profile-root `bundle-manifest.json`.

**Expected:** 65 rules for `cursor-core` (frozen — do not change without explicit approval). Stack profiles include `cursor-core` via `includes` and add stack-specific guides (~74 for single-stack, ~83 for combined-stack). Rule counts must remain stable across composition refactors.

**Profile composition:** `includes` resolves knowledge paths depth-first before assembly. Included profiles contribute paths only; root profile owns `adapter`, `filters`, and `outputs`. See ADR-0008.

Copying generated files into a consumer project is documented in [`docs/deployment.md`](docs/deployment.md).

## `dist/` policy

- **Never commit** `dist/` — it is in `.gitignore`.
- Regenerate locally after knowledge changes.
- CI regenerates on every run; artifacts are not uploaded.
- `dist/` is the deployable output; `rules/` is scaffold only.

## Continuous integration

Workflow: [`.github/workflows/ekp-validation.yml`](.github/workflows/ekp-validation.yml)

Triggers: `push` and `pull_request` to `master` and `staging`.

Steps mirror local validation: validate → generate-index → adapter tests → assemble tests → `assemble --verify` for all seven Cursor profiles → `assemble --verify` for `ekp-php` (cursor, copilot) → `assemble --verify` for `ekp-typescript` (cursor, copilot) → `assemble --verify` for `ekp-symfony` (cursor, copilot) → `assemble --verify` for `ekp-frontend` (cursor, copilot) → `assemble --verify` for `ekp-core` (cursor, copilot, antigravity, claude).

## Before opening a PR

1. `py -3 scripts/validate/validate.py`
2. Adapter and assemble tests (above)
3. `assemble --verify` if you touched knowledge, profiles, adapters, or assemble

## Related

- [scripts/validate/README.md](scripts/validate/README.md) — validator tiers and rules
- [docs/adapter-architecture.md](docs/adapter-architecture.md) — pipeline design
- [docs/deployment.md](docs/deployment.md) — copy generated artifacts into a consumer project
- [CONTRIBUTING.md](CONTRIBUTING.md) — contribution workflow
