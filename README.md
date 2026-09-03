# Engineering Knowledge Pack (EKP)

An open-source engineering knowledge base that captures how senior software engineers design, build, review, and maintain software.

EKP is the **source of truth** for engineering practices. It is intentionally independent of any AI assistant, IDE, or vendor tooling. Tool-specific formats—Cursor Rules, Claude Skills, GitHub Copilot instructions—are derived from this knowledge through adapters, not authored here directly.

## Using EKP in a consumer project

Install the EKP Consumer CLI on your machine, then run it inside a consumer project to deploy and manage EKP engineering context. In v0.16.0, automatic Consumer CLI deployment and lifecycle management target Cursor. You do not need to clone this repository, run the validator, generate indexes, assemble bundles, or copy files manually.

```bash
pipx install git+https://github.com/WarryPro/engineering-knowledge-pack.git@v0.16.0
```

Alternative: install into a virtual environment with `pip install git+https://github.com/WarryPro/engineering-knowledge-pack.git@v0.16.0`.

### Basic usage

```bash
cd my-project
ekp detect
ekp install
ekp status
ekp update
ekp uninstall
```

- `ekp update` synchronizes the project's existing managed EKP files to the resources bundled with the currently running package.
- `ekp uninstall` removes only EKP-owned managed files recorded in `.ekp/install.json`.

Explicit profile:

```bash
ekp install --profile cursor-symfony
```

Non-interactive:

```bash
ekp install --profile cursor-flutter --yes
```

Preview without writing files:

```bash
ekp install --profile cursor-flutter --dry-run
```

Scoped directory:

```bash
ekp install --path ./backend
```

### Package upgrade vs project update

Upgrading the CLI/package and synchronizing a project are separate steps:

```bash
# upgrade or reinstall a newer Git tag on your machine
pipx install --force git+https://github.com/WarryPro/engineering-knowledge-pack.git@v0.16.0

# then synchronize an existing managed project
cd my-project
ekp update
```

`ekp update` uses the resources bundled with the currently running package. It does not contact GitHub or download releases.

### Update an existing project

```bash
# after installing a newer EKP package
cd my-project
ekp status
ekp update --dry-run
ekp update
ekp status
```

Non-interactive:

```bash
ekp update --yes
```

`--yes` skips confirmation only; it does not bypass ownership or safety checks.

### Uninstall managed files

```bash
ekp uninstall --dry-run
ekp uninstall
```

- Only managed files recorded by EKP are removed
- Modified owned files block uninstall
- Unmanaged Cursor rules survive
- Conservative directory cleanup may intentionally leave harmless empty `.cursor` / `.ekp` directories when ownership was not proven

### Empty project

```bash
mkdir my-project
cd my-project
ekp install
```

If no stack is detected, interactive mode asks for the intended stack. Non-interactive mode requires `--profile`. EKP does not auto-detect a profile in an empty directory.

### Safety

- EKP-managed files are tracked in `.ekp/install.json`
- Existing unmanaged Cursor rule collisions are preserved and block install
- `--yes` skips confirmation prompts, not safety checks
- `--dry-run` shows the installation or lifecycle plan without writing files

### Current limitation

**Consumer CLI v0.16.0 deploys and manages Cursor only.** Copilot, Antigravity, and Claude adapters still exist in this repository and are generated through the manual assemble pipeline where supported — adapter existence is not the same as Consumer CLI deployment support.

See [`docs/deployment.md`](docs/deployment.md) for the full Consumer CLI path vs manual adapter deployment.

---

## Developing EKP itself

Contributors and maintainers work with the knowledge pipeline below. This path is **not** required for the supported Cursor Consumer CLI workflow.

## What this repository contains

| Area | Purpose |
|------|---------|
| [`knowledge/`](knowledge/) | Tool-agnostic engineering knowledge (patterns, practices, guidelines) |
| [`profiles/`](profiles/) | Composed sets of knowledge (`cursor-*` operational including `cursor-nativescript` and `cursor-flutter`; `ekp-php`, `ekp-typescript`, `ekp-symfony`, `ekp-frontend`, `ekp-devops`, and `ekp-nativescript` Cursor+Copilot; `ekp-core` multi-adapter pilot) |
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

### Consumer projects (Cursor)

