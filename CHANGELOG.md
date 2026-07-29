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
- `schema/concept-namespaces.json` — namespace ownership registry (EKP-P, EKP-CC, EKP-SL, EKP-DP, EKP-RF, EKP-EH, EKP-TS, EKP-LB, EKP-AI).
- `schema/vocabularies.json` — controlled vocabulary (not enforced yet).
- Core engineering knowledge guides: clean-code, solid, design-patterns, refactoring, error-handling, testing, layering-and-boundaries.
- `knowledge/ai/ai-assisted-development.md` — EKP-AI01–12 AI Decision Flow and orchestrator concepts.
- `profiles/cursor-core.yaml` — first operational profile for Cursor AI-assisted development.
- Adapter common extraction layer (`scripts/adapters/common/`).
- Cursor adapter generator (`scripts/adapters/cursor/`) — knowledge → `.mdc` rules.
- Assemble pipeline (`scripts/assemble/assemble.py`) — profile composition, bundle manifest, `--verify`.
- Generated bundle output: `dist/<profile>/cursor/*.mdc` and `bundle-manifest.json` (gitignored).

### Changed

- Consolidated ADR storage under `knowledge/architecture/decisions/`; removed top-level `adr/` directory.
- Validation excludes `adr-*.md` files from knowledge frontmatter checks (decision record format).
- Extended `schema/profile.schema.json` with `adapter` block (`target`, `include.adapter_priority`).
- Documentation aligned with operational pipeline state (Phase 2B / 3A stabilize).

## [0.1.0] - 2026-07-23

### Added

- Repository foundation: directory structure, documentation, and document templates.
- Project vision, architecture, roadmap, style guide, and contribution guidance.
