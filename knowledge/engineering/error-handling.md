---
title: Error Handling
domain: engineering
tags: [errors, failures, reliability, contracts, resilience]
severity: recommended
applies_to: [backend, frontend, api, mobile]
type: guide
role: practice
depends_on:
  - knowledge/engineering/engineering-principles.md
implements:
  - EKP-P07
related:
  - knowledge/engineering/engineering-principles.md
  - knowledge/engineering/clean-code.md
  - knowledge/engineering/solid.md
  - knowledge/engineering/design-patterns.md
  - knowledge/engineering/refactoring.md
  - knowledge/testing/testing.md
  - knowledge/architecture/layering-and-boundaries.md
  - knowledge/architecture/decisions/README.md
  - knowledge/architecture/decisions/adr-0004-clean-code-position-in-knowledge-graph.md
extends: []
concept_ids: [EKP-EH01, EKP-EH02, EKP-EH03, EKP-EH04, EKP-EH05, EKP-EH06, EKP-EH07, EKP-EH08, EKP-EH09, EKP-EH10, EKP-EH11, EKP-EH12]
adapter_priority: high
---

# Error Handling

## Summary

Stack-agnostic **practice-layer** guidance for how software should detect, represent, propagate, and recover from failure. Errors are part of normal system behavior—not accidents to hide. How failures are handled is a **design decision** with trade-offs in reliability, debuggability, and user experience.

This document operationalizes **EKP-P07** (Fail fast and visibly). It defines *how* to think about failures at the unit and module level—not how to configure loggers, trace collectors, retry libraries, or framework exception hierarchies.

Apply during implementation, API design, and code review. Relax per **EKP-P02** (Proportionality) for throwaway scripts and prototypes with documented lifespan. Boundary-level error contracts across services are owned by `layering-and-boundaries.md` (EKP-LB11).

This document does not teach SOLID (`solid.md`), naming rules (`clean-code.md`), structural patterns (`design-patterns.md`), or safe migration procedures (`refactoring.md`).

## Context

Failures are inevitable: invalid input, violated business rules, unavailable dependencies, race conditions, and defects. Teams that treat errors as afterthoughts produce systems that fail silently, leak internal detail to users, or require production archaeology to diagnose.

[Engineering Principles](engineering-principles.md) define *why* failures must surface visibly. This document defines *how* to handle them in code and contracts. Every practice traces to an **EKP-EH** concept ID and **EKP-P07**.

**Boundaries:**

| Concern | Owner document / domain | This document |
|---------|----------------------|---------------|
| Failure philosophy and unit-level handling | **this document** (EKP-EH) | Primary content |
| Readable error paths and names | `clean-code.md` (EKP-CC) | Cross-reference only |
| Who owns recovery logic | `solid.md` (EKP-SL) | Cross-reference only |
| Cross-service error contracts | `layering-and-boundaries.md` (EKP-LB) | Escalation |
| Logging configuration, log levels, appenders | `devops/`, stack domains | Out of scope |
| Metrics, tracing, dashboards | `performance/`, observability stacks | Out of scope |
| Retry/backoff library usage | Stack domains | Out of scope |
| Input validation at API boundary | `layering-and-boundaries.md` (EKP-LB09) | Complementary—not duplicated |

**Out of scope:** language-specific exception syntax tutorials, framework exception base classes (`symfony/`, `typescript/`), logging setup, distributed saga compensation patterns (architecture ADRs), security incident response (`security/`).

## EKP layer positioning

| Layer | Role | Example documents | This document |
|-------|------|-------------------|---------------|
| **Principles** | Why — value judgments | `engineering-principles.md` (EKP-P01–P10) | Implements EKP-P07 by reference |
| **Practices** | What good failure handling looks like | **this document** (EKP-EH), `clean-code.md`, `solid.md` | Primary content |
| **Patterns** | Named structures for variation | `design-patterns.md` (EKP-DP) | Related — patterns may organize handlers |
| **Procedures** | How to change structure safely | `refactoring.md` (EKP-RF) | Related — migration of error paths |
| **Architecture** | System boundary contracts | `layering-and-boundaries.md` (EKP-LB) | Escalation for distributed failures |

Error handling is a **practice-layer** artifact per ADR-0004. Adapters (Cursor, Claude, Google Gravity, future tools) should extract the **AI Decision Flow** as a high-priority constraint.

## Guidance

### EKP-EH01: Expected vs unexpected failures

**Implements:** EKP-P07

