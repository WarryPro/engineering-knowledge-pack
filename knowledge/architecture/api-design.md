---
title: API Design
domain: architecture
tags: [api, http, rest, contracts, versioning, resources]
severity: recommended
applies_to: [backend, frontend, api, mobile]
type: guide
role: architecture
depends_on:
  - knowledge/engineering/engineering-principles.md
implements:
  - EKP-P04
  - EKP-P06
  - EKP-P07
related:
  - knowledge/engineering/engineering-principles.md
  - knowledge/engineering/error-handling.md
  - knowledge/security/security-fundamentals.md
  - knowledge/architecture/layering-and-boundaries.md
  - knowledge/architecture/README.md
extends: []
concept_ids: [EKP-AP01, EKP-AP02, EKP-AP03, EKP-AP04, EKP-AP05, EKP-AP06, EKP-AP07, EKP-AP08, EKP-AP09]
adapter_priority: high
---

# API Design

## Summary

Stack-agnostic **architecture-layer** guidance for designing **HTTP-oriented public APIs**: resources, verbs, contract shape, versioning, pagination, and mutation safety. This document operationalizes **EKP-P04** (Explicit over implicit), **EKP-P06** (Own the boundary), and **EKP-P07** (Fail fast and visibly) at the **API surface**—not at network infrastructure or framework wiring.

Apply when adding or changing endpoints consumed by other teams, clients, or services. Relax per **EKP-P02** for internal-only functions with no HTTP contract.

**Boundaries:**

| Concern | Owner document | This document |
|---------|----------------|---------------|
| Resource naming, HTTP usage, API versioning | **this document (EKP-AP)** | Primary content |
| Boundary validation placement | `layering-and-boundaries.md` (EKP-LB09) | Cite — do not duplicate |
| Contract ownership between teams | `layering-and-boundaries.md` (EKP-LB08) | Cite |
| Error code taxonomy, leak prevention | `error-handling.md` (EKP-EH07–09) | Cite |
| Cross-service error propagation | `layering-and-boundaries.md` (EKP-LB11) | Escalation |
| Idempotency at integration boundary | `layering-and-boundaries.md` (EKP-LB12) | Cite — AP07 applies at HTTP layer |
| Authn/authz | `security-fundamentals.md` (EKP-SF05) | Cite |
| OpenAPI/Swagger tooling, gRPC/protobuf | Stack domains, `devops/` | Out of scope |

**Out of scope:** GraphQL schema design, framework route attributes, API gateway config, rate-limit infrastructure.

## Guidance

### EKP-AP01: API as owned contract

**Implements:** EKP-P06

**Intent:** Every public API has an owner who approves breaking changes.

**Rules:**

- Document consumers (mobile app, partner, internal service).
- Breaking changes require version strategy or migration plan (**EKP-AP05**).
- Internal "private" APIs still need owner if multiple teams call them.

---

### EKP-AP02: Resources and naming

**Implements:** EKP-P04

**Intent:** URLs identify **resources** (nouns), not actions (verbs).

**Rules:**

- Prefer `/orders/{id}` over `/getOrder`.
- Use plural nouns consistently (`/users`, not `/user`).
- Sub-resources express containment: `/orders/{id}/items`.
- Non-CRUD operations: POST to action sub-path with care (`/orders/{id}/cancel`)—sparingly.

---

### EKP-AP03: HTTP semantics

**Implements:** EKP-P07

**Intent:** Method and status code convey outcome explicitly.

| Method | Typical use |
|--------|-------------|
| GET | Safe read |
| POST | Create or non-idempotent action |
| PUT/PATCH | Update |
| DELETE | Remove |

**Rules:**

- 2xx success, 4xx client fault, 5xx server fault—use consistently.
- GET must not mutate state.
- 404 vs 403: do not leak existence via security-sensitive resources (**EKP-SF07**).

---

### EKP-AP04: Request and response shape

**Implements:** EKP-P04

