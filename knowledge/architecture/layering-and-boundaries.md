---
title: Layering and Boundaries
domain: architecture
tags: [layering, boundaries, contracts, dependencies, integration]
severity: recommended
applies_to: [backend, frontend, api, mobile]
type: guide
role: architecture
depends_on:
  - knowledge/engineering/engineering-principles.md
implements:
  - EKP-P05
  - EKP-P06
related:
  - knowledge/engineering/engineering-principles.md
  - knowledge/engineering/solid.md
  - knowledge/engineering/design-patterns.md
  - knowledge/engineering/refactoring.md
  - knowledge/engineering/clean-code.md
  - knowledge/architecture/decisions/README.md
  - knowledge/architecture/decisions/adr-0004-clean-code-position-in-knowledge-graph.md
extends: []
concept_ids: [EKP-LB01, EKP-LB02, EKP-LB03, EKP-LB04, EKP-LB05, EKP-LB06, EKP-LB07, EKP-LB08, EKP-LB09, EKP-LB10, EKP-LB11, EKP-LB12, EKP-LB13, EKP-LB14, EKP-LB15, EKP-LB16]
adapter_priority: high
---

# Layering and Boundaries

## Summary

Stack-agnostic **architecture-layer** guidance for system structure: layer responsibilities, dependency direction, integration contracts, and boundary ownership. This document operationalizes **EKP-P05** (Local reasoning) at system scale and **EKP-P06** (Own the boundary). It defines *where* concerns belong and *what crosses* between layers—not how to name functions (`clean-code.md`), evaluate classes (`solid.md`), name patterns (`design-patterns.md`), or execute structural change (`refactoring.md`).

Apply during system design, integration design, and architecture review. Relax per **EKP-P02** (Proportionality) for prototypes and short-lived systems with documented expiry. One-way structural decisions require an ADR (`decisions/`). Level 4 refactoring escalates here per `refactoring.md` (EKP-RF07).

This document does not prescribe microservices, CQRS, event sourcing, or hexagonal architecture as mandatory styles—those are project decisions recorded in ADRs when adopted.

## Context

Systems fail at boundaries: undefined contracts, dependencies pointing inward from infrastructure to policy, errors that vanish at service edges, and "internal" APIs treated as stable when they are not. Class-level SOLID compliance does not prevent a well-factored domain from calling a database through a controller (**EKP-P05** at system scale).

[Engineering Principles](../engineering/engineering-principles.md) define *why* local reasoning and boundary ownership matter. [SOLID](../engineering/solid.md) defines class/module structure. This document defines *system-level* layering and integration contracts. Every section traces to an **EKP-LB** concept ID and EKP-P05 or EKP-P06.

**Boundaries:**

| Layer | Document | Unit of analysis |
|-------|----------|------------------|
| Function/file readability | `clean-code.md` (EKP-CC) | Names, functions, formatting |
| Class/module structure | `solid.md` (EKP-SL) | Responsibilities, dependencies |
| Named collaborations | `design-patterns.md` (EKP-DP) | In-process structural patterns |
| Safe structural change | `refactoring.md` (EKP-RF) | Refactoring levels and procedures |
| System structure | **this document** (EKP-LB) | Layers, services, integration contracts |

**Out of scope:** SOLID definitions (`solid.md`), in-process pattern catalog (`design-patterns.md`), refactoring step sequences (`refactoring.md`), framework wiring (`symfony/`, stack domains), security threat models (`security/`), performance tuning (`performance/`), project-specific topology decisions (ADRs), enterprise pattern tutorials (CQRS, saga choreography as full guides).

## EKP layer positioning

| Layer | Role | Example documents | This document |
|-------|------|-------------------|---------------|
| **Principles** | Why — value judgments | `engineering-principles.md` (EKP-P01–P10) | Implements EKP-P05, EKP-P06 by reference |
| **Practices** | Unit-level structure | `clean-code.md`, `solid.md` | Prerequisites — cite EKP-CC/EKP-SL IDs only |
| **Patterns** | Named in-process structures | `design-patterns.md` | Escalation target when scope exceeds module |
| **Procedures** | How to change structure | `refactoring.md` | Level 4 escalation — cite EKP-RF07 only |
| **Architecture** | System boundaries | **this document** (EKP-LB), ADRs | Primary content |

Layering and boundaries is an **architecture-layer** artifact per ADR-0004. Adapters (Cursor, Claude, Google Gravity, future tools) should extract the **AI Decision Flow** and **boundary ownership rules** as high-priority constraints.

## Guidance

### EKP-LB01: When layering matters

**Implements:** EKP-P05, EKP-P02

