# Adapter Architecture

This document describes how EKP knowledge flows from authored markdown to deployable AI assistant artifacts.

## Pipeline overview

```
knowledge/
    ↓
validate
    ↓
generate-index
    ↓
adapter generation
    ↓
assemble
    ↓
deploy artifact
```

## Stages

### 1. Knowledge markdown

Authors maintain guides under `knowledge/` with YAML frontmatter. Graph metadata (`depends_on`, `role`, `concept_ids`, `adapter_priority`) is validated by the EKP validator.

### 2. Validator

`scripts/validate/validate.py` enforces structural, graph, and registry rules. In v2.3 it also supports:

- `--changed-only` for incremental CI validation
- `--tier` for scoped validation passes
- `--generate-index` for adapter artifacts
- `--report adapters` and `--report scale` for readiness metrics

### 3. Generated indexes

Running:

```bash
py -3 scripts/validate/validate.py --generate-index
```

writes:

| File | Purpose |
|------|---------|
| `dist/concept-index.json` | Concept ID → document metadata lookup |
| `dist/knowledge-graph.json` | Nodes and `depends_on` / `related` edges |
| `dist/adapter-manifest.json` | Principles and adapter rule priorities |

Adapters consume these JSON files instead of parsing markdown at runtime.

### 4. Adapter common extraction layer

`scripts/adapters/common/` provides shared logic used by all tool adapters:

| Module | Purpose |
|--------|---------|
| `models.py` | Data structures including `GeneratedRule` (in-memory IR) |
| `extract.py` | Parses knowledge markdown into concept blocks and decision flows |
| `paths.py` | Repository path resolution for knowledge and output targets |
| `profile_resolve.py` | Profile `includes` resolution |
| `profile_loader.py` | Profile loading; canonical `outputs` resolution |
| `selection.py` | Shared adapter-manifest concept selection |
| `registry.py` | Adapter dispatch registry (Cursor, Copilot, Antigravity, Claude) |

### 5. Cursor adapter

`scripts/adapters/cursor/` transforms extracted and normalized knowledge into Cursor Rules (`.mdc`):

| Module | Purpose |
|--------|---------|
| `generate.py` | Orchestrates extract → selection → normalization → writer |
| `normalize.py` | Builds `GeneratedRule` objects for Cursor |
| `mdc_writer.py` | Writes `.mdc` files with Cursor frontmatter |
| `naming.py` | Deterministic rule file naming from concept metadata |
| `manifest.py` | Cursor bundle manifest generation |
| `verify.py` | Cursor bundle verification |

The adapter reads profile knowledge paths and `adapter.include.adapter_priority` filters to select which concepts become rules.

### 5b. Copilot adapter (AI30B pilot)

`scripts/adapters/copilot/` writes GitHub Copilot custom instructions from the same extract + selection pipeline. Mapping lives in the Copilot writer — `GeneratedRule` is not extended with globs or Copilot metadata.

| Module | Purpose |
|--------|---------|
| `generate.py` | Orchestrates extract → selection → grouping → writer |
| `grouping.py` | Always-on vs path-specific file policy |
| `writer.py` | Renders instruction markdown and `applyTo` frontmatter |
| `manifest.py` | `adapter-manifest.json` |
| `verify.py` | Tree, naming, frontmatter, sources, determinism |

**Output (under `dist/<profile>/copilot/`):**

```
.github/copilot-instructions.md
.github/instructions/*.instructions.md   # only when profile knowledge justifies it
adapter-manifest.json                    # written by assemble
```

v1 grouping:

- One compact always-on `copilot-instructions.md` (orchestrator, foundation, and unscoped domains).
- Path-specific `*.instructions.md` files only for knowledge prefixes with a clear consumer path (`testing`, `php`, `symfony`, `typescript`, `frontend`, `nativescript`, `devops`). `ekp-core` therefore emits testing instructions, not a 1:1 Cursor `.mdc` dump.
- Copilot skills are **not** generated.

**PATH_GROUPS** (defined in `scripts/adapters/copilot/grouping.py`; first matching prefix wins):

| Group | Knowledge prefix | Output file | `applyTo` (representative) |
|-------|------------------|-------------|----------------------------|
| `php` | `knowledge/php/` | `php.instructions.md` | `**/*.php` |
| `symfony` | `knowledge/symfony/` | `symfony.instructions.md` | `**/*.php,**/*.twig,**/*.yaml,**/*.yml` |
| `typescript` | `knowledge/typescript/` | `typescript.instructions.md` | `**/*.ts,**/*.tsx` |
| `frontend` | `knowledge/frontend/` | `frontend.instructions.md` | `**/*.{js,jsx,ts,tsx,css,scss,html,vue}` |
| `nativescript` | `knowledge/nativescript/` | `nativescript.instructions.md` | `**/*.xml,**/App_Resources/**,**/nativescript.config.{ts,js}` |
| `devops` | `knowledge/devops/` | `devops.instructions.md` | Docker/workflow/yaml globs |
| `testing` | `knowledge/testing/` | `testing.instructions.md` | test directory / spec globs |

