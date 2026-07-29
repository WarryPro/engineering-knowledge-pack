# Roadmap

Development is organized into phases. Each phase produces a usable artifact; later phases build on earlier ones without requiring rework of the foundation.

## Phase status overview

| Phase | Status | Summary |
|-------|--------|---------|
| Phase 1 — Foundation | **Complete** | Structure, templates, schemas, validation skeleton |
| Phase 2 — Core engineering knowledge | **In progress** | 12 guides published; Phase 2C cross-cutting complete |
| Phase 3A — AI operational pipeline | **Operational** | Validator v2.3, profiles, Cursor adapter, assemble |
| Phase 3B — Architecture knowledge expansion | **Planned** | Deeper architecture and database knowledge |
| Phase 4 — Technology knowledge | **Planned** | Stack-specific domains (PHP, Symfony, Flutter, etc.) |
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

**Status:** In progress

Populate cross-cutting engineering domains that apply regardless of technology stack.

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
- [ ] 15–25 focused knowledge documents across all core domains
- [x] Security and performance guides (Phase 2C)
- [ ] Cross-reference index per domain

**Exit criteria:** A team can adopt EKP for code review and engineering standards without any technology-specific content.

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
- [ ] CI workflow for validate → generate-index → tests → assemble
- [ ] Deploy documentation for consumer projects

**Exit criteria:** A team can select a profile, run the pipeline, and deploy engineering context to Cursor. Changes to knowledge propagate to generated rules via assemble.

---

## Phase 3B: Architecture knowledge expansion

**Status:** Planned

Expand system design and architectural decision-making knowledge beyond current boundary coverage.

**Target domains:**

- `knowledge/architecture/` — additional patterns (hexagonal, CQRS, event-driven), ADR practices
- `knowledge/database/` — schema design, migrations, transaction boundaries, query patterns

**Deliverables:**

- Architecture decision record examples in `examples/`
- Knowledge documents covering common architectural patterns
- Review checklist template populated with architecture-specific items

**Exit criteria:** A tech lead can use EKP to guide architecture reviews and document decisions consistently.

---

## Phase 4: Technology knowledge

**Status:** Planned

Add stack-specific guidance for the technologies this project targets.

**Target domains:**

- `knowledge/php/`
- `knowledge/symfony/`
- `knowledge/flutter/`
- `knowledge/typescript/`
- `knowledge/frontend/`
- `knowledge/devops/`

**Deliverables:**

- Technology-specific knowledge documents with clear scope boundaries
- Profiles per major stack (e.g., `profiles/symfony-api.yaml`, `profiles/flutter-mobile.yaml`)
- Examples showing how generic engineering principles apply within a specific stack

**Exit criteria:** A developer working in a supported stack can find actionable guidance for common tasks without wading through irrelevant content.

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
