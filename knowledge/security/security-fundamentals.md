---
title: Security Fundamentals
domain: security
tags: [security, validation, authentication, authorization, secrets, blast-radius]
severity: recommended
applies_to: [backend, frontend, api, mobile]
type: guide
role: practice
depends_on:
  - knowledge/engineering/engineering-principles.md
implements:
  - EKP-P02
  - EKP-P06
  - EKP-P07
related:
  - knowledge/engineering/engineering-principles.md
  - knowledge/engineering/error-handling.md
  - knowledge/architecture/layering-and-boundaries.md
  - knowledge/ai/ai-assisted-development.md
  - knowledge/engineering/logging-and-observability.md
  - knowledge/security/README.md
extends: []
concept_ids: [EKP-SF01, EKP-SF02, EKP-SF03, EKP-SF04, EKP-SF05, EKP-SF06, EKP-SF07, EKP-SF08]
adapter_priority: high
---

# Security Fundamentals

## Summary

Stack-agnostic **practice-layer** guidance for security-minded engineering: blast-radius awareness, trust boundaries, least privilege, authentication vs authorization, safe defaults, and dependency risk. This document operationalizes **EKP-P02** (Proportionality), **EKP-P06** (Own the boundary), and **EKP-P07** (Fail fast and visibly) for security-sensitive decisions.

Apply during design, implementation, and code review when data, identity, payments, or external trust is involved. Relax per **EKP-P02** for throwaway prototypes with no real users, data, or network exposure—and document the exception.

This is **not** an exhaustive security handbook, threat-modeling tutorial, or compliance framework. It defines *how to think* about security proportionally—not how to configure WAF rules, IAM policies, or framework security bundles.

## Context

Security failures compound silently: leaked credentials, missing authorization checks, and trust placed in unvalidated input are among the highest blast-radius defects in production systems. AI-assisted development amplifies this risk—assistants generate plausible but insecure patterns (hardcoded secrets, missing authz, over-broad permissions) unless explicitly constrained.

[Engineering Principles](../engineering/engineering-principles.md) define *why* boundaries and visible failure matter. This document defines *how* to apply security judgment at the practice layer. Every concept traces to an **EKP-SF** ID.

**Boundaries:**

| Concern | Owner document / domain | This document |
|---------|-------------------------|---------------|
| Security mindset and proportional controls | **this document** (EKP-SF) | Primary content |
| Boundary validation and API contracts | `layering-and-boundaries.md` (EKP-LB09) | Escalation — do not duplicate |
| Failure semantics and error contracts | `error-handling.md` (EKP-EH) | Complementary — security errors are failures |
| Secrets in AI prompts and generated code | `ai-assisted-development.md` (EKP-AI08) | Reference only — do not restate |
| Application logging and PII in logs | [logging-and-observability.md](../engineering/logging-and-observability.md) (EKP-LO) | Cross-reference |
| Framework security config (Symfony, OAuth libs) | Stack domains | Out of scope |
| Infrastructure hardening, WAF, network segmentation | `devops/` | Out of scope |
| Threat modeling workshops, compliance (SOC2, PCI) | ADRs, security team process | Out of scope |
| Penetration testing and security test suites | `security/` (future), `testing/` | Out of scope |

**Out of scope:** OWASP encyclopedic coverage, CVE database tooling, SIEM configuration, encryption algorithm selection tutorials, incident response runbooks.

## EKP layer positioning

| Layer | Role | Example documents | This document |
|-------|------|-------------------|---------------|
| **Principles** | Why — value judgments | `engineering-principles.md` (EKP-P01–P10) | Implements EKP-P02, EKP-P06, EKP-P07 |
| **Practices** | What good security judgment looks like | **this document** (EKP-SF), `error-handling.md` | Primary content |
| **Architecture** | System boundaries | `layering-and-boundaries.md` (EKP-LB) | Escalation for boundary contracts |
| **AI orchestration** | AI workflow gates | `ai-assisted-development.md` (EKP-AI08) | EKP-AI08 = secrets minimum bar |

Security is a **practice-layer** artifact in the `security` domain. Adapters should extract the **AI Decision Flow** as a high-priority routing constraint when security-sensitive change is detected.

## Guidance

### EKP-SF01: Security is blast-radius management

**Implements:** EKP-P02, EKP-P06

**Intent:** Security effort should match data sensitivity, exposure surface, and reversibility of failure—not every line of code needs enterprise-grade controls.

**Rules:**

- Classify the asset: public data, internal-only, PII, credentials, financial, regulated.
- Classify the exposure: local script, internal API, public internet, third-party integration.
- High blast radius (auth, payment, PII, production data) warrants stricter controls and human review (**EKP-AI07**).
- Low blast radius (local throwaway spike) may accept reduced ceremony with documented lifespan (**EKP-P02**).

**Good:** Internal admin tool behind VPN with audit log for sensitive actions.

