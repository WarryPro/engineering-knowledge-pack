# Adapters

Knowledge → tool-specific format transformers. One adapter per target tool.

## Implemented

- `cursor/` — knowledge → Cursor Rules (`.mdc`)
- `copilot/` — knowledge → GitHub Copilot instructions (AI30B pilot)
- `antigravity/` — knowledge → Antigravity workspace rules (AI30B pilot)

## Planned

- `claude/` — knowledge → Claude Skills format

Adapter dispatch is handled by `common/registry.py` (ADR-0009). Each implemented adapter registers `generate`, `verify`, and `build_manifest`. Claude remains unimplemented and fails explicitly if requested.

Each adapter follows the pipeline documented in `docs/adapter-architecture.md`.

## From profile to deployable bundle

End-to-end workflow:

```
1. Validate knowledge
        ↓
2. Generate indexes
        ↓
3. Assemble bundle
        ↓
4. Deploy to consumer project
```

### 1. Validate knowledge

```bash
py -3 scripts/validate/validate.py
```

Ensures knowledge documents, profiles, and graph integrity are valid before generation.

### 2. Generate indexes

```bash
py -3 scripts/validate/validate.py --generate-index
```

Writes machine-readable artifacts to `dist/`:

- `concept-index.json`
- `knowledge-graph.json`
- `adapter-manifest.json`

Adapters consume these indexes instead of parsing markdown at runtime.

### 3. Assemble bundle

Cursor-only operational profiles:

```bash
py -3 scripts/assemble/assemble.py --profile cursor-core --clean --verify
```

Multi-adapter pilot:

```bash
py -3 scripts/assemble/assemble.py --profile ekp-core --clean --verify
```

`ekp-core` writes:

```
dist/ekp-core/
├── assemble-manifest.json
├── bundle-manifest.json
├── cursor/
│   └── *.mdc
├── copilot/
│   ├── .github/copilot-instructions.md
│   ├── .github/instructions/testing.instructions.md
│   └── adapter-manifest.json
└── antigravity/
    ├── .agents/rules/*.md
    └── adapter-manifest.json
```

Cursor keeps `bundle-manifest.json` at the profile root. Copilot and Antigravity write `<adapter>/adapter-manifest.json`. Claude remains unimplemented.

Options:

- `--profile <name>` — required profile identifier
- `--clean` — remove previous bundle output before generation
- `--verify` — validate bundle integrity after assembly

### 4. Deploy

- Cursor: copy `dist/<profile>/cursor/*.mdc` to the consumer `.cursor/rules/`
- Copilot: copy `dist/<profile>/copilot/.github/` to the consumer repository root
- Antigravity: copy `dist/<profile>/antigravity/.agents/rules/` to the consumer `.agents/rules/`

EKP does not write into consumer tool directories during assembly — bundles are produced under `dist/` only.

Antigravity file generation does not prove activation. See the empirical check in `docs/adapter-architecture.md`.

## Package layout

```
scripts/adapters/
├── common/          # Shared extraction, selection, profile loading, registry
├── cursor/          # Cursor .mdc generator
├── copilot/         # Copilot instructions generator (pilot)
├── antigravity/     # Antigravity rules generator (pilot)
└── tests/
```

## Running adapter tests

```bash
py -3 -m unittest discover -s scripts/adapters/tests -v
py -3 -m unittest discover -s scripts/assemble/tests -v
```

## Direct Cursor generation (without manifest)

For development only:

```bash
py -3 scripts/adapters/cursor/generate.py --profile cursor-core
```

Prefer `assemble.py` for production bundles.
