# Engineering Knowledge Pack (EKP)

An open-source engineering knowledge base that captures how senior software engineers design, build, review, and maintain software.

EKP is the **source of truth** for engineering practices. It is intentionally independent of any AI assistant, IDE, or vendor tooling. Tool-specific formats—Cursor Rules, Claude Skills, GitHub Copilot instructions—are derived from this knowledge through adapters, not authored here directly.

## What this repository contains

| Area | Purpose |
|------|---------|
| [`knowledge/`](knowledge/) | Tool-agnostic engineering knowledge (patterns, practices, guidelines) |
| [`profiles/`](profiles/) | Composed sets of knowledge (`cursor-core`, `cursor-php`, `cursor-symfony`, `cursor-typescript`, `cursor-frontend`) |
| [`scripts/`](scripts/) | Validation, adapters, and assembly pipeline |
| [`dist/`](dist/) | Generated deployable bundles (gitignored; produced by `assemble`) |
| [`rules/`](rules/) | Scaffold for tool-specific rule layouts; **not** the primary bundle source |
| [`templates/`](templates/) | Document templates for knowledge, rules, reviews, and decisions |
| [`docs/`](docs/) | Project vision, architecture, governance, roadmap, and contribution guidance |
| [`examples/`](examples/) | Educational ADR and review checklist examples |

## Knowledge pipeline

Content flows from authored knowledge to deployable artifacts:

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

| Stage | Command | Output |
|-------|---------|--------|
| Validate | `py -3 scripts/validate/validate.py` | Structural and graph checks |
| Generate index | `py -3 scripts/validate/validate.py --generate-index` | `dist/concept-index.json`, `dist/knowledge-graph.json`, `dist/adapter-manifest.json` |
| Assemble | `py -3 scripts/assemble/assemble.py --profile <name> --clean --verify` | `dist/<profile>/cursor/*.mdc` + `bundle-manifest.json` |

Install validator dependencies first:

```bash
py -3 -m pip install -r scripts/validate/requirements.txt
```

### `dist/` vs `rules/`

- **`dist/`** is the **generated artifact** produced by the assemble pipeline. It contains adapter output (e.g. Cursor `.mdc` rules) and bundle metadata. It is **gitignored** and must be regenerated locally or in CI.
- **`rules/`** is a **scaffold directory** for tool-specific layouts. It is **not** the final bundle source. Do not treat checked-in files under `rules/` as the deployable output—run `assemble` to produce `dist/<profile>/`.

## Getting started

1. Read [`docs/vision.md`](docs/vision.md) to understand why EKP exists.
2. Read [`docs/architecture.md`](docs/architecture.md) to understand how the repository is organized.
3. Read [`docs/governance.md`](docs/governance.md) for lifecycle, namespaces, profiles, and releases.
4. Read [`docs/adapter-architecture.md`](docs/adapter-architecture.md) for the operational adapter pipeline.
5. Read [`docs/contribution-guide.md`](docs/contribution-guide.md) before adding or changing content.
6. Read [`DEVELOPMENT.md`](DEVELOPMENT.md) to run validation and assemble locally.

## Validation

See [`DEVELOPMENT.md`](DEVELOPMENT.md) for the full pipeline. Quick check:

```bash
py -3 scripts/validate/validate.py
py -3 scripts/validate/validate.py --generate-index
py -3 scripts/assemble/assemble.py --profile cursor-core --clean --verify
py -3 scripts/assemble/assemble.py --profile cursor-php --clean --verify
py -3 scripts/assemble/assemble.py --profile cursor-symfony --clean --verify
py -3 scripts/assemble/assemble.py --profile cursor-typescript --clean --verify
py -3 scripts/assemble/assemble.py --profile cursor-frontend --clean --verify
```

## Status

| Phase | Status | Scope |
|-------|--------|-------|
| Phase 1 — Foundation | **Complete** | Structure, templates, validation skeleton, schemas |
| Phase 2 — Core engineering knowledge | **In progress** | Cross-cutting guides; Phase 2C complete |
| Phase 3A — AI operational pipeline | **Operational** | Validator v2.3, profiles, Cursor adapter, assemble pipeline |
| Phase 3B — Architecture knowledge expansion | **Complete** | ADR practices, API design, integration patterns, database design |
| Phase 3B.1 — Repository consolidation | **Complete** | CI, examples, v0.2.0 release |
| Phase 3C — Governance foundation | **Complete** | ADRs, governance.md, lifecycle status |
| Phase 4 — Technology knowledge | **In progress** | Wave 1–2 on staging; Wave 3 next |

### Repository metrics

| Metric | Value |
|--------|-------|
| Knowledge guides | 20 |
| Concepts | 187 |
| Namespaces | 21 |
| Graph depth | 2–3 (tech L2 → L1 → L0) |
| Adapter-ready | 100% |
| `cursor-core` bundle | 65 rules (unchanged) |
| Tech profiles | `cursor-php`, `cursor-symfony`, `cursor-typescript`, `cursor-frontend` |

See [`docs/roadmap.md`](docs/roadmap.md) for the full development plan.

## License

MIT — see [LICENSE](LICENSE).
