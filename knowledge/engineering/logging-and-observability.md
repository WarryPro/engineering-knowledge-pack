---
title: Logging and Observability
domain: engineering
tags: [logging, observability, correlation, debugging, metrics, tracing]
severity: recommended
applies_to: [backend, frontend, api, mobile, devops]
type: guide
role: practice
depends_on:
  - knowledge/engineering/engineering-principles.md
implements:
  - EKP-P04
  - EKP-P07
related:
  - knowledge/engineering/engineering-principles.md
  - knowledge/engineering/error-handling.md
  - knowledge/security/security-fundamentals.md
  - knowledge/performance/performance-mindset.md
  - knowledge/engineering/README.md
extends: []
concept_ids: [EKP-LO01, EKP-LO02, EKP-LO03, EKP-LO04, EKP-LO05, EKP-LO06, EKP-LO07, EKP-LO08]
adapter_priority: medium
---

# Logging and Observability

## Summary

Stack-agnostic **practice-layer** guidance for application-level logging and observability signals: structured logs, correlation identifiers, proportional log levels, and what to record (or avoid recording) for operability. This document operationalizes **EKP-P07** (Fail fast and visibly) and **EKP-P04** (Explicit over implicit) for runtime visibility.

Apply during implementation of services, APIs, background jobs, and error paths. Relax per **EKP-P02** (Proportionality) for local scripts and throwaway spikes with no production observability requirement.

This document does not teach log aggregator setup, Prometheus/Grafana configuration, OpenTelemetry wiring, or alerting runbooks—that belongs in `devops/` and stack domains.

## Context

When failures occur, teams need to reconstruct what happened without guessing. Error handling defines *how* failures are represented; logging defines *what evidence* is preserved for operators and developers. Silent or unstructured logs turn production incidents into archaeology.

[Engineering Principles](engineering-principles.md) require visible failure and correlation across boundaries (**EKP-P07**). [Error Handling](error-handling.md) owns failure semantics—this document owns the **operational record** of runtime behavior without duplicating error taxonomy or catch-block design.

**Boundaries:**

| Concern | Owner document / domain | This document |
|---------|-------------------------|---------------|
| Application logging and correlation context | **this document** (EKP-LO) | Primary content |
| Failure semantics and error contracts | `error-handling.md` (EKP-EH) | Complementary — log errors, do not redefine |
| PII, secrets, and security-sensitive log content | `security-fundamentals.md` (EKP-SF04) | Cross-reference — never duplicate EKP-AI08 |
| Performance measurement and bottlenecks | `performance-mindset.md` (EKP-PM) | Related — metrics inform optimization |
| Log shipping, retention, dashboards, alerting | `devops/` | Out of scope |
| Distributed tracing SDK configuration | `devops/`, stack domains | Out of scope |
| API boundary validation | `layering-and-boundaries.md` (EKP-LB) | Out of scope |

**Out of scope:** log4j/xml config tutorials, ELK stack setup, Sentry/Datadog account configuration, SIEM rules, log-based billing optimization.

## EKP layer positioning

| Layer | Role | Example documents | This document |
|-------|------|-------------------|---------------|
| **Principles** | Why — value judgments | `engineering-principles.md` (EKP-P01–P10) | Implements EKP-P07, EKP-P04 |
| **Practices** | What good observability looks like | **this document** (EKP-LO), `error-handling.md` | Primary content |
| **Security** | Sensitive data handling | `security-fundamentals.md` (EKP-SF) | PII/secrets in logs |
| **DevOps** | Infrastructure observability | `devops/` | Escalation for platform tooling |

Logging completes the cross-cutting chain: **error-handling → logging → security boundaries → devops infrastructure**.

## Guidance

### EKP-LO01: Logs are operational signals

**Implements:** EKP-P07

**Intent:** Logs exist to answer operational questions after the fact—not to narrate every line of execution.

**Rules:**

