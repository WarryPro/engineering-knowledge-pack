# Architecture

## Overview

EKP follows a **knowledge-first, adapter-second** architecture. Human-authored engineering knowledge is the canonical source. Profiles, indexes, and tool-specific rules are derived or composed from that source through the operational pipeline (Phase 3A).

```
knowledge/
    ↓ validate
    ↓ generate-index  →  dist/*.json
    ↓ adapter         →  dist/<profile>/<tool>/
    ↓ assemble        →  bundle-manifest.json
    ↓ deploy          →  consumer project (Consumer CLI or manual copy — see deployment.md)
```

### Consumer CLI deployment layer (`v0.19` multi-assistant + `v0.20` configure + upcoming (unreleased) `v0.21` workspaces)

For application developers, the Consumer CLI composes technology components (root and/or workspaces), generates assistant bundles, then deploys selected assistants through a shared lifecycle:

```
Detection
  → Component Proposal
  → Composition (dependency closure per scope)
  → ProjectConfig (.ekp/project.yaml intent: schema1 or schema2)
  → ScopedKnowledgeInventory (GLOBAL + WORKSPACE)
  → AdapterRegistry (one generate_scoped / assistant → one bundle)
  → DeployRegistry (DesiredManagedFile mapping)
  → SharedDeploymentEngine / TransactionApplier
  → Manifest / Lifecycle (.ekp/install.json — one project-wide manifest)
```

```
Canonical knowledge (knowledge/, components/, schema/)
      ↓
ComponentRegistry + resolve_project_composition (per-scope)
      ↓
ScopedKnowledgeInventory (GLOBAL / WORKSPACE)
      ↓
AdapterRegistry → one scoped bundle per assistant
      ↓
DeployRegistry → DesiredManagedFile[]
      ↓
Consumer CLI
├── detect / component proposal
├── install (composition default; --assistant; --workspace schema2; --profile legacy)
├── status (one top-level state; nested workspace diagnostics; no WORKSPACE_* states)
├── configure (exact desired-state; schema1↔schema2; HEALTHY composition only)
└── lifecycle
    ├── update (bound to project.yaml semantic hash; no redetect; no workspace rediscovery)
    └── uninstall (project-wide; preserves project.yaml)
      ↓
safe multi-assistant deployment + .ekp/project.yaml + .ekp/install.json
      ↓
consumer project
```

**Boundaries (ADR-0010 / ADR-0011 / ADR-0012 historical; workspace pipeline is upcoming (unreleased) v0.21):**

| Artifact | Role |
|----------|------|
| `components/*.yaml` | Composition source of truth (requires + direct knowledge) |
| `.ekp/project.yaml` | User/project requested intent (schema1 components+assistants, or schema2 + workspaces) |
| `.ekp/install.json` | Operational ownership (`mode`, `configuration_sha256`, multi-adapter inventory; manifest `schema_version` remains 1) |
| `AdapterRegistry` | Assistant-specific **generation** (including scoped GLOBAL/WORKSPACE mapping) |
| `DeployRegistry` | Assistant-specific **Consumer filesystem mapping** |
| `cursor-*` / `ekp-*` profiles | Compatibility / packaging presets — not the default Consumer composition graph |

**Hard invariants:** STACK ≠ ASSISTANT; Adapter ≠ Deployer; one technology composition graph → one `project.yaml` → one `install.json` → one lifecycle. Components never encode Cursor/Copilot/Claude/Antigravity. Assistants are project-global even when knowledge is workspace-scoped.

**Scope mapping (upcoming (unreleased) v0.21):**

| Scope | Meaning |
|-------|---------|
| GLOBAL | Root `components` (schema2 may be empty) → always-on / project-level assistant outputs |
| WORKSPACE | Per-workspace `components` → path-scoped assistant outputs at the **project** assistant roots |

Adapter mapping for WORKSPACE knowledge:

| Assistant | Mapping |
|-----------|---------|
| Cursor | `.cursor/rules/*.mdc` with `globs` + `alwaysApply: false` |
| Copilot | `.github/instructions/*.instructions.md` with workspace-prefixed `applyTo` |
| Claude | `.claude/rules/*.md` (GLOBAL remains `CLAUDE.md` + Skills) |
| Antigravity | `.agents/rules/*.md` with verified Glob frontmatter (`trigger: glob` / `globs: path/**` only) |

