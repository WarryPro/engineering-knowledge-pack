---
title: Performance Mindset
domain: performance
tags: [performance, measurement, optimization, caching, bottlenecks, slos]
severity: recommended
applies_to: [backend, frontend, api, mobile]
type: guide
role: practice
depends_on:
  - knowledge/engineering/engineering-principles.md
implements:
  - EKP-P02
  - EKP-P08
related:
  - knowledge/engineering/engineering-principles.md
  - knowledge/engineering/clean-code.md
  - knowledge/testing/testing.md
  - knowledge/performance/performance-mindset.md
  - knowledge/performance/README.md
extends: []
concept_ids: [EKP-PM01, EKP-PM02, EKP-PM03, EKP-PM04, EKP-PM05, EKP-PM06, EKP-PM07]
adapter_priority: medium
---

# Performance Mindset

## Summary

Stack-agnostic **practice-layer** guidance for evidence-based performance work: measure before optimizing, define targets and trade-offs, find real bottlenecks, and know when *not* to optimize. This document operationalizes **EKP-P08** (Evidence before optimization) and **EKP-P02** (Proportionality).

Apply during design review, implementation of latency-sensitive paths, and when performance regressions are reported. Relax per **EKP-P02** for throwaway prototypes, cold code paths, and changes with no measurable user or cost impact.

This document does not teach profiling tool configuration, database index design, infrastructure autoscaling, or micro-benchmark techniques.

## Context

Performance work fails in two predictable ways: optimizing without measurement (wasted complexity) and never optimizing despite clear evidence (user pain, runaway cost). AI assistants often suggest premature caching, async layers, or micro-optimizations without profiling data—or ignore obvious bottlenecks because the prompt did not mention latency.

[Engineering Principles](../engineering/engineering-principles.md) state *why* evidence precedes optimization (**EKP-P08**). This document defines *how* to apply that judgment proportionally (**EKP-P02**). Every concept traces to an **EKP-PM** ID.

**Boundaries:**

| Concern | Owner document / domain | This document |
|---------|-------------------------|---------------|
| Performance mindset and measurement-first approach | **this document** (EKP-PM) | Primary content |
| Hot-path readability exceptions | `clean-code.md` (EKP-CC) | Cross-reference — document exceptions |
| Verification of behavior after optimization | `testing.md` (EKP-TS) | Related — tests guard regressions |
| Database index and query design | `database/` | Out of scope |
| Load/stress test execution | `performance/` (future), `devops/` | Out of scope |
| Infrastructure scaling, CDN, caching infra | `devops/` | Out of scope |
| Framework-specific optimizations | Stack domains | Out of scope |
| Logging and tracing for diagnosis | `logging-and-observability.md` (EKP-LO) | Complementary |

**Out of scope:** JVM tuning flags, GPU kernel optimization, kernel-level profiling, capacity planning spreadsheets, vendor APM setup tutorials.

## EKP layer positioning

| Layer | Role | Example documents | This document |
|-------|------|-------------------|---------------|
| **Principles** | Why — value judgments | `engineering-principles.md` (EKP-P01–P10) | Implements EKP-P08, EKP-P02 |
| **Practices** | What good performance judgment looks like | **this document** (EKP-PM), `clean-code.md` | Primary content |
| **Architecture** | System structure | `layering-and-boundaries.md` | Escalation when bottleneck is architectural |
| **Testing** | Verification | `testing.md` (EKP-TS) | Tests prove optimization did not break behavior |

Performance is a **practice-layer** artifact in the `performance` domain.

## Guidance

### EKP-PM01: Measure before optimizing

**Implements:** EKP-P08

**Intent:** Do not change code for performance without data showing a problem exists in the relevant path.

**Rules:**

- State what is slow or expensive: endpoint, query, render, batch job—not "the app feels slow."
- Use profiling, tracing, or metrics appropriate to the stack before rewriting logic.
- One measurement cycle per hypothesis; avoid changing ten things at once.
- If you cannot measure, define how you will know the optimization worked.

**Good:** "p95 checkout latency 2.4s; flame graph shows N+1 query in OrderRepository."

**Bad:** "Added Redis cache because performance is important."

**Review signals:** Optimization PR with no before/after metric; cache layer with no hit-rate observation.

---

### EKP-PM02: Define target and acceptable trade-off

**Implements:** EKP-P08, EKP-P02

**Intent:** Performance work needs a goal and a budget for complexity—not "as fast as possible."

**Rules:**

- State target: p95 latency, throughput, memory ceiling, cost per request.
- State acceptable trade-off: added complexity, cache staleness, operational burden.
- Match investment to blast radius: checkout path vs admin report generator (**EKP-P02**).
- "Faster" without a number is not a requirement.

**Good:** "Reduce p95 from 800ms to 400ms; accept 5-minute cache TTL on product catalog."

**Bad:** "Make it faster" with no metric and unbounded scope.

**Review signals:** Large refactor for 10ms gain on unused endpoint; no documented target.

---

### EKP-PM03: Optimize the bottleneck

**Implements:** EKP-P08

**Intent:** Improve the constraint that limits the system—not the code that is easiest to rewrite.

**Rules:**

