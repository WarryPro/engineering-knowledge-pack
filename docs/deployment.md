# Deploying EKP to a consumer project

How to choose a profile, assemble a bundle, and copy generated artifacts into a consumer repository for each implemented adapter.

This guide describes **what EKP generates and how to copy it**. It does not claim that a consumer AI tool will load or follow those files at runtime unless that behavior is listed under automated verification.

Related:

- [`adapter-architecture.md`](adapter-architecture.md) — how adapters transform knowledge
- [`../DEVELOPMENT.md`](../DEVELOPMENT.md) — local validate / test / assemble pipeline
- [`../scripts/adapters/README.md`](../scripts/adapters/README.md) — adapter package layout

## 1. Choose a profile

Profiles live under `profiles/` and declare **knowledge paths** plus **`outputs`** (which adapters to assemble). `outputs` is canonical (ADR-0009). `adapter.target` is a legacy fallback when `outputs` is absent.

| Profile | Audience | Cursor | Copilot | Antigravity | Claude |
|---------|----------|--------|---------|-------------|--------|
| `cursor-core` | Cross-cutting engineering (frozen Cursor foundation) | yes | no | no | no |
| `cursor-php` | PHP (`includes: [cursor-core]`) | yes | no | no | no |
| `cursor-symfony` | Symfony (`includes: [cursor-core]`) | yes | no | no | no |
| `cursor-typescript` | TypeScript (`includes: [cursor-core]`) | yes | no | no | no |
| `cursor-frontend` | Frontend (`includes: [cursor-core]`) | yes | no | no | no |
| `cursor-devops` | DevOps (`includes: [cursor-core]`) | yes | no | no | no |
| `cursor-nativescript` | NativeScript (`includes: [cursor-typescript]`) | yes | no | no | no |
| `ekp-php` | PHP multi-adapter (`includes: [cursor-php]`) | yes | yes | no | no |
| `ekp-typescript` | TypeScript multi-adapter (`includes: [cursor-typescript]`) | yes | yes | no | no |
| `ekp-symfony` | Symfony multi-adapter (`includes: [cursor-symfony]`) | yes | yes | no | no |
| `ekp-frontend` | Frontend multi-adapter (`includes: [cursor-frontend]`) | yes | yes | no | no |
| `ekp-devops` | DevOps multi-adapter (`includes: [cursor-devops]`) | yes | yes | no | no |
| `ekp-core` | Multi-adapter **pilot** (`includes: [cursor-core]`) | yes | yes | yes | yes |

Operational Cursor products include the six original `cursor-*` profiles plus `cursor-nativescript`. `ekp-php`, `ekp-typescript`, `ekp-symfony`, `ekp-frontend`, and `ekp-devops` are stack-specific multi-adapter profiles (Cursor + Copilot). Antigravity and Claude remain available only through the `ekp-core` pilot. `ekp-nativescript` remains deferred. `ekp-frontend` packages frontend architecture and styling/markup knowledge (`frontend-architecture.md` EKP-FE01–FE08 and `frontend-styling-and-markup.md` EKP-FE09–FE16). `ekp-devops` packages existing DevOps fundamentals (EKP-DV01–DV08) via `includes: [cursor-devops]`.

Pick:

- A `cursor-*` profile if you only need Cursor Rules.
- `ekp-php` if you need Cursor Rules and/or Copilot instructions for PHP (same knowledge as `cursor-php`).
- `ekp-typescript` if you need Cursor Rules and/or Copilot instructions for TypeScript (same knowledge as `cursor-typescript`).
- `ekp-symfony` if you need Cursor Rules and/or Copilot instructions for Symfony (same knowledge as `cursor-symfony`).
- `ekp-frontend` if you need Cursor Rules and/or Copilot instructions for frontend architecture and styling/markup (same knowledge as `cursor-frontend`; EKP-FE01–FE16).
- `ekp-devops` if you need Cursor Rules and/or Copilot instructions for DevOps (same knowledge as `cursor-devops`; EKP-DV01–DV08).
- `ekp-core` if you need Copilot, Antigravity, and/or Claude artifacts **in addition to** the same Cursor knowledge as `cursor-core` (foundation only; no stack knowledge).