**Intent:** Distinguish failures the system is designed to handle from defects that indicate broken assumptions.

**Expected failures** are part of the domain model: invalid user input, rejected business rule, insufficient balance, resource not found, upstream timeout within defined SLO. The system should handle them deliberately—with explicit outcomes, stable contracts, and tests.

**Unexpected failures** indicate programming defects, configuration errors, or violated invariants: null where forbidden, impossible state, uncaught dependency failure outside contract. These should surface loudly, preserve diagnostic context, and typically abort the current operation—not be normalized into "success with default."

**Rules:**

- Classify each failure path during design: expected (handled) vs unexpected (defect or escalation).
- Expected failures use domain-appropriate representation (result type, rejection code, validation error)—not generic catch-all handling.
- Unexpected failures must not be converted to empty success responses.

**Review signals:** `catch (Exception)` returning default for all cases; business rejection indistinguishable from server error in API response.

---

### EKP-EH02: Fail explicitly, not silently

**Implements:** EKP-P07

**Intent:** Absence of signal is not a valid error strategy unless the absence itself is a documented, safe outcome.

**Rules:**

- Do not swallow failures and return `null`, `false`, or empty collections without documenting that as intentional domain semantics.
- Prefer explicit failure types over ambiguous "no result" when the caller cannot distinguish "not found" from "error occurred."
- Boolean success flags without reason codes violate **EKP-P07**—include machine-readable failure category.
- Internal pipelines: fail loudly. User-facing paths: fail gracefully with safe messaging—not silently.

**Good:** Operation returns `Result<Invoice, InvoiceError>` with `NotFound` vs `StorageUnavailable` variants.

**Bad:** Method returns empty list when database query failed.

**Review signals:** Empty catch blocks; `return null` after caught exception; HTTP 200 with implicit failure in body.

---

### EKP-EH03: Preserve useful failure context

**Implements:** EKP-P07

**Intent:** A failure without context forces guesswork. Preserve what is needed to diagnose—not everything.

**Rules:**

- Include: operation attempted, relevant identifiers (correlation ID, entity ID), failure category, timestamp at boundary.
- Exclude from outward responses: stack traces, SQL fragments, internal hostnames, credential hints (**EKP-EH08**).
- When rethrowing or wrapping, preserve the original cause chain for internal logs—do not discard root cause.
- Correlation identifiers across service boundaries support diagnosis (**EKP-P07**); propagation rules belong at architecture layer (EKP-LB11).

**Review signals:** Log line "something went wrong" with no ID; wrapped exception with message replaced by generic text and no inner cause retained internally.

---

### EKP-EH04: Handle errors at the correct boundary

**Implements:** EKP-P07

**Intent:** Translate failures at the layer edge—do not scatter boundary-specific handling through domain core.

| Layer | Typical handling |
|-------|------------------|
| **Delivery** (API, UI) | Map domain failures to HTTP status, user-safe messages, form field errors |
| **Application** | Orchestrate recovery, transaction rollback, compensation within use case |
| **Domain** | Express business rule violations as domain failures—not transport concerns |
| **Infrastructure** | Catch provider failures; translate to port-level failure types |

**Rules:**

- Domain logic should not choose HTTP status codes or UI toast text.
- Validate external input at entry boundary (EKP-LB09)—before domain execution.
- Do not catch infrastructure failures in domain only to rethrow as generic errors without classification.

**Review signals:** Entity class catches network timeout; controller contains business rule validation mixed with SQL error parsing.

---

### EKP-EH05: Do not use exceptions as normal control flow

**Implements:** EKP-P07

**Intent:** Exceptions (or equivalent non-local jumps) signal exceptional conditions—not routine branches.

**Rules:**

- Expected business outcomes ("coupon invalid", "seat unavailable") should use return values, result types, or domain-specific rejection—not exceptions for flow control in languages where exceptions are expensive or culturally reserved for defects.
- Using exceptions for validation in hot paths obscures happy-path readability and complicates review.
- When the language or framework convention strongly favors exceptions for expected cases, document the convention and keep categories distinct from defect exceptions.

**Review signals:** `throw` for every validation failure in a loop; catch used to implement `if/else` business logic.

---

### EKP-EH06: Define ownership of recovery decisions

**Implements:** EKP-P07

**Intent:** Someone must decide: retry, abort, compensate, degrade, or escalate. Unowned recovery becomes inconsistent behavior.

**Rules:**

