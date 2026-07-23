# Folder Structure

This document describes the purpose of each top-level directory and how content flows between them.

```
/
├── README.md                  # Project overview and entry point
├── LICENSE                    # MIT license
├── CHANGELOG.md               # Version history
├── CONTRIBUTING.md            # Contribution entry point
├── CODE_OF_CONDUCT.md         # Community standards
│
├── docs/                      # Project meta-documentation
│   ├── vision.md
│   ├── architecture.md
│   ├── roadmap.md
│   ├── folder-structure.md    # This file
│   ├── style-guide.md
│   └── contribution-guide.md
│
├── knowledge/                 # Engineering knowledge (source of truth)
│   ├── engineering/           # Cross-cutting engineering practices
│   ├── architecture/          # System design and architectural patterns
│   ├── php/
│   ├── symfony/
│   ├── flutter/
│   ├── typescript/
│   ├── frontend/
│   ├── database/
│   ├── security/
│   ├── testing/
│   ├── performance/
│   ├── devops/
│   └── ai/                    # Guidance on using AI in engineering workflows
│
├── rules/                     # Tool-specific AI rules (derived from knowledge)
├── profiles/                  # Composed knowledge + rule sets for specific contexts
│
├── templates/                 # Document templates for consistent authoring
│   ├── knowledge-document-template.md
│   ├── cursor-rule-template.md
│   ├── review-checklist-template.md
│   └── decision-record-template.md
│
├── examples/                  # Reference implementations and usage demonstrations
└── scripts/                   # Adapters, validators, and build tooling
```

## Directory details

### `docs/`

Meta-documentation about the EKP project itself. This is **not** engineering knowledge—it explains how the repository works, how to contribute, and where things go.

Do not place engineering practices here. If it would help an engineer write better code, it belongs in `knowledge/`.

### `knowledge/`

The canonical source of engineering knowledge. Organized by domain:

| Directory | Scope |
|-----------|-------|
| `engineering/` | Language-agnostic practices: naming, error handling, logging, code organization |
| `architecture/` | System design: layering, boundaries, patterns, ADRs |
| `php/` | PHP language idioms and ecosystem conventions |
| `symfony/` | Symfony framework patterns and conventions |
| `flutter/` | Flutter/Dart mobile and UI development |
| `typescript/` | TypeScript language patterns and type system usage |
| `frontend/` | Frontend architecture, state management, accessibility |
| `database/` | Schema design, migrations, queries, transactions |
| `security/` | Security principles and practices |
| `testing/` | Testing strategies, patterns, and tooling |
| `performance/` | Profiling, optimization, caching |
| `devops/` | CI/CD, infrastructure, deployment, observability |
| `ai/` | Using AI assistants responsibly in engineering workflows |

Each subdirectory will contain individual markdown files—one concern per document. Subdirectories may gain nested folders as content grows (e.g., `knowledge/symfony/services/`).

### `rules/`

Tool-specific rule files generated from or curated against knowledge documents. Expected subdirectories (created in Phase 5):

```
rules/
├── cursor/        # Cursor Rules (.mdc)
├── copilot/       # GitHub Copilot instructions
└── claude/        # Claude Skills
```

Do not author rules directly without a corresponding knowledge document.

### `profiles/`

YAML or JSON manifests that compose knowledge documents and rules for a specific context. A profile answers: "What engineering context does this team/project need?"

```
profiles/
├── symfony-api.yaml
├── flutter-mobile.yaml
└── full-stack.yaml
```

### `templates/`

Scaffolds for creating new documents. Copy the relevant template when adding content. Templates define required sections and metadata fields.

### `examples/`

Worked examples showing EKP in practice: sample profiles, adapter output, decision records, review checklists applied to realistic scenarios.

### `scripts/`

Build and transformation tooling:

```
scripts/
├── validate/      # Document structure and link validation
├── adapters/      # Knowledge → tool-specific format transformers
└── assemble/      # Profile composition and bundle generation
```

## Content flow

```
Author writes knowledge document
        │
        ▼
  knowledge/<domain>/<topic>.md
        │
        ├──► Referenced by profile
        │
        └──► Transformed by adapter
                    │
                    ▼
              rules/<tool>/<rule>.mdc
                    │
                    ▼
              Deployed via profile bundle
```

## Naming conventions

See [style-guide.md](style-guide.md) for file and document naming rules. At the directory level:

- Use **lowercase kebab-case** for all file and directory names
- Use **singular nouns** for document topics (`error-handling.md`, not `errors.md`)
- Domain directories use the **technology or concern name** directly (`php/`, not `php-knowledge/`)
