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

### Changed

- Consolidated ADR storage under `knowledge/architecture/decisions/`; removed top-level `adr/` directory.
- Validation excludes `adr-*.md` files from knowledge frontmatter checks (decision record format).

## [0.1.0] - 2026-07-23

### Added

- Repository foundation: directory structure, documentation, and document templates.
- Project vision, architecture, roadmap, style guide, and contribution guidance.