`ekp-core` does not add extra knowledge beyond `cursor-core`; it only requests more adapters. `ekp-php`, `ekp-typescript`, `ekp-symfony`, `ekp-frontend`, and `ekp-devops` do not modify their included Cursor profiles; included profiles contribute knowledge paths only.

## 2. Assemble

Install validator dependencies, then generate indexes (required before assemble):

```bash
py -3 -m pip install -r scripts/validate/requirements.txt
py -3 scripts/validate/validate.py
py -3 scripts/validate/validate.py --generate-index
```

Assemble a profile (CLI requires `--profile`):

```bash
py -3 scripts/assemble/assemble.py --profile cursor-core
py -3 scripts/assemble/assemble.py --profile cursor-core --clean --verify
py -3 scripts/assemble/assemble.py --profile ekp-php --clean --verify
py -3 scripts/assemble/assemble.py --profile ekp-typescript --clean --verify
py -3 scripts/assemble/assemble.py --profile ekp-symfony --clean --verify
py -3 scripts/assemble/assemble.py --profile ekp-frontend --clean --verify
py -3 scripts/assemble/assemble.py --profile ekp-devops --clean --verify
py -3 scripts/assemble/assemble.py --profile ekp-core --clean --verify
```

| Flag | Meaning |
|------|---------|
| `--profile <name>` | Required. Loads `profiles/<name>.yaml`. |
| `--clean` | Delete `dist/<name>/` before generation. |
| `--verify` | Run each requested adapter's verifier after generation. |

There is no `assemble <profile>` shorthand. Unknown or unimplemented adapter names fail explicitly; assemble does not fall back to Cursor.

### Output layout

Every assembled profile writes:

```
dist/<profile>/
├── assemble-manifest.json     # profile-level adapter inventory (deterministic; no timestamp)
├── bundle-manifest.json       # Cursor contract (only when cursor is in outputs)
├── cursor/                    # when cursor is requested
│   └── *.mdc
├── copilot/                   # when copilot is requested
│   ├── .github/
│   └── adapter-manifest.json
├── antigravity/               # when antigravity is requested
│   ├── .agents/rules/
│   └── adapter-manifest.json
└── claude/                    # when claude is requested
    ├── CLAUDE.md
    ├── .claude/skills/
    └── adapter-manifest.json
```

`dist/` is gitignored. Never treat `rules/` as the deployable source.

### Manifests

| File | Owner | Role |
|------|--------|------|
| `dist/<profile>/assemble-manifest.json` | assemble | Lists adapters, directories, and manifest paths. Deterministic. |
| `dist/<profile>/bundle-manifest.json` | Cursor | Cursor rule inventory. Includes `generated_at`. Stays at the **profile root**. |
| `dist/<profile>/<adapter>/adapter-manifest.json` | Copilot / Antigravity / Claude | Per-adapter file list and sources. Includes `generated_at`. |

Adapters do not overwrite each other's manifests. Do **not** copy EKP manifests into the consumer tool tree unless you want them as local inventory; they are not consumer-tool configuration.

## 3. Cursor deployment

**Source profile:** any `cursor-*` profile, `ekp-php` (same Cursor knowledge as `cursor-php`), `ekp-typescript` (same Cursor knowledge as `cursor-typescript`), `ekp-symfony` (same Cursor knowledge as `cursor-symfony`), `ekp-frontend` (same Cursor knowledge as `cursor-frontend`), `ekp-devops` (same Cursor knowledge as `cursor-devops`), or `ekp-core` (same Cursor knowledge as `cursor-core`).

**Generated:** `dist/<profile>/cursor/*.mdc`

**Copy:**

```
dist/<profile>/cursor/  →  <consumer>/.cursor/rules/
```

Examples:

```
dist/cursor-core/cursor/        →  <project>/.cursor/rules/
dist/cursor-php/cursor/         →  <project>/.cursor/rules/
dist/ekp-php/cursor/            →  <project>/.cursor/rules/
dist/ekp-typescript/cursor/     →  <project>/.cursor/rules/
dist/ekp-symfony/cursor/        →  <project>/.cursor/rules/
dist/ekp-frontend/cursor/       →  <project>/.cursor/rules/
dist/ekp-devops/cursor/         →  <project>/.cursor/rules/
dist/ekp-core/cursor/           →  <project>/.cursor/rules/
```

