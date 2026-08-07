# EKP Governance

Authoritative governance entry point for the Engineering Knowledge Pack.  
Lightweight rules for a small team — protect architecture without bureaucracy.

See also: [contribution-guide.md](contribution-guide.md), [DEVELOPMENT.md](../DEVELOPMENT.md), [architecture.md](architecture.md).

---

## Governance principles

1. **Protect meaning, not paperwork** — rules prevent semantic drift, not velocity.
2. **Stable IDs, explicit change** — published concept IDs are contracts.
3. **Downward dependencies only** — Foundation never depends on technology.
4. **Apply, don't redefine** — tech guides cite L0; duplication is a defect.
5. **Profiles are products** — each profile serves a distinct audience with an owner.
6. **Adapters are derived** — canonical knowledge stays tool-agnostic.
7. **Automate mechanical checks** — humans judge semantics.
8. **Proportional ADRs** — record high blast-radius decisions only.
9. **Small-team defaults** — one domain owner can approve domain changes.
10. **`cursor-core` is constitution** — unchanged without explicit governance approval.

---

## Knowledge lifecycle

| State | Meaning | Adapters | Profiles | On `master` |
|-------|---------|----------|----------|-------------|
| **draft** | Work in progress | No (default) | No | No |
| **review** | PR open; checklist in progress | Preview local | No | No |
| **validated** | Passes validator; awaiting merge | Preview | No | Optional on `staging` |
| **published** | Canonical | Yes | Yes, if listed | Yes |
| **deprecated** | Superseded; still linked | Yes (banner later) | Yes with caution | Yes |
| **retired** | Removed from active graph | No | No | Archived / removed |

**Compatibility:** Guides without `status` in frontmatter are treated as **`published`** (validator default). No mass-edit required for existing guides.

### Transitions

| From → To | Who | Requirements |
|-----------|-----|----------------|
| draft → review | Author | PR opened |
| review → validated | Author + CI | `validate.py` PASS |
| validated → published | Domain owner (+ platform if graph/ns) | Merge to `master` via `staging`; DoD complete |
| published → deprecated | Domain owner; ADR if concepts affected | `superseded_by` documented; CHANGELOG |
| deprecated → retired | Platform owner | No incoming `depends_on`; ≥1 minor release deprecated |

**MVP note:** Automated exclusion of non-published guides from assemble is **not** implemented yet (see ADR-0007).

---

## Concept governance

| Rule | Detail |
|------|--------|
| One owner | Each `EKP-XX##` has exactly one owning guide |
| Unique IDs | No duplicate concept IDs across documents |
| No recycling | Retired IDs are never reused |
| Rename | **Breaking** — new ID + deprecate old |
| Split | New IDs; deprecate old with mapping |
| Merge | Deprecate merged IDs; ADR if published |
| Move between guides | **Breaking** — namespace owner change + ADR |
| Semantic change | Cannot silently reuse an existing ID |

### Breaking knowledge changes

- Remove or rename concept ID
- Remove guide from profile without deprecation period
- Change `depends_on` to forbidden direction
- Material adapter output contract change

Non-breaking: typos, clarifications, new concepts, new guides, new profiles.

---

## Namespace governance

**Model:** one namespace prefix → one owner guide in `schema/concept-namespaces.json`.

| Rule | Detail |
|------|--------|
| Reserve before authoring | Registry entry before first concept ID in repo |
| Never rename | Existing prefixes are permanent |
| Never reuse | Retired prefixes stay retired |
| Allocation | Platform owner approves; contributor proposes via issue |
| Collisions | Automated validation; human resolves ambiguity |

### Allocated prefixes (do not reassign)

| Prefix | Domain | Notes |
|--------|--------|-------|
| EKP-P, CC, SL, DP, RF, EH, LO | engineering | |
| EKP-TS | testing | **Not** TypeScript |
| EKP-LB, AD, MC, AP, IN | architecture | |
| EKP-AI | ai | |
| EKP-SF | security | **Not** Symfony |
| EKP-PM | performance | |
| EKP-DB | database | |
| EKP-PH | php | |
| EKP-SY | symfony | |
| EKP-TY | typescript | |
| EKP-FE | frontend | |

Future namespaces (DevOps, Flutter, etc.) are requested at implementation time — not bulk-reserved in advance.

---

## Profile governance

| Rule | Detail |
|------|--------|
| Audience | Distinct stack or role required |
| Composition | Explicit `knowledge:` path list — no hidden inheritance |
| Owner | Domain owner for stack profiles |
| Verification | `assemble --verify` required; CI for all operational profiles |
| Documentation | Expected rule count band documented in profile or release notes |
| **`cursor-core`** | **Frozen** at 65 rules — change only with ADR + explicit approval |

### Profile creation checklist

1. Justify audience vs existing profiles  
2. List knowledge paths explicitly  
3. Run assemble `--verify`  
4. Add CI assemble step  
5. Update README / DEVELOPMENT  
6. CHANGELOG entry  

### Deferred: `includes` / `extends`

Profile composition fragments remain **deferred** until:

- **6th profile**, OR  
- documented **L0 drift** between profiles, OR  
- **>15% duplicate-path errors** in profile review  

Until then, duplicate the L0 subset explicitly (as `cursor-php`, `cursor-symfony`, etc. do today).

---

## Adapter contract

```
Knowledge (canonical markdown)
    ↓ selected by
Profile (YAML paths + filters)
    ↓ transformed by
Adapter (e.g. Cursor → .mdc)
    ↓ assembled into
Generated artifact (dist/<profile>/ — gitignored)
```

