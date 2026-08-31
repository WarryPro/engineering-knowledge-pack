# Roadmap

Development is organized into phases. Each phase produces a usable artifact; later phases build on earlier ones without requiring rework of the foundation.

## Phase status overview

| Phase | Status | Summary |
|-------|--------|---------|
| Phase 1 — Foundation | **Complete** | Structure, templates, schemas, validation skeleton |
| Phase 2 — Core engineering knowledge | **Substantially complete** | Cross-cutting L0 guides; quality bar over doc count |
| Phase 3A — AI operational pipeline | **Operational** | Validator v2.3, profiles, Cursor adapter, assemble |
| Phase 3B — Architecture knowledge expansion | **Complete** | 5 architecture guides + database-design |
| Phase 3B.1 — Repository consolidation | **Complete** | CI, examples, DEVELOPMENT.md, v0.2.0 released |
| Phase 3C — Governance foundation | **Complete** | ADRs 0005–0007, governance.md, lifecycle status |
| Phase 4 — Technology knowledge | **Substantially complete** | Waves 1–3 published; `cursor-nativescript` (NativeScript L2); `cursor-flutter` (Flutter L2 published in `v0.14.0`); `ekp-flutter` deferred |
| Phase 5 — Additional AI adapters | **Partial** | Cursor complete; Copilot stack profiles complete (`ekp-php` through `ekp-nativescript` in `v0.6.0`–`v0.13.0`); Antigravity + Claude in `v0.4.0`/`v0.5.0` (`ekp-core` pilot only); `ekp-flutter`, Antigravity/Claude on stack profiles, and `ekp-core` promotion deferred |

---

## Phase 1: Foundation

**Status:** Complete

Establish the repository structure, meta-documentation, templates, and contribution workflow.

**Deliverables:**

- [x] Directory structure (`knowledge/`, `rules/`, `profiles/`, `templates/`, `docs/`, `scripts/`, `examples/`)
- [x] Project documentation (vision, architecture, roadmap, style guide, contribution guide)
- [x] Document templates (knowledge, rules, review checklist, decision record, profile)
- [x] Validation script in `scripts/validate/`
- [x] GitHub issue and PR templates
- [x] JSON Schema contracts in `schema/`
- [x] Domain README stubs with scope boundaries
- [x] ADR and checklist artifact locations defined

**Exit criteria:** A contributor can read the docs, pick a template, and know exactly where to place new content and how to format it.

---

## Phase 2: Core engineering knowledge

**Status:** Substantially complete

Populate cross-cutting engineering domains that apply regardless of technology stack.

**Exit criteria (revised):** A team can adopt EKP for code review and engineering standards without any technology-specific content. Completion is measured by **coverage and quality** of cross-cutting guides, not a fixed document count.

**Note:** The earlier “15–25 documents” target is **retired** as a simplistic completion metric. Further L0 expansion is opportunistic, not a gate for Phase 4.

**Target domains:**

- `knowledge/engineering/` — principles, clean code, SOLID, design patterns, refactoring, error handling, logging
- `knowledge/testing/` — testing philosophy, test pyramid, test naming, fixture management
- `knowledge/security/` — input validation, authentication patterns, secrets management
- `knowledge/performance/` — profiling mindset, caching principles, query awareness

**Deliverables:**

- [x] Foundational guides: engineering-principles, clean-code, solid, design-patterns, refactoring, error-handling
- [x] Testing guide: `knowledge/testing/testing.md`
- [x] Architecture boundary guide: `knowledge/architecture/layering-and-boundaries.md`
- [x] AI orchestrator guide: `knowledge/ai/ai-assisted-development.md`
- [x] First operational profile: `profiles/cursor-core.yaml`
- [x] Security guide: `knowledge/security/security-fundamentals.md`
- [x] Performance guide: `knowledge/performance/performance-mindset.md`
- [x] Logging guide: `knowledge/engineering/logging-and-observability.md`
- [x] Cross-cutting security and performance guides (Phase 2C)
- [ ] Cross-reference index per domain (ongoing)

---

## Phase 3A: AI operational pipeline

**Status:** Operational

Build the transformation layer that converts knowledge into deployable AI assistant artifacts.

**Deliverables:**

