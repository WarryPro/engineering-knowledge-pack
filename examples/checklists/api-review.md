# Review Checklist: HTTP API

> **Example checklist** — educational artifact in `examples/`. Knowledge source: EKP-AP.

**Applies to:** New or changed HTTP endpoints consumed by other teams, clients, or services.

## Instructions

Mark each item pass, fail, or N/A.

---

## Contract design (EKP-AP)

| # | Criterion | Severity | Pass | Fail | N/A |
|---|-----------|----------|------|------|-----|
| 1.1 | API owner identified (EKP-AP01) | required | [ ] | [ ] | [ ] |
| 1.2 | Resources use noun-based paths (EKP-AP02) | required | [ ] | [ ] | [ ] |
| 1.3 | HTTP methods and status codes appropriate (EKP-AP03) | required | [ ] | [ ] | [ ] |
| 1.4 | Request/response shape explicit and evolvable (EKP-AP04) | recommended | [ ] | [ ] | [ ] |
| 1.5 | Breaking changes versioned or migration planned (EKP-AP05) | required | [ ] | [ ] | [ ] |

**Knowledge:** [api-design.md](../../knowledge/architecture/api-design.md)

## Operations (EKP-AP)

| # | Criterion | Severity | Pass | Fail | N/A |
|---|-----------|----------|------|------|-----|
| 2.1 | Pagination/filtering contract defined for list endpoints (EKP-AP06) | recommended | [ ] | [ ] | [ ] |
| 2.2 | Critical mutations support idempotency keys (EKP-AP07) | recommended | [ ] | [ ] | [ ] |
| 2.3 | Error responses stable and non-leaking (EKP-AP08; see EKP-EH) | required | [ ] | [ ] | [ ] |

**Knowledge:** [api-design.md](../../knowledge/architecture/api-design.md), [error-handling.md](../../knowledge/engineering/error-handling.md)

## Security (EKP-SF — cite only)

| # | Criterion | Severity | Pass | Fail | N/A |
|---|-----------|----------|------|------|-----|
| 3.1 | Authn/authz checked per resource (EKP-SF05) | required | [ ] | [ ] | [ ] |
| 3.2 | Input validated at boundary (EKP-LB09, EKP-SF02) | required | [ ] | [ ] | [ ] |

**Knowledge:** [security-fundamentals.md](../../knowledge/security/security-fundamentals.md)

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
