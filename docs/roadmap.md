# Roadmap

Development is organized into five phases. Each phase produces a usable artifact; later phases build on earlier ones without requiring rework of the foundation.

## Phase 1: Foundation

**Status:** In progress

Establish the repository structure, meta-documentation, templates, and contribution workflow.

**Deliverables:**

- [x] Directory structure (`knowledge/`, `rules/`, `profiles/`, `templates/`, `docs/`, `scripts/`, `examples/`)
- [x] Project documentation (vision, architecture, roadmap, style guide, contribution guide)
- [x] Document templates (knowledge, rules, review checklist, decision record)
- [ ] Validation script skeleton in `scripts/`
- [ ] GitHub issue and PR templates

**Exit criteria:** A contributor can read the docs, pick a template, and know exactly where to place new content and how to format it.

---

## Phase 2: Core engineering knowledge

Populate cross-cutting engineering domains that apply regardless of technology stack.

**Target domains:**

- `knowledge/engineering/` — code organization, naming, error handling, logging, documentation
- `knowledge/testing/` — testing philosophy, test pyramid, test naming, fixture management
- `knowledge/security/` — input validation, authentication patterns, secrets management
- `knowledge/performance/` — profiling mindset, caching principles, query awareness

**Deliverables:**

- 15–25 focused knowledge documents across core domains
- Cross-reference index per domain
- At least one example profile composing core knowledge

**Exit criteria:** A team can adopt EKP for code review and engineering standards without any technology-specific content.

---

## Phase 3: Architecture knowledge

Capture system design and architectural decision-making practices.

**Target domains:**

- `knowledge/architecture/` — layering, boundaries, coupling, cohesion, ADR practices
- `knowledge/database/` — schema design, migrations, transaction boundaries, query patterns

**Deliverables:**

- Architecture decision record examples in `examples/`
- Knowledge documents covering common architectural patterns (hexagonal, CQRS, event-driven)
- Review checklist template populated with architecture-specific items

**Exit criteria:** A tech lead can use EKP to guide architecture reviews and document decisions consistently.

---

## Phase 4: Technology knowledge

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

## Phase 5: AI assistant adapters

Build the transformation layer that converts knowledge into tool-specific formats.

**Deliverables:**

- Adapter: knowledge → Cursor Rules (`.mdc`)
- Adapter: knowledge → GitHub Copilot instructions
- Adapter: knowledge → Claude Skills format
- Profile assembly script (knowledge + rules → deployable bundle)
- Validation CLI (`scripts/validate`) for structure, metadata, and broken links
- Documentation for running adapters and deploying profiles

**Exit criteria:** A team can select a profile, run a script, and deploy engineering context to their AI assistant of choice. Changes to knowledge automatically propagate to rules.

---

## Principles across all phases

1. **Ship incrementally** — each phase delivers value on its own.
2. **Quality over quantity** — ten excellent documents beat fifty shallow ones.
3. **Review everything** — knowledge documents follow the same rigor as production code.
4. **Measure adoption** — gather feedback from teams using EKP before expanding domains.