The `nativescript` group (added in `v0.13.0`) intentionally excludes broad `**/*.ts`, `**/*.js`, and `**/*.vue` globs. TypeScript knowledge continues to route via the `typescript` group. Structural generation and verify are supported; empirical Copilot runtime session behavior is not claimed.

### 5c. Antigravity adapter (AI30B pilot)

`scripts/adapters/antigravity/` writes workspace rules as **plain Markdown** under `.agents/rules/`.

| Module | Purpose |
|--------|---------|
| `generate.py` | Orchestrates extract → selection → per-document grouping → writer |
| `grouping.py` | One file per knowledge document; 12,000-character split policy |
| `writer.py` | Plain Markdown (no YAML activation frontmatter) |
| `manifest.py` | `adapter-manifest.json` |
| `verify.py` | Tree, 12k limit, sources, no Cursor frontmatter |

**Output (under `dist/<profile>/antigravity/`):**

```
.agents/rules/00-orchestrator.md
.agents/rules/01-foundation.md
.agents/rules/10-<document-stem>.md
adapter-manifest.json
```

Official Antigravity research did **not** establish a file-based YAML contract for Always On / Manual / Model Decision / Glob. This adapter therefore does **not** invent Cursor-style frontmatter (`alwaysApply` or otherwise). Skills and workflows are out of scope.

**Validation status (non-blocking):**

Technically verified by generation, adapter verify, `ekp-core` assemble, automated tests, and CI:

- files are written under `.agents/rules/`
- content is plain Markdown
- each file is under the 12,000-character limit
- output is deterministic
- `adapter-manifest.json` matches the generated tree
- source references are preserved

Not verified, and not claimed:

- runtime activation inside a real Antigravity workspace
- whether generated files are automatically Always On
- whether Manual / Model Decision / Glob activation can be persisted purely through generated files
- any undocumented frontmatter or activation semantics

Runtime activation status: structurally and deterministically validated, but not empirically validated in a live Antigravity workspace because the EKP maintainer does not currently use Antigravity. The adapter therefore makes no claim about runtime activation semantics beyond what is supported by official documentation.

A future contributor who actively uses Antigravity may perform a runtime validation and update the adapter only if official/documented behavior supports it. Until then, this limitation is environmental, not an implementation failure.

**Optional future runtime check (Antigravity user):**

1. Copy `dist/ekp-core/antigravity/.agents/rules/` into a workspace `.agents/rules/`.
2. Run a task that should exercise orchestrator and foundation guidance.
3. Observe whether the agent follows or cites those files.
4. Record which files appear Always On vs ignored.
5. Update this adapter only when the observation matches official documentation.

### 5d. Claude adapter (AI30D pilot)

`scripts/adapters/claude/` writes Claude Code project memory plus document-grouped Skills. Packaging follows the AI30C recommendation: compact `CLAUDE.md` + Skills — **not** 65 pathless `.claude/rules/*.md`.

| Module | Purpose |
|--------|---------|
| `generate.py` | Orchestrates extract → `selected_knowledge` → Claude grouping → writer |
| `grouping.py` | Always-on vs document skills; deterministic skill IDs |
| `writer.py` | Renders `CLAUDE.md` and `SKILL.md` (official `name` / `description` frontmatter only) |
| `manifest.py` | `adapter-manifest.json` (`kind`: `memory` \| `skill`) |
| `verify.py` | Tree, frontmatter, sources, leakage, forbid `.claude/rules/` |

**Output (under `dist/<profile>/claude/`):**

```
CLAUDE.md
.claude/skills/<skill-id>/SKILL.md
adapter-manifest.json
```

v1 model:

- `CLAUDE.md` holds compact always-on material (orchestrator + engineering foundation) and a short skill index. Soft target: under ~200 lines.
- Each remaining selected knowledge document becomes one Skill (for example `ekp-refactoring`, `ekp-testing`, `ekp-error-handling`, `ekp-layering`).
- Pathless `.claude/rules/*.md` are intentionally **not** generated (they load at session start and recreate always-on context bloat).
- No Cursor / Copilot / Antigravity activation metadata is emitted.
- Shared `GeneratedRule` IR is not extended with Claude-specific fields.

**Validation status (non-blocking for runtime):**

Technically verified by generation, adapter verify, `ekp-core` assemble, automated tests, and CI:

- expected Claude packaging tree
- skill frontmatter and provenance
- deterministic content (apart from manifest `generated_at`)
- no cross-adapter leakage
- no pathless rules directory

Not verified, and not claimed:

- runtime Claude Code skill auto-invocation
- whether `/skill-name` or description-based loading behaves as expected in a live Claude Code session

### 6. Assemble pipeline