- Identify the slowest step in the critical path (Amdahl's law applies).
- Fixing non-bottlenecks yields diminishing returns.
- Consider I/O, network, serialization, and algorithmic complexity before micro-optimizing loops.
- Re-measure after each change to confirm the bottleneck moved.

**Good:** Batch database queries after profiling showed 40 round-trips per request.

**Bad:** Rewrote sorting algorithm while network call to payment gateway dominates latency.

**Review signals:** CPU micro-optimization while DB query takes 95% of time; optimization without post-change profile.

---

### EKP-PM04: When not to optimize

**Implements:** EKP-P02, EKP-P08

**Intent:** Proportional engineering includes *declining* optimization when cost exceeds benefit.

**Do not optimize when:**

- Code path is cold, admin-only, or batch with generous SLA.
- Prototype or spike with documented discard date (**EKP-P02**).
- Measured impact is below user perception threshold and cost is negligible.
- Optimization would harm readability without measured hot-path justification (**EKP-CC** documents exceptions).
- Problem is architectural (chatty services, missing index strategy)—escalate to `layering-and-boundaries.md` or `database/` instead of local hacks.

**Good:** "Admin export runs once daily; 30s acceptable; deferred."

**Bad:** Distributed cache for static config read once at startup.

**Review signals:** Premature async/parallel complexity on trivial CRUD; optimization during feature rush without ticket.

---

### EKP-PM05: Caching as a deliberate trade-off

**Implements:** EKP-P08, EKP-P09

**Intent:** Caching trades freshness and complexity for speed—apply only when measurement justifies it.

**Rules:**

- Cache only after identifying repeated expensive reads with acceptable staleness.
- Define invalidation strategy before adding cache—not after production surprises.
- Prefer simplest cache scope: in-process → shared → CDN; escalate complexity only with evidence.
- Monitor hit rate and stale-read incidents; remove cache that does not earn its keep.

**Good:** Product catalog cached 5 minutes with explicit invalidation on admin update.

**Bad:** Cache everything by default; no TTL or invalidation documented.

**Review signals:** Cache with no metrics; stale data bugs; cache key explosion.

---

### EKP-PM06: Performance budgets and SLO awareness

**Implements:** EKP-P08

**Intent:** Teams that care about performance define budgets before breaches become emergencies.

**Rules:**

- Critical user journeys should have informal or formal budgets (latency, error rate, payload size).
- Regressions: compare against baseline in CI or synthetic checks where feasible—not only production firefighting.
- Budget violation triggers investigation, not automatic rewrite—find bottleneck first (**EKP-PM03**).
- SLO definition and error budgets are architecture/ops concerns; this concept covers *awareness* at code level.

**Good:** PR notes "adds 50ms to search p95; within 200ms budget."

**Bad:** Each release degrades latency 10% until users complain.

**Review signals:** No baseline; performance discussed only after outage.

---

### EKP-PM07: Performance review signals

**Implements:** EKP-P02, EKP-P08

**Intent:** Recognize when performance work is warranted vs cargo-cult optimization.

| Signal | Verdict | Concept |
|--------|---------|---------|
| Profile data identifies bottleneck; target stated; tests pass | Good optimization | EKP-PM01, EKP-PM02, EKP-PM03 |
| Cache with invalidation and metrics | Good caching | EKP-PM05 |
| Optimization without measurement | Premature | EKP-PM01, EKP-PM04 |
| Micro-optimization on cold path | Disproportionate | EKP-PM04, EKP-P02 |
| Latency fix requires new service boundary | Escalate architecture | EKP-LB |

## When not to apply

Skip formal performance analysis when **all** apply:

- Change does not touch latency-sensitive path, data volume, or resource consumption.
- Prototype with no production path and documented discard (**EKP-P02**).
- Existing measurements show headroom orders of magnitude above requirement.

**Still apply:** Do not add gratuitous I/O, unbounded loops, or N+1 queries even in prototypes if the pattern would be copied to production.

## Trade-offs

| Benefit | Cost |
|---------|------|
| Measurement prevents wasted optimization (**EKP-P08**) | Profiling and instrumentation time |
| Clear targets align team effort (**EKP-PM02**) | Upfront requirement discipline |
| Bottleneck focus maximizes impact (**EKP-PM03**) | May require cross-team fixes |
| Proportional non-optimization preserves simplicity (**EKP-P02**) | Requires judgment in review |
| Caching improves hot paths (**EKP-PM05**) | Staleness bugs, operational complexity |

**When this document is insufficient:**

- Readable hot-path code trade-offs → `clean-code.md` (EKP-CC)
- Test strategy for regressions → `testing.md` (EKP-TS)
- Schema and query design → `database/`
- Load testing and capacity → `devops/`, future performance guides
- Distributed tracing setup → `logging-and-observability.md` (EKP-LO), `devops/`

## Knowledge graph position

| Field | Value |
|-------|-------|
| `role` | `practice` |
| `depends_on` | `engineering-principles.md` |
| `implements` | EKP-P02, EKP-P08 |
| `concept_ids` | EKP-PM01–EKP-PM07 |
| `adapter_priority` | medium |

## Related

- [Engineering Principles](../engineering/engineering-principles.md) — EKP-P08, EKP-P02
- [Clean Code](../engineering/clean-code.md) — hot-path readability exceptions (EKP-CC)
- [Testing](../testing/testing.md) — regression verification (EKP-TS)
- [Performance domain index](README.md)