- [x] Validator v2.3 with graph validation, concept registry, and index generation
- [x] Generated indexes: `dist/concept-index.json`, `dist/knowledge-graph.json`, `dist/adapter-manifest.json`
- [x] Adapter common extraction layer (`scripts/adapters/common/`)
- [x] Cursor adapter (`scripts/adapters/cursor/`) — knowledge → `.mdc` rules
- [x] Assemble pipeline (`scripts/assemble/assemble.py`) with `--verify` and `bundle-manifest.json`
- [x] Profile `cursor-core` producing `dist/cursor-core/cursor/*.mdc`
- [x] CI workflow for validate → generate-index → tests → assemble (15 profiles)
- [x] Deploy documentation for consumer projects (`docs/deployment.md`)

**Exit criteria:** A team can select a profile, run the pipeline, and deploy engineering context to Cursor. Changes to knowledge propagate to generated rules via assemble.

---

## Phase 3B: Architecture knowledge expansion

**Status:** Complete

Expand system design and architectural decision-making knowledge beyond boundary coverage.

**Target domains:**

- `knowledge/architecture/` — ADR practices, coupling/cohesion, API design, integration patterns
- `knowledge/database/` — schema design, migrations, transaction boundaries

**Deliverables:**

- [x] `adr-practices.md` — EKP-AD
- [x] `coupling-and-cohesion.md` — EKP-MC
- [x] `api-design.md` — EKP-AP
- [x] `integration-patterns.md` — EKP-IN
- [x] `database-design.md` — EKP-DB (database domain)
- [x] EKP-AI10 escalation routes to Phase 3B guides
- [x] Example ADR and review checklists in `examples/` (Phase 3B.1)

**Exit criteria:** A tech lead can use EKP to guide architecture reviews and document decisions consistently.

---

## Phase 3B.1: Repository consolidation & release preparation

**Status:** Complete

Consolidated documentation, CI, examples, and release readiness.

**Deliverables:**

- [x] Documentation sync (README, architecture, CONTRIBUTING, rules READMEs)
- [x] `DEVELOPMENT.md` — local validation and pipeline
- [x] `NAVIGATION_READMES` extended (ai, security, performance, database)
- [x] CI workflow `.github/workflows/ekp-validation.yml`
- [x] `examples/` — ADR sample + architecture and API review checklists
- [x] Git tag `v0.2.0` and GitHub Release

**Exit criteria:** CI green; validator 0 README warnings; `cursor-core` stable at 65 rules.

---

## Phase 3C: Governance foundation

**Status:** Complete (EKP-AI16)

Establish lightweight governance so EKP scales beyond 20 guides without semantic drift.

**Deliverables:**

- [x] `docs/governance.md` — single governance entry point
- [x] `templates/knowledge-review-checklist.md`
- [x] ADR-0005 — Technology knowledge evolution
- [x] ADR-0006 — Versioning & compatibility
- [x] ADR-0007 — Knowledge & concept lifecycle
- [x] Optional frontmatter `status` (default: published)
- [x] `.github/CODEOWNERS` ownership boundaries (documented)
- [x] PR template governance section
- [x] Roadmap and meta-doc synchronization

**Deferred:** `technology` validator role, automated deprecation enforcement, Copilot/Claude adapters.

**Exit criteria:** Contributors can follow documented lifecycle, namespace, profile, and release rules without ad hoc convention.

---

## Phase 4: Technology knowledge

**Status:** In progress (Waves 1–3 published on `master`; profile composition `includes` released in `v0.3.3`; adapter dispatch released in `v0.3.4`; multi-adapter packaging released in `v0.3.5`; Copilot/Antigravity pilots released in `v0.4.0`; Claude adapter released in `v0.5.0`)

Add stack-specific guidance for the technologies this project targets, without contaminating foundation knowledge.

**Releases:** `v0.3.0` (PHP/Symfony), `v0.3.1` (TypeScript/Frontend + governance), `v0.3.2` (DevOps), `v0.3.3` (profile `includes`), `v0.3.4` (adapter dispatch), `v0.3.5` (multi-adapter packaging), `v0.4.0` (Copilot + Antigravity pilots), `v0.5.0` (Claude adapter), `v0.5.1` (consumer deployment docs), `v0.6.0` (`ekp-php` Cursor + Copilot), `v0.7.0` (`cursor-nativescript` NativeScript L2), `v0.8.0` (`ekp-typescript` Cursor + Copilot), `v0.9.0` (`ekp-symfony` Cursor + Copilot), `v0.10.0` (`ekp-frontend` Cursor + Copilot), `v0.11.0` (frontend styling/markup knowledge EKP-FE09–FE16) published; `v0.12.0` (`ekp-devops` Cursor + Copilot) published; `v0.13.0` (`ekp-nativescript` Cursor + Copilot) published; `v0.14.0` (`cursor-flutter` Flutter L2) published.

