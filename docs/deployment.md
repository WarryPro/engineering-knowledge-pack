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
| `ekp-php` | PHP multi-adapter (`includes: [cursor-php]`) | yes | yes | no | no |
| `ekp-core` | Multi-adapter **pilot** (`includes: [cursor-core]`) | yes | yes | yes | yes |

The six `cursor-*` profiles are the operational Cursor products. `ekp-php` is the first stack-specific multi-adapter profile (Cursor + Copilot). Antigravity and Claude remain available only through the `ekp-core` pilot. Other stack multi-adapter profiles remain deferred.

Pick:

- A `cursor-*` profile if you only need Cursor Rules.
- `ekp-php` if you need Cursor Rules and/or Copilot instructions for PHP (same knowledge as `cursor-php`).
- `ekp-core` if you need Copilot, Antigravity, and/or Claude artifacts **in addition to** the same Cursor knowledge as `cursor-core` (foundation only; no PHP stack knowledge).

`ekp-core` does not add extra knowledge beyond `cursor-core`; it only requests more adapters. `ekp-php` does not modify `cursor-php`; included profiles contribute knowledge paths only.

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

**Source profile:** any `cursor-*` profile, `ekp-php` (same Cursor knowledge as `cursor-php`), or `ekp-core` (same Cursor knowledge as `cursor-core`).

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
dist/ekp-core/cursor/           →  <project>/.cursor/rules/
```

Copy the `.mdc` files only (or the whole `cursor/` directory). Leave `bundle-manifest.json` at `dist/<profile>/`; it is an EKP inventory file, not a Cursor rule.

Expected `cursor-core` count: **65** `.mdc` files (frozen). Stack profiles add technology guides (~74 single-stack, ~83 combined-stack).

Cursor generation, verify, and CI assemble gates cover packaging. This guide does not claim how Cursor loads `.mdc` files in a given IDE version.

## 4. Copilot deployment

**Source profiles:** `ekp-core` (foundation knowledge) or `ekp-php` (PHP stack knowledge via `includes: [cursor-php]`).

**Generated under** `dist/<profile>/copilot/`:

```
.github/copilot-instructions.md
.github/instructions/*.instructions.md   # domain files when knowledge justifies them
adapter-manifest.json
```

Always-on instructions have **no** `applyTo`. Path-specific `*.instructions.md` files are emitted only when the profile knowledge includes a mapped domain prefix. Examples:

- `ekp-core` includes `knowledge/testing/` → `testing.instructions.md`
- `ekp-php` also includes `knowledge/php/` → `testing.instructions.md` and `php.instructions.md` (`applyTo: "**/*.php"`)

Copilot **skills** are not generated.

**Copy:**

```
dist/ekp-php/copilot/.github/   →  <consumer-repo>/.github/
dist/ekp-core/copilot/.github/  →  <consumer-repo>/.github/
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
- six operational Cursor profile assemble gates
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