**Bad:** Same auth model applied to a one-hour prototype and a payment API without distinction.

**Review signals:** Security controls absent on high-blast-radius paths; enterprise ceremony on discarded spike code.

---

### EKP-SF02: Validate at trust boundaries

**Implements:** EKP-P06

**Intent:** Never trust input that crosses a trust boundary—validate, sanitize, or reject at the edge before it reaches domain logic.

**Rules:**

- Identify trust boundaries: HTTP request, message queue, file upload, third-party webhook, database row from external source.
- Validate shape, type, range, and authorization **before** business logic executes.
- Boundary validation mechanics and API contract design → `layering-and-boundaries.md` (EKP-LB09). Cite; do not duplicate.
- Reject invalid input visibly (**EKP-P07**) with stable, non-leaking error contracts (**EKP-EH07**, **EKP-EH08**).

**Good:** Controller validates DTO; domain receives typed, already-validated value object.

**Bad:** Domain service parses raw JSON and hopes callers were careful.

**Review signals:** `request.body` accessed deep in domain; missing validation on "internal" endpoint reachable from network.

---

### EKP-SF03: Least privilege

**Implements:** EKP-P06

**Intent:** Grant the minimum access required for the operation—roles, scopes, database permissions, API tokens, file permissions.

**Rules:**

- Default deny; explicitly grant permissions needed for the task.
- Scope API tokens and service accounts to specific resources and operations.
- Avoid shared superuser credentials across services or environments.
- Periodic review: permissions accumulate; remove unused grants.

**Good:** Read-only DB role for reporting service; write role only on tables it owns.

**Bad:** Application uses `root` database user because "it was easier."

**Review signals:** New feature adds broad `admin` role; service account with `*` scope.

---

### EKP-SF04: Secrets are never literals

**Implements:** EKP-P07

**Intent:** Credentials, tokens, and connection strings must not appear in source code, logs, prompts, or chat output.

**Rules:**

- **EKP-AI08 is the authoritative rule for AI-assisted work**—this concept reinforces it for human-authored code.
- Use environment variables, secret managers, or existing project patterns—never hardcode.
- Rotate credentials when exposure is suspected; do not "just remove from the diff."
- Do not commit `.env`, key files, or credential artifacts.

**Good:** `DATABASE_URL` from environment; secret manager reference in deployment config.

**Bad:** API key in source, test fixture, or log statement.

**Review signals:** Literal `sk-`, `password=`, connection strings in diff; secrets echoed in AI chat summaries.

---

### EKP-SF05: Authentication vs authorization

**Implements:** EKP-P06

**Intent:** Authentication proves *who*; authorization proves *what they may do*. Both are required; neither substitutes for the other.

**Rules:**

- Authentication: identity established (login, token, certificate).
- Authorization: permission checked for the specific resource and action.
- Authenticated user ≠ authorized for all resources.
- Check authorization at the boundary or use-case layer—not only at login.
- Changes to authn/authz paths require explicit human approval (**EKP-AI07**).

**Good:** User logged in; endpoint checks `canEditOrder(user, orderId)` before mutation.

**Bad:** "User is logged in" treated as sufficient for delete-all operation.

**Review signals:** Auth middleware added but no per-resource check; role check only at session start.

---

### EKP-SF06: Dependency and supply-chain awareness

**Implements:** EKP-P03

**Intent:** Third-party code is part of your attack surface. Know what you depend on and respond to known vulnerabilities proportionally.

**Rules:**

- Pin dependency versions in production systems; understand what each major dependency does.
- Monitor advisories for direct dependencies on high-blast-radius services.
- Evaluate upgrade vs mitigate vs accept with documented rationale for known CVEs.
- Do not add dependencies to solve problems solvable with stdlib or existing project utilities (**EKP-P02**).

**Good:** CVE in auth library triggers prioritized patch with regression test.

**Bad:** 200 transitive dependencies never reviewed; `npm audit` ignored for years.

**Review signals:** New dependency for trivial utility; critical CVE unaddressed on public-facing service.

---

### EKP-SF07: Fail closed on security decisions

**Implements:** EKP-P07

**Intent:** When security state is unknown or invalid, deny access—do not default to permissive behavior.

**Rules:**

- Missing token, expired session, or failed validation → reject; do not proceed with anonymous elevated access.
- Ambiguous authorization → deny and log (see [logging-and-observability.md](../engineering/logging-and-observability.md) EKP-LO04).
- Security configuration errors should surface at startup or test time—not silently in production.
- Prefer explicit security exceptions over returning empty data that hides denial.

**Good:** Invalid JWT returns 401; middleware rejects before handler runs.

**Bad:** Catch auth exception and continue as guest with write access.

**Review signals:** `catch` block swallows auth failure; optional auth treated as full access.

---

### EKP-SF08: Security review signals

**Implements:** EKP-P02, EKP-P06

