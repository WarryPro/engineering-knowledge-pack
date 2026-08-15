# ADR-0009: Adapter Dispatch Architecture

## Status

Accepted

## Date

2026-08-11

## Context

EKP v0.3.3 introduced profile composition via `includes` (ADR-0008). Assembly and adapter generation remain **Cursor-only at runtime** despite schema support for multiple adapter targets.

Prior to this ADR:

- `assemble.py` imported `cursor.generate` directly and hardcoded `dist/<profile>/cursor/`
- `adapter.target` and `outputs` were validated in profiles but **not read** at assembly time
- Concept selection and `GeneratedRule` normalization lived inside `cursor/generate.py`
- Verification logic was Cursor-specific but lived in `assemble.py`

Phase 5 requires Copilot, Antigravity, and Claude adapters without another assembly rewrite. EKP-AI27 recommended extracting shared selection/normalization and introducing an adapter registry before implementing non-Cursor adapters.

## Decision

### Adapter dispatch via registry

`assemble.py` orchestrates adapters through `common/registry.py`. Each adapter registers:

- `generate(profile_name, output_dir, profile, repo_root)`
- `verify(bundle_dir)`
- `build_manifest(profile_name, adapter_output_dir)`

Only **Cursor** is implemented in this milestone. **Copilot**, **Antigravity**, and **Claude** are registered as known future adapters but raise `AdapterNotImplementedError` if requested.

### Pipeline

```text
Profile YAML
  → profile_resolve (includes)
  → profile_loader (outputs, adapter_priorities)
  → per adapter:
        extract (common/extract.py)
        → selection (common/selection.py)
        → normalization (cursor/normalize.py → GeneratedRule)
        → adapter writer (cursor/mdc_writer.py)
        → adapter manifest (cursor/manifest.py)
        → adapter verify (cursor/verify.py)
```

### In-memory normalization only

`GeneratedRule` (`common/models.py`) is the shared intermediate representation. Normalization is **in-memory** between extraction and adapter writers.

Do **not** persist `dist/normalized-rules.json` or any serialized IR artifact.

### `outputs` is canonical

Profiles declare requested adapters with:

```yaml
outputs:
  - cursor
```

`adapter.target` remains in the schema as a **legacy fallback** when `outputs` is absent. New profiles should use `outputs` only. Both fields are validated; neither is removed in this milestone.

### Cursor backward compatibility

The following invariants are mandatory:

- Output path: `dist/<profile>/cursor/*.mdc`
- Manifest path: `dist/<profile>/bundle-manifest.json` with `"adapter": "cursor"`
- Rule counts unchanged for all six operational profiles
- `.mdc` format, naming, frontmatter, and orchestrator behavior unchanged

### Adapter-owned serialization and verification

Cursor-specific concerns (`.mdc`, `alwaysApply`, orchestrator filename, manifest scanning) belong under `scripts/adapters/cursor/`. `assemble.py` must not contain format-specific verification logic.

### Manifest layout

- **Cursor** keeps the legacy-compatible profile-root file `dist/<profile>/bundle-manifest.json`. It is not moved into `cursor/`.
- **Non-Cursor adapters** write `dist/<profile>/<adapter>/adapter-manifest.json`.
- **Profile assembly** writes deterministic `dist/<profile>/assemble-manifest.json` listing adapters, output directories, and manifest paths. It does not include timestamps.
- `assemble.py` resolves all requested `outputs` before generation. An unimplemented adapter fails explicitly; there is no Cursor fallback and no overwrite of the Cursor bundle manifest.

### Knowledge remains adapter-neutral

Knowledge documents are not modified for adapter dispatch. Tool-specific hints remain in optional `### Cursor` / `### Claude` sections; adapters decide how to consume them.

### Deferred adapters

Copilot, Antigravity, and Claude are **intentionally not implemented** in this milestone. Antigravity is included in the registry design because it is a confirmed future EKP consumer.

## Rationale

- **Registry dispatch** allows adding adapters by implementing writer + verify modules without rewriting assembly or extraction.
- **Shared selection** prevents duplicating manifest filtering across adapters.
- **`GeneratedRule` IR** is sufficient; a persisted normalized JSON file adds maintenance cost without benefit at current scale.
- **`outputs` canonical** aligns with `templates/profile-template.yaml` and Phase 5 roadmap; `adapter.target` preserved for compatibility.
- **Cursor regression gate** ensures this refactor is architectural, not behavioral.

## Alternatives considered

### Serialized normalized rules (`dist/normalized-rules.json`)

Rejected — extra artifact, versioning burden, no consumer yet.

### Implement Copilot in the same milestone

Rejected — violates EKP-AI28 scope; dispatch must land first.

### Remove `adapter.target` from schema

Rejected — breaking change for existing six profiles; legacy fallback is sufficient.

## Consequences

### Positive

- Clear extension point for Copilot, Antigravity, Claude
- Shared selection logic in one module
- Cursor verification isolated and testable

### Negative

- Slight indirection in assemble path
- Cursor consumers must ignore `assemble-manifest.json` (additive file at profile root)

### Compliance

- Cursor rule counts must match pre-refactor baselines in CI
- `cursor-core.yaml` and `graph-rules.yaml` must remain unchanged

## Related

- [ADR-0008](adr-0008-profile-composition-includes.md) — Profile `includes`
- [ADR-0006](adr-0006-versioning-and-compatibility.md) — Versioning
- [adapter-architecture.md](../../../docs/adapter-architecture.md)
