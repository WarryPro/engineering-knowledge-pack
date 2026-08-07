# ADR-0005: Technology Knowledge Evolution

## Status

Accepted

## Date

2026-08-07

## Context

EKP v0.2.0 established foundation knowledge and an operational pipeline. v0.3.0 added the first technology vertical (PHP L1, Symfony L2). Phase 4 Wave 2 on `staging` adds TypeScript (L1) and Frontend (L2).

Without a recorded decision, contributors may:

- nest frameworks under languages in directory structure,
- embed language fundamentals inside framework guides,
- redefine L0 principles in stack-specific documents,
- create parallel domains per UI framework (e.g. `vue/`, `react/`),
- or expand `cursor-core` with technology content.

EKP-AI13 and EKP-AI15 defined the target model; this ADR records what is **already implemented** and governs future technology expansion.

## Decision

Adopt a **flat sibling domain layout** with explicit **layer semantics**:

```
L0 Foundation   — engineering, architecture, security, testing, ai, database, …
L1 Language     — php, typescript, …
L2 Framework / Frontend — symfony, frontend, flutter, …
L3 Ops          — devops (when published)
```

### Rules

1. **Technology applies Foundation** — tech guides use `implements` / `Applies` / `related`; they do not restate EKP-P, EKP-LB, EKP-SF, etc.
2. **Language before framework** — L2 may `depends_on` L1 of the same stack (with documented graph exception under V2 policy).
3. **Downward dependencies only** — L0 never `depends_on` technology; no cross-stack `depends_on` (e.g. frontend ↛ php).
4. **Opt-in profiles** — `cursor-core` remains foundation-only (65 rules, frozen). Stack profiles compose explicit L0 subset + tech paths.
5. **One guide per concern initially** — e.g. `php-fundamentals`, `symfony-architecture`; split only when size/scope demands.
6. **Framework-agnostic frontend** — React/Vue/Angular are not separate top-level domains; UI framework specifics stay inside `frontend/` when needed.
7. **Graph policy V2** — reuse existing roles (`practice`, `architecture`); document L2→L1 exceptions in `graph-rules.yaml` until exception count triggers role `technology` (deferred).

### Implemented technology (reference)

| Layer | Domain | Guide | Namespace |
|-------|--------|-------|-----------|
| L1 | php | php-fundamentals | EKP-PH |
| L2 | symfony | symfony-architecture | EKP-SY |
| L1 | typescript | typescript-fundamentals | EKP-TY |
| L2 | frontend | frontend-architecture | EKP-FE |

## Rationale

- **Flat siblings** match existing stubs, profiles, and validator paths — no migration cost.
- **Language/framework split** enables `cursor-php` without Symfony and reuses patterns across stacks.
- **Foundation-first** keeps adapters and `cursor-core` stable as stacks multiply.

## Alternatives considered

### Nested directories (`knowledge/php/symfony/`)

Rejected — breaks profile paths, README conventions, and namespace ownership clarity.

### Framework monolith (Symfony guide includes all PHP)

Rejected — duplicates language guidance; blocks PHP-only profile; violates separation already proven in Wave 1.

### Per-framework domains (`vue/`, `react/`)

Rejected — premature fragmentation; `frontend/` boundary README already defines scope.

### Technology content in `cursor-core`

Rejected — violates constitution model; consumers need opt-in stacks.

### Validator role `technology` (V1 graph)

Deferred — only four cross-layer exceptions today; V2 + YAML exceptions sufficient until count grows (see governance.md).

## Consequences

### Positive

- Clear placement rules for Wave 3+ (DevOps, Flutter, Laravel peer, etc.)
- Consistent profile naming (`cursor-<stack>`)
- Documented graph exceptions for Symfony→PHP and Frontend→TypeScript

### Negative

- L0 path lists duplicated across profiles until `includes` is approved
- Exception list in YAML requires discipline

### Compliance

- New tech guides must pass [technology-guide-checklist.md](../../../templates/technology-guide-checklist.md)
- Graph exceptions require platform owner review; ADR for new exception *patterns*
- `cursor-core` diff must remain empty on technology waves

## Related

- [governance.md](../../../docs/governance.md)
- [architecture.md](../../../docs/architecture.md)
- [php-fundamentals.md](../../php/php-fundamentals.md)
- [symfony-architecture.md](../../symfony/symfony-architecture.md)
- [typescript-fundamentals.md](../../typescript/typescript-fundamentals.md)
- [frontend-architecture.md](../../frontend/frontend-architecture.md)
