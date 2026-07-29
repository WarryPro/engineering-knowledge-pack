---
title: Database Design
domain: database
tags: [database, schema, migrations, transactions, persistence, modeling]
severity: recommended
applies_to: [backend, api, mobile]
type: guide
role: architecture
depends_on:
  - knowledge/engineering/engineering-principles.md
implements:
  - EKP-P03
  - EKP-P06
  - EKP-P10
related:
  - knowledge/engineering/engineering-principles.md
  - knowledge/performance/performance-mindset.md
  - knowledge/security/security-fundamentals.md
  - knowledge/architecture/layering-and-boundaries.md
  - knowledge/architecture/adr-practices.md
  - knowledge/database/README.md
extends: []
concept_ids: [EKP-DB01, EKP-DB02, EKP-DB03, EKP-DB04, EKP-DB05, EKP-DB06, EKP-DB07, EKP-DB08]
adapter_priority: medium
---

# Database Design

## Summary

Stack-agnostic **architecture-layer** guidance for **persistent data design**: schema as contract, modeling trade-offs, migrations, transaction scope, and ownership—without SQL dialects, ORM configuration, or vendor-specific tuning.

This document operationalizes **EKP-P03** (Prefer reversible decisions), **EKP-P06** (Own the boundary), and **EKP-P10** (Maintainability is a feature) for data that outlives application code.

Apply when designing schemas, planning migrations, or reviewing data model changes. Relax per **EKP-P02** for throwaway local stores with no production path.

**Boundaries:**

| Concern | Owner document | This document |
|---------|----------------|---------------|
| Schema modeling, migrations, transaction scope | **this document (EKP-DB)** | Primary content |
| Query/index performance tuning | `performance-mindset.md` (EKP-PM) | Cite EKP-DB07 only |
| Input validation at API | `layering-and-boundaries.md` (EKP-LB09) | Not SQL injection tutorials |
| SQL injection / trust boundaries | `security-fundamentals.md` (EKP-SF02) | Cite |
| Persistence in layer model | `layering-and-boundaries.md` (EKP-LB06–07) | Cite |
| ORM mapping, repository code | Stack domains | Out of scope |
| PostgreSQL/MySQL/SQLite specifics | Stack domains | Out of scope |
| Backup, replication, HA | `devops/` | Out of scope |

**Out of scope:** Flyway/Liquibase config, connection pool tuning, CQRS read models (see ADR + `integration-patterns.md`).

## Guidance

### EKP-DB01: Schema as contract

**Implements:** EKP-P06

**Intent:** Tables and columns are integration surfaces—consumers include reports, services, and future you.

**Rules:**

- Name schema changes with same rigor as API changes.
- Document breaking column renames/removals as migrations with consumer checklist.
- Shared database across services is a coupling smell—justify with ADR (**EKP-AD01**).

---

### EKP-DB02: Normalization pragmatism

**Implements:** EKP-P02

**Intent:** Normalize to reduce update anomalies; denormalize with measured read benefit.

**Rules:**

- Default normalized for core domain entities.
- Denormalize for proven hot reads—document staleness acceptance (**EKP-PM05** caching analogy).
- Do not denormalize "because joins are scary" without measurement.

---

### EKP-DB03: Aggregate boundaries

**Implements:** EKP-P05

**Intent:** One transactional consistency boundary per business invariant—not per table.

**Rules:**

- Identify aggregates: cluster of data that must stay consistent together.
- Cross-aggregate updates: eventual consistency or saga—escalate `integration-patterns.md`, not hidden dual writes.
- Do not teach DDD tactical patterns exhaustively—use boundary language only.

---

### EKP-DB04: Migration strategy

**Implements:** EKP-P03

**Intent:** Schema changes are deploy events—plan forward and rollback.

**Rules:**

- Prefer backward-compatible migrations (expand → migrate → contract).
- Destructive changes: multi-phase with feature flags or dual-write period.
- One migration per logical change; reversible steps when possible.
- Level 4 schema replacement requires ADR (**EKP-RF07**).

---

### EKP-DB05: Transaction scope

**Implements:** EKP-P07

**Intent:** Transactions bound consistency—keep scope minimal and explicit.

**Rules:**

- Transaction wraps one business operation's invariant—not entire HTTP request by default.
- Long-running transactions hold locks—split or use async handoff.
- Do not nest distributed transactions casually—cite integration patterns for cross-service consistency.

---

### EKP-DB06: Identifiers

**Implements:** EKP-P04

**Intent:** Primary keys are permanent references—choose deliberately.

**Rules:**

- Surrogate keys (UUID, serial) for entity identity; natural keys as unique constraints when needed.
- Avoid composite keys that leak business rules into every join unless justified.
- Public IDs exposed in API may differ from internal PK—document mapping.

---

### EKP-DB07: Query and index awareness

**Implements:** EKP-P08

**Intent:** Designers acknowledge access patterns—detailed tuning is performance domain.

**Rules:**

- List expected read/write paths when adding tables.
- Flag N+1 and full-table scan risks at design review.
- Index design and profiling → **EKP-PM**—do not duplicate here.

---

### EKP-DB08: Review signals

**Implements:** EKP-P10

| Signal | Verdict |
|--------|---------|
| Migration reversible or phased | Good |
| Nullable column without default on NOT NULL migration | Risk |
| New FK without index on child | Review |
| Schema change in hotfix without migration file | Reject |

## When not to apply

- In-memory prototype with discard date.
- Read-only import of static seed data.
- File-based persistence with no shared consumers.

## Trade-offs

| Benefit | Cost |
|---------|------|
| Schema contracts protect integrators | Migration discipline |
| Clear aggregates simplify reasoning | Upfront modeling time |
| Phased migrations reduce downtime | Temporary dual schemas |

## Related

- [Performance Mindset](../performance/performance-mindset.md) — EKP-PM
- [Security Fundamentals](../security/security-fundamentals.md) — EKP-SF
- [Layering and Boundaries](../architecture/layering-and-boundaries.md) — EKP-LB
- [ADR Practices](../architecture/adr-practices.md) — EKP-AD
- [Database domain index](README.md)
