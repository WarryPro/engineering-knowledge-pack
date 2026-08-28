# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.12.0] - 2026-08-28

### Added

- Profile `ekp-devops` (`includes: [cursor-devops]`, `outputs: [cursor, copilot]`) — fifth stack-specific multi-adapter profile parallel to `cursor-devops`
- CI assemble `--verify` gate for `ekp-devops`
- Assemble tests for `ekp-devops` knowledge resolution, Cursor `.mdc` identity vs `cursor-devops`, and Copilot DevOps instructions

### Compatibility

- Existing twelve operational profiles unchanged: 65 / 74 / 83 / 74 / 92 / 74 / 84 / 74 / 74 / 83 / 92 / 65 (Cursor rule counts)
- Cursor `.mdc` content for those profiles remains byte-identical to `v0.11.0`
- `ekp-devops` Cursor `.mdc` content byte-identical to `cursor-devops` (74 rules)
- Copilot output for `ekp-devops`: `copilot-instructions.md`, `devops.instructions.md`, `testing.instructions.md` only (reuses existing DevOps PATH_GROUP)
- Antigravity and Claude remain outside `ekp-devops` (still demonstrated via `ekp-core` pilot only)
- `ekp-core` remains a four-adapter packaging pilot
- Remaining stack multi-adapter profile (`ekp-nativescript`) deferred
- Packaging-only — no knowledge, schema, or adapter implementation changes
- Copilot output for `ekp-devops` is structurally generated and verified; empirical Copilot runtime session behavior is not claimed

## [0.11.0] - 2026-08-27

### Added

- Guide `knowledge/frontend/frontend-styling-and-markup.md` (EKP-FE09–FE16): semantic HTML and native capabilities, styling architecture, simplest-fit styling mechanism, cascade/specificity ownership, design tokens, layout and responsive strategy, operational accessibility for interactive surfaces, and UI verification by user-visible outcomes
- Profile `cursor-frontend` includes the styling/markup guide; assembled Cursor rule count **83 → 92**
- `ekp-frontend` inherits the expanded frontend knowledge via `includes: [cursor-frontend]` (92 rules); `ekp-frontend.yaml` unchanged
- EKP-FE namespace `additional_owners` for the two-document frontend structure (`frontend-architecture.md` + `frontend-styling-and-markup.md`); single-owner behavior unchanged for all other namespaces
- Frontend Copilot routing includes styling/markup knowledge through the existing `frontend.instructions.md` group (no new Copilot groups)

### Compatibility

- FE01–FE08 concept content and generated `.mdc` files remain byte-identical to `v0.10.0`
- Existing non-frontend profiles unchanged and Cursor-only: 65 / 74 / 83 / 74 / 74 / 84
- `cursor-frontend` ↔ `ekp-frontend` Cursor `.mdc` content byte-identical
- Antigravity and Claude remain outside `ekp-frontend` (still demonstrated via `ekp-core` pilot only)
- `ekp-core` remains a four-adapter packaging pilot
- Remaining stack multi-adapter profiles (`ekp-devops`, `ekp-nativescript`) deferred
- Does **not** include React/Vue/Angular tutorials, Bootstrap/Tailwind encyclopedias, SCSS/CSS-in-JS tutorials, component-library catalogs, Flutter/Dart knowledge, WCAG encyclopedia, browser compatibility matrices, performance profile changes, `ekp-devops`/`ekp-nativescript` changes, or new adapters
- Copilot output for `ekp-frontend` is structurally generated and verified; empirical Copilot runtime session behavior is not claimed

## [0.10.0] - 2026-08-26

### Added

- Profile `ekp-frontend` (`includes: [cursor-frontend]`, `outputs: [cursor, copilot]`) — fourth stack-specific multi-adapter profile parallel to `cursor-frontend`
- CI assemble `--verify` gate for `ekp-frontend`
- Assemble tests for `ekp-frontend` knowledge resolution, Cursor `.mdc` identity vs `cursor-frontend`, and Copilot TypeScript/Frontend instructions

### Compatibility

- Existing seven operational Cursor profiles unchanged and Cursor-only: 65 / 74 / 83 / 74 / 83 / 74 / 84
- `ekp-frontend` Cursor `.mdc` content byte-identical to `cursor-frontend`
- Antigravity and Claude remain outside `ekp-frontend` (still demonstrated via `ekp-core` pilot only)
- `ekp-core` remains a four-adapter packaging pilot
- Remaining stack multi-adapter profiles (`ekp-devops`, `ekp-nativescript`) deferred
- Frontend CSS/HTML/layout/design-system/styling knowledge expansion remains a separate deferred initiative — not part of this packaging work
- Copilot output for `ekp-frontend` is structurally generated and verified; empirical Copilot runtime session behavior is not claimed

