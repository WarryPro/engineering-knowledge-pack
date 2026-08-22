# Folder Structure

This document describes the purpose of each top-level directory and how content flows between them.

```
/
├── README.md                  # Project overview and entry point
├── LICENSE                    # MIT license
├── CHANGELOG.md               # Version history
├── CONTRIBUTING.md            # Contribution entry point
├── CODE_OF_CONDUCT.md         # Community standards
├── .gitignore
│
├── docs/                      # Project meta-documentation
│   ├── vision.md
│   ├── architecture.md
│   ├── adapter-architecture.md
│   ├── deployment.md
│   ├── governance.md
│   ├── roadmap.md
│   ├── folder-structure.md    # This file
│   ├── style-guide.md
│   └── contribution-guide.md
│
├── schema/                    # JSON Schema contracts for validation
│   ├── knowledge-frontmatter.schema.json
│   └── profile.schema.json
│
├── knowledge/                 # Engineering knowledge (source of truth)
│   ├── engineering/
│   ├── architecture/
│   │   ├── decisions/         # Architecture decision records (ADRs)
│   │   └── checklists/        # Architecture review checklists
│   ├── php/
│   ├── symfony/
│   ├── flutter/
│   ├── typescript/
│   ├── frontend/
│   ├── nativescript/
│   ├── database/
│   ├── security/
│   ├── testing/
│   ├── performance/
│   ├── devops/
│   └── ai/
│
├── rules/                     # Tool-specific AI rules (derived from knowledge)
│   ├── cursor/
│   ├── copilot/
│   └── claude/
│
├── profiles/                  # Composed knowledge sets for specific contexts
│
├── templates/                 # Document templates for consistent authoring
│   ├── knowledge-document-template.md
│   ├── cursor-rule-template.md
│   ├── review-checklist-template.md
│   ├── decision-record-template.md
│   └── profile-template.yaml
│
├── examples/                  # Reference implementations and usage demonstrations
├── scripts/                   # Adapters, validators, and build tooling
│   ├── validate/
│   ├── adapters/
│   └── assemble/
│
└── dist/                      # Generated bundles (gitignored, created by assemble)
```

## Directory details

### `docs/`

Meta-documentation about the EKP project itself. This is **not** engineering knowledge—it explains how the repository works, how to contribute, and where things go.

Do not place engineering practices here. If it would help an engineer write better code, it belongs in `knowledge/`.

Note: `docs/architecture.md` describes the **repository** architecture. `knowledge/architecture/` contains **system design** knowledge.

### `schema/`

JSON Schema definitions for machine validation:

- `knowledge-frontmatter.schema.json` — required metadata fields for knowledge documents
- `profile.schema.json` — profile manifest structure

### `knowledge/`

The canonical source of engineering knowledge. Each domain has a `README.md` defining scope and boundaries.

| Directory | Scope |
|-----------|-------|
| `engineering/` | Language-agnostic practices: naming, error handling, logging, code organization |
| `architecture/` | System design: layering, boundaries, patterns, ADRs |
| `php/` | PHP language idioms and ecosystem conventions |
| `symfony/` | Symfony framework patterns and conventions |
| `flutter/` | Flutter/Dart mobile and UI development |
| `typescript/` | TypeScript language patterns and type system usage |
| `frontend/` | Frontend architecture, state management, accessibility |
| `nativescript/` | NativeScript native mobile architecture on TypeScript |
| `database/` | Schema design, migrations, queries, transactions |
| `security/` | Security principles and practices |
| `testing/` | Testing strategies, patterns, and tooling |
| `performance/` | Profiling, optimization, caching |
| `devops/` | CI/CD, infrastructure, deployment, observability |
| `ai/` | Using AI assistants responsibly in engineering workflows |

#### Domain boundary: `typescript/` vs `frontend/` vs `nativescript/`

| Topic | Domain |
|-------|--------|
| Type narrowing, generics, `strict` config | `typescript/` |
| React/Vue web component architecture, DOM/SSR | `frontend/` |
| NativeScript native UI, navigation, plugins, platforms | `nativescript/` |
| Shared types between API and UI | `typescript/` (type design) + link to UI domain |

When a document spans domains, place it in the domain of the primary concern and link to the other.

NativeScript-Vue (and similar UI frameworks under NativeScript) stays inside `nativescript/` — not a separate top-level domain.

#### Document types and locations