Copy the `.mdc` files only (or the whole `cursor/` directory). Leave `bundle-manifest.json` at `dist/<profile>/`; it is an EKP inventory file, not a Cursor rule.

Expected `cursor-core` count: **65** `.mdc` files (frozen). Stack profiles add technology guides (~74 single-stack, ~83 combined-stack). `cursor-nativescript` is a combined TypeScript + NativeScript Cursor product.

Cursor generation, verify, and CI assemble gates cover packaging. This guide does not claim how Cursor loads `.mdc` files in a given IDE version.

## 4. Copilot deployment

**Source profiles:** `ekp-core` (foundation knowledge), `ekp-php` (PHP stack knowledge via `includes: [cursor-php]`), `ekp-typescript` (TypeScript stack knowledge via `includes: [cursor-typescript]`), `ekp-symfony` (Symfony stack knowledge via `includes: [cursor-symfony]`), `ekp-frontend` (frontend architecture and styling/markup knowledge via `includes: [cursor-frontend]`), or `ekp-devops` (DevOps stack knowledge via `includes: [cursor-devops]`).

**Generated under** `dist/<profile>/copilot/`:

```
.github/copilot-instructions.md
.github/instructions/*.instructions.md   # domain files when knowledge justifies them
adapter-manifest.json
```

Always-on instructions have **no** `applyTo`. Path-specific `*.instructions.md` files are emitted only when the profile knowledge includes a mapped domain prefix. Examples:

- `ekp-core` includes `knowledge/testing/` → `testing.instructions.md`
- `ekp-php` also includes `knowledge/php/` → `testing.instructions.md` and `php.instructions.md` (`applyTo: "**/*.php"`)
- `ekp-typescript` also includes `knowledge/typescript/` → `testing.instructions.md` and `typescript.instructions.md` (`applyTo: "**/*.ts,**/*.tsx"`)
- `ekp-symfony` also includes `knowledge/php/` and `knowledge/symfony/` → `testing.instructions.md`, `php.instructions.md` (`applyTo: "**/*.php"`), and `symfony.instructions.md` (`applyTo: "**/*.php,**/*.twig,**/*.yaml,**/*.yml"`)
- `ekp-frontend` also includes `knowledge/typescript/` and `knowledge/frontend/` → `testing.instructions.md`, `typescript.instructions.md` (`applyTo: "**/*.ts,**/*.tsx"`), and `frontend.instructions.md` (`applyTo: "**/*.{js,jsx,ts,tsx,css,scss,html,vue}"`) — covers EKP-FE01–FE16 (architecture + styling/markup)
- `ekp-devops` also includes `knowledge/devops/` → `testing.instructions.md` and `devops.instructions.md` (`applyTo: "**/{Dockerfile,docker-compose*.yml,docker-compose*.yaml},**/.github/workflows/**,**/*.{yml,yaml}"`)

Copilot **skills** are not generated.

**Copy:**

```
dist/ekp-php/copilot/.github/        →  <consumer-repo>/.github/
dist/ekp-typescript/copilot/.github/ →  <consumer-repo>/.github/
dist/ekp-symfony/copilot/.github/    →  <consumer-repo>/.github/
dist/ekp-frontend/copilot/.github/   →  <consumer-repo>/.github/
dist/ekp-devops/copilot/.github/     →  <consumer-repo>/.github/
dist/ekp-core/copilot/.github/       →  <consumer-repo>/.github/
```

That places `copilot-instructions.md` and `instructions/*.instructions.md` at the consumer repository root's `.github/` tree. Do not copy `adapter-manifest.json` into `.github/`.

EKP structurally generates and verifies the Copilot file tree, `applyTo` shape where present, sources, and determinism. Empirical Copilot runtime session behavior is not claimed.


## 5. Antigravity deployment

**Source profile:** `ekp-core` only (v0.5.0).

**Generated under** `dist/ekp-core/antigravity/`:

```
.agents/rules/00-orchestrator.md
.agents/rules/01-foundation.md
.agents/rules/10-<document-stem>.md
adapter-manifest.json
```