- Assign recovery ownership to the layer that understands business impact—usually application/use-case, not infrastructure adapter alone.
- Retry decisions require idempotency awareness (EKP-LB12)—escalate to architecture when cross-service.
- Infrastructure may retry transient provider errors only when application has declared the operation idempotent or safe to repeat.
- "Let the caller figure it out" without a documented contract is not ownership.

**Review signals:** Three different retry strategies for the same dependency across modules; repository silently retries writes.

---

### EKP-EH07: Keep error contracts stable

**Implements:** EKP-P07

**Intent:** Callers and integrators depend on failure shapes. Breaking error contracts is a breaking API change.

**Rules:**

- Document stable error codes or categories exposed to external consumers.
- Adding new failure types is usually safe; removing or renumbering codes requires migration (EKP-LB10).
- Internal-only failures may evolve more freely—separate public contract from internal diagnostics.
- Version error payloads when multiple API versions are supported.

**Review signals:** Error code `PAYMENT_FAILED` repurposed for different meaning; field `error` sometimes string, sometimes object.

---

### EKP-EH08: Avoid leaking implementation details

**Implements:** EKP-P07

**Intent:** Outward failure messages must not expose infrastructure the caller cannot act on—and attackers should not learn system internals.

**Rules:**

- Map provider errors (database, queue, payment gateway) to stable outward categories at adapter/boundary layer.
- User-facing text: safe, actionable where possible ("Payment could not be processed")—not ("ORA-12154" or "NullPointerException in OrderRepository line 42").
- Internal logs and traces may contain detail—outward responses may not (**EKP-LB11**).

**Review signals:** API returns SQL error text; frontend displays raw exception message from server.

---

### EKP-EH09: Prefer actionable failures

**Implements:** EKP-P07

**Intent:** When the caller or user can correct the failure, say what to do—not only that something failed.

**Rules:**

- Validation failures: identify field or constraint violated.
- Business rejections: state rule and relevant domain fact ("Insufficient balance: required 100, available 40").
- System failures: actionable for operators (correlation ID, dependency name)—not for end users.
- "An error occurred" with no category is never sufficient for expected failure paths.

**Review signals:** Generic `400 Bad Request` with no body; all failures map to single `INTERNAL_ERROR` code.

---

### EKP-EH10: Avoid over-catching and swallowing failures

**Implements:** EKP-P07

**Intent:** Broad catch blocks that absorb unknown failures hide defects and corrupt state.

**Rules:**

- Catch at the narrowest scope that can meaningfully recover or translate.
- `catch (Exception)` / `catch (...)` at outer shell only—to log, translate, and rethrow or fail the request—not to continue as if success.
- Never catch without handling: log + rethrow, log + mapped failure, or documented safe fallback with business justification.
- Empty catch blocks are prohibited except in documented finalizer patterns with explicit rationale.

**Review signals:** `catch (Exception e) { }`; catch that logs and returns success; nested try/catch masking inner failure.

---

### EKP-EH11: Match failure strategy to system scope

**Implements:** EKP-P07, EKP-P02

**Intent:** A CLI script, monolith module, and distributed workflow need different failure strategies—proportionality applies.

| Scope | Typical strategy |
|-------|------------------|
| Single function / script | Fail fast; print or exit with code; minimal recovery |
| Modular monolith | Domain failures + boundary translation; transaction boundaries |
| Multi-service workflow | Contracted error codes, idempotency, saga/ADR—architecture domain |

**Rules:**

- Do not import distributed retry/circuit-breaker ceremony into a one-off script (**EKP-P02**).
- Do not treat a cross-service payment failure as a local catch-and-ignore.
- Escalate to `layering-and-boundaries.md` when failure handling requires contract changes across deployable units.

**Review signals:** Kafka consumer retry logic in a synchronous CRUD handler; single-process app with enterprise error bus for three endpoints.

---

### EKP-EH12: Do not hide architectural problems behind error handling

**Implements:** EKP-P07

**Intent:** Retry, fallback, and catch-and-continue can mask wrong boundaries, missing idempotency, or coupling defects.

**Rules:**

- If failures recur at the same integration point, investigate contract and boundary design—not only add retries.
- Fallback to stale cache is a product decision, not a default error handler.
- Generic "degraded mode" without defined behavior is silent failure (**EKP-EH02**).
- Structural fixes (split responsibility, fix dependency direction) belong in `refactoring.md` / architecture—not deeper catch blocks.

