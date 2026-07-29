# Review Checklist: Architecture

> **Example checklist** — educational artifact in `examples/`. For production reviews, copy and adapt. Knowledge sources: EKP-LB, EKP-AD.

**Applies to:** Pull requests and design reviews that change system structure, boundaries, or integration contracts.

## Instructions

Mark each item pass, fail, or N/A. Link findings to EKP concept IDs where helpful.

---

## Boundary and layering (EKP-LB)

| # | Criterion | Severity | Pass | Fail | N/A |
|---|-----------|----------|------|------|-----|
| 1.1 | Change justified for lifespan and blast radius (EKP-LB01, EKP-LB02) | required | [ ] | [ ] | [ ] |
| 1.2 | Dependency direction respected (EKP-LB05) | required | [ ] | [ ] | [ ] |
| 1.3 | Contract owner identified for cross-team/service changes (EKP-LB08) | required | [ ] | [ ] | [ ] |
| 1.4 | Validation at trust boundary, not deep in domain (EKP-LB09) | recommended | [ ] | [ ] | [ ] |
| 1.5 | Idempotency considered for mutating integrations (EKP-LB12) | recommended | [ ] | [ ] | [ ] |

**Knowledge:** [layering-and-boundaries.md](../../knowledge/architecture/layering-and-boundaries.md)

## Governance (EKP-AD)

| # | Criterion | Severity | Pass | Fail | N/A |
|---|-----------|----------|------|------|-----|
| 2.1 | Level 4 / one-way door changes have ADR or draft (EKP-AD01, EKP-RF07) | required | [ ] | [ ] | [ ] |
| 2.2 | ADR lists alternatives and consequences if new decision (EKP-AD03) | recommended | [ ] | [ ] | [ ] |

**Knowledge:** [adr-practices.md](../../knowledge/architecture/adr-practices.md)

## Module structure (EKP-MC)

| # | Criterion | Severity | Pass | Fail | N/A |
|---|-----------|----------|------|------|-----|
| 3.1 | No new circular package dependencies (EKP-MC04) | recommended | [ ] | [ ] | [ ] |
| 3.2 | Extraction justified — not premature microservice (EKP-MC06) | recommended | [ ] | [ ] | [ ] |

**Knowledge:** [coupling-and-cohesion.md](../../knowledge/architecture/coupling-and-cohesion.md)

---

## Reviewer notes

| Field | Value |
|-------|-------|
| Reviewer | |
| Date | |
| PR / artifact | |
| Overall result | Approved / Changes requested / Rejected |

### Findings

### Follow-up actions