**Persist contract:**

- ProjectConfig: schema1 **or** schema2 (schema1 remains first-class)
- InstallManifest: schema1; `configuration_sha256` hashes **requested** intent
- ManagedFile entries: path + adapter + sha256 (workspace scope is **not** stored on manifest entries)

Key lifecycle concepts:

- **ManifestSnapshot** — ownership parse and fingerprint from one byte read
- **LifecyclePlan** — planned CREATE / WRITE / DELETE / NOOP operations bound to a manifest snapshot
- **TransactionApplier** — backup, apply-time revalidation, rollback, and recovery workspace retention
- **ManifestStore** — ownership persistence with compare-and-swap for update and last-step removal for uninstall
- **configuration_sha256** — **semantic** normalized project intent (schema1-compatible hashing rules for schema1; schema2 includes workspaces; persisted in manifest)
- **project.yaml content SHA-256** — **physical** exact-byte identity used only for transactional CAS / rollback (not a persistent user-facing schema field)

### Safe Reconfiguration flow (v0.20; workspace-aware in upcoming (unreleased) v0.21)

Authorized intentional intent change for a HEALTHY composition install:

```text
current ProjectConfig
  ↓
desired ProjectConfig (exact component + assistant [+ workspace] sets)
  ↓
semantic hash transition (configuration_sha256)
  ↓
assemble desired composition (once; scoped when schema2)
  ↓
desired managed inventory
  ↓
LifecyclePlan
  ↓
transactional exact-byte config replacement
  ↓
managed-file delta (CREATE / WRITE / DELETE / NOOP)
  ↓
install.json LAST
```

Public CLI: `ekp configure` — prepare once, render, confirm, apply the **same** prepared plan. Manual `project.yaml` edits remain drift and are refused. Workspace / monorepo support is **upcoming (unreleased) v0.21** (ADR-0012 remains historical for the v0.20 decision boundary).

Package vs project version:

```text
running installed package version
  = bundled resource version
  = update target version
```

There is no remote version resolver in Consumer lifecycle. Same-version resource drift inside one package is treated as an internal consistency failure. Package acquisition ≠ project update ≠ configure.

Manual assembly (contributor path) stops at `dist/<profile>/` for copy-based deployment. See [`deployment.md`](deployment.md).
```
┌─────────────────────────────────────────────────────────┐
│                     knowledge/                          │
│         (tool-agnostic markdown, source of truth)       │
└────────────────────────┬────────────────────────────────┘
                         │
           ┌─────────────┼─────────────┐
           ▼             ▼             ▼
    ┌──────────┐  ┌──────────┐  ┌──────────┐
    │ profiles/│  │ examples/│  │ templates│
    │ (compose │  │ (educational│ │ (authoring│
    │  sets)   │  │  samples) │  │ scaffolds)│
    └────┬─────┘  └──────────┘  └──────────┘
         │
         ▼
    ┌──────────┐     ┌──────────┐
    │ scripts/ │ ──► │  dist/   │  (gitignored, generated)
    │ validate │     │ bundles  │
    │ adapters │     └──────────┘
    │ assemble │
    └──────────┘
```

See [`adapter-architecture.md`](adapter-architecture.md) for pipeline details and [`deployment.md`](deployment.md) for copying artifacts into a consumer project.

## Repository layers

### `knowledge/` — Source of truth

Contains engineering knowledge as markdown documents organized by domain:

- **Cross-cutting domains** — `engineering/`, `architecture/`, `security/`, `testing/`, `performance/`, `devops/`, `ai/`, `database/`
- **Technology domains** — `php/` (L1), `symfony/` (L2), `typescript/` (L1), `frontend/` (L2), `nativescript/` (L2), `flutter/` (L2), `devops/` (L3)

Technology knowledge **applies** foundation concepts; it must not redefine them. Layering:

```
L0 Foundation → L1 Language (php, typescript) → L2 Framework (symfony, frontend, nativescript, flutter) → L3 Ops (devops)
```

