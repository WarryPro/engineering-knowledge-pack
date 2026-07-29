---
title: Integration Patterns
domain: architecture
tags: [integration, messaging, events, sync, async, acl, distributed]
severity: recommended
applies_to: [backend, api, mobile]
type: guide
role: pattern
depends_on:
  - knowledge/engineering/engineering-principles.md
  - knowledge/architecture/layering-and-boundaries.md
implements:
  - EKP-P05
  - EKP-P06
  - EKP-P09
related:
  - knowledge/engineering/engineering-principles.md
  - knowledge/engineering/design-patterns.md
  - knowledge/architecture/layering-and-boundaries.md
  - knowledge/architecture/api-design.md
  - knowledge/database/database-design.md
  - knowledge/architecture/adr-practices.md
  - knowledge/architecture/README.md
extends: []
concept_ids: [EKP-IN01, EKP-IN02, EKP-IN03, EKP-IN04, EKP-IN05, EKP-IN06, EKP-IN07, EKP-IN08]
adapter_priority: medium
---

# Integration Patterns

## Summary

Stack-agnostic **pattern-layer** catalog for **between-system** integration: synchronous vs asynchronous styles, messaging patterns, anti-corruption layers, and orchestration awareness—without enterprise tutorials (full CQRS, event sourcing implementations) or broker configuration.

This document operationalizes **EKP-P05**, **EKP-P06**, and **EKP-P09** when systems—not classes—collaborate. Depends on **layering-and-boundaries** for contract ownership (**EKP-LB08–LB13**); does not restate those rules.

Apply when choosing how services, applications, or bounded deployables exchange data. Relax per **EKP-P02** when a single monolith has no external integration.

**Boundaries:**

| Concern | Owner document | This document |
|---------|----------------|---------------|
| Integration **style** selection (named patterns) | **this document (EKP-IN)** | Primary content |
| Layer placement, contract ownership | `layering-and-boundaries.md` (EKP-LB) | Prerequisite — cite |
| HTTP resource API design | `api-design.md` (EKP-AP) | Sync HTTP detail |
| Schema and migrations | `database-design.md` (EKP-DB) | Persistence |
| In-process GoF-style patterns | `design-patterns.md` (EKP-DP) | Out of scope |
| Kafka/RabbitMQ setup | `devops/` | Out of scope |
| CQRS/event sourcing full guides | ADR + future docs | Out of scope |

**Out of scope:** service mesh config, saga framework APIs, protobuf/gRPC tutorials.

## Guidance

### EKP-IN01: Sync vs async integration

**Implements:** EKP-P02

**Intent:** Match integration style to latency, coupling, and failure isolation needs.

| Style | Strength | Weakness |
|-------|----------|----------|
| **Sync HTTP/RPC** | Simple mental model; immediate response | Couples availability; latency chains |
| **Async messaging** | Decouples time; buffers load | Complexity; eventual consistency |

**Rules:**

- Default sync for query/read paths with clear timeout (**EKP-LB13**).
- Prefer async when peak load, fan-out, or slow consumers would block callers.
- Do not add message broker without failure handling plan.

---

### EKP-IN02: Point-to-point vs broker

**Implements:** EKP-P06

**Intent:** Choose topology deliberately.

**Rules:**

- Point-to-point queue: one consumer group per logical worker pool.
- Pub/sub broker: multiple subscribers; requires schema for event shape.
- Owner documents event contract version (**EKP-LB10**).

---

### EKP-IN03: Event notification vs event-carried state transfer

**Implements:** EKP-P04

**Intent:** Events either **notify** ("something happened") or **carry state** ("here is the payload").

**Rules:**

- Notification: consumer fetches authoritative state—slower, consistent.
- Carried state: faster; risk stale fields—version fields required.
- Do not ship full aggregate by default without consumer need.

---

### EKP-IN04: Anti-corruption layer (ACL)

**Implements:** EKP-P06

**Intent:** Translate foreign models at the boundary—do not leak partner schema into domain.

**Rules:**

- Adapter module maps external DTO → internal model.
- Domain never depends on partner field names.
- ACL is not an excuse for god-object mapper—keep mapping explicit.

---

### EKP-IN05: Choreography vs orchestration

**Implements:** EKP-P05

**Intent:** Multi-step cross-service flows need coordination model.

| Model | Description | Risk |
|-------|-------------|------|
| **Choreography** | Services react to events | Hard to trace; implicit flow |
| **Orchestration** | Central coordinator | Single point of failure/complexity |

**Rules:**

- Simple flows: choreography may suffice.
- Money, compliance, or strict ordering: consider orchestration + ADR (**EKP-AD01**).
- Do not implement saga framework here—awareness only.

---

### EKP-IN06: Idempotency and ordering

**Implements:** EKP-P07

**Intent:** Messages deliver at-least-once; handlers must cope.

**Rules:**

- Consumers idempotent or dedupe by message ID.
- Ordering: partition key when per-entity order matters.
- Align with **EKP-LB12**—do not redefine idempotency rules.

---

### EKP-IN07: When not to introduce messaging

**Implements:** EKP-P02

**Do not add async integration when:**

- Two modules in one deployable could call a function.
- One consumer, one producer, sync SLA &lt;100ms acceptable.
- Team lacks operational maturity for broker monitoring.
- Problem is bad module boundary—fix **EKP-MC** first.

---

### EKP-IN08: Integration review signals

**Implements:** EKP-P06

| Signal | Verdict |
|--------|---------|
| Contract versioned; idempotent consumer | Good |
| Dual write without reconciliation plan | Reject |
| Broker added for single cron job | Over-engineered |
| Missing timeout on sync call | EKP-LB13 gap |

## When not to apply

- Monolith with no external system calls.
- Internal in-process event bus only (cite **EKP-DP** observer if needed).
- Prototype with mock external API.

## Trade-offs

| Benefit | Cost |
|---------|------|
| Async decouples peak load | Operational complexity |
| ACL protects domain | Mapping maintenance |
| Explicit integration style | Upfront design time |

## Graph dependency note

This document `depends_on` `layering-and-boundaries.md` per `schema/graph-rules.yaml` exception—integration patterns require system boundary context. All contract ownership rules remain in **EKP-LB**.

## Related

- [Layering and Boundaries](layering-and-boundaries.md) — EKP-LB
- [API Design](api-design.md) — EKP-AP
- [Database Design](../database/database-design.md) — EKP-DB
- [Design Patterns](../engineering/design-patterns.md) — EKP-DP (in-process)
- [ADR Practices](adr-practices.md) — EKP-AD
- [Architecture domain index](README.md)