**Intent:** Layering is a tool for local reasoning at system scale—not a default tax on every codebase.

**Apply layering when:**

- Multiple teams or deployable units share a codebase or integration surface.
- Business policy must be testable without databases, networks, or UI frameworks.
- Integration contracts change on a different schedule than domain rules.
- Blast radius of a boundary violation exceeds a single module (data corruption, security, revenue).

**Defer strict layering when:**

- Throwaway prototype or script with documented discard date (**EKP-P02**).
- Solo developer, single deployable, stable requirements, and no anticipated split.
- Cost of layer ceremony exceeds benefit for the system's lifespan.

**Review signals:** Four layers introduced for a 500-line CRUD app; no layer diagram can be drawn without ambiguity.

---

### EKP-LB02: Proportionality in architecture

**Implements:** EKP-P02

**Intent:** Match architectural structure to problem significance, lifespan, and blast radius.

| Factor | Lean toward minimal layers | Lean toward explicit boundaries |
|--------|---------------------------|--------------------------------|
| Lifespan | Experiment, internal tool | Core product, long-lived API |
| Blast radius | Isolated failure | Payments, auth, PII, financial data |
| Team count | Solo or pair | Multiple teams, shared services |
| Change frequency | Stable domain | High-churn integrations |

A modular monolith with clear package boundaries may outperform premature service extraction. Service boundaries are an ADR decision—not a layering default.

**Review signals:** Microservice split proposed without independent deployment or scaling need; "clean architecture" cited without stated problem.

---

### EKP-LB03: Convention alignment

**Implements:** EKP-P05

**Intent:** Follow existing system structure before introducing new layer vocabulary.

**Rules:**

- Name layers and boundaries with domain and team language—not framework jargon unless the framework *is* the boundary (e.g. HTTP API).
- New modules fit existing dependency direction; do not introduce a parallel layering scheme in one feature.
- When migrating legacy systems, document divergence from target layering in tickets or ADRs—not only in code comments.

**Review signals:** New `domain/` package in a codebase that has always used `services/`; inconsistent layer names across modules (`core` vs `domain` vs `business`).

---

### EKP-LB04: Escalation from engineering documents

**Implements:** EKP-P05, EKP-P06

**Intent:** Route questions to the correct layer document—avoid solving system problems with class patterns or refactor procedures alone.

| Symptom | Diagnose with | Escalate here when |
|---------|---------------|-------------------|
| Unclear function name | EKP-CC01 (`clean-code.md`) | — |
| Mixed class responsibilities | EKP-SL01 (`solid.md`) | Responsibility spans deployable units |
| Growing variant `switch` | EKP-SL02 / EKP-DP08 | Variation is cross-service policy |
| Domain imports ORM driver | EKP-SL05 (`solid.md`) | Layer placement and port ownership unclear |
| Cross-service Adapter | EKP-DP10 (`design-patterns.md`) | Contract spans teams or deployment boundaries |
| Level 4 refactor proposed | EKP-RF07 (`refactoring.md`) | **Always** — ADR + this document |

**Rule:** If the fix requires changing *who owns the contract* between systems or layers, the problem is architectural (EKP-LB)—not a SOLID or pattern problem alone.

---

### EKP-LB05: Dependency direction

**Implements:** EKP-P05, EKP-P06

**Intent:** Source code dependencies point **inward** toward policy and domain—not outward toward infrastructure details.

**Default direction (conceptual, not mandatory taxonomy):**

```text
[ Delivery / UI / API ]  →  [ Application / Use cases ]  →  [ Domain ]  ←  [ Infrastructure ]
         (outer)                    (orchestration)           (policy)         (implements ports)
```

**Rules:**

- Domain and application policy must not import database drivers, HTTP client SDKs, or UI frameworks directly—use abstractions (ports) per **EKP-SL05**.
- Infrastructure implements interfaces defined by inner layers; it does not define business rules.
- Shared kernel between services is a **boundary decision**—minimize; version explicitly; prefer duplication over wrong shared coupling (**EKP-P02**).

**When NOT to apply strictly:** Outermost delivery layer (CLI entrypoint, controller) naturally depends on frameworks—that is the composition root, not a violation.

**Review signals:** `import Doctrine\...` or `import axios` inside domain package; circular package dependencies.

---

### EKP-LB06: Layer responsibilities

**Implements:** EKP-P05

**Intent:** Each layer has a single architectural reason to change—SRP at system scale (**EKP-SL01** analogy).

