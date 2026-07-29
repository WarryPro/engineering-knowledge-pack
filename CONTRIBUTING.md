# Contributing

Thank you for your interest in Engineering Knowledge Pack (EKP).

## Before you start

1. Read [`docs/vision.md`](docs/vision.md) — understand the project's purpose.
2. Read [`docs/architecture.md`](docs/architecture.md) — understand where content belongs.
3. Read [`docs/contribution-guide.md`](docs/contribution-guide.md) — follow the knowledge authoring workflow.
4. Read [`docs/style-guide.md`](docs/style-guide.md) — follow naming and formatting conventions.
5. Read [`DEVELOPMENT.md`](DEVELOPMENT.md) — run validation and the assemble pipeline locally.

## Quick rules

- **Knowledge goes in `knowledge/`** — tool-agnostic, human-readable markdown.
- **Do not commit generated bundles** — output lives in `dist/` (gitignored); produce it with `assemble`.
- **`rules/` is a scaffold** — deployable Cursor rules are generated into `dist/<profile>/cursor/`.
- **No filler content** — every document must convey actionable engineering guidance backed by reasoning.
- **One concern per document** — keep documents focused and link related topics.

## How to contribute

1. Open an issue to discuss significant additions or structural changes.
2. Fork the repository and create a branch from `main` or `staging` (follow your team's integration branch).
3. Write or update content following the style guide and relevant template.
4. Run validation locally (see [`DEVELOPMENT.md`](DEVELOPMENT.md)).
5. Open a pull request with a clear description of what changed and why.

## Code of conduct

All contributors are expected to follow our [Code of Conduct](CODE_OF_CONDUCT.md).

## Questions

Open a GitHub issue with the `question` label if something is unclear. Prefer discussing structural changes before investing significant effort.
