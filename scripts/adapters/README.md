# Adapters

Knowledge → tool-specific format transformers. One adapter per target tool.

Planned adapters (Phase 5):

- `cursor/` — knowledge → Cursor Rules (`.mdc`)
- `copilot/` — knowledge → GitHub Copilot instructions
- `claude/` — knowledge → Claude Skills format

Each adapter follows the pipeline documented in `docs/architecture.md`.