- Each log line should help answer: *what happened, in what context, with what outcome?*
- Log at decision points: request received, external call made, business rule rejected, job completed/failed.
- Avoid noise that drowns signal—high-volume debug in production hides incidents.
- Logs complement errors: an handled error should still leave a trace when diagnosis may be needed.

**Good:** `order_id=12345 payment_declined reason=insufficient_funds`.

**Bad:** `Entering function processOrder` on every call in production.

**Review signals:** Log volume grows 10× per release; on-call cannot find failure in flood of debug.

---

### EKP-LO02: Structured logging

**Implements:** EKP-P04

**Intent:** Machine-parseable fields enable search, aggregation, and correlation—free-text-only logs do not scale.

**Rules:**

- Prefer key=value or JSON fields over prose-only messages.
- Use consistent field names across services: `request_id`, `user_id`, `order_id`, `duration_ms`.
- Include outcome: `status=success|failure`, `error_code` when applicable.
- Human-readable message is optional supplement—not the only payload.

**Good:** `{"event":"payment_processed","order_id":"12345","duration_ms":142,"status":"success"}`.

**Bad:** `Payment done for order 12345 took a while`.

**Review signals:** Regex required to parse logs; same concept named `userId` and `user_id` across files.

---

### EKP-LO03: Correlation identifiers

**Implements:** EKP-P07

**Intent:** Trace a single user action or request across components, threads, and services.

**Rules:**

- Generate or propagate a correlation ID at the entry boundary (HTTP header, message metadata).
- Include correlation ID in every log line for that request/job context.
- Pass correlation ID to downstream HTTP calls and queue messages.
- Do not invent a new ID per internal function call—reuse the inbound context.

**Good:** `X-Request-Id: abc-123` propagated through API → worker → email service logs.

**Bad:** Each microservice logs with only its own internal counter; incident spans three opaque traces.

**Review signals:** Cannot link API 500 to background job failure; missing ID on async handoff.

---

### EKP-LO04: Log levels and proportionality

**Implements:** EKP-P02, EKP-P07

**Intent:** Severity levels encode urgency—use them consistently and proportionally.

**Rules:**

| Level | Use for |
|-------|---------|
| **ERROR** | Operation failed; user impact or data risk; needs attention |
| **WARN** | Recoverable anomaly, deprecation, retry succeeded |
| **INFO** | Significant business/ops events (start/stop, completion) |
| **DEBUG** | Development diagnosis—off or sampled in production (**EKP-P02**) |

- ERROR should mean something actionable—not routine validation failures logged as errors.
- Match verbosity to environment: local debug OK; production lean unless incident.
- Scripts and prototypes may use console output only (**EKP-P02**).

**Good:** Validation failure → INFO or WARN with code; unhandled DB connection loss → ERROR.

**Bad:** Every 404 logged as ERROR; DEBUG enabled globally in production.

**Review signals:** Alert fatigue from ERROR spam; zero logs on critical failure path.

---

### EKP-LO05: What to log and what never to log

**Implements:** EKP-P07

**Intent:** Logs are often exported, indexed, and retained—treat them as a data store with security implications.

**Rules:**

- **Never log:** passwords, API keys, tokens, full credit card numbers, session secrets (**EKP-SF04**, **EKP-AI08**).
- **Avoid or redact:** full PII unless required for audit with retention policy (email, phone, government ID).
- **Do log:** correlation ID, error codes, stable identifiers, duration, outcome, sanitized context.
- When logging errors, include type/code internally—do not duplicate public leak rules from **EKP-EH08**; cite error-handling for outward messages.

**Good:** `auth_failed user_id=42 reason=invalid_token` (token value not logged).

**Bad:** `login failed password=secret123`.

**Review signals:** Secrets in log aggregation; GDPR exposure from verbose request body logging.

---

### EKP-LO06: Logs, metrics, and traces

**Implements:** EKP-P08

**Intent:** Three complementary signals—know which tool answers which question.

**Rules:**

| Signal | Answers | This document |
|--------|---------|---------------|
| **Logs** | What happened on this instance, with detail | Primary |
| **Metrics** | Aggregated rates, latency percentiles, saturation | Awareness—instrumentation in `devops/` |
| **Traces** | Cross-service path and span timing | Awareness—correlation ID is the bridge |

