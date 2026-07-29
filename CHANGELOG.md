# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- Phase 1 completion: validation CLI, GitHub templates, JSON Schema contracts.
- Domain README stubs with scope boundaries for all knowledge domains.
- ADR location (`knowledge/architecture/decisions/`) and checklist convention (`knowledge/<domain>/checklists/`).
- Profile template and schema; profiles reference knowledge only.
- Tool scaffold directories: `rules/cursor/`, `rules/copilot/`, `rules/claude/`.
- Script scaffolds: `scripts/validate/`, `scripts/adapters/`, `scripts/assemble/`.
- `knowledge/engineering/engineering-principles.md` — foundational engineering principles (EKP-P01–P10).
- ADR-0004: Clean Code position in the EKP knowledge graph.
- Validator v2.0–v2.3: graph validation, concept registry, incremental validation (`--changed-only`), tiered passes (`--tier`), index generation (`--generate-index`), scale and adapter reports.
- `schema/concept-namespaces.json` — namespace registry (through EKP-IN).
- `schema/vocabularies.json` — controlled vocabulary (not enforced yet).
- Core engineering knowledge guides: clean-code, solid, design-patterns, refactoring, error-handling, testing, layering-and-boundaries.
- `knowledge/ai/ai-assisted-development.md` — EKP-AI01–12 AI Decision Flow and orchestrator concepts.
- `profiles/cursor-core.yaml` — first operational profile for Cursor AI-assisted development.
- Adapter common extraction layer (`scripts/adapters/common/`).
- Cursor adapter generator (`scripts/adapters/cursor/`) — knowledge → `.mdc` rules.
- Assemble pipeline (`scripts/assemble/assemble.py`) — profile composition, bundle manifest, `--verify`.
- Generated bundle output: `dist/<profile>/cursor/*.mdc` and `bundle-manifest.json` (gitignored).
- Phase 2C knowledge expansion:
  - `knowledge/security/security-fundamentals.md` — EKP-SF01–SF08; AI Decision Flow; EKP-P02, EKP-P06, EKP-P07.
  - `knowledge/performance/performance-mindset.md` — EKP-PM01–PM07; EKP-P02, EKP-P08.
  - `knowledge/engineering/logging-and-observability.md` — EKP-LO01–LO08; EKP-P04, EKP-P07.
- Namespaces EKP-SF, EKP-PM, EKP-LO in `schema/concept-namespaces.json`.
- Phase 3B architecture knowledge expansion:
  - `knowledge/architecture/adr-practices.md` — EKP-AD01–AD07.
  - `knowledge/architecture/coupling-and-cohesion.md` — EKP-MC01–MC07.
  - `knowledge/architecture/api-design.md` — EKP-AP01–AP09; AI Decision Flow.
  - `knowledge/architecture/integration-patterns.md` — EKP-IN01–IN08.
  - `knowledge/database/database-design.md` — EKP-DB01–DB08.
- Namespaces EKP-AD, EKP-MC, EKP-AP, EKP-DB, EKP-IN.
- Graph exception: `integration-patterns.md` → `layering-and-boundaries.md` (documented in `graph-rules.yaml`).

### Changed

- Consolidated ADR storage under `knowledge/architecture/decisions/`; removed top-level `adr/` directory.
- Validation excludes `adr-*.md` files from knowledge frontmatter checks (decision record format).
- Extended `schema/profile.schema.json` with `adapter` block (`target`, `include.adapter_priority`).
- Documentation aligned with operational pipeline state (Phase 2B / 3A stabilize).
- `ai-assisted-development.md` — EKP-AI10 routes to Phase 2C and 3B guides.
- `error-handling.md`, `testing.md`, `engineering-principles.md` — cross-links to Phase 2C guides.
- `layering-and-boundaries.md` — LB04 escalation to coupling-and-cohesion.
- `architecture/README.md`, `database/README.md` — published indexes.

## [0.1.0] - 2026-07-23

### Added

- Repository foundation: directory structure, documentation, and document templates.
- Project vision, architecture, roadmap, style guide, and contribution guidance.
