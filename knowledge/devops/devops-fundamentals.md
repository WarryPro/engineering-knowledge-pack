---
title: DevOps Fundamentals
domain: devops
tags: [devops, ci-cd, deployment, infrastructure, observability, reliability]
severity: recommended
applies_to: [backend, frontend, api, devops]
type: guide
role: architecture
depends_on:
  - knowledge/engineering/engineering-principles.md
implements:
  - EKP-P01
  - EKP-P04
  - EKP-P06
  - EKP-P07
  - EKP-P09
  - EKP-P10
related:
  - knowledge/engineering/engineering-principles.md
  - knowledge/engineering/logging-and-observability.md
  - knowledge/engineering/error-handling.md
  - knowledge/security/security-fundamentals.md
  - knowledge/testing/testing.md
  - knowledge/performance/performance-mindset.md
  - knowledge/architecture/layering-and-boundaries.md
  - knowledge/architecture/adr-practices.md
  - knowledge/devops/README.md
extends: []
concept_ids: [EKP-DV01, EKP-DV02, EKP-DV03, EKP-DV04, EKP-DV05, EKP-DV06, EKP-DV07, EKP-DV08]
adapter_priority: high
---

# DevOps Fundamentals

## Summary

Operations-layer guidance for **platform and delivery engineering**: environment boundaries, reproducible deploys, configuration and secrets at the platform edge, CI/CD as policy, platform observability, operational failure planning, infrastructure-as-code decisions, and feedback loops. This document **applies** **EKP-P01**, **EKP-P04**, **EKP-P06**, **EKP-P07**, **EKP-P09**, and **EKP-P10**, and routes to L0 logging, security, testing, and error-handling guides—it does not replace them or teach vendor tool syntax.

Apply when designing or reviewing pipelines, environments, deployment strategy, platform observability, or operational boundaries. Application logging belongs in [`logging-and-observability.md`](../engineering/logging-and-observability.md) (EKP-LO). Relax per **EKP-P02** for personal experiments with documented discard date.

## Context

Operational failures often look like “tooling problems” but originate in missing engineering decisions: shared dev/prod data, non-reproducible builds, secrets in repositories, CI that does not gate merges, and observability with no owner. Assistants generate pipeline YAML and infrastructure snippets unless constrained to **decisions** that survive tool changes.

**Boundaries:**

| Concern | Owner | This document |
|---------|-------|---------------|
| Application log content and correlation IDs | `logging-and-observability.md` (EKP-LO) | Cite — platform collects and routes |
| User-visible failure semantics | `error-handling.md` (EKP-EH) | Cite — ops plans rollback and incident hooks |
| Authn/authz, input validation, secrets in code | `security-fundamentals.md` (EKP-SF) | Cite — platform owns injection and rotation |
| What tests prove and verification philosophy | `testing.md` (EKP-TS) | Cite — CI enforces contract |
| Profiling and capacity mindset | `performance-mindset.md` (EKP-PM) | Cite for load/capacity decisions |
| Layer and environment responsibilities | `layering-and-boundaries.md` (EKP-LB) | Apply — especially EKP-LB06 |
| One-way platform choices | `adr-practices.md` (EKP-AD) | Cite when blast radius is high |
| PHP/Symfony/TypeScript/Frontend stacks | `php/`, `symfony/`, `typescript/`, `frontend/` | **Out of scope** — no cross-stack deps |
| Docker/K8s/Terraform/AWS/GitHub Actions syntax | Vendor docs | Out of scope |

**Out of scope:** Command references, manifest cookbooks, cloud service catalogs, SRE textbook depth, tool comparison matrices.

## EKP layer positioning

| Layer | Role | This document |
|-------|------|---------------|
| **Principles (L0)** | Why | Implements EKP-P01, P04, P06, P07, P09, P10 by reference |
| **Ops (L3)** | Platform and delivery architecture | **Primary** |

## Guidance

### EKP-DV01: Separate environments by purpose

**Implements:** EKP-P04

**Applies:** EKP-LB06 (layer responsibilities)

**Intent:** Each environment exists for a defined purpose—mixing purposes creates data leaks, false confidence, and promotion surprises.

**Rules:**

- Name and document dev, staging, and production purposes; who may access each and what data each may hold.
- Production data must not flow to lower environments without explicit, audited process (**EKP-P06**).
- Promotion rules are explicit: what must pass before an artifact reaches the next environment.
- Environment-specific configuration is injected at deploy boundary—not hard-coded per branch in application source.

**Good:** Staging mirrors production topology with synthetic data; promotion requires green CI on the same artifact hash.

