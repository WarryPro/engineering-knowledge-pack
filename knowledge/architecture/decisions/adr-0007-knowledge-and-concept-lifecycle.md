# ADR-0007: Knowledge & Concept Lifecycle

## Status

Accepted

## Date

2026-08-07

## Context

All guides on `master` are implicitly **published**. There is no metadata for draft, deprecated, or retired content. As EKP grows beyond 20 guides, WIP documents risk being treated as canonical, and concept deprecation lacks a standard path.

EKP-AI15 proposed a lifecycle without heavy process. This ADR defines policy and the **minimal MVP implementation**.

## Decision

### Lifecycle states

```
draft → review → validated → published → deprecated → retired
```

| State | Adapter consumption (policy) | Profile eligibility (policy) |
|-------|------------------------------|------------------------------|
| draft | No | No |
| review | Preview local only | No |
| validated | Preview local | No |
| published | Yes | Yes, if listed |
| deprecated | Yes (future banner) | Yes with caution |
| retired | No | No |

### Default for existing content

Documents **without** `status` in frontmatter are treated as **`published`** by the validator. No mass-edit of existing 20 guides is required for MVP.

### Schema

Optional frontmatter field:

```yaml
status: draft | review | validated | published | deprecated | retired
```

Validated by `knowledge-frontmatter.schema.json` and `lifecycle_validate.py`.

### Future optional fields (not MVP)

Documented for later; **not required or enforced** in EKP-AI16:

- `deprecated_since: "0.4.0"`
- `superseded_by: knowledge/.../guide.md`

### Concept migration

| Action | Policy |
|--------|--------|
| Deprecate concept | Keep ID in guide; mark deprecated in body/CHANGELOG; min 1 minor release before removal |
| Remove concept | **Breaking** — major bump; ADR if wide impact |
| Rename ID | New ID + deprecate old; never recycle old ID |
| Move to another guide | Breaking; ADR + namespace owner update |

### Retirement

A guide may move to **retired** when:

1. Deprecated for ≥1 minor release,
2. No other guide `depends_on` it,
3. Profiles no longer list it,
4. CHANGELOG and ADR document retirement.

### MVP implementation scope (EKP-AI16)

**In scope:**

- Schema accepts optional `status`
- Validator rejects invalid `status` values
- Missing `status` ≡ `published` (compatibility)

**Out of scope (deferred):**

- Assemble excludes non-published guides automatically
- Warnings for deprecated concepts in profiles
- `deprecated_since` / `superseded_by` enforcement
- Automated retirement checks

## Rationale

- Frontmatter `status` reuses existing validation pipeline — no parallel registry.
- Default `published` preserves backward compatibility.
- Deferred assemble filtering avoids breaking current CI/profiles before deprecation is used in practice.

## Alternatives considered

### Separate lifecycle registry JSON

Rejected for MVP — duplicate source of truth.

### Directory-based draft (`knowledge/_draft/`)

Rejected — path churn on publish; complicates profiles.

### Require `status` on all guides immediately

Rejected — unnecessary churn; default handles compatibility.

## Consequences

### Positive

- Contributors can mark WIP explicitly in new guides
- Policy exists before scale pain

### Negative

- Until assemble filtering ships, draft on `master` would still bundle if listed in profile — **mitigation:** do not merge draft guides to `master`

### Compliance

- Reviewers verify `status` on new guides
- Deprecation/retirement follows [governance.md](../../../docs/governance.md)

## Related

- [governance.md](../../../docs/governance.md)
- [ADR-0006](adr-0006-versioning-and-compatibility.md)
- [knowledge-frontmatter.schema.json](../../../schema/knowledge-frontmatter.schema.json)
