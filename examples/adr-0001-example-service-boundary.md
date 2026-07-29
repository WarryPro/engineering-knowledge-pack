# ADR-0001: Example — Service boundary for order notifications

> **Educational example only.** This file lives in `examples/` to demonstrate ADR format. It is **not** a canonical EKP project decision. For the ADR process, see [`knowledge/architecture/adr-practices.md`](../knowledge/architecture/adr-practices.md).

## Status

Accepted (example)

## Date

2026-07-30

## Context

An e-commerce monolith sends order confirmation emails inline during the checkout HTTP request. Latency p95 increased when the email provider slowed down. The team must decide whether to extract a notification component or keep email inline with async handoff.

**Constraints:**

- Checkout must remain reliable if email fails.
- Team size: 4 engineers, single deployable today.
- No message broker in production yet.

## Decision

Keep the monolith deployable. Introduce an **outbox table** and a background worker within the same codebase to send emails asynchronously. Do **not** split a separate notification microservice until independent scaling or team ownership is required.

## Rationale

- Blast radius of email failure is isolated without new network boundary (**EKP-P02** proportionality).
- Outbox pattern provides retry without broker operational cost today.
- Service extraction would add deployment and contract overhead without current scaling need (**EKP-LB02**).

## Alternatives considered

### Separate notification microservice

Rejected for now — operational overhead exceeds benefit at current scale. Revisit if email volume requires independent scaling (document in new ADR).

### Continue synchronous email in request

Rejected — couples checkout latency to third-party SLA.

## Consequences

### Positive

- Checkout p95 decoupled from email provider latency.
- Retry logic centralized in worker.

### Negative

- Additional table and worker process to maintain.
- Eventual consistency for "email sent" state.

### Risks

- Worker failure delays notifications — requires monitoring and dead-letter handling.

## Compliance

- Integration tests cover outbox enqueue on checkout.
- Architecture review uses [`checklists/architecture-review.md`](checklists/architecture-review.md).

## Related

- [`adr-practices.md`](../knowledge/architecture/adr-practices.md) — EKP-AD
- [`layering-and-boundaries.md`](../knowledge/architecture/layering-and-boundaries.md) — EKP-LB02
- [`integration-patterns.md`](../knowledge/architecture/integration-patterns.md) — EKP-IN01