**Intent:** Stable, evolvable payloads—explicit fields, documented null semantics.

**Rules:**

- Prefer explicit fields over ambiguous bags.
- Additive changes (new optional fields) are usually safe; removals/renames are breaking.
- Date/time: ISO-8601 with timezone; money: amount + currency fields.
- Do not echo internal stack traces in body (**EKP-EH08**).

---

### EKP-AP05: Versioning strategy

**Implements:** EKP-P03

**Intent:** Consumers need time to migrate; version explicitly.

**Rules:**

- Choose URL prefix (`/v1/`) or header strategy—document one per API family.
- Deprecate old versions with timeline; monitor usage before removal.
- Breaking change without version bump is a defect.

---

### EKP-AP06: Pagination, filtering, sorting

**Implements:** EKP-P04

**Intent:** List endpoints need stable contracts for large datasets.

**Rules:**

- Cursor or offset pagination—document limits and defaults.
- Filter/sort parameters: whitelist allowed fields.
- Return total count only when cheap; document when omitted.

---

### EKP-AP07: Idempotent mutations

**Implements:** EKP-P07

**Intent:** Retries must not double-charge or duplicate side effects.

**Rules:**

- POST creating resources: support idempotency key header for critical operations.
- Align with **EKP-LB12** for cross-service semantics—HTTP layer exposes the key.
- PUT to stable URI is naturally idempotent; POST usually is not.

---

### EKP-AP08: Error responses

**Implements:** EKP-P07

**Intent:** API errors are machine- and human-actionable without internal detail.

**Rules:**

- Stable `code` or `type` field + safe `message` for clients.
- Map internal failures per **EKP-EH07**—do not redefine taxonomy here.
- Validation errors: field-level detail when safe (**EKP-LB09** validates before domain).

---

### EKP-AP09: API review signals

**Implements:** EKP-P06

| Signal | Verdict |
|--------|---------|
| New endpoint with owner + tests + error contract | Good |
| Breaking rename without version | Reject |
| GET with side effects | Reject |
| Verb in URL path for CRUD | Revise |

## AI Decision Flow

For new or changed HTTP API surface. Run after `ai-assisted-development.md` steps 1–3.

```
1. Is this a public or multi-team HTTP contract (EKP-AP01)?
   → NO: Internal function only — stop; do not apply API guide.
   → YES: continue.

2. Resource model (EKP-AP02)
   → Nouns, consistent paths. Revise verb-based URLs.

3. HTTP method and status semantics (EKP-AP03)
   → GET read-only; correct status codes.

4. Breaking change check (EKP-AP05)
   → YES: Flag migration/version plan before implementation.

5. Mutation idempotency (EKP-AP07)
   → Payment/order/create: idempotency key required.

6. Error and validation contracts
   → Shape per EKP-AP08; validation placement per EKP-LB09; auth per EKP-SF05.

7. Cross-service ownership
   → Multi-team impact: escalate EKP-LB08 — do not invent local policy.
```

| ID | Rule |
|----|------|
| **AP-AI-01** | Do not add endpoints without resource model and owner. |
| **AP-AI-02** | Flag breaking payload changes explicitly. |
| **AP-AI-03** | Route validation placement to EKP-LB09—not controller hacks only. |

## When not to apply

- Private method calls within one deployable.
- Prototype with no external consumer (**EKP-P02**).
- Non-HTTP RPC already governed by ADR—cite ADR instead.

## Trade-offs

| Benefit | Cost |
|---------|------|
| Explicit contracts reduce integration defects | Design time before coding |
| Versioning protects consumers | Multiple versions to maintain |
| Idempotency keys improve reliability | Client and server complexity |

## Related

- [Layering and Boundaries](layering-and-boundaries.md) — EKP-LB08–LB12
- [Error Handling](../engineering/error-handling.md) — EKP-EH
- [Security Fundamentals](../security/security-fundamentals.md) — EKP-SF
- [Architecture domain index](README.md)