| Layer | May change independently | Versioned |
|-------|--------------------------|-----------|
| Knowledge | Yes (SemVer repo) | Via repo tag |
| Profile | Yes | Via repo tag |
| Adapter | Yes (adapter semver future) | Documented in CHANGELOG |
| Generated | Always regenerated | Not in git |

**Prohibited in knowledge:** Cursor `alwaysApply`, Copilot directives, tool-specific globs. Those belong in adapters/generated output only.

---

## Graph governance

### Layer model (preserved)

```
L0 Foundation
  ↑ depends_on
L1 Language (php, typescript, …)
  ↑
L2 Framework / Frontend (symfony, frontend, …)
  ↑
L3 Ops (devops — when published)
```

| Allowed | Forbidden |
|---------|-----------|
| L1 → L0 | L0 → technology |
| L2 → L1 + L0 | L1 → L2 |
| L3 → L0 (+ careful `related`) | L2 ↔ L2 cross-stack `depends_on` |

### `depends_on` vs `related`

- **`depends_on`** — prerequisite; creates graph edge  
- **`related`** — citation, escalation, peer awareness; no prerequisite

### Depth limits (`schema/graph-rules.yaml`)

- `warn_at: 3`  
- `error_at: 4`  

Target tech chain: **L2 → L1 → L0** (depth 2 edges from leaf).

### Documented exceptions (V2 policy)

| Source | Allowed dependency |
|--------|-------------------|
| design-patterns | solid |
| integration-patterns | layering-and-boundaries |
| symfony-architecture | php-fundamentals |
| frontend-architecture | typescript-fundamentals |

New exceptions: platform owner approval; ADR if precedent-setting. No `technology` validator role in MVP.

---

## Human review model

Use [knowledge-review-checklist.md](../templates/knowledge-review-checklist.md) on knowledge PRs.

| # | Question | Automatable? |
|---|----------|--------------|
| 1 | Concept already exists? | Partial (ID uniqueness) |
| 2 | New concept vs L0 application? | Human |
| 3 | Belongs in Foundation? | Human |
| 4 | Graph depth justified? | Partial (depth rules) |
| 5 | Duplicates another guide? | Human |
| 6 | Tech leaking into Foundation? | Human |
| 7 | Examples = decisions not tutorials? | Human |
| 8 | `related` / `depends_on` correct? | Partial (graph validator) |
| 9 | Profile scope justified? | Human |
| 10 | CHANGELOG required? | Human |

**Never automate:** semantic duplication, tutorial vs decision, profile audience judgment, release/tag creation.

---

## Release policy (0.x SemVer)

| Bump | Typical contents |
|------|------------------|
| **Patch** | Wording, typos, non-semantic docs, CI-only |
| **Minor** | New guide, namespace, profile, concepts, graph exception, tech vertical |
| **Major** | Concept removal/rename, schema breaking, adapter output breaking, `cursor-core` change, retired contracts |

Generated rule counts are documented in CHANGELOG — not independently versioned.

**Release remains human-approved:** staging → gate → CHANGELOG cut → merge `master` → annotated tag → GitHub Release.

---

## Contributor workflow

```
Issue/proposal (when required)
    ↓
Authoring (branch from staging)
    ↓
validate.py + assemble --verify (affected profiles)
    ↓
PR → staging + checklist + reviewers
    ↓
CI green
    ↓
Merge staging
    ↓
Release gate (human)
    ↓
CHANGELOG cut → merge master → tag → GitHub Release
```

### When to open an issue first

| Change | Issue? |
|--------|--------|
| Typo | No |
| New guide in existing domain | Optional |
| New domain / namespace / profile | **Yes** |
| Graph exception (new pattern) | **Yes** + ADR |

---

## ADR policy

| Event | ADR required? |
|-------|----------------|
| New namespace only | No (registry PR) |
| New domain directory | **Yes** |
| New profile | No (unless new L0 subset) |
| Graph exception (new pattern) | **Yes** |
| Graph exception (same L2→L1 pattern) | No if covered by ADR-0005 |
| Schema breaking | **Yes** |
| Adapter contract breaking | **Yes** |
| Deprecate published guide | **Yes** |
| Change `cursor-core` | **Yes** + explicit approval |

Index: [architecture/decisions/README.md](../knowledge/architecture/decisions/README.md).

---

## Ownership model

| Zone | Owner role |
|------|------------|
| `knowledge/<domain>/` | Domain owner |
| `profiles/` | Platform + domain owner for stack profiles |
| `schema/`, `scripts/validate/` | Platform owner |
| `profiles/cursor-core.yaml` | Foundation steward + platform |
| `docs/governance.md` | Platform owner |

Assign GitHub `CODEOWNERS` entries when maintainer roster is defined (see `.github/CODEOWNERS`).

---

## Automation (current vs planned)

**Enforced today:** namespace format, duplicate IDs, graph direction/depth, broken paths, profile paths, assemble verify, README index warnings.

**Planned (post-MVP):** deprecated concept in profile warning, profile path deduplication, `cursor-core` ⊆ profile L0 consistency.

**Human only:** duplication of meaning, ADR necessity, release version selection.

---

## Related ADRs

- [ADR-0005](../knowledge/architecture/decisions/adr-0005-technology-knowledge-evolution.md) — Technology knowledge evolution  
- [ADR-0006](../knowledge/architecture/decisions/adr-0006-versioning-and-compatibility.md) — Versioning & compatibility  
- [ADR-0007](../knowledge/architecture/decisions/adr-0007-knowledge-and-concept-lifecycle.md) — Knowledge & concept lifecycle  