1. Install the published package (see [Using EKP in a consumer project](#using-ekp-in-a-consumer-project)).
2. Run `ekp detect`, `ekp install`, `ekp status`, and later `ekp update` / `ekp uninstall` as needed.

### Contributors

1. Read [`docs/vision.md`](docs/vision.md) to understand why EKP exists.
2. Read [`docs/architecture.md`](docs/architecture.md) to understand how the repository is organized.
3. Read [`docs/governance.md`](docs/governance.md) for lifecycle, namespaces, profiles, and releases.
4. Read [`docs/adapter-architecture.md`](docs/adapter-architecture.md) for the operational adapter pipeline.
5. Read [`docs/deployment.md`](docs/deployment.md) for Consumer CLI deployment and manual adapter copy paths.
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
py -3 scripts/assemble/assemble.py --profile cursor-flutter --clean --verify
```

## Release status

- **Latest published release:** `v0.16.0`
- **v0.16.0:** Consumer Lifecycle — `ekp update` and `ekp uninstall`; safe cross-version project synchronization; transactional rollback; manifest CAS; 160 Consumer CLI tests; Ubuntu + Windows lifecycle packaging smoke; install via `pipx install git+https://github.com/WarryPro/engineering-knowledge-pack.git@v0.16.0`
- **v0.15.0:** Consumer CLI (`ekp version`, `detect`, `install`, `status`); Cursor-only consumer installation; project detection and profile resolution; ownership manifest and safe deployment; Windows + Ubuntu validation; install via `pipx install git+https://github.com/WarryPro/engineering-knowledge-pack.git@v0.15.0`
- **v0.14.0:** Flutter L2 technology vertical — `EKP-FL01`–`FL09` engineering knowledge; profile `cursor-flutter` (`includes: [cursor-core]`, `outputs: [cursor]` only); 75 Cursor rules (65 inherited core + 10 Flutter); no TypeScript/frontend/NativeScript inheritance; 15 profiles; 15th CI `--verify` gate; `ekp-flutter` and Copilot Flutter routing deferred
- **v0.13.0:** Sixth stack-specific multi-adapter profile `ekp-nativescript` (`includes: [cursor-nativescript]`, `outputs: [cursor, copilot]`); adds Copilot `nativescript` PATH_GROUP; Cursor output byte-identical to `cursor-nativescript` (84 rules); Copilot emits NativeScript, TypeScript, and testing instruction groups; completes Phase 5 stack multi-adapter profiles
- **v0.12.0:** Fifth stack-specific multi-adapter profile `ekp-devops` (`includes: [cursor-devops]`, `outputs: [cursor, copilot]`); packaging-only Phase 5 continuation; Cursor output byte-identical to `cursor-devops` (74 rules); Copilot uses existing DevOps + inherited testing routing
- **v0.11.0:** Frontend Knowledge Enhancement — EKP-FE09–FE16 styling/markup guide; `cursor-frontend` **83 → 92** rules; `ekp-frontend` inherits via `includes: [cursor-frontend]`; FE01–FE08 preserved; framework-neutral engineering principles only (no React/Vue/Angular/Bootstrap/Tailwind tutorials)
- **v0.10.0:** Fourth stack-specific multi-adapter profile `ekp-frontend` (`includes: [cursor-frontend]`, `outputs: [cursor, copilot]`); packaging-only Phase 5 continuation; seven operational Cursor profiles unchanged; assembled Cursor output for those profiles unchanged vs `v0.9.0`; remaining stacks (`ekp-devops`, `ekp-nativescript`) deferred
- **v0.9.0:** Third stack-specific multi-adapter profile `ekp-symfony` (`includes: [cursor-symfony]`, `outputs: [cursor, copilot]`); seven operational Cursor profiles unchanged; assembled Cursor output for those profiles unchanged vs `v0.8.0`; remaining stacks (`ekp-frontend`, `ekp-devops`, `ekp-nativescript`) deferred
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
| copilot | implemented (`ekp-php`, `ekp-typescript`, `ekp-symfony`, `ekp-frontend`, `ekp-devops`, `ekp-nativescript`; `ekp-core` pilot) |
| antigravity | implemented (`ekp-core` pilot) |
| claude | implemented (`ekp-core` pilot) |

Copilot, Antigravity, and Claude are demonstrated through the `ekp-core` pilot profile. `ekp-php`, `ekp-typescript`, `ekp-symfony`, `ekp-frontend`, `ekp-devops`, and `ekp-nativescript` additionally expose Copilot for PHP, TypeScript, Symfony, frontend, DevOps, and NativeScript stack knowledge respectively. Operational `cursor-*` profiles (including `cursor-nativescript`) remain Cursor-only. `cursor-frontend` / `ekp-frontend` package frontend architecture (EKP-FE01–FE08) and styling/markup engineering knowledge (EKP-FE09–FE16). `ekp-devops` packages existing DevOps fundamentals (EKP-DV01–DV08) via `includes: [cursor-devops]`. `ekp-nativescript` packages NativeScript architecture (EKP-NS01+) and inherited TypeScript fundamentals via `includes: [cursor-nativescript]`.

## Status

| Phase | Status | Scope |
|-------|--------|-------|
| Phase 1 — Foundation | **Complete** | Structure, templates, validation skeleton, schemas |
| Phase 2 — Core engineering knowledge | **Substantially complete** | Cross-cutting L0 guides; quality bar over doc count |
| Phase 3A — AI operational pipeline | **Operational** | Validator v2.3, profiles, Cursor adapter, assemble pipeline |
| Phase 3B — Architecture knowledge expansion | **Complete** | ADR practices, API design, integration patterns, database design |
| Phase 3B.1 — Repository consolidation | **Complete** | CI, examples, v0.2.0 release |
| Phase 3C — Governance foundation | **Complete** | ADRs, governance.md, lifecycle status |
| Phase 4 — Technology knowledge | **Substantially complete** | Waves 1–3 published; `cursor-nativescript` (NativeScript L2); `cursor-flutter` (Flutter L2 published in `v0.14.0`); Flutter multi-adapter (`ekp-flutter`) deferred |
| Phase 5 — Additional AI adapters | **Partial** | Stack multi-adapter profiles complete (`ekp-php` through `ekp-nativescript`, Cursor + Copilot); four-adapter `ekp-core` pilot; `ekp-flutter`, Antigravity/Claude on stack profiles, and `ekp-core` promotion deferred |
| Phase 6 — Consumer productization | **Substantially operational (`v0.16.0`)** | Package; `ekp` CLI (`version`, `detect`, `install`, `status`, `update`, `uninstall`); safe Cursor lifecycle; Windows + Ubuntu CI; 160 Consumer CLI tests; remote acquisition / PyPI / non-Cursor Consumer lifecycle still deferred |

### Repository metrics

| Metric | Value |
|--------|-------|
| Knowledge guides | 24 |
| Concepts | 221 |
| Namespaces | 24 |
| Profiles | 15 total — 8 operational Cursor (`cursor-core` + 7 stack) + 6 stack `ekp-*` (Cursor + Copilot) + `ekp-core` packaging pilot |
| CI `--verify` gates | 15 profiles |
| Consumer CLI tests | 160 (Windows + Ubuntu CI; 9 expected Unix-only skips on Windows) |
| Graph depth | max 2 |
| Adapter-ready | 100% |
| `cursor-core` bundle | 65 rules (frozen) |
| Tech profiles | `cursor-php`, `cursor-symfony`, `cursor-typescript`, `cursor-frontend`, `cursor-devops` (each `includes: [cursor-core]`); `cursor-nativescript` (`includes: [cursor-typescript]`); `cursor-flutter` (`includes: [cursor-core]`); `ekp-php` (`includes: [cursor-php]`, `outputs: [cursor, copilot]`); `ekp-typescript` (`includes: [cursor-typescript]`, `outputs: [cursor, copilot]`); `ekp-symfony` (`includes: [cursor-symfony]`, `outputs: [cursor, copilot]`); `ekp-frontend` (`includes: [cursor-frontend]`, `outputs: [cursor, copilot]`); `ekp-devops` (`includes: [cursor-devops]`, `outputs: [cursor, copilot]`); `ekp-nativescript` (`includes: [cursor-nativescript]`, `outputs: [cursor, copilot]`) |

See [`docs/roadmap.md`](docs/roadmap.md) for the full development plan.

## License

MIT — see [LICENSE](LICENSE).