| Layer (conceptual) | Owns | Must not own |
|--------------------|------|--------------|
| **Domain** | Business rules, invariants, domain events (as concepts) | HTTP status codes, SQL, UI layout |
| **Application** | Use-case orchestration, transaction boundaries, authorization checks at use-case level | Framework request objects in domain |
| **Infrastructure** | Persistence, messaging, external API clients | Business policy decisions |
| **Delivery** | HTTP routing, serialization, CLI parsing | Direct database access bypassing application layer |

Layers may map to packages, modules, or directories—consistency matters more than the label.

**Review signals:** Controller method contains SQL; entity class renders HTML; repository encodes business rules that belong in domain services.

---

### EKP-LB07: What crosses a layer

**Implements:** EKP-P06

**Intent:** Only deliberate, validated artifacts cross layer boundaries—never raw framework or persistence leakage.

**May cross inward (toward domain):**

- Domain types, value objects, domain service interfaces
- Commands/queries as explicit DTOs (not framework request objects)
- Abstractions (ports) owned or co-owned by inner layers

**May cross outward (from domain):**

- Nothing that pulls infrastructure types inward
- Domain events as plain data structures—not message broker envelopes

**Must be validated at the boundary:**

- External input (API body, queue message, file upload)
- Responses leaving the system (API JSON shape, error payloads)

**Review signals:** Entity returned directly from REST controller without mapping; queue consumer passes raw JSON into domain without schema validation.

---

### EKP-LB08: Contract stability and ownership

**Implements:** EKP-P06

**Intent:** Every boundary has a named owner responsible for the contract's stability, documentation, and breaking-change process.

**Rules:**

- Assign an owner (team, module, or service) per integration boundary—not "shared ownership" with no decision maker.
- Publish contract artifacts: OpenAPI for HTTP, schema for events, documented error codes—not tribal knowledge.
- Breaking changes require a migration path: versioned endpoint, dual-write period, or explicit consumer notification.
- "Internal" APIs between teams are **still boundaries**—treat them with the same discipline as public APIs unless documented otherwise.

**Review signals:** Undocumented JSON field additions relied on by another service; breaking change deployed without consumer coordination.

---

### EKP-LB09: Validation at the boundary

**Implements:** EKP-P06

**Intent:** Validate and normalize at the point of entry—do not trust upstream because it is "internal."

**Rules:**

- Parse and validate input at delivery/infrastructure edge before domain logic executes.
- Reject invalid input with explicit error semantics—do not coerce silently unless documented safe default (**EKP-P07** defers error-handling detail to future `error-handling.md`).
- Map external representations to domain types in the outer layer—domain should not parse raw HTTP or SQL row shapes.
- Idempotency keys and auth tokens are boundary concerns—validate before use-case execution.

**Good:** API controller validates DTO → maps to `PlaceOrderCommand` → handler executes.

**Bad:** Domain service accepts untyped `array $payload` from controller.

**Review signals:** `$_POST` or `request.body` accessed inside domain; missing validation on "trusted" internal endpoint.

---

### EKP-LB10: Versioning and migration

**Implements:** EKP-P06, EKP-P03

**Intent:** Evolve contracts deliberately—prefer reversible migration steps.

**Rules:**

- Prefer additive changes (new fields optional, new endpoints) over breaking replacements when consumers exist.
- Deprecate before remove: mark fields/endpoints deprecated; measure usage; set removal date.
- Large boundary moves (extract service, replace persistence) follow Level 4 refactoring governance (**EKP-RF07**) and require ADR.
- Feature flags and parallel endpoints are valid two-way doors (**EKP-P03**) during migration.

**Review signals:** Big-bang API version swap with no dual-run; database schema change without migration plan affecting multiple services.

---

### EKP-LB11: Error semantics across boundaries

**Implements:** EKP-P06, EKP-P05

**Intent:** Errors crossing a boundary must be explicit, structured, and owned—never ambiguous success/failure.

**Rules:**

- Define error categories at the boundary: client error (4xx), server error (5xx), domain rejection (mapped consistently).
- Do not leak internal stack traces or infrastructure details in outward responses.
- Propagate correlation IDs across service calls for diagnosis (**EKP-P07**).
- Boolean `success: false` without reason code is insufficient—include machine-readable error type and human message.
- Map domain exceptions to boundary responses in the delivery/adapter layer—not in domain core.

**Review signals:** HTTP 200 with `{ "error": "something failed" }`; swallowed exceptions returning empty lists across service boundary.

---

### EKP-LB12: Idempotency at boundaries

**Implements:** EKP-P06

**Intent:** Operations that may be retried (webhooks, message consumers, payment callbacks) must declare idempotency behavior at the boundary.

**Rules:**