## [0.9.0] - 2026-08-22

### Added

- Profile `ekp-symfony` (`includes: [cursor-symfony]`, `outputs: [cursor, copilot]`) — third stack-specific multi-adapter profile parallel to `cursor-symfony`
- CI assemble `--verify` gate for `ekp-symfony`
- Assemble tests for `ekp-symfony` knowledge resolution, Cursor `.mdc` identity vs `cursor-symfony`, and Copilot PHP/Symfony instructions

### Compatibility

- Existing seven operational Cursor profiles unchanged and Cursor-only: 65 / 74 / 83 / 74 / 83 / 74 / 84
- Cursor `.mdc` content for those profiles remains byte-identical to `v0.8.0`
- `ekp-symfony` Cursor `.mdc` content byte-identical to `cursor-symfony`
- Antigravity and Claude remain outside `ekp-symfony` (still demonstrated via `ekp-core` pilot only)
- `ekp-core` remains a four-adapter packaging pilot
- Remaining stack multi-adapter profiles (`ekp-frontend`, `ekp-devops`, `ekp-nativescript`) deferred
- Copilot output for `ekp-symfony` is structurally generated and verified; empirical Copilot runtime session behavior is not claimed

## [0.8.0] - 2026-08-22

### Added

- Profile `ekp-typescript` (`includes: [cursor-typescript]`, `outputs: [cursor, copilot]`) — second stack-specific multi-adapter profile parallel to `cursor-typescript`
- CI assemble `--verify` gate for `ekp-typescript`
- Assemble tests for `ekp-typescript` knowledge resolution, Cursor `.mdc` identity vs `cursor-typescript`, and Copilot TypeScript instructions

### Compatibility

- Existing seven operational Cursor profiles unchanged and Cursor-only: 65 / 74 / 83 / 74 / 83 / 74 / 84
- Cursor `.mdc` content for those profiles remains byte-identical to `v0.7.0`
- `ekp-typescript` Cursor `.mdc` content byte-identical to `cursor-typescript`
- Antigravity and Claude remain outside `ekp-typescript` (still demonstrated via `ekp-core` pilot only)
- `ekp-core` remains a four-adapter packaging pilot
- Remaining stack multi-adapter profiles (`ekp-symfony`, `ekp-frontend`, `ekp-devops`, `ekp-nativescript`) deferred
- Copilot output for `ekp-typescript` is structurally generated and verified; empirical Copilot runtime session behavior is not claimed

## [0.7.0] - 2026-08-22

### Added

- Profile `cursor-nativescript` (`includes: [cursor-typescript]`, `outputs: [cursor]`) — NativeScript L2 technology vertical on TypeScript
- Guide `knowledge/nativescript/nativescript-architecture.md` (EKP-NS01–NS09) covering native runtime model, UI/navigation/lifecycle, platform and plugin boundaries, NativeScript-Vue integration (bounded), and build/device/performance discipline
- Namespace `EKP-NS`; graph-rules exception NativeScript → TypeScript
- CI assemble `--verify` gate and assemble tests for `cursor-nativescript`
- Assembled `cursor-nativescript` Cursor rule count: **84** (TypeScript 74 + NativeScript concepts)

### Compatibility

- Existing six Cursor profiles unchanged and Cursor-only: 65 / 74 / 83 / 74 / 83 / 74
- Cursor `.mdc` content for those six profiles remains byte-identical to `v0.6.0`
- `cursor-nativescript` does not include `cursor-frontend` or frontend knowledge
- Flutter remains deferred; `ekp-nativescript` (multi-adapter packaging) not created
- No adapter generator, IR, or `cursor-core.yaml` changes
- Antigravity and Claude remain `ekp-core` pilot only; Copilot not added to NativeScript

## [0.6.0] - 2026-08-21

### Added

- Profile `ekp-php` (`includes: [cursor-php]`, `outputs: [cursor, copilot]`) — first stack-specific multi-adapter profile parallel to `cursor-php`
- CI assemble `--verify` gate for `ekp-php`
- Assemble tests for `ekp-php` knowledge resolution, Cursor `.mdc` identity vs `cursor-php`, and Copilot PHP instructions

### Compatibility

- Six operational Cursor profiles unchanged and Cursor-only: 65 / 74 / 83 / 74 / 83 / 74
- Cursor output paths, filenames, and `.mdc` content byte-identical to `v0.5.1`
- `ekp-php` Cursor `.mdc` content byte-identical to `cursor-php`
- Antigravity and Claude remain outside `ekp-php` (still demonstrated via `ekp-core` pilot only)
- `ekp-core` remains a four-adapter packaging pilot
- Remaining stack multi-adapter profiles (`ekp-symfony`, …) deferred
- No adapter generator, knowledge, IR, or `cursor-core.yaml` changes
- Copilot output for `ekp-php` is structurally generated and verified; empirical Copilot runtime session behavior is not claimed
- Antigravity runtime activation and Claude skill invocation remain not empirically validated

