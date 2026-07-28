# Assemble

Profile composition and deployable bundle generation.

## Usage

```bash
py -3 scripts/assemble/assemble.py --profile cursor-core
py -3 scripts/assemble/assemble.py --profile cursor-core --clean --verify
```

## Pipeline

1. Load profile from `profiles/<name>.yaml`
2. Verify `dist/concept-index.json`, `dist/knowledge-graph.json`, and `dist/adapter-manifest.json` exist
3. Invoke the Cursor adapter generator
4. Write `dist/<profile>/cursor/*.mdc` and `dist/<profile>/bundle-manifest.json`

If indexes are missing, run:

```bash
py -3 scripts/validate/validate.py --generate-index
```

See `scripts/adapters/README.md` for the full validate → generate-index → assemble → deploy workflow.