- Document which operations are idempotent and which are not.
- Accept idempotency keys for externally triggered writes where duplicates are possible.
- Consumers must handle duplicate delivery without corrupting state.
- Side effects (email, charge, shipment) require deduplication strategy at boundary or application layer.

**Review signals:** Webhook handler creates duplicate orders on retry; no idempotency key on payment API.

---

### EKP-LB13: Timeout, retry, and failure contracts

**Implements:** EKP-P06

**Intent:** Cross-boundary calls must define timeout, retry, and failure behavior—not infinite waits or unbounded retries.

**Rules:**

- Set explicit timeouts on outbound calls; document expected latency SLO at boundary.
- Retries only for idempotent operations or with deduplication; use backoff.
- Define circuit-breaking or degradation behavior when downstream fails—at application or infrastructure layer, documented per boundary.
- Cascading failure from one slow dependency is a boundary design failure.

**Review signals:** No timeout on HTTP client; retry loop on non-idempotent POST; thread pool exhaustion from blocking calls.

---

### EKP-LB14: Leaky abstractions

**Implements:** EKP-P05, EKP-P06

**Intent:** A boundary fails when inner layers must understand outer-layer details to function correctly.

| Leak | Symptom | Fix direction |
|------|---------|---------------|
| ORM in domain | Entities carry persistence annotations; lazy-load in domain logic | Map at infrastructure boundary |
| Framework in domain | Domain imports Symfony/Express/Spring types | Delivery adapter maps to domain |
| Transport in use case | Use case knows HTTP status codes | Map in controller |
| Shared mutable global | Static config mutated across requests | Inject configuration; document thread model |

**Review signals:** Domain test requires database; renaming database column breaks domain unit tests; domain imports `javax.servlet` or `Illuminate\Http`.

---

### EKP-LB15: Anemic boundaries

**Implements:** EKP-P06

**Intent:** Boundaries that pass through data without ownership create integration defects no single team fixes.

**Symptoms:**

- DTO passes through five services with no owner validating shape evolution.
- "Shared library" of models used by all services but owned by none.
- Integration tests missing because "it's just data."

**Rules:**

- Every shared contract has an owner and a changelog.
- Prefer consumer-driven contract tests or schema validation in CI for critical boundaries.
- Thin pass-through services that only forward JSON add latency without boundary value—consolidate or justify with ADR.

**Review signals:** Breaking field rename breaks three services; no schema registry or OpenAPI diff in CI.

---

### EKP-LB16: Architecture change governance

**Implements:** EKP-P06, EKP-P03

**Intent:** Structural architecture work requires explicit governance—not scope smuggling in feature or bugfix PRs.

**Rules:**

- Level 4 refactoring (**EKP-RF07**): ADR required before implementation; phased plan; full regression strategy.
- Do not extract services, replace persistence layer, or restructure module graph in bugfix PRs.
- AI assistants: propose architecture changes as ADR drafts—do not auto-apply Level 4 work.
- Temporary bridges across layers are allowed with **documented expiry** (ticket, ADR, or tech-debt register).

**Review signals:** Feature PR introduces new service boundary; hotfix includes package restructure; "while we're here" hexagonal migration.

## AI Decision Flow

Canonical sequence for Cursor, Claude, Google Gravity, and future EKP adapters.

```
1. Is the problem at function, class, or system level?
   → Function/name: clean-code.md (EKP-CC). Stop.
   → Class/module: solid.md (EKP-SL). Stop.
   → In-process pattern: design-patterns.md (EKP-DP). Stop.
   → System/integration boundary: continue.

2. Is explicit layering justified for this system's lifespan and blast radius?
   → NO: Prefer simpler structure (EKP-LB01, EKP-LB02). Stop.
   → YES: continue.

3. Does the change alter a contract between teams, services, or layers?
   → YES: Identify boundary owner (EKP-LB08). Document contract impact.
   → NO: Apply layer rules within single deployable (EKP-LB05–07).

4. Does the change require Level 4 refactoring?
   → YES: Do NOT auto-apply. Draft ADR + phased plan (EKP-RF07, EKP-LB16).
   → NO: Link refactoring.md procedure if structural steps needed.

5. Are validation, errors, idempotency, and timeouts defined at the boundary?
   → NO: Define before implementation (EKP-LB09–13).
   → YES: proceed with implementation.

6. Never solve a service-boundary problem with only a class-level pattern.
   → Escalate to EKP-LB; cite EKP-DP10 cross-service case explicitly.
```

**Adapter enforcement:**