**Layer model:** L0 foundation → L1 language → L2 framework → L3 ops (downward `depends_on` only).

**Target domains:**

- `knowledge/php/` (L1) — **Wave 1**
- `knowledge/symfony/` (L2) — **Wave 1**
- `knowledge/typescript/` (L1) — **Wave 2** — complete
- `knowledge/frontend/` (L2) — **Wave 2** — complete; styling/markup guide (EKP-FE09–FE16) published in `v0.11.0`
- `knowledge/devops/` (L3) — **Wave 3** — complete
- `knowledge/nativescript/` (L2) — **complete** (`cursor-nativescript`; `ekp-nativescript` Cursor + Copilot in `v0.13.0`)
- `knowledge/flutter/` (L2) — **complete** (`flutter-architecture.md` EKP-FL01–FL09; `cursor-flutter` published in `v0.14.0`)

**Deliverables:**

- [x] Wave 0: namespaces `EKP-PH` / `EKP-SY`, graph V2 exception (Symfony → PHP), tech templates/checklist, docs
- [x] `php-fundamentals.md` (EKP-PH)
- [x] `symfony-architecture.md` (EKP-SY)
- [x] Profiles `cursor-php`, `cursor-symfony` (explicit composition; `cursor-core` unchanged)
- [x] CI assemble `--verify` for `cursor-core`, `cursor-php`, `cursor-symfony`
- [x] Wave 2: `typescript-fundamentals.md` (EKP-TY), `frontend-architecture.md` (EKP-FE)
- [x] Profiles `cursor-typescript`, `cursor-frontend`
- [x] CI assemble `--verify` for all five Cursor profiles
- [x] Wave 3: `devops-fundamentals.md` (EKP-DV)
- [x] Profile `cursor-devops`
- [x] CI assemble `--verify` for six Cursor profiles
- [x] Profile `includes` (ADR-0008; `cursor-core` frozen; no `extends`)
- [x] NativeScript: `nativescript-architecture.md` (EKP-NS), profile `cursor-nativescript` (`includes: [cursor-typescript]`)
- [x] Flutter: `flutter-architecture.md` (EKP-FL), profile `cursor-flutter` (`includes: [cursor-core]`); validation, tests, CI wiring published in `v0.14.0`
- [ ] `ekp-flutter` + Copilot Flutter PATH_GROUP (deferred — planned separately)
- [ ] `technology` validator role (deferred)
- [x] Copilot / Antigravity / Claude adapters (Phase 5; `v0.4.0` / `v0.5.0`)

**Exit criteria:** A developer on a supported stack can find actionable guidance without wading through unrelated stacks; tech guides cite L0 concepts instead of duplicating them.

**v0.3.3:** Profile composition (`includes`, ADR-0008) — stack profiles include `cursor-core`; assembled rule counts unchanged; `cursor-core` frozen.

**v0.3.4:** Adapter dispatch (ADR-0009) — registry, canonical `outputs`, Cursor isolation; Copilot/Antigravity/Claude planned, not implemented; Cursor output unchanged.

**v0.3.5:** Multi-adapter packaging — deterministic `assemble-manifest.json`, fail-fast unimplemented adapters, `ekp-core` packaging pilot; Copilot/Antigravity/Claude still not implemented; Cursor output unchanged.

**v0.4.0:** Copilot + Antigravity adapter pilots via `ekp-core` (`outputs: [cursor, copilot, antigravity]`); six operational profiles remain Cursor-only; Cursor output unchanged; Claude remains the next adapter milestone.

**v0.5.0:** Claude adapter pilot via `ekp-core` (`CLAUDE.md` + document-grouped Skills); six operational profiles remain Cursor-only; Cursor output unchanged vs `v0.4.0`.