- Use logs for diagnosable events; use metrics for SLO dashboards (**EKP-PM06**).
- Correlation ID should appear in logs and trace spans when tracing is enabled.
- Do not log the same counter every request instead of emitting a metric—use the right signal.

**Good:** Metric for `http_requests_total`; log line only on anomaly or sampled debug.

**Bad:** Count requests by parsing gigabytes of INFO logs nightly.

**Review signals:** No metrics on critical path; only logs, no aggregation possible.

---

### EKP-LO07: Context preservation for debugging

**Implements:** EKP-P07, EKP-P04

**Intent:** When something fails, logs must contain enough context to reproduce or narrow the cause—without dumping entire payloads.

**Rules:**

- On failure, log: operation name, identifiers, error code/type, correlation ID, relevant parameters (sanitized).
- On external call failure, log: dependency name, latency, HTTP status or error class—not full response body if sensitive.
- Align with **EKP-EH03** (preserve internal context)—logging is how context survives async and production.
- Avoid logging full request/response bodies by default; opt in for debug sessions only.

**Good:** `external_call service=payment_gateway status=503 duration_ms=3001 correlation_id=abc-123`.

**Bad:** `something failed` with no IDs.

**Review signals:** Production bug requires redeploy with println to diagnose; logs missing order ID on failure.

---

### EKP-LO08: Logging review signals

**Implements:** EKP-P02

**Intent:** Recognize good operability vs log debt.

| Signal | Verdict | Concept |
|--------|---------|---------|
| Structured fields; correlation ID present; secrets absent | Good logging | EKP-LO02, EKP-LO03, EKP-LO05 |
| ERROR on true failures only; actionable context | Good levels | EKP-LO04, EKP-LO07 |
| Secrets or PII in log statements | Security defect | EKP-LO05, EKP-SF04 |
| DEBUG flood in production | Disproportionate | EKP-LO04, EKP-P02 |
| New error path with no log trace | Visibility gap | EKP-LO01, EKP-EH |

## When not to apply

Skip formal structured logging when **all** apply:

- Local one-off script with no production path and documented discard (**EKP-P02**).
- No network, no persistence, no operator other than the author.
- Output is sufficient via stdout for the task lifespan.

**Still apply:** Never log secrets (**EKP-SF04**, **EKP-AI08**) even in local scripts.

## Trade-offs

| Benefit | Cost |
|---------|------|
| Faster incident diagnosis (**EKP-P07**) | Log volume and storage cost |
| Structured fields enable search (**EKP-P04**) | Discipline in field naming |
| Correlation across services | Propagation plumbing in code |
| Security-aware logging reduces breach impact | Redaction logic and review |
| Right signal type (log vs metric) (**EKP-LO06**) | Multiple instrumentation paths |

**When this document is insufficient:**

- Error taxonomy and catch-block design → `error-handling.md` (EKP-EH)
- Secrets and PII policy → `security-fundamentals.md` (EKP-SF)
- Performance targets and profiling → `performance-mindset.md` (EKP-PM)
- Log aggregation, retention, alerting → `devops/`
- Framework logger configuration → stack domains

## Knowledge graph position

| Field | Value |
|-------|-------|
| `role` | `practice` |
| `depends_on` | `engineering-principles.md` |
| `implements` | EKP-P04, EKP-P07 |
| `concept_ids` | EKP-LO01–EKP-LO08 |
| `adapter_priority` | medium |
| Chain | error-handling → **logging** → security → devops |

## Related

- [Engineering Principles](engineering-principles.md) — EKP-P04, EKP-P07
- [Error Handling](error-handling.md) — failure semantics (EKP-EH)
- [Security Fundamentals](../security/security-fundamentals.md) — secrets and PII (EKP-SF)
- [Performance Mindset](../performance/performance-mindset.md) — measurement (EKP-PM)
- [Engineering domain index](README.md)