Files are **plain Markdown**. EKP does **not** emit Always On / Manual / Model Decision / Glob YAML. Skills and workflows are out of scope. Each file is kept under a 12,000-character limit.

**Copy:**

```
dist/ekp-core/antigravity/.agents/rules/  →  <consumer-workspace>/.agents/rules/
```

### Structurally verified

- files under `.agents/rules/`
- plain Markdown, no invented activation frontmatter
- 12,000-character limit
- deterministic content (except manifest `generated_at`)
- `adapter-manifest.json` matches disk
- source references present

### Not runtime verified

Runtime activation inside a live Antigravity workspace is **not** empirically validated. EKP does not claim that generated files are automatically Always On, or that undocumented frontmatter would persist activation.

## 6. Claude deployment

**Source profile:** `ekp-core` only (v0.5.0).

**Generated under** `dist/ekp-core/claude/`:

```
CLAUDE.md
.claude/skills/ekp-error-handling/SKILL.md
.claude/skills/ekp-layering/SKILL.md
.claude/skills/ekp-refactoring/SKILL.md
.claude/skills/ekp-testing/SKILL.md
adapter-manifest.json
```

- `CLAUDE.md` is compact always-on project memory (orchestrator + engineering foundation). It is not a dump of every Cursor concept. Soft target: under ~200 lines.
- Each remaining selected knowledge document becomes one Skill (`name` + `description` frontmatter only). Skills are document-grouped, not 1:1 Cursor `.mdc` files.
- Pathless `.claude/rules/*.md` are **not** generated.

**Copy:**

```
dist/ekp-core/claude/CLAUDE.md           →  <consumer>/CLAUDE.md
dist/ekp-core/claude/.claude/skills/     →  <consumer>/.claude/skills/
```

Do not copy `adapter-manifest.json` into the consumer `.claude/` tree.

### Structurally verified

- expected packaging tree
- Skill frontmatter (`name`, `description`) and provenance
- no pathless `.claude/rules/`
- no Cursor `alwaysApply` / Copilot `applyTo` leakage
- deterministic content (except manifest `generated_at`)
- manifest matches disk

### Not runtime verified

Runtime Claude Code skill invocation (including `/skill-name` or description-based loading) has **not** been empirically verified by the EKP maintainer. Auto-invocation is **not** guaranteed.

## 7. What is verified automatically vs at runtime

### Automated (repository / CI)

- knowledge validator
- adapter unit tests
- assemble tests
- `assemble --verify` per requested adapter (tree, sources, manifests, leakage checks where implemented)
- thirteen operational profile assemble gates (seven `cursor-*` + five stack `ekp-*` + `ekp-core` pilot)
- `ekp-php` assemble gate (cursor + copilot)
- `ekp-typescript` assemble gate (cursor + copilot)
- `ekp-symfony` assemble gate (cursor + copilot)
- `ekp-frontend` assemble gate (cursor + copilot)
- `ekp-devops` assemble gate (cursor + copilot)
- `ekp-core` assemble gate (cursor + copilot + antigravity + claude)
- deterministic generated **content** (manifest `generated_at` may change)
- Cursor `.mdc` byte-identity vs the frozen Cursor baseline, when that comparison is run

### Runtime (consumer AI tool)

- whether Cursor loads `.mdc` rules in a given session
- whether Copilot applies custom instructions as GitHub documents
- whether Antigravity treats `.agents/rules/` as Always On
- whether Claude Code loads `CLAUDE.md` or invokes Skills

Structural success is **not** a runtime support claim.

## 8. Update after EKP changes

1. Update this repository (pull the tag or branch you pin).
2. `py -3 scripts/validate/validate.py`
3. `py -3 scripts/validate/validate.py --generate-index`
4. Assemble the same profile with `--clean --verify`.
5. Inspect `dist/<profile>/` (and `assemble-manifest.json`).
6. Copy the adapter directories above into the consumer project, replacing the previous copies.

EKP never writes into consumer tool directories during assemble.

Pin consumers to a **repository release tag** (ADR-0006), then regenerate. Do not commit `dist/` in EKP.