**v0.5.1:** Consumer deployment documentation (`docs/deployment.md`) and adapter-status reconciliation; documentation-only PATCH; Cursor output unchanged vs `v0.5.0`.

**v0.6.0:** `ekp-php` (`includes: [cursor-php]`, `outputs: [cursor, copilot]`) is the first stack-specific multi-adapter profile. Cursor `.mdc` content matches `cursor-php` and remains byte-identical to `v0.5.1` for all six operational Cursor profiles. Remaining stacks, Antigravity/Claude on stack profiles, and promoting `ekp-core` from pilot remain deferred.

**v0.7.0:** `cursor-nativescript` (`includes: [cursor-typescript]`, `outputs: [cursor]`) is the NativeScript L2 technology vertical. Cursor `.mdc` content for the six operational Cursor profiles remains byte-identical to `v0.6.0`. Flutter and `ekp-nativescript` remain deferred.

**v0.8.0:** `ekp-typescript` (`includes: [cursor-typescript]`, `outputs: [cursor, copilot]`) is the second stack-specific multi-adapter profile. Cursor `.mdc` content for all operational Cursor profiles remains byte-identical to `v0.7.0`. Remaining stacks (`ekp-symfony`, `ekp-frontend`, `ekp-devops`, `ekp-nativescript`), Antigravity/Claude on stack profiles, and promoting `ekp-core` from pilot remain deferred.

**v0.9.0:** `ekp-symfony` (`includes: [cursor-symfony]`, `outputs: [cursor, copilot]`) is the third stack-specific multi-adapter profile. Cursor `.mdc` content for all operational Cursor profiles remains byte-identical to `v0.8.0`. Remaining stacks (`ekp-frontend`, `ekp-devops`, `ekp-nativescript`), Antigravity/Claude on stack profiles, and promoting `ekp-core` from pilot remain deferred.

---

## Phase 5: Additional AI adapters

**Status:** Partial (Cursor complete; all six stack multi-adapter profiles — `ekp-php`, `ekp-typescript`, `ekp-symfony`, `ekp-frontend`, `ekp-devops`, and `ekp-nativescript` — Cursor + Copilot in `v0.6.0`–`v0.13.0`; Antigravity + Claude remain `ekp-core` pilot only; Antigravity/Claude on stack profiles and `ekp-core` promotion deferred)

Extend the adapter layer to additional AI assistant platforms.

**Deliverables:**

- [x] Adapter: knowledge → Cursor Rules (`.mdc`)
- [x] Adapter: knowledge → GitHub Copilot instructions (`ekp-core` pilot)
- [x] Adapter: knowledge → Antigravity workspace rules (`ekp-core` pilot)
- [x] Adapter: knowledge → Claude Code `CLAUDE.md` + Skills (`ekp-core` pilot)
- [x] Profile assembly script (knowledge + adapter → deployable bundle)
- [x] Validation CLI (`scripts/validate`) for structure, metadata, and broken links
- [x] Documentation for deploying profiles to consumer projects (`docs/deployment.md`)
- [x] Expand operational profiles beyond Cursor (all six stack multi-adapter profiles — `ekp-php`, `ekp-typescript`, `ekp-symfony`, `ekp-frontend`, `ekp-devops`, and `ekp-nativescript` — Cursor + Copilot; Antigravity/Claude remain `ekp-core` pilot only)
- [ ] Antigravity / Claude on stack profiles (deferred)
- [ ] Promote `ekp-core` from four-adapter pilot (deferred)

**Exit criteria:** A team can select a profile, run a script, and deploy engineering context to their AI assistant of choice. Changes to knowledge automatically propagate to rules.

**v0.4.0 note:** Antigravity generation is structurally validated; runtime activation in a live Antigravity workspace is not empirically validated in the current maintainer environment.

**v0.5.0 note:** Claude generation is structurally validated (`CLAUDE.md` + Skills, no pathless rules). Runtime Claude Code skill invocation is not empirically verified.

**v0.5.1 note:** Documentation-only PATCH. Antigravity runtime activation and Claude Code skill invocation remain not empirically validated.

**v0.6.0:** `ekp-php` (`includes: [cursor-php]`, `outputs: [cursor, copilot]`) is the first stack-specific multi-adapter profile. Cursor `.mdc` content matches `cursor-php` and remains byte-identical to `v0.5.1` for all six operational Cursor profiles. Remaining stacks, Antigravity/Claude on stack profiles, and promoting `ekp-core` from pilot remain deferred.