`scripts/assemble/assemble.py` composes deployable bundles for a profile by dispatching to registered adapters based on profile `outputs`:

```bash
py -3 scripts/assemble/assemble.py --profile cursor-core --clean --verify
```

| Flag | Purpose |
|------|---------|
| `--profile` | Profile YAML to assemble (e.g. `cursor-core`) |
| `--clean` | Remove existing output before generation |
| `--verify` | Run per-adapter verification after assembly |

Profiles declare requested adapters with `outputs` (canonical). Legacy profiles may still use `adapter.target` as a fallback when `outputs` is omitted.

Output structure:

```
dist/<profile>/
├── assemble-manifest.json  # profile-level adapter list (deterministic)
├── bundle-manifest.json    # Cursor contract when cursor is assembled
├── cursor/
│   └── *.mdc
├── copilot/                # when requested and implemented
│   ├── .github/
│   └── adapter-manifest.json
├── antigravity/            # when requested and implemented
│   ├── .agents/rules/
│   └── adapter-manifest.json
└── claude/                 # when requested and implemented
    ├── CLAUDE.md
    ├── .claude/skills/
    └── adapter-manifest.json
```

The `ekp-core` pilot assembles Cursor + Copilot + Antigravity + Claude. Six stack `ekp-*` profiles assemble Cursor + Copilot for their included `cursor-*` knowledge:

- `ekp-php` (`includes: [cursor-php]`)
- `ekp-typescript` (`includes: [cursor-typescript]`)
- `ekp-symfony` (`includes: [cursor-symfony]`)
- `ekp-frontend` (`includes: [cursor-frontend]`)
- `ekp-devops` (`includes: [cursor-devops]`)
- `ekp-nativescript` (`includes: [cursor-nativescript]`)

Operational `cursor-*` profiles remain Cursor-only. Antigravity and Claude remain available only through `ekp-core`. Unknown adapters fail explicitly with no Cursor fallback.

Cursor `bundle-manifest.json` stays at the profile root and is never overwritten by another adapter.

### 7. Bundle manifests

`dist/<profile>/bundle-manifest.json` is the **Cursor** contract. It records:

- Profile name and generation timestamp
- Rule inventory with source knowledge paths
- Concept IDs included

`dist/<profile>/assemble-manifest.json` records the full assembly (profile, adapter list, per-adapter directories and manifest paths). It is deterministic and has no timestamp.

Non-Cursor adapters use `dist/<profile>/<adapter>/adapter-manifest.json`. Copilot, Antigravity, and Claude pilots write these files.

### 8. Profiles

Stack-specific profiles under `profiles/` reference **knowledge paths only**. Adapters derive rules at build time based on profile `adapter` settings:

```yaml
adapter:
  target:
    - cursor
  include:
    adapter_priority:
      - high
```

See `profiles/cursor-core.yaml` for the first operational Cursor profile, `profiles/cursor-flutter.yaml` for the Flutter L2 Cursor profile (`includes: [cursor-core]` only; Cursor-only), `profiles/ekp-php.yaml` through `profiles/ekp-nativescript.yaml` for the six stack multi-adapter profiles (Cursor + Copilot), and `profiles/ekp-core.yaml` for the four-adapter pilot. Flutter has no Copilot PATH_GROUP in `v0.14.0`; `ekp-flutter` remains deferred.

## Output locations

| Path | Role |
|------|---------|
| `dist/<profile>/cursor/*.mdc` | **Deployable artifact** — copy to consumer `.cursor/rules/` |
| `dist/<profile>/copilot/.github/` | Copilot instructions (pilot; copy into a consumer repo root) |
| `dist/<profile>/antigravity/.agents/rules/` | Antigravity rules (pilot; copy into a consumer workspace) |
| `dist/<profile>/claude/` | Claude Code `CLAUDE.md` + Skills (pilot) |
| `dist/<profile>/bundle-manifest.json` | Cursor bundle contract (profile root) |
| `dist/<profile>/assemble-manifest.json` | Profile-level assembly inventory |
| `dist/*.json` | Generated indexes for adapter consumption |
| `rules/` | Scaffold only — **not** the primary bundle source |

## Design principles

- **Single source of truth:** Markdown remains authoritative; indexes and rules are generated outputs.
- **Fail closed:** Validation must pass before indexes are published.
- **Incremental scale:** Changed-only and tiered validation keep CI fast at 100–500 documents.
- **Explicit adapter contract:** `adapter_priority` and manifest JSON define what adapters prioritize.
- **Reproducible bundles:** `assemble --verify` ensures generated output matches profile and source refs.

## Related documents

- `scripts/validate/README.md` — validator usage and tiers
- `docs/deployment.md` — copy generated artifacts into a consumer project
- `docs/folder-structure.md` — directory layout and content flow
- `schema/concept-namespaces.json` — namespace ownership registry
- `schema/vocabularies.json` — controlled vocabulary (not enforced yet)