Dependency direction is downward only. Graph policy for Phase 4 is **V2**: reuse existing roles (`practice`, `architecture`, …); add explicit `graph-rules.yaml` exceptions when an L2 guide must `depends_on` an L1 guide (e.g. Symfony → PHP, Frontend → TypeScript, NativeScript → TypeScript). Do not introduce a `technology` role until exceptions become costly.

**Technology namespaces:** `EKP-PH`, `EKP-SY`, `EKP-TY`, `EKP-FE`, `EKP-NS`, `EKP-FL`. Do not reuse `EKP-TS` (Testing) or `EKP-SF` (Security).

Each document follows the [knowledge document template](../templates/knowledge-document-template.md) or, for stack guides, the [technology knowledge template](../templates/technology-knowledge-document-template.md), and adheres to the [style guide](style-guide.md).

Knowledge documents must be:

- Understandable without any AI tool
- Free of tool-specific syntax (no Cursor frontmatter, no Copilot directives)
- Self-contained enough to be useful alone, with links to related documents

**Current scale:** 24 published guides; 221 concepts; 24 namespaces.

### `rules/` — Scaffold (not primary output)

Layout reference for tool-specific rule formats. **Deployable output is generated in `dist/`** by the assemble pipeline—not authored directly under `rules/`.

Rules trace back to knowledge documents. If a rule cannot be justified by knowledge, it should not exist.

### `profiles/` — Composed contexts

A profile defines which knowledge applies to a specific context (team, role, workflow). Profiles reference **knowledge paths only**—adapters derive rules at build time.

Operational profiles:

| Profile | Role |
|---------|------|
| `cursor-core` | Minimal L0 bundle (65 rules) — **frozen**; included by stack profiles |
| `cursor-php` | `includes: [cursor-core]` + `php-fundamentals` |
| `cursor-symfony` | `includes: [cursor-core]` + PHP + `symfony-architecture` |
| `cursor-typescript` | `includes: [cursor-core]` + `typescript-fundamentals` |
| `cursor-frontend` | `includes: [cursor-core]` + TypeScript + `frontend-architecture` |
| `cursor-devops` | `includes: [cursor-core]` + `devops-fundamentals` |
| `cursor-nativescript` | `includes: [cursor-typescript]` + `nativescript-architecture` (Cursor-only) |
| `cursor-flutter` | `includes: [cursor-core]` + `flutter-architecture` (Cursor-only; no TypeScript/frontend/NativeScript inheritance) |
| `ekp-php` | `includes: [cursor-php]`; `outputs: [cursor, copilot]` — first stack multi-adapter profile |
| `ekp-typescript` | `includes: [cursor-typescript]`; `outputs: [cursor, copilot]` — second stack multi-adapter profile |
| `ekp-symfony` | `includes: [cursor-symfony]`; `outputs: [cursor, copilot]` — third stack multi-adapter profile |
| `ekp-frontend` | `includes: [cursor-frontend]`; `outputs: [cursor, copilot]` — fourth stack multi-adapter profile |
| `ekp-devops` | `includes: [cursor-devops]`; `outputs: [cursor, copilot]` — fifth stack multi-adapter profile |
| `ekp-nativescript` | `includes: [cursor-nativescript]`; `outputs: [cursor, copilot]` — sixth stack multi-adapter profile |
| `ekp-core` | Multi-adapter **pilot** (`includes: [cursor-core]`; Cursor + Copilot + Antigravity + Claude) |

Stack packaging follows a consistent pattern: **`cursor-*` technology profiles** define knowledge composition and Cursor output; matching **`ekp-*` stack profiles** inherit via `includes` and add Copilot (`outputs: [cursor, copilot]`). Operational `cursor-*` profiles remain Cursor-only.

Profiles compose knowledge via **`includes`** (ADR-0008). Included profiles contribute knowledge paths only; the root profile owns `adapter`, `filters`, and `outputs`. **`extends` is not supported.**

Example stack profile (`profiles/cursor-php.yaml`):

```yaml
name: cursor-php
includes:
  - cursor-core
knowledge:
  - knowledge/php/php-fundamentals.md
```

See `templates/profile-template.yaml` and `schema/profile.schema.json`.

### `templates/` — Authoring scaffolds

Reusable document structures for knowledge, ADRs, checklists, profiles, and rules.