**Review signals:** Fifth retry wrapper added to same call; "we catch it so it's fine" for cross-layer violation.

## Error taxonomy

Conceptual categories—map to project-specific codes in stack guides. No framework types.

| Category | Nature | Typical handling | Example signal |
|----------|--------|------------------|----------------|
| **Validation failure** | Expected; caller correctable | Reject at boundary; field-level detail | Invalid email format |
| **Business rule failure** | Expected; domain rejection | Domain result type; stable business code | Insufficient inventory |
| **Infrastructure failure** | Expected transient or hard outage | Retry if idempotent; map at adapter; escalate if persistent | Storage timeout |
| **Integration failure** | Expected at boundary; partner or dependency | Contracted error from EKP-LB; correlation ID | Partner API 503 |
| **Programming defect** | Unexpected; invariant violated | Fail loudly; alert; fix code | Impossible enum state |

**Distinction guidance:**

- Validation vs business rule: validation is syntactic/shape; business rule is semantic/policy.
- Infrastructure vs integration: infrastructure is your runtime dependency; integration is a defined external contract.
- Defect vs expected: if the system should never reach the state, it is a defect—not a business rejection.

## Relationship boundaries

### With `clean-code.md`

| This document | `clean-code.md` |
|---------------|-----------------|
| Failure categories, propagation, contracts | Readable error paths; meaningful names for handlers |
| EKP-EH01–EH12 | EKP-CC01 (names like `isRetryable`, `PaymentRejected`) |
| Do not duplicate naming rules | Cite EKP-CC when error branch readability is poor |

### With `solid.md`

| This document | `solid.md` |
|---------------|------------|
| Where recovery decisions live | Which class owns the responsibility (EKP-SL01) |
| Error translation at boundary | DIP: adapters map provider failures (EKP-SL05) |
| Do not re-teach SOLID | Cite EKP-SL when error handling spans mixed responsibilities |

### With `design-patterns.md`

| This document | `design-patterns.md` |
|---------------|---------------------|
| Philosophy of failure representation | Command, Strategy may structure handlers—cite EKP-DP when pattern is justified |
| No pattern catalog | Problem-first pattern selection (EKP-DP01) applies |

### With `refactoring.md`

| This document | `refactoring.md` |
|---------------|------------------|
| Target error-handling shape | Procedures to migrate throws to results, extract handler—cite EKP-RF |
| Do not duplicate refactor steps | Level 2+ when error path restructuring is non-trivial |

### With `layering-and-boundaries.md`

| This document | `layering-and-boundaries.md` |
|---------------|------------------------------|
| Unit/module failure philosophy | Cross-service error semantics (EKP-LB11), idempotency (EKP-LB12), timeout/retry contracts (EKP-LB13) |
| Escalate when failure crosses deployable boundary | Owns distributed failure contracts |

## Anti-patterns

| Anti-pattern | Symptom | EKP stance |
|--------------|---------|------------|
| **Catch everything and ignore** | Empty or log-only catch; operation continues | Violates EKP-EH02, EKP-EH10 |
| **Generic error everywhere** | Single `INTERNAL_ERROR` for all failures | Violates EKP-EH09; obscures diagnosis |
| **Leaking provider errors** | SQL/HTTP/SDK text in API response | Violates EKP-EH08 |
| **Errors as business flow** | `throw` for expected branch | Violates EKP-EH05 |
| **Retry without ownership** | Retry loop with no idempotency check | Violates EKP-EH06; see EKP-LB12 |
| **Boolean success only** | `{ success: false }` with no code | Violates EKP-P07, EKP-EH02 |
| **Defensive default mask** | Return `0` or `[]` on any failure | Silent corruption risk |

## AI Decision Flow

Canonical sequence for Cursor, Claude, Google Gravity, and future EKP adapters.

```
1. What failure type is this (taxonomy)?
   → Classify: validation, business, infrastructure, integration, defect.
   → EH-AI-01: Do not suggest handling without classification. Stop if unknown.

2. Is this expected or unexpected (EKP-EH01)?
   → Expected: explicit rejection path with stable contract.
   → Unexpected: fail visibly; do not normalize to success.

3. Is this the correct boundary to handle it (EKP-EH04)?
   → NO: Move handling to delivery/application/infrastructure edge.
   → YES: continue.

4. Does handling preserve context without leaking detail (EKP-EH03, EKP-EH08)?
   → NO: Fix mapping before adding catch blocks.

5. Does the change alter a public error contract (EKP-EH07)?
   → YES: Flag breaking change; EH-AI-03: preserve existing contracts unless requested.

6. Is retry, fallback, or circuit-breaking required?
   → YES: Verify ownership (EKP-EH06) and idempotency (EKP-LB12).
   → Cross-service: escalate to architecture—do not invent local retry policy.

7. Is a new abstraction introduced only for errors?
   → EH-AI-04: Reject unless variation or test seam justifies (EKP-DP01).

8. Does recurring failure indicate architectural defect (EKP-EH12)?
   → YES: EH-AI-05: Propose boundary/contract fix—not deeper catch.
```

