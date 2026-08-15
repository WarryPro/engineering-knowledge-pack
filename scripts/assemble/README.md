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
3. Resolve profile `outputs` and fail if any adapter is unimplemented
4. Invoke each implemented adapter generator
5. Write Cursor `dist/<profile>/cursor/*.mdc` and `dist/<profile>/bundle-manifest.json`
6. Write `dist/<profile>/assemble-manifest.json`

Non-Cursor adapters (not implemented yet) will write `dist/<profile>/<adapter>/adapter-manifest.json`. Copilot, Antigravity, and Claude fail explicitly if requested.

If indexes are missing, run:

```bash
py -3 scripts/validate/validate.py --generate-index
```

See `scripts/adapters/README.md` for the full validate → generate-index → assemble → deploy workflow.