**Bad:** Developers point local apps at production databases for “quick debugging.”

**Review signals:** Shared credentials across envs; manual prod edits without promotion path.

---

### EKP-DV02: Make builds and deploys reproducible

**Implements:** EKP-P04, EKP-P09

**Intent:** The artifact tested in CI is the artifact deployed—reproducibility prevents “works on my machine” at scale.

**Rules:**

- Builds produce **immutable artifacts** (images, bundles, packages) identified by version or content hash.
- Dependency versions are pinned or locked for release builds; document exceptions.
- Deployments reference artifact identity—not “latest” without governance.
- Pipeline inputs (source revision, build parameters) are recorded for audit and rollback.

**Good:** CI builds `app:sha-abc123`; staging and production deploy that exact tag after gates pass.

**Bad:** SSH to server and `git pull` on production without artifact record.

**Review signals:** Floating `latest` tags in production; unrecorded manual deploy steps.

---

### EKP-DV03: Own configuration and secrets at the platform boundary

**Implements:** EKP-P06

**Applies:** EKP-SF (secrets management mindset)

**Intent:** Configuration and secrets cross a trust boundary at deploy/runtime—applications receive values; they do not own secret storage policy.

**Rules:**

- Distinguish **configuration** (non-secret, versionable defaults) from **secrets** (credentials, keys, tokens).
- Secrets never belong in source control, chat logs, or CI output—cite EKP-SF for review bar.
- Platform provides injection mechanism (env, secret store, identity)—applications read, do not embed.
- Rotation and least-privilege access are platform responsibilities with documented owners.

**Good:** Database URL injected at deploy from a secret store; repo contains only non-secret config schema.

**Bad:** API keys committed “temporarily” in `.env.example` or pipeline variables without rotation plan.

**Review signals:** Secrets in git history; shared prod credentials in team wiki.

---

### EKP-DV04: Treat CI/CD as an engineering contract

**Implements:** EKP-P07

**Applies:** EKP-TS (verification philosophy)

**Intent:** CI/CD encodes **what must be true before change ships**—fast feedback, proportional checks, fail-fast gates—not a bag of arbitrary scripts.

**Rules:**

- Every merge path defines required checks aligned with risk (**EKP-P02** proportionality).
- Failed gates block promotion; bypass requires documented exception and owner approval.
- Feedback time matters—optimize for fast signal on common paths (cite EKP-TS: tests define done).
- Pipeline changes are reviewed like application code—they alter the shipping contract.

**Good:** PR requires lint + unit tests; main branch deploys only after integration suite on release artifact.

**Bad:** Optional CI job that everyone ignores; 45-minute pipeline with no parallelization and no owner.

**Review signals:** “Skip CI” culture; flaky jobs left red for weeks.

---

### EKP-DV05: Design observability as a platform capability

**Implements:** EKP-P07

**Applies:** EKP-LO (application logging vs platform collection)

**Intent:** Metrics, logs, and traces are **owned capabilities** with clear boundaries—applications emit signals; platform aggregates, retains, and alerts.

**Rules:**

- Define who owns collection, retention, dashboards, and on-call routing for each signal type.
- Application code follows EKP-LO for **what** to log; this guide covers **how the platform** makes signals operable.
- Correlation identifiers started in application must survive platform boundaries (cite EKP-LO02).
- Alerting ties to user-impacting symptoms where possible—not only infrastructure vanity metrics.

**Good:** Standard log shipping contract; SLO dashboard owned by platform team; apps use structured logs per EKP-LO.

**Bad:** Each team runs a different log stack with no retention policy; alerts fire on CPU only with no trace to requests.

**Review signals:** Cannot trace a user request across services; logs lost on pod restart with no policy.

---

### EKP-DV06: Plan for failure operationally

**Implements:** EKP-P07

**Applies:** EKP-EH (failure semantics)

**Intent:** Deployments and platforms fail—rollback, health checks, blast radius, and incident hooks must be designed, not improvised.

**Rules:**

- Every production deploy path has a **rollback or forward-fix** strategy documented before first use.
- Health checks distinguish “process up” from “serving correct work” where feasible.
- Blast radius limits: canary, staged rollout, or feature flags for high-risk changes (**EKP-P03** reversibility).
- Incident response hooks (who gets paged, where status is communicated) exist before incidents.

**Good:** Automated rollback when error rate exceeds threshold after deploy; runbook link in on-call rotation.

**Bad:** First production outage is when the team learns there is no rollback and no owner.

**Review signals:** Manual hotfix directly in prod without record; health check only hits `/health` returning 200 always.

---

### EKP-DV07: Decide when infrastructure belongs in code

