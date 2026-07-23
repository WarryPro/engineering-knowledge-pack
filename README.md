# Engineering Knowledge Pack (EKP)

An open-source engineering knowledge base that captures how senior software engineers design, build, review, and maintain software.

EKP is the **source of truth** for engineering practices. It is intentionally independent of any AI assistant, IDE, or vendor tooling. Tool-specific formats—Cursor Rules, Claude Skills, GitHub Copilot instructions—are derived from this knowledge through adapters, not authored here directly.

## What this repository contains

| Area | Purpose |
|------|---------|
| [`knowledge/`](knowledge/) | Tool-agnostic engineering knowledge (patterns, practices, guidelines) |
| [`rules/`](rules/) | Generated or curated rules for AI assistants (populated in later phases) |
| [`profiles/`](profiles/) | Composed sets of knowledge and rules for specific contexts (team, stack, role) |
| [`templates/`](templates/) | Document templates for knowledge, rules, reviews, and decisions |
| [`docs/`](docs/) | Project vision, architecture, roadmap, and contribution guidance |
| [`examples/`](examples/) | Reference implementations and usage examples |
| [`scripts/`](scripts/) | Build and transformation scripts for adapters |

## Getting started

1. Read [`docs/vision.md`](docs/vision.md) to understand why EKP exists.
2. Read [`docs/architecture.md`](docs/architecture.md) to understand how the repository is organized.
3. Read [`docs/contribution-guide.md`](docs/contribution-guide.md) before adding or changing content.

## Status

This repository is in **Phase 1: Foundation**. Knowledge domains and AI adapters are not yet populated. See [`docs/roadmap.md`](docs/roadmap.md) for the development plan.

## License

MIT — see [LICENSE](LICENSE).