## [0.5.1] - 2026-08-18

### Added

- Consumer deployment guide (`docs/deployment.md`) covering profile selection, assemble CLI, per-adapter copy paths, manifests, regeneration, and automated vs runtime verification

### Changed

- Stale adapter status in architecture, scaffold READMEs, `ekp-core` comments, and `DEVELOPMENT.md` aligned with v0.5.0 (four implemented adapters; Copilot/Antigravity/Claude remain `ekp-core` pilots)

### Compatibility

- Documentation-only PATCH; no adapter implementation, profile, knowledge, IR, or CI workflow changes
- Six operational Cursor profiles unchanged and Cursor-only: 65 / 74 / 83 / 74 / 83 / 74
- Cursor output paths, filenames, and `.mdc` content byte-identical to `v0.5.0`
- Copilot, Antigravity, and Claude remain `ekp-core` pilots
- Antigravity runtime activation is structurally validated but not empirically validated in a live Antigravity workspace
- Claude runtime skill invocation is structurally validated but not empirically validated in a live Claude Code session

## [0.5.0] - 2026-08-17

### Added

- Claude adapter (`scripts/adapters/claude/`) generating compact `CLAUDE.md` plus document-grouped `.claude/skills/<skill-id>/SKILL.md`
- `ekp-core` pilot now includes Claude alongside Cursor, Copilot, and Antigravity

### Changed

- Default adapter registry implements Cursor, Copilot, Antigravity, and Claude
- Claude packaging intentionally avoids pathless `.claude/rules/*.md` and 1:1 Cursor concept dumps

### Compatibility

- Six operational Cursor profiles unchanged and Cursor-only: 65 / 74 / 83 / 74 / 83 / 74
- Cursor output paths, filenames, and `.mdc` content byte-identical to `v0.4.0`
- Multi-adapter manifests remain isolated (`bundle-manifest.json`, per-adapter `adapter-manifest.json`, deterministic `assemble-manifest.json`)
- Copilot, Antigravity, and Claude are demonstrated through the `ekp-core` pilot, not the six operational profiles
- Claude v1 does not emit pathless `.claude/rules/` or 1:1 Cursor concept dumps
- Claude runtime skill invocation is structurally validated but not empirically validated in a live Claude Code session
- No new knowledge guides, concepts, namespaces, or graph exceptions

## [0.4.0] - 2026-08-16

### Added

- Copilot adapter (`scripts/adapters/copilot/`) generating `.github/copilot-instructions.md` plus a small set of path-specific `*.instructions.md` files
- Antigravity adapter (`scripts/adapters/antigravity/`) generating plain Markdown rules under `.agents/rules/` (12,000-character limit; no invented activation frontmatter)
- `ekp-core` pilot assemble/verify CI gate for Cursor + Copilot + Antigravity

### Changed

- Default adapter registry implements Cursor, Copilot, and Antigravity; Claude remains unimplemented

### Compatibility

- Six operational Cursor profiles unchanged and Cursor-only: 65 / 74 / 83 / 74 / 83 / 74
- Cursor output paths, filenames, and `.mdc` content byte-identical to `v0.3.5`
- Multi-adapter manifests remain isolated (`bundle-manifest.json`, per-adapter `adapter-manifest.json`, deterministic `assemble-manifest.json`)
- Copilot and Antigravity are demonstrated through the `ekp-core` pilot, not the six operational profiles
- Copilot skills, Antigravity skills/workflows, and Claude remain out of scope
- Antigravity runtime activation is structurally validated but not empirically validated in a live Antigravity workspace
- No new knowledge guides, concepts, namespaces, or graph exceptions

## [0.3.5] - 2026-08-15

### Added

- Deterministic `assemble-manifest.json` for profile-level adapter assembly
- Profile `ekp-core` (`includes: [cursor-core]`) declaring planned Copilot and Antigravity outputs

### Changed

- Assemble writes Cursor `bundle-manifest.json` only for the Cursor adapter (no overwrite by other adapters)
- Unimplemented adapters fail before generation
- Profile schema allows includes-only profiles (no local `knowledge` list)

### Compatibility

- All six Cursor profiles unchanged: 65 / 74 / 83 / 74 / 83 / 74
- Cursor output paths, filenames, and `.mdc` content byte-identical to `v0.3.4`
- Copilot, Antigravity, and Claude remain planned, not implemented
- No new knowledge guides, concepts, namespaces, or graph exceptions

## [0.3.4] - 2026-08-15

### Added

