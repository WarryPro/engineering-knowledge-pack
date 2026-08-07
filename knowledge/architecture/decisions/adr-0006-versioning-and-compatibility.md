# ADR-0006: Versioning & Compatibility

## Status

Accepted

## Date

2026-08-07

## Context

EKP uses repository SemVer tags (`v0.1.0`, `v0.2.0`, `v0.3.0`) while internal components (validator “v2.3”, adapters, schemas) evolve on independent cadences. Consumers assemble profiles from knowledge at a given tag; generated `dist/` is not committed.

Without explicit compatibility rules, contributors may:

- break concept IDs without migration,
- change profile paths silently,
- change adapter output layout without notice,
- or conflate patch doc fixes with breaking knowledge changes.

## Decision

### Repository SemVer (0.x until 1.0.0)

| Bump | Criteria |
|------|----------|
| **PATCH** | Wording, typos, non-semantic clarifications, CI/docs-only, no new concept IDs |
| **MINOR** | New guide, namespace, profile, concepts, graph exception, technology vertical |
| **MAJOR** | Concept removal/rename, schema breaking change, adapter output breaking change, `cursor-core` change, retirement of deprecated contracts |

`1.0.0` remains a future gate (governance complete, multiple stacks, lifecycle proven) — not defined here.

### Knowledge compatibility

- **Concept IDs are stable contracts** once published on `master`.
- Rename/remove = **breaking**; requires deprecation period and migration mapping (ADR-0007).
- New concepts in existing guides = **minor**.
- Semantic change must not reuse an existing ID.

### Profile compatibility

- Profiles are versioned by **repository release tag**, not independent profile SemVer.
- Consumers pin: checkout tag + `assemble --profile <name>`.
- Removing a knowledge path from a profile = compatibility-affecting **minor** change (document in CHANGELOG).
- **`cursor-core.yaml`** changes require ADR + explicit governance approval (treated as **major**).

### Adapter compatibility

- Adapters transform knowledge + profile → tool format (Cursor `.mdc` today).
- Breaking adapter change: filename convention, orchestrator slot, or extraction rules that change consumer-visible layout without profile/knowledge change.
- Document adapter-impacting changes in CHANGELOG; semver for adapter package is **future work**.

### Generated artifacts

- `dist/` is **derived**, gitignored, regenerated on every assemble/CI run.
- Not versioned in git; rule counts documented per release in CHANGELOG/README.

### Schema compatibility

- Additive schema fields = minor (if optional).
- New **required** frontmatter fields = breaking unless default behavior preserves all existing documents (see `status` in ADR-0007).

## Rationale

- Single repo tag is the consumer pin point — simple for small teams.
- Separating knowledge, profile, and adapter contracts prevents Cursor-specific leakage into knowledge while allowing adapter fixes.
- Explicit `cursor-core` major policy protects the foundation bundle.

## Alternatives considered

### Independent SemVer per profile

Rejected for MVP — overhead without multiple external consumers pinning profiles separately.

### No SemVer (calendar versioning)

Rejected — project already uses SemVer; consumers expect 0.x growth semantics.

### Version generated bundles

Rejected — generated output is ephemeral; source tag is sufficient.

## Consequences

### Positive

- Clear release gate expectations (patch vs minor vs major)
- Concept ID stability explicit

### Negative

- Profile duplication until `includes` may cause rule-count drift between releases (documented, not versioned separately)

### Compliance

- Release manager applies bump tier at CHANGELOG cut (human decision)
- `git diff vX..HEAD -- profiles/cursor-core.yaml` must be empty unless major release approved

## Related

- [governance.md](../../../docs/governance.md)
- [CHANGELOG.md](../../../CHANGELOG.md)
- [ADR-0007](adr-0007-knowledge-and-concept-lifecycle.md)
