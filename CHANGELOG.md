# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.2.0] - 2026-07-30

### Added

#### Knowledge guides (16 total)

- Core engineering: engineering-principles, clean-code, solid, design-patterns, refactoring, error-handling.
- Testing: testing.
- Architecture: layering-and-boundaries, adr-practices, coupling-and-cohesion, api-design, integration-patterns.
- AI: ai-assisted-development (EKP-AI01–12, orchestrator Decision Flow).
- Phase 2C: security-fundamentals (EKP-SF), performance-mindset (EKP-PM), logging-and-observability (EKP-LO).
- Phase 3B: database-design (EKP-DB) in `knowledge/database/`.

#### Concept namespaces

- EKP-P, CC, SL, DP, RF, EH, TS, LB, AI (foundation through 3A).
- EKP-SF, PM, LO (Phase 2C).
- EKP-AD, MC, AP, IN, DB (Phase 3B).

#### Operational pipeline (Phase 3A)

- Validator v2.3: graph validation, concept registry, `--changed-only`, `--tier`, `--generate-index`, scale/adapter reports.
- Adapter common layer and Cursor adapter (`knowledge` → `.mdc`).
- Assemble pipeline with `--verify` and `bundle-manifest.json`.
- Profile `cursor-core` (65 rules when assembled with `high` priority filter).

#### Examples (Phase 3B.1)

- `examples/adr-0001-example-service-boundary.md`
- `examples/checklists/architecture-review.md`
- `examples/checklists/api-review.md`
- `examples/README.md`

#### Schemas and infrastructure artifacts

- `schema/concept-namespaces.json`, `graph-rules.yaml` (incl. integration-patterns → layering-and-boundaries exception).
- `schema/profile.schema.json` adapter block.
- GitHub issue/PR templates; domain README stubs; ADR-0004.

### Changed

- Documentation synchronized with operational state (README, `docs/architecture.md`, CONTRIBUTING, contribution-guide, rules READMEs).
- `ai-assisted-development.md`: EKP-AI10 escalation routes to Phase 2C and 3B guides.
- Cross-links in engineering-principles, error-handling, testing, layering-and-boundaries, refactoring, decisions README.
- ADR storage consolidated under `knowledge/architecture/decisions/`.
- Roadmap: Phase 3A operational, 3B and 3B.1 complete.

### Infrastructure

- CI workflow `.github/workflows/ekp-validation.yml`: validate → generate-index → adapter tests → assemble tests → assemble `--verify`.
- Extended `NAVIGATION_READMES` for ai, security, performance, database domains (0 README navigation warnings).

### Documentation

- `DEVELOPMENT.md` — local validation and assemble pipeline.
- `docs/adapter-architecture.md`, `docs/folder-structure.md` — operational pipeline and `dist/` vs `rules/`.
- Educational examples for ADR format and architecture/API review checklists.

## [0.1.0] - 2026-07-23

### Added

- Repository foundation: directory structure, documentation, and document templates.
- Project vision, architecture, roadmap, style guide, and contribution guidance.