**Adapter rules:**

| ID | Rule |
|----|------|
| **EH-AI-01** | Identify failure type before suggesting handling. |
| **EH-AI-02** | Do not add generic exception handling without evidence of unhandled failure class. |
| **EH-AI-03** | Preserve existing error contracts; flag breaking changes explicitly. |
| **EH-AI-04** | Do not introduce abstraction layers only for error routing. |
| **EH-AI-05** | Escalate architectural and cross-service failures to EKP-LB / ADR. |

## Review signals

| Signal | Verdict | Concept |
|--------|---------|---------|
| Failure type clear; boundary owner explicit; context preserved internally | Good error handling | EKP-EH01, EKP-EH04, EKP-EH03 |
| Stable outward codes; actionable validation messages | Good contracts | EKP-EH07, EKP-EH09 |
| Empty catch; success returned after failure | Swallowed error | EKP-EH02, EKP-EH10 |
| Production debug requires guessing which branch failed | Poor context | EKP-EH03 |
| Raw provider message in API | Leak | EKP-EH08 |
| `catch (Exception)` at controller returning 200 | Catch-all anti-pattern | EKP-EH10 |
| Retry on non-idempotent write without ADR | Ownership failure | EKP-EH06, EKP-EH11 |
| Unclear function name in error branch only | Hygiene issue | EKP-CC01 (`clean-code.md`) |

## Trade-offs

Explicit failure handling improves reliability and debuggability. It is not free.

| Benefit | Cost |
|---------|------|
| Visible failures reduce silent corruption (**EKP-P07**) | More types, branches, and tests |
| Stable contracts enable integrator trust | Versioning overhead |
| Actionable errors improve UX | Careful message design; localization |
| Shared vocabulary (EKP-EH) for review | Learning curve; over-engineering risk in small scripts |

**When this document is insufficient:**

- Readable error branch structure → `clean-code.md` (EKP-CC)
- Class ownership of handlers → `solid.md` (EKP-SL)
- Cross-service error codes and idempotency → `layering-and-boundaries.md` (EKP-LB)
- Safe migration of error paths → `refactoring.md` (EKP-RF)
- Logging setup, log aggregation → `devops/`, stack domains
- Framework exception hierarchy → `symfony/`, `typescript/`, etc.

## Knowledge graph position

| Field | Value |
|-------|-------|
| `role` | `practice` |
| `depends_on` | `engineering-principles.md` |
| `implements` | EKP-P07 |
| `concept_ids` | EKP-EH01–EKP-EH12 |
| `adapter_priority` | high — AI Decision Flow |
| Siblings | `clean-code.md`, `solid.md` (practices); `design-patterns.md` (pattern); `refactoring.md` (procedure) |
| Escalation | `layering-and-boundaries.md` (distributed contracts) |

```
engineering-principles
        │
        ├── error-handling (practice) ◄── this document
        ├── clean-code (practice)
        ├── solid (practice)
        ├── design-patterns (pattern)
        └── refactoring (procedure)
```

## Related

- [Engineering Principles](engineering-principles.md) — EKP-P01–P10 foundation
- [Clean Code](clean-code.md) — readable error paths (EKP-CC)
- [SOLID](solid.md) — responsibility ownership (EKP-SL)
- [Design Patterns](design-patterns.md) — structural organization of handlers (EKP-DP)
- [Refactoring](refactoring.md) — safe migration of error paths (EKP-RF)
- [Testing](../testing/testing.md) — failure behavior verification (EKP-TS)
- [Layering and Boundaries](../architecture/layering-and-boundaries.md) — cross-service failure contracts (EKP-LB)
- [ADR-0004: Knowledge graph layering](../architecture/decisions/adr-0004-clean-code-position-in-knowledge-graph.md)
- [Architecture decision records](../architecture/decisions/README.md)
- [Engineering domain index](README.md)