**v0.8.0:** `ekp-typescript` (`includes: [cursor-typescript]`, `outputs: [cursor, copilot]`) is the second stack-specific multi-adapter profile. Cursor `.mdc` content matches `cursor-typescript` and remains byte-identical to `v0.7.0` for all operational Cursor profiles. Remaining stacks, Antigravity/Claude on stack profiles, and promoting `ekp-core` from pilot remain deferred.

**v0.9.0:** `ekp-symfony` (`includes: [cursor-symfony]`, `outputs: [cursor, copilot]`) is the third stack-specific multi-adapter profile. Cursor `.mdc` content matches `cursor-symfony` and remains byte-identical to `v0.8.0` for all operational Cursor profiles. Remaining stacks, Antigravity/Claude on stack profiles, and promoting `ekp-core` from pilot remain deferred.

**v0.10.0:** `ekp-frontend` (`includes: [cursor-frontend]`, `outputs: [cursor, copilot]`) is the fourth stack-specific multi-adapter profile. Cursor `.mdc` content matches `cursor-frontend` and remains byte-identical to `v0.9.0` for all operational Cursor profiles. Packages frontend architecture knowledge (EKP-FE01–FE08) only. Remaining stacks (`ekp-devops`, `ekp-nativescript`), Antigravity/Claude on stack profiles, and promoting `ekp-core` from pilot remain deferred.

**v0.11.0:** Frontend Knowledge Enhancement — `frontend-styling-and-markup.md` (EKP-FE09–FE16); `cursor-frontend` **83 → 92** rules; `ekp-frontend` inherits via `includes: [cursor-frontend]`; FE01–FE08 preserved byte-identical to `v0.10.0`; EKP-FE `additional_owners` for two-document frontend structure; framework-neutral engineering principles only. Remaining stacks (`ekp-devops`, `ekp-nativescript`), Antigravity/Claude on stack profiles, and promoting `ekp-core` from pilot remain deferred.

**v0.12.0:** `ekp-devops` (`includes: [cursor-devops]`, `outputs: [cursor, copilot]`) is the fifth stack-specific multi-adapter profile. Cursor `.mdc` content matches `cursor-devops` and remains byte-identical to `v0.11.0` for all existing profiles. Copilot reuses existing DevOps PATH_GROUP routing plus inherited testing instructions. Packaging-only — no knowledge, schema, or adapter implementation changes. Remaining stack (`ekp-nativescript`), Antigravity/Claude on stack profiles, and promoting `ekp-core` from pilot remain deferred.

**v0.13.0:** `ekp-nativescript` (`includes: [cursor-nativescript]`, `outputs: [cursor, copilot]`) is the sixth and final stack-specific multi-adapter profile. Cursor `.mdc` content matches `cursor-nativescript` and remains byte-identical to `v0.12.0` for all existing profiles. Adds Copilot `nativescript` PATH_GROUP (`applyTo: "**/*.xml,**/App_Resources/**,**/nativescript.config.{ts,js}"`); TypeScript knowledge continues via existing `typescript` PATH_GROUP. No knowledge or schema changes. Completes Phase 5 stack multi-adapter packaging. Antigravity/Claude on stack profiles, `ekp-core` promotion, and Flutter remain deferred.

**v0.14.0:** Flutter L2 technology vertical — `flutter-architecture.md` (EKP-FL01–FL09); profile `cursor-flutter` (`includes: [cursor-core]`, `outputs: [cursor]`); 75 Cursor rules (65 inherited core + 10 Flutter); no TypeScript/frontend/NativeScript inheritance; Flutter README validator registration; assemble/profile tests; 15th CI `--verify` gate. Existing fourteen profiles unchanged and byte-identical to `v0.13.0`. **`ekp-flutter`**, Copilot Flutter PATH_GROUP, Antigravity/Claude on stack profiles, and `ekp-core` promotion remain deferred.

---

## Principles across all phases

1. **Ship incrementally** — each phase delivers value on its own.
2. **Quality over quantity** — ten excellent documents beat fifty shallow ones.
3. **Review everything** — knowledge documents follow the same rigor as production code.
4. **Measure adoption** — gather feedback from teams using EKP before expanding domains.