- ADR-0009 — Adapter dispatch architecture
- Adapter registry (`scripts/adapters/common/registry.py`) with explicit failure for unimplemented adapters
- Shared profile loading (`profile_loader.py`) and shared selection (`selection.py`)
- In-memory Cursor `GeneratedRule` normalization (`cursor/normalize.py`)
- Adapter-specific Cursor verification (`cursor/verify.py`) and bundle manifests (`cursor/manifest.py`)
- Profile schema: `antigravity` added to adapter enum (planned, not implemented)

### Changed

- `outputs` is the canonical profile field; `adapter.target` remains a legacy fallback when `outputs` is absent
- `assemble.py` dispatches through the adapter registry instead of calling Cursor generation directly
- Cursor generation, verification, and manifests are isolated under `scripts/adapters/cursor/`

### Compatibility

- All six Cursor profiles unchanged: 65 / 74 / 83 / 74 / 83 / 74
- Cursor output paths, filenames, and `.mdc` content byte-identical to `v0.3.3`
- Copilot, Antigravity, and Claude remain planned, not implemented
- No new knowledge guides, concepts, namespaces, or graph exceptions

## [0.3.3] - 2026-08-10

### Added

- ADR-0008 — Profile composition via `includes` (no `extends`)
- `scripts/adapters/common/profile_resolve.py` — recursive includes resolution with cycle detection
- Profile schema optional `includes` array
- Validator checks for unknown/circular includes and resolved knowledge paths
- Tests for profile includes composition and rule-count regression

### Changed

- Stack profiles (`cursor-php`, `cursor-symfony`, `cursor-typescript`, `cursor-frontend`, `cursor-devops`) now `include: [cursor-core]` instead of duplicating L0 knowledge paths
- Assembly resolves `includes` before Cursor rule generation (included profiles contribute knowledge paths only)
- Documentation: governance, architecture, DEVELOPMENT, ADR index

## [0.3.2] - 2026-08-09

### Added

- Phase 4 Wave 3 (DevOps):
  - `knowledge/devops/devops-fundamentals.md` — EKP-DV01–DV08
  - Namespace EKP-DV
  - Profile `cursor-devops`
  - CI assemble `--verify` for `cursor-devops`
  - Profile isolation tests for `cursor-devops`

### Changed

- `ai-assisted-development.md` — EKP-AI10 routes to EKP-DV
- engineering-principles downstream technology table
- Documentation: README, roadmap, architecture, DEVELOPMENT metrics

## [0.3.1] - 2026-08-07

### Added

- Phase 4 Wave 2 (TypeScript + Frontend):
  - `knowledge/typescript/typescript-fundamentals.md` — EKP-TY01–TY08
  - `knowledge/frontend/frontend-architecture.md` — EKP-FE01–FE08
  - Namespaces EKP-TY, EKP-FE
  - Profiles `cursor-typescript`, `cursor-frontend`
  - Graph V2 exception: frontend-architecture → typescript-fundamentals
  - CI assemble `--verify` for `cursor-typescript`, `cursor-frontend`

- Phase 3C Governance foundation (EKP-AI16):
  - `docs/governance.md`
  - `templates/knowledge-review-checklist.md`
  - ADR-0005, ADR-0006, ADR-0007
  - Optional frontmatter `status` (default: published)
  - `.github/CODEOWNERS` ownership boundaries
  - PR template governance section

### Changed

- Documentation: README/DEVELOPMENT metrics and multi-profile assemble
- `ai-assisted-development.md` — EKP-AI10 routes to EKP-TY and EKP-FE
- engineering-principles downstream technology table
- Roadmap: v0.2.0/v0.3.0 released; Phase 3A CI complete; Phase 2 exit criteria revised; Phase 3C added

## [0.3.0] - 2026-08-04

### Added

#### Technology knowledge (Phase 4 Wave 1)

- `knowledge/php/php-fundamentals.md` — EKP-PH01–PH08
- `knowledge/symfony/symfony-architecture.md` — EKP-SY01–SY08
- Namespaces EKP-PH, EKP-SY (EKP-TY / EKP-FE reserved for later)

#### Profiles

- `profiles/cursor-php.yaml` (74 rules when assembled)
- `profiles/cursor-symfony.yaml` (83 rules)
- `cursor-core` unchanged at 65 rules

#### Authoring / infrastructure

- Technology knowledge template and guide checklist
- Graph V2 exception: symfony-architecture → php-fundamentals
- CI assemble `--verify` for cursor-core, cursor-php, cursor-symfony

### Changed

- Architecture/roadmap: L0–L3 technology layer model; Phase 4 in progress
- README / DEVELOPMENT: multi-profile assemble
- EKP-AI10 routes to EKP-PH and EKP-SY
- engineering-principles related/downstream tables for tech guides

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