**Intent:** Recognize patterns that warrant escalation, deeper review, or ADR—not automatic approval.

**High-signal changes (escalate / require human approval):**

- Authentication or authorization logic modified
- New external integration receiving or sending sensitive data
- Permission model expanded (new roles, broader scopes)
- Cryptographic or session handling changed
- Input validation removed or bypassed
- Secrets handling pattern changed

**Review signals:** Security-sensitive path changed without test update; auth logic in agent-generated diff without discussion.

## When not to apply

Relax or defer full security ceremony when **all** apply:

- Code has documented throwaway lifespan (hours/days) with no real users or data (**EKP-P02**).
- No network exposure, no persistence of sensitive data, no authentication surface.
- Running in isolated local environment with synthetic data only.

**Still apply even in prototypes:** EKP-AI08 (no secrets in code), basic input validation if handling any external input.

Document exceptions in PR description when reviewers might object.

## AI Decision Flow

Canonical sequence for security-sensitive changes. Run after `ai-assisted-development.md` steps 1–3; may run in parallel with error-handling flow when both apply.

```
1. Blast-radius classification (EKP-SF01)
   What data and exposure surface does this change affect?
   → LOW (local, no sensitive data): Apply EKP-AI08 only; proceed with proportionality.
   → HIGH (auth, PII, payment, production): Continue. EKP-AI07 human gate required.

2. Trust boundary identification (EKP-SF02)
   Does input cross a trust boundary?
   → YES: Validate at boundary (EKP-LB09). Do not trust domain to sanitize.
   → NO: Continue.

3. Authn/authz impact (EKP-SF05)
   Does change touch identity or permissions?
   → YES: Stop auto-apply. Require explicit approval (EKP-AI07).
   → NO: Continue.

4. Secrets check (EKP-SF04)
   Could this introduce credentials in code, logs, or output?
   → YES: Apply EKP-AI08. Use env/secret manager patterns only.
   → NO: Continue.

5. Least privilege (EKP-SF03)
   Are new permissions minimal for the stated task?
   → NO: Reduce scope before implementing.
   → YES: Continue.

6. Fail-closed verification (EKP-SF07)
   On invalid/missing security state, does code deny access?
   → NO: Fix before merge.
   → YES: Continue.

7. Dependency impact (EKP-SF06)
   New third-party dependency on security-critical path?
   → YES: Document rationale; check advisories.
   → NO: Done.
```

**Adapter rules:**

| ID | Rule |
|----|------|
| **SF-AI-01** | Classify blast radius before suggesting security controls. |
| **SF-AI-02** | Route boundary validation to EKP-LB09—do not invent local validation policy. |
| **SF-AI-03** | Block auto-apply on authn/authz changes; require EKP-AI07 approval. |
| **SF-AI-04** | Enforce EKP-AI08 for secrets—cite, do not duplicate rules. |
| **SF-AI-05** | Default deny on ambiguous authorization—fail closed. |

## Trade-offs

| Benefit | Cost |
|---------|------|
| Proportional security reduces catastrophic failure (**EKP-P02**, **EKP-P06**) | Analysis time before implementation |
| Boundary validation prevents injection and contract drift | Validation code and test maintenance |
| Least privilege limits breach impact | Permission management overhead |
| Fail-closed prevents silent privilege escalation | Stricter UX on edge cases |
| Supply-chain awareness catches known vulnerabilities | Dependency review and upgrade cycles |

**When this document is insufficient:**

- API boundary contracts and validation placement → `layering-and-boundaries.md` (EKP-LB)
- Error message design and leak prevention → `error-handling.md` (EKP-EH)
- AI secret handling in prompts → `ai-assisted-development.md` (EKP-AI08)
- Logging sensitive data → [logging-and-observability.md](../engineering/logging-and-observability.md) (EKP-LO)
- Framework OAuth, CSRF, CORS config → stack domains
- Infrastructure WAF, TLS termination, IAM → `devops/`

## Knowledge graph position

| Field | Value |
|-------|-------|
| `role` | `practice` |
| `depends_on` | `engineering-principles.md` |
| `implements` | EKP-P02, EKP-P06, EKP-P07 |
| `concept_ids` | EKP-SF01–EKP-SF08 |
| `adapter_priority` | high — AI Decision Flow |
| Escalation | `layering-and-boundaries.md`, `ai-assisted-development.md` (EKP-AI07, EKP-AI08) |

## Related

- [Engineering Principles](../engineering/engineering-principles.md) — EKP-P01–P10 foundation
- [Error Handling](../engineering/error-handling.md) — failure semantics (EKP-EH)
- [Layering and Boundaries](../architecture/layering-and-boundaries.md) — boundary validation (EKP-LB)
- [AI-Assisted Development](../ai/ai-assisted-development.md) — EKP-AI07, EKP-AI08
- [Security domain index](README.md)
