# Adapters

Knowledge → tool-specific format transformers. One adapter per target tool.

## Implemented

- `cursor/` — knowledge → Cursor Rules (`.mdc`)

## Planned

- `copilot/` — knowledge → GitHub Copilot instructions
- `antigravity/` — knowledge → Antigravity rules (format TBD)
- `claude/` — knowledge → Claude Skills format

Adapter dispatch is handled by `common/registry.py` (ADR-0009). Only Cursor is registered; future adapters implement `generate`, `verify`, and `build_manifest` without changing `assemble.py`.

Each adapter follows the pipeline documented in `docs/adapter-architecture.md`.

## From profile to deployable bundle

End-to-end workflow for producing a Cursor rule bundle:

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

```bash
py -3 scripts/assemble/assemble.py --profile cursor-core --clean --verify
```

Reads `profiles/cursor-core.yaml`, invokes the Cursor adapter, and writes:

```
dist/cursor-core/
├── cursor/
│   ├── 00-ekp-orchestrator.mdc
│   ├── 01-ekp-foundation.mdc
│   ├── ...
│   └── concept-ekp-*.mdc
└── bundle-manifest.json
```

Options:

- `--profile <name>` — required profile identifier
- `--clean` — remove previous bundle output before generation
- `--verify` — validate bundle integrity after assembly

### 4. Deploy

Copy `dist/<profile>/cursor/*.mdc` to the consumer project's `.cursor/rules/` directory.

EKP does not write to `.cursor/rules/` during assembly — bundles are produced under `dist/` only.

## Package layout

```
scripts/adapters/
├── common/          # Shared extraction, selection, profile loading, registry
├── cursor/          # Cursor .mdc generator (normalize, manifest, verify)
└── tests/

scripts/assemble/
├── assemble.py      # Profile → bundle orchestrator
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

Prefer `assemble.py` for production bundles — it verifies indexes and writes `bundle-manifest.json`.