### `examples/` — Educational samples

Demonstrates ADR format and review checklists. **Not** production decisions—see [`examples/README.md`](../examples/README.md).

### `scripts/` — Operational pipeline

| Component | Path | Role |
|-----------|------|------|
| Validator | `scripts/validate/` | Structure, graph, concepts, links |
| Adapters | `scripts/adapters/` | Knowledge → tool formats (Cursor operational) |
| Assemble | `scripts/assemble/` | Profile → deployable bundle + manifest |

Scripts are idempotent, testable, and documented. See [`DEVELOPMENT.md`](../DEVELOPMENT.md).

### `dist/` — Generated artifacts (gitignored)

- `dist/concept-index.json`, `knowledge-graph.json`, `adapter-manifest.json` — from `validate --generate-index`
- `dist/<profile>/` — from `assemble` (Cursor `.mdc`, optional Copilot/Antigravity/Claude trees, manifests)

Never commit `dist/`. Regenerate locally or in CI.

### `docs/` — Project meta-documentation

Vision, architecture, roadmap, contribution process, deployment—not engineering knowledge.

## Knowledge vs. rules vs. profiles

| Aspect | Knowledge | Rules (generated) | Profiles |
|--------|-----------|-------------------|----------|
| **Audience** | Engineers (human and AI) | AI assistants | Both, scoped |
| **Format** | Markdown | Tool-specific (`.mdc`, etc.) | YAML manifest |
| **Authored by** | Engineers | Adapters from knowledge | Composed from knowledge paths |
| **Stability** | High — changes require review | Regenerated on knowledge changes | Low — easy to recompose |
| **Contains reasoning** | Yes — trade-offs, context | No — concise directives only | No — references only |

## Adapter pipeline (operational)

```
1. Validate   — Frontmatter, graph, concepts, links
2. Index      — dist/*.json for adapter consumption
3. Extract    — scripts/adapters/common/ parses knowledge
4. Transform  — registered adapters (cursor, copilot, antigravity, claude)
5. Assemble   — Profile bundle + manifests + --verify
6. Deploy     — Consumer CLI (`ekp install` / `update` / `uninstall`) or copy dist/<profile>/<adapter>/ artifacts (see deployment.md)
```

### Design constraints

- **Deterministic** — same knowledge + profile → same output
- **Incremental** — changed-only validation for CI efficiency
- **Explicit contract** — `adapter_priority`, concept IDs, Decision Flows

### Metadata contract

Knowledge frontmatter is validated against `schema/knowledge-frontmatter.schema.json`. Adapters filter on `adapter_priority`, `severity`, and profile `knowledge` paths.

## Extension points

**Operational today:**

- Validator v2.3 with graph rules, namespaces, index generation, reports
- Adapters: Cursor (all 15 profiles), Copilot on six stack `ekp-*` profiles (`ekp-php`, `ekp-typescript`, `ekp-symfony`, `ekp-frontend`, `ekp-devops`, `ekp-nativescript`) plus `ekp-core`, Antigravity / Claude (`ekp-core` pilot)
- Assemble pipeline with `--verify` (CI verifies all 15 profiles)
- Consumer CLI (`v0.19` published; upcoming (unreleased) `v0.21` workspaces) — multi-assistant composition detect/install/status/update/uninstall/configure (Cursor default; Copilot / Claude / Antigravity via `--assistant`; schema2 `--workspace`); legacy `--profile` retained

**Planned / deferred:**

- `ekp-flutter` + Copilot Flutter PATH_GROUP (deferred — planned separately after `v0.14.0` publication)
- Graph role `technology` (V1) if V2 exceptions proliferate (deferred)
- Antigravity / Claude on stack profiles (deferred; remain `ekp-core` pilot)
- Promote `ekp-core` from four-adapter pilot (deferred)
- Public publication of v0.21 Workspace / Monorepo Support (implementation complete; release pending)

## Related

- [`adapter-architecture.md`](adapter-architecture.md) — pipeline stages
- [`deployment.md`](deployment.md) — consumer copy paths per adapter
- [`folder-structure.md`](folder-structure.md) — directory layout
- [`DEVELOPMENT.md`](../DEVELOPMENT.md) — local validation and CI
