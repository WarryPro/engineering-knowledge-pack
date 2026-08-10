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
| Phase 4 — Technology knowledge | **In progress** | Waves 1–3 published; profile `includes` (v0.3.3); Flutter deferred |
| Phase 5 — Additional AI adapters | **Partial** | Cursor complete; Copilot and Claude pending |

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
- [x] CI workflow for validate → generate-index → tests → assemble (5 profiles)
- [ ] Deploy documentation for consumer projects

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

**Status:** In progress (Waves 1–3 published on `master`; profile composition `includes` released in `v0.3.3`)

Add stack-specific guidance for the technologies this project targets, without contaminating foundation knowledge.

**Releases:** `v0.3.0` (PHP/Symfony), `v0.3.1` (TypeScript/Frontend + governance), `v0.3.2` (DevOps), `v0.3.3` (profile `includes`) published on `master`.

**Layer model:** L0 foundation → L1 language → L2 framework → L3 ops (downward `depends_on` only).

**Target domains:**

- `knowledge/php/` (L1) — **Wave 1**
- `knowledge/symfony/` (L2) — **Wave 1**
- `knowledge/typescript/` (L1) — **Wave 2** — complete
- `knowledge/frontend/` (L2) — **Wave 2** — complete
- `knowledge/devops/` (L3) — **Wave 3** — complete
- `knowledge/flutter/` (L2) — **Deferred** (post–Wave 3)

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
- [ ] Flutter (deferred)
- [ ] `technology` validator role (deferred)
- [ ] Copilot / Claude adapters (Phase 5)

**Exit criteria:** A developer on a supported stack can find actionable guidance without wading through unrelated stacks; tech guides cite L0 concepts instead of duplicating them.

**v0.3.3:** Profile composition (`includes`, ADR-0008) — stack profiles include `cursor-core`; assembled rule counts unchanged; `cursor-core` frozen.

---

## Phase 5: Additional AI adapters

**Status:** Partial (Cursor complete)

Extend the adapter layer to additional AI assistant platforms.

**Deliverables:**

- [x] Adapter: knowledge → Cursor Rules (`.mdc`)
- [ ] Adapter: knowledge → GitHub Copilot instructions
- [ ] Adapter: knowledge → Claude Skills format
- [x] Profile assembly script (knowledge + adapter → deployable bundle)
- [x] Validation CLI (`scripts/validate`) for structure, metadata, and broken links
- [ ] Documentation for deploying profiles to consumer projects

**Exit criteria:** A team can select a profile, run a script, and deploy engineering context to their AI assistant of choice. Changes to knowledge automatically propagate to rules.

---

## Principles across all phases

1. **Ship incrementally** — each phase delivers value on its own.
2. **Quality over quantity** — ten excellent documents beat fifty shallow ones.
3. **Review everything** — knowledge documents follow the same rigor as production code.
4. **Measure adoption** — gather feedback from teams using EKP before expanding domains.