| Type | Location | Template |
|------|----------|----------|
| Guide | `knowledge/<domain>/<topic>.md` | `knowledge-document-template.md` |
| Decision record | `knowledge/architecture/decisions/adr-<number>-<topic>.md` | `decision-record-template.md` |

Use zero-padded four-digit numbers (e.g. `adr-0004-clean-code-position-in-knowledge-graph.md`). See [decisions/README.md](../knowledge/architecture/decisions/README.md).
| Review checklist | `knowledge/<domain>/checklists/<name>.md` | `review-checklist-template.md` |

Set `type: decision-record` or `type: checklist` in frontmatter where applicable.

### `rules/`

Scaffold directory for tool-specific rule layouts:

```
rules/
├── cursor/        # Cursor Rules (.mdc) — scaffold only
├── copilot/       # GitHub Copilot instructions — scaffold only
└── claude/        # Claude Skills — scaffold only
```

**`rules/` is not the primary bundle source.** Adapters generate deployable output into `dist/<profile>/` during assembly. Do not author rules directly without a corresponding knowledge document. Do not treat checked-in files under `rules/` as the final deployable artifact.

### `profiles/`

YAML manifests that compose knowledge documents for a specific context. Profiles reference **knowledge paths only**—adapters derive rules at build time.

```
profiles/
├── symfony-api.yaml
├── flutter-mobile.yaml
└── full-stack.yaml
```

See `templates/profile-template.yaml` and `schema/profile.schema.json`.

### `templates/`

Scaffolds for creating new documents. Copy the relevant template when adding content.

### `examples/`

Worked examples showing EKP in practice: sample profiles, adapter output, decision records, review checklists applied to realistic scenarios.

### `scripts/`

```
scripts/
├── validate/      # Document structure and link validation
├── adapters/      # Knowledge → tool-specific format transformers
└── assemble/      # Profile composition and bundle generation
```

Run validation: `py -3 scripts/validate/validate.py`

### `dist/`

Generated deployable bundles (**gitignored**). Created by `scripts/assemble/assemble.py`:

```
dist/
├── concept-index.json          # Generated by validate --generate-index
├── knowledge-graph.json
├── adapter-manifest.json
├── cursor-core/                # Example Cursor-only profile bundle
│   ├── assemble-manifest.json
│   ├── bundle-manifest.json
│   └── cursor/
│       └── *.mdc
├── ekp-php/                    # Stack multi-adapter (Cursor + Copilot; includes cursor-php)
│   ├── assemble-manifest.json
│   ├── bundle-manifest.json
│   ├── cursor/
│   └── copilot/.github/
├── ekp-typescript/             # Stack multi-adapter (Cursor + Copilot; includes cursor-typescript)
│   ├── assemble-manifest.json
│   ├── bundle-manifest.json
│   ├── cursor/
│   └── copilot/.github/
├── ekp-symfony/                # Stack multi-adapter (Cursor + Copilot; includes cursor-symfony)
│   ├── assemble-manifest.json
│   ├── bundle-manifest.json
│   ├── cursor/
│   └── copilot/.github/
└── ekp-core/                   # Multi-adapter pilot (Cursor + Copilot + Antigravity + Claude)
    ├── assemble-manifest.json
    ├── bundle-manifest.json
    ├── cursor/
    ├── copilot/.github/
    ├── antigravity/.agents/rules/
    └── claude/
        ├── CLAUDE.md
        └── .claude/skills/
```

Regenerate locally: `py -3 scripts/assemble/assemble.py --profile cursor-core --clean --verify`

## Content flow

```
Author writes knowledge document
        │
        ▼
  knowledge/<domain>/<topic>.md
        │
        ▼
     validate
        │
        ▼
   generate-index  →  dist/*.json (concept-index, knowledge-graph, adapter-manifest)
        │
        ▼
  adapter generation  →  dist/<profile>/<adapter>/
        │
        ▼
     assemble  →  dist/<profile>/bundle-manifest.json
                  dist/<profile>/assemble-manifest.json
                  dist/<profile>/<adapter>/adapter-manifest.json (non-Cursor)
        │
        ▼
  Deployed to consumer project (see docs/deployment.md)
```

**Note:** `rules/` is a scaffold directory. The authoritative generated output lives in `dist/`, which remains gitignored.

## Naming conventions

See [style-guide.md](style-guide.md) for file and document naming rules. At the directory level:

- Use **lowercase kebab-case** for all file and directory names
- Use **singular nouns** for document topics (`error-handling.md`, not `errors.md`)
- Domain directories use the **technology or concern name** directly (`php/`, not `php-knowledge/`)