| Step | Auto-apply | Notes |
|------|------------|-------|
| 1 | Route by layer | Hard classification |
| 2–3 | Conditional | Human review for new boundaries |
| 4 | Block | ADR gate |
| 5 | Block until defined | Contract completeness |
| 6 | Hard block | Anti-pattern |

## AI-specific guidance

### Universal rules

- **LB-AI-01:** Classify problem level before suggesting architecture (function → class → pattern → boundary).
- **LB-AI-02:** Do not propose new services or layers without stated scaling, team, or contract isolation need (**EKP-LB02**).
- **LB-AI-03:** Cite EKP-LB ID when recommending boundary or layering changes.
- **LB-AI-04:** Never bundle architecture migration into unrelated feature or bugfix tasks (**EKP-LB16**, EKP-RF06).
- **LB-AI-05:** Define boundary contract (validation, errors, idempotency, timeout) before generating integration code.
- **LB-AI-06:** Prefer existing project layer conventions (**EKP-LB03**).
- **LB-AI-07:** Level 4 changes → ADR proposal text only—not implementation.
- **LB-AI-08:** Cross-reference EKP-SL/EKP-DP for class-level issues; do not duplicate their guidance.

### Cursor

- Run AI Decision Flow before suggesting new packages, services, or API versions.
- Block multi-module dependency inversion in agent mode without explicit user approval.

### Claude

- Separate "architectural recommendation" from "required for current task."
- List contract impacts when proposing boundary changes.

### Google Gravity

- Bind layering suggestions to explicit user scope.
- Do not introduce microservice or event-driven vocabulary without user-requested modernization.

## Review signals

| Signal | Verdict | Concept |
|--------|---------|---------|
| Clear layer ownership; validated boundary input; documented contract | Good architecture | EKP-LB05–09 |
| Domain imports infrastructure package | Layer violation | EKP-LB14 |
| Breaking API change without migration plan | Boundary failure | EKP-LB08, EKP-LB10 |
| New service in feature PR without ADR | Governance failure | EKP-LB16, EKP-RF07 |
| HTTP 200 on error payload | Error semantics failure | EKP-LB11 |
| Webhook creates duplicates on retry | Idempotency gap | EKP-LB12 |
| Four layers for trivial CRUD | Over-engineering | EKP-LB01, EKP-LB02 |
| SOLID violation only within one class | Not this document | → EKP-SL |

## Trade-offs

Explicit layering and boundaries improve local reasoning and integration safety. They are not free.

| Benefit | Cost |
|---------|------|
| Testable domain without infrastructure (**EKP-P05**) | Mapping layers; more types and files |
| Clear contract ownership (**EKP-P06**) | Ceremony for internal APIs |
| Safer cross-team integration | Versioning and migration overhead |
| Shared review vocabulary (EKP-LB) | Learning curve; misuse as dogma |

**When this document is insufficient:**

- Function readability → `clean-code.md` (EKP-CC)
- Class responsibility → `solid.md` (EKP-SL)
- In-process patterns → `design-patterns.md` (EKP-DP)
- Refactoring steps → `refactoring.md` (EKP-RF)
- Project-specific topology (microservices vs monolith) → ADR in `decisions/`
- Framework module configuration → stack domains (`symfony/`, `typescript/`)
- Error handling philosophy detail → future `error-handling.md` (EKP-P07)
- Test strategy → future `testing/` domain guides

## Knowledge graph position

| Field | Value |
|-------|-------|
| `role` | `architecture` |
| `depends_on` | `engineering-principles.md` |
| `implements` | EKP-P05, EKP-P06 |
| `concept_ids` | EKP-LB01–EKP-LB16 |
| `adapter_priority` | high — AI Decision Flow + boundary ownership |
| Prerequisites (related) | `solid.md`, `design-patterns.md`, `refactoring.md` |
| Escalation | ADRs in `decisions/` for one-way doors |

```
engineering-principles
        │
        ├── engineering/ (practices, patterns, procedures)
        │
        └── architecture/
                ├── layering-and-boundaries (architecture) ◄── this document
                └── decisions/ (ADRs)
```

## Related

- [Engineering Principles](../engineering/engineering-principles.md) — EKP-P01–P10 foundation
- [SOLID](../engineering/solid.md) — class/module structure (EKP-SL)
- [Design Patterns](../engineering/design-patterns.md) — in-process patterns (EKP-DP)
- [Refactoring](../engineering/refactoring.md) — Level 4 escalation (EKP-RF07)
- [Clean Code](../engineering/clean-code.md) — function/file readability (EKP-CC)
- [ADR-0004: Knowledge graph layering](decisions/adr-0004-clean-code-position-in-knowledge-graph.md)
- [Architecture decision records](decisions/README.md)
