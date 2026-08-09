# ADR-0008: Profile Composition (`includes`)

## Status

Accepted

## Date

2026-08-09

## Context

EKP reached **six profiles** in v0.3.2. Five stack profiles (`cursor-php`, `cursor-symfony`, `cursor-typescript`, `cursor-frontend`, `cursor-devops`) each duplicated the same six-path L0 subset already defined in `cursor-core`:

- `engineering-principles.md`
- `ai-assisted-development.md`
- `refactoring.md`
- `testing.md`
- `error-handling.md`
- `layering-and-boundaries.md`

Governance (EKP-AI16) deferred profile composition until the **6th profile** threshold. EKP-AI23 recommended resolving duplication before adding a 7th profile (e.g. Flutter).

Alternatives considered:

- Continue explicit duplication (low effort, rising drift risk)
- `profile.extends` with override semantics (OOP inheritance — wrong fit for path lists)
- Generalized composition framework (over-engineered for current scale)

## Decision

### Single composition mechanism: `includes`

Profiles may declare:

```yaml
name: cursor-php
includes:
  - cursor-core
knowledge:
  - knowledge/php/php-fundamentals.md
```

### Profiles do NOT support `extends`

`extends` is **intentionally unsupported**. Profile composition is **path inclusion**, not inheritance. There is no override model for `adapter`, `filters`, or `outputs`.

### Resolution semantics

Given a profile with `includes` and local `knowledge`:

1. **Resolve `includes` recursively** (depth-first, in list order).
2. **Detect circular includes** (e.g. `A → B → A`) — validation error.
3. **Merge paths**: all included paths first, then local paths.
4. **Deduplicate** preserving **first occurrence** order.
5. **Multiple includes** allowed; each resolved fully before the next.
6. **Nested includes** supported (e.g. `A → B → C`).
7. **Unknown profile names** in `includes` — validation error.

### Local profile authority (MVP)

Included profiles contribute **`knowledge` paths only**.

The **root profile** remains authoritative for:

- `name`
- `description`
- `filters`
- `adapter`
- `outputs`

### `cursor-core` immutability

`profiles/cursor-core.yaml` is **not modified** by this ADR. Stack profiles **include** `cursor-core` by reference; assembled rule counts must remain identical to pre-composition behavior.

### Knowledge graph

`includes` affects **profile assembly only**. It does **not** change knowledge `depends_on` / `related` or `graph-rules.yaml`.

## Rationale

- **Deterministic** — same profile graph → same flattened path list → same rule output.
- **Simple** — one mechanism, no inheritance edge cases.
- **Frozen core preserved** — `cursor-core` stays the canonical L0 product profile.
- **Scalable** — 7th+ profiles add only stack-specific paths locally.

## Alternatives considered

### Continue explicit duplication

Rejected for EKP-AI24 — threshold met; drift cost now exceeds implementation cost.

### `profile.extends`

Rejected — implies override semantics; conflicts with frozen `cursor-core` policy and knowledge frontmatter `extends` (different meaning).

### Merge `adapter` / `filters` from includes

Rejected for MVP — local profile must control adapter output; included profiles are path fragments only.

## Consequences

### Positive

- Five stack profiles shrink to `includes` + 1–2 local paths
- Single source for L0 path list (`cursor-core`)
- Validator catches cycles and unknown includes before assemble

### Negative

- Resolver must be shared by validator and Cursor adapter
- Profile review must understand resolution order

### Compliance

- `schema/profile.schema.json` documents optional `includes`
- `profile_validate.py` validates includes graph
- `scripts/adapters/common/profile_resolve.py` implements resolution
- Assembled rule counts for all six profiles unchanged vs v0.3.2

## Related

- [governance.md](../../../docs/governance.md)
- [architecture.md](../../../docs/architecture.md)
- [ADR-0005](adr-0005-technology-knowledge-evolution.md)
- [ADR-0006](adr-0006-versioning-and-compatibility.md)