**Implements:** EKP-P04

**Applies:** EKP-AD (ADR for one-way doors)

**Intent:** Infrastructure-as-code is an **engineering decision** about drift, reviewability, and environment parity—not a default for every resource.

**Rules:**

- Record ADR when adopting IaC for a subsystem with high blast radius or multi-team ownership.
- Environments should be **parity-aware**: differences are explicit, not accidental drift.
- Manual changes in production require exception process; reconcile back into code or document debt.
- Prefer reversible platform choices early (**EKP-P03**); IaC depth follows proven need.

**Good:** ADR: “All network ingress via reviewed Terraform modules; exceptions time-boxed.”

**Bad:** Half the fleet click-ops, half Terraform, with no inventory of which is authoritative.

**Review signals:** “Snowflake” servers; staging cannot be recreated from repository state.

---

### EKP-DV08: Close the operational feedback loop

**Implements:** EKP-P01, EKP-P10

**Intent:** Deploy → observe → learn → change is a continuous loop—post-incident learning and metrics inform the next engineering decision.

**Rules:**

- Production signals (errors, latency, saturation) feed back into backlog with proportionate priority (**EKP-P01**).
- Post-incident reviews produce actionable items—blameless, linked to concepts (cite EKP-AD for durable decisions).
- Repeated manual toil triggers automation or removal (**EKP-P10** design for change).
- Operational learnings update runbooks, CI gates, or architecture docs—not only chat memory.

**Good:** Incident leads to tighter health check + new integration test in CI contract (EKP-DV04).

**Bad:** Same outage twice with “we’ll remember next time” and no tracked follow-up.

**Review signals:** No metrics review rhythm; incidents closed without root-cause category.

## AI Decision Flow

For platform, CI/CD, and operational architecture changes. Run after `ai-assisted-development.md` steps 1–3. Application-only logging/errors route to **EKP-LO** / **EKP-EH** first.

```
1. Application concern vs platform concern?
   → Log content, correlation in code: logging-and-observability.md (EKP-LO).
   → User/API failure semantics: error-handling.md (EKP-EH).
   → Environments, deploy, CI, infra boundaries: continue.

2. Environment separation (EKP-DV01)
   → Prod data in lower env or unclear promotion: block; apply LB06 + isolation rules.

3. Reproducibility (EKP-DV02)
   → Deploy without immutable artifact identity: require artifact hash/tag policy.

4. Config/secrets (EKP-DV03)
   → Secret in repo or CI log: block; route to EKP-SF mindset + platform injection.

5. CI/CD contract (EKP-DV04)
   → Missing or bypassed gates: align with EKP-TS verification philosophy.

6. Observability platform (EKP-DV05)
   → App logging only: cite EKP-LO; define platform ownership for collection/alerting.

7. Operational failure (EKP-DV06)
   → Deploy without rollback/health plan: require strategy before prod change.

8. IaC decision (EKP-DV07)
   → One-way platform choice: require ADR (EKP-AD) when blast radius is high.

9. Feedback loop (EKP-DV08)
   → Repeat incident without learning item: require tracked follow-up.
```

| ID | Rule |
|----|------|
| **DV-AI-01** | No Docker/K8s/Terraform/AWS command tutorials—decisions only. |
| **DV-AI-02** | Do not duplicate EKP-LO / EKP-EH / EKP-SF / EKP-TS—cite and route. |
| **DV-AI-03** | No cross-stack depends_on—ops applies foundation, not PHP/TS guides. |

## When not to apply

- Pure application code with no delivery or platform impact (**EKP-P02**).
- Single-developer local scripts with documented discard date.
- Stack-specific language/framework design — route to L1/L2 guides.

## Trade-offs

| Benefit | Cost |
|---------|------|
| Clear env and artifact policy reduces prod surprises | More upfront platform discipline |
| CI contract improves quality bar | Pipeline maintenance and flake management |
| Platform observability speeds incident response | Operational ownership overhead |

## Related

- [Engineering Principles](../engineering/engineering-principles.md) — EKP-P
- [Logging and Observability](../engineering/logging-and-observability.md) — EKP-LO
- [Error Handling](../engineering/error-handling.md) — EKP-EH
- [Security Fundamentals](../security/security-fundamentals.md) — EKP-SF
- [Testing](../testing/testing.md) — EKP-TS
- [Performance Mindset](../performance/performance-mindset.md) — EKP-PM
- [Layering and Boundaries](../architecture/layering-and-boundaries.md) — EKP-LB
- [ADR Practices](../architecture/adr-practices.md) — EKP-AD
- [DevOps domain index](README.md)
