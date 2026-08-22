# Engineering Knowledge Pack (EKP)

An open-source engineering knowledge base that captures how senior software engineers design, build, review, and maintain software.

EKP is the **source of truth** for engineering practices. It is intentionally independent of any AI assistant, IDE, or vendor tooling. Tool-specific formats—Cursor Rules, Claude Skills, GitHub Copilot instructions—are derived from this knowledge through adapters, not authored here directly.

## What this repository contains

| Area | Purpose |
|------|---------|
| [`knowledge/`](knowledge/) | Tool-agnostic engineering knowledge (patterns, practices, guidelines) |
| [`profiles/`](profiles/) | Composed sets of knowledge (`cursor-*` operational including `cursor-nativescript`; `ekp-php`, `ekp-typescript`, and `ekp-symfony` Cursor+Copilot; `ekp-core` multi-adapter pilot) |
| [`scripts/`](scripts/) | Validation, adapters, and assembly pipeline |
| [`dist/`](dist/) | Generated deployable bundles (gitignored; produced by `assemble`) |
| [`rules/`](rules/) | Scaffold for tool-specific rule layouts; **not** the primary bundle source |
| [`templates/`](templates/) | Document templates for knowledge, rules, reviews, and decisions |
| [`docs/`](docs/) | Project vision, architecture, governance, roadmap, contribution, and deployment guidance |
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
| Assemble | `py -3 scripts/assemble/assemble.py --profile <name> --clean --verify` | `dist/<profile>/` (adapter dirs + manifests) |

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
5. Read [`docs/deployment.md`](docs/deployment.md) to assemble a profile and copy artifacts into a consumer project.
6. Read [`docs/contribution-guide.md`](docs/contribution-guide.md) before adding or changing content.
7. Read [`DEVELOPMENT.md`](DEVELOPMENT.md) to run validation and assemble locally.

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
py -3 scripts/assemble/assemble.py --profile cursor-devops --clean --verify
py -3 scripts/assemble/assemble.py --profile cursor-nativescript --clean --verify
```

## Release status

- **Latest published release:** `v0.8.0` (on `staging`)
- **v0.8.0:** Second stack-specific multi-adapter profile `ekp-typescript` (`includes: [cursor-typescript]`, `outputs: [cursor, copilot]`); seven operational Cursor profiles unchanged; assembled Cursor output for those profiles unchanged vs `v0.7.0`; remaining stacks and `ekp-nativescript` deferred
- **v0.7.0:** NativeScript L2 vertical — `cursor-nativescript` (`includes: [cursor-typescript]`, `outputs: [cursor]`); six operational Cursor profiles unchanged; assembled Cursor output for those six profiles unchanged vs `v0.6.0`; Flutter and `ekp-nativescript` deferred
- **v0.6.0:** First stack-specific multi-adapter profile `ekp-php` (`includes: [cursor-php]`, `outputs: [cursor, copilot]`); six operational Cursor profiles unchanged; assembled Cursor output unchanged vs `v0.5.1`
- **v0.5.1:** Consumer deployment documentation (`docs/deployment.md`) and adapter-status reconciliation; documentation-only PATCH; assembled Cursor output unchanged vs `v0.5.0`
- **v0.5.0:** Claude adapter pilot via `ekp-core` (`CLAUDE.md` + document-grouped Skills); six operational profiles remain Cursor-only; assembled Cursor output unchanged vs `v0.4.0`
- **v0.4.0:** Copilot + Antigravity adapter pilots via `ekp-core`; six operational profiles remain Cursor-only; assembled Cursor output unchanged vs `v0.3.5`
- **v0.3.5:** Multi-adapter packaging — deterministic `assemble-manifest.json`, fail-fast unimplemented adapters, `ekp-core` packaging pilot; assembled Cursor output unchanged vs `v0.3.4`
- See [CHANGELOG.md](CHANGELOG.md) for full release history

### Adapter status

| Adapter | Status |
|---------|--------|
| cursor | implemented |
| copilot | implemented (`ekp-php`, `ekp-typescript`, `ekp-symfony`; `ekp-core` pilot) |
| antigravity | implemented (`ekp-core` pilot) |
| claude | implemented (`ekp-core` pilot) |

Copilot, Antigravity, and Claude are demonstrated through the `ekp-core` pilot profile. `ekp-php`, `ekp-typescript`, and `ekp-symfony` additionally expose Copilot for PHP, TypeScript, and Symfony stack knowledge respectively. Operational `cursor-*` profiles (including `cursor-nativescript`) remain Cursor-only.

## Status

| Phase | Status | Scope |
|-------|--------|-------|
| Phase 1 — Foundation | **Complete** | Structure, templates, validation skeleton, schemas |
| Phase 2 — Core engineering knowledge | **Substantially complete** | Cross-cutting L0 guides; quality bar over doc count |
| Phase 3A — AI operational pipeline | **Operational** | Validator v2.3, profiles, Cursor adapter, assemble pipeline |
| Phase 3B — Architecture knowledge expansion | **Complete** | ADR practices, API design, integration patterns, database design |
| Phase 3B.1 — Repository consolidation | **Complete** | CI, examples, v0.2.0 release |
| Phase 3C — Governance foundation | **Complete** | ADRs, governance.md, lifecycle status |
| Phase 4 — Technology knowledge | **In progress** | Waves 1–3 published; `cursor-nativescript`; Flutter deferred |

### Repository metrics

| Metric | Value |
|--------|-------|
| Knowledge guides | 22 |
| Concepts | 204 |
| Namespaces | 23 |
| Profiles | 7 operational Cursor (`cursor-core` + 6 stack) + `ekp-php` + `ekp-typescript` + `ekp-symfony` (Cursor + Copilot) + `ekp-core` packaging pilot |
| Graph depth | max 2 |
| Adapter-ready | 100% |
| `cursor-core` bundle | 65 rules (frozen) |
| Tech profiles | `cursor-php`, `cursor-symfony`, `cursor-typescript`, `cursor-frontend`, `cursor-devops` (each `includes: [cursor-core]`); `cursor-nativescript` (`includes: [cursor-typescript]`); `ekp-php` (`includes: [cursor-php]`, `outputs: [cursor, copilot]`); `ekp-typescript` (`includes: [cursor-typescript]`, `outputs: [cursor, copilot]`); `ekp-symfony` (`includes: [cursor-symfony]`, `outputs: [cursor, copilot]`) |

See [`docs/roadmap.md`](docs/roadmap.md) for the full development plan.

## License

MIT — see [LICENSE](LICENSE).
