---
title: Symfony Architecture
domain: symfony
tags: [symfony, architecture, dependency-injection, httpkernel, boundaries]
severity: recommended
applies_to: [backend, api]
type: guide
role: architecture
depends_on:
  - knowledge/engineering/engineering-principles.md
  - knowledge/php/php-fundamentals.md
implements:
  - EKP-P04
  - EKP-P05
  - EKP-P06
  - EKP-P09
related:
  - knowledge/engineering/engineering-principles.md
  - knowledge/php/php-fundamentals.md
  - knowledge/architecture/layering-and-boundaries.md
  - knowledge/architecture/coupling-and-cohesion.md
  - knowledge/architecture/api-design.md
  - knowledge/architecture/integration-patterns.md
  - knowledge/architecture/adr-practices.md
  - knowledge/security/security-fundamentals.md
  - knowledge/database/database-design.md
  - knowledge/symfony/README.md
extends: []
concept_ids: [EKP-SY01, EKP-SY02, EKP-SY03, EKP-SY04, EKP-SY05, EKP-SY06, EKP-SY07, EKP-SY08]
adapter_priority: high
---

# Symfony Architecture

## Summary

Framework-layer guidance for **structuring Symfony applications**: dependency injection, thin entrypoints, config at the edge, module boundaries, messaging, and security integration. This document **applies** **EKP-P04**, **EKP-P05**, **EKP-P06**, and **EKP-P09**, and routes to L0 architecture/security guides—it does not replace them or rewrite PHP language rules ([`php-fundamentals.md`](../php/php-fundamentals.md), EKP-PH).

Apply when designing or reviewing Symfony project structure, services, controllers, and integration with Messenger/Security. Record one-way structural choices in ADRs (EKP-AD). Relax per **EKP-P02** for throwaway prototypes with documented expiry.

## Context

Symfony failures often appear as “DI issues” or “controller bloat” but are boundary failures: domain logic coupled to HttpFoundation, services fetched from the container as a locator, and config/`getenv` scattered through the domain. Assistants frequently generate fat controllers and `$this->get()` patterns unless constrained.

**Boundaries:**

| Concern | Owner | This document |
|---------|-------|---------------|
| PHP typing, Composer, globals | `php-fundamentals.md` (EKP-PH) | Prerequisite — cite |
| System layers / contracts | `layering-and-boundaries.md` (EKP-LB) | Apply — do not redefine layers |
| Module coupling | `coupling-and-cohesion.md` (EKP-MC) | Apply at PHP package / Symfony module level |
| HTTP resource design | `api-design.md` (EKP-AP) | Cite for public HTTP shape |
| Sync/async integration style | `integration-patterns.md` (EKP-IN) | Cite; Messenger is an implementation choice |
| Authn/authz mindset | `security-fundamentals.md` (EKP-SF) | Apply via Security component — no parallel model |
| Schema/migrations | `database-design.md` (EKP-DB) | Cite; Doctrine specifics only as boundary examples |
| ADR / one-way doors | `adr-practices.md` (EKP-AD) | Escalate Level 4 structure |

**Out of scope:** Full Symfony component reference, every Best Practices cookbook page, Flex recipe catalogs, version-by-version changelogs.

## EKP layer positioning

| Layer | Role | This document |
|-------|------|---------------|
| **Principles (L0)** | Why | Implements EKP-P04, P05, P06, P09 by reference |
| **Language (L1)** | PHP fundamentals | Depends on EKP-PH |
| **Framework (L2)** | Symfony application structure | **Primary** |

## Guidance

### EKP-SY01: Framework is infrastructure, not the domain

**Implements:** EKP-P05, EKP-P06

**Applies:** EKP-LB01–LB04, EKP-PH07

**Intent:** Symfony (HttpKernel, forms, Doctrine bridges, Security) is the delivery mechanism. Business policy should remain understandable without the framework where proportionality allows.

**Rules:**

- Keep domain rules in plain PHP types when they do not require framework services.
- Depend inward: delivery adapters use domain; domain does not import HttpFoundation/ORM details casually.
- Do not treat “extends AbstractController” as a domain modeling tool.
- When framework types leak into the domain, document the exception and the exit plan.

**Good:** Domain service called from a thin controller or message handler.

**Bad:** Entity methods that render Twig or read `Request` attributes.

**Review signals:** `Request`/`Response` in domain services; Doctrine annotations driving unrelated business workflows.

---

### EKP-SY02: Prefer constructor injection over service location

**Implements:** EKP-P04, EKP-P05

**Applies:** EKP-PH05, EKP-SL (DIP)

**Intent:** Collaborators must be explicit in constructors (or invokable handler signatures)—not fetched from a hidden container.

**Rules:**

- Declare services as constructor dependencies; let the container wire them.
- Avoid `$container->get()`, `$this->get()`, and static service registries in application code.
- Prefer autowiring with clear type-hints; configure explicitly when ambiguity exists.
- Do not inject the whole container into services.

**Good:** `__construct(private UserRepository $users, private MailerInterface $mailer)`

**Bad:** `$this->container->get(UserRepository::class)` inside business methods.

**Review signals:** Container injection; locator pattern for convenience; optional deps resolved at call time via globals.

---

### EKP-SY03: Keep HTTP entrypoints thin

**Implements:** EKP-P05, EKP-P06

**Applies:** EKP-LB09, EKP-AP (HTTP shape)

**Intent:** Controllers and API entrypoints translate HTTP ↔ application calls. They are not the home of business workflows.

**Rules:**

- Controllers: validate/authz at edge, map input, call one application service/handler, map output.
- Do not embed multi-step business workflows in controller actions.
- Place input validation at the boundary (forms/DTO validators)—cite EKP-LB09; do not re-specify validation theory here.
- Public HTTP naming and status codes follow EKP-AP—not ad-hoc controller habits.

**Good:** `CreateOrderController` → `CreateOrderHandler`.

**Bad:** 200-line controller with SQL, email, and pricing rules.

**Review signals:** Repositories used for complex workflows only in controllers; duplicated logic across actions.

---

### EKP-SY04: Load configuration at the edge

**Implements:** EKP-P04, EKP-P06

**Applies:** EKP-PH06, EKP-SF04

**Intent:** `%env%` parameters and config files are edge inputs. Domain code receives validated values.

**Rules:**

- Bind parameters/env to service arguments or typed config objects.
- Fail fast when required env is missing (kernel boot).
- Do not call `getenv` / `$_ENV` inside domain services.
- Keep secrets out of logs and out of committed config (EKP-SF / EKP-LO).

**Good:** `->bind('$openAiKey', '%env(OPENAI_API_KEY)%')` into a single client adapter.

**Bad:** Reading env inside a pricing calculator.

**Review signals:** Env sprawl across packages; default secrets in `services.yaml`.

---

### EKP-SY05: Align packages with module boundaries

**Implements:** EKP-P09, EKP-P05

**Applies:** EKP-MC01–MC03, EKP-LB04

**Intent:** Symfony directory layout should reflect cohesive modules—not a single `src/Service` junk drawer.

**Rules:**

- Group by bounded capability (module) when the app grows past a small CRUD.
- Avoid cyclic package dependencies; depend on stable interfaces at module edges (EKP-MC).
- Prefer clear public APIs between modules over cross-reaching into `Internal/` folders.
- Record large modularization moves as ADRs when costly to reverse (EKP-AD).

**Good:** `Order/` and `Billing/` packages with explicit interfaces.

**Bad:** Every class under `App\Service\` with circular requires.

**Review signals:** Cross-module private class imports; “util” packages depended on by everything.

---

### EKP-SY06: Choose Messenger/async deliberately

**Implements:** EKP-P02, EKP-P06

**Applies:** EKP-IN (integration style), EKP-LB12 (idempotency)

**Intent:** Messenger is a tool for integration and async boundaries—not a default for every method call.

**Rules:**

- Prefer synchronous calls inside one process when consistency and simplicity matter (**EKP-P02**).
- Use messages when crossing time, process, or ownership boundaries (cite EKP-IN).
- Define handler idempotency for at-least-once delivery (cite EKP-LB12 / EKP-IN).
- Do not hide critical business writes only in fire-and-forget events without durability analysis.

**Good:** Email send or projection update via message after order commit.

**Bad:** Every repository call wrapped in a message “for cleanliness.”

**Review signals:** Unclear delivery guarantees; duplicate side effects; async used to avoid modeling transactions (EKP-DB).

---

### EKP-SY07: Apply security fundamentals through Security—not a parallel model

**Implements:** EKP-P06, EKP-P07

**Applies:** EKP-SF02–SF05, EKP-LB09

**Intent:** Authentication, authorization, and firewall configuration implement EKP-SF. Do not invent a second security vocabulary in controllers.

**Rules:**

- Declare access rules centrally (attributes/voters/security config) consistent with least privilege (EKP-SF).
- Distinguish authentication vs authorization (EKP-SF05).
- Validate untrusted input at the edge before domain work (EKP-SF02 / EKP-LB09).
- Do not disable security “temporarily” in production paths without an expiry and owner.

**Good:** Voter or `IsGranted` on sensitive operations; thin controller.

**Bad:** Ad-hoc `if ($user->getId() === …)` scattered with inconsistent rules.

**Review signals:** Security checks only in UI; missing authz on API twins; secrets in repo.

---

### EKP-SY08: Extend Symfony; do not fork the framework

**Implements:** EKP-P09, EKP-P03

**Applies:** EKP-AD (one-way doors)

**Intent:** Prefer documented extension points (event subscribers, compiler passes used sparingly, decorating services) over copying framework internals.

**Rules:**

- Prefer composition/decoration over modifying vendor code.
- Treat invasive overrides of core classes as one-way doors—require ADR (EKP-AD).
- Upgrade cost is part of architecture; minimize private API reliance.
- Document intentional vendor patches with removal criteria.

**Good:** Decorate a mailer; subscribe to kernel events for cross-cutting concerns.

**Bad:** Copied HttpKernel class into `src/` with local edits.

**Review signals:** `vendor/` edits; deep overrides without ADR; upgrade blockers.

## AI Decision Flow

For Symfony application-structure changes. Run after `ai-assisted-development.md` steps 1–3. Language-only PHP issues route to **EKP-PH** first.

```
1. Language vs framework?
   → PHP typing/globals/Composer only: php-fundamentals.md (EKP-PH).
   → Symfony structure/DI/HTTP entrypoints: continue.

2. Domain vs delivery (EKP-SY01)
   → Framework types in domain: push outward to adapters.

3. Injection style (EKP-SY02)
   → Service location / container injection: replace with constructor DI.

4. Entrypoint thickness (EKP-SY03)
   → Fat controller: extract handler/application service.
   → Public HTTP shape: also apply EKP-AP Decision Flow.

5. Config/env (EKP-SY04)
   → Edge-only; secrets per EKP-SF.

6. Module boundaries (EKP-SY05)
   → Cite EKP-MC; escalate ADR if one-way modularization (EKP-AD).

7. Async/Messenger (EKP-SY06)
   → Justify with EKP-IN; idempotency for handlers.

8. Security (EKP-SY07)
   → Route detailed threat thinking to EKP-SF Decision Flow.

9. Vendor lock / forks (EKP-SY08)
   → Invasive override: require ADR before implementing.
```

| ID | Rule |
|----|------|
| **SY-AI-01** | No container/service locator in application services. |
| **SY-AI-02** | Controllers stay thin; workflows live in handlers/services. |
| **SY-AI-03** | Do not duplicate EKP-SF / EKP-LB / EKP-AP—cite and route. |

## When not to apply

- Pure PHP libraries with no Symfony runtime — use EKP-PH only.
- Micro-scripts without HttpKernel (**EKP-P02**).
- Detailed Doctrine mapping tutorials — use EKP-DB + project conventions.

## Trade-offs

| Benefit | Cost |
|---------|------|
| Clear delivery vs domain split improves testability | More types and wiring upfront |
| Explicit DI clarifies dependencies | Verbose constructors |
| Module boundaries reduce change blast radius | Requires packaging discipline |

## Related

- [PHP Fundamentals](../php/php-fundamentals.md) — EKP-PH
- [Engineering Principles](../engineering/engineering-principles.md) — EKP-P
- [Layering and Boundaries](../architecture/layering-and-boundaries.md) — EKP-LB
- [Coupling and Cohesion](../architecture/coupling-and-cohesion.md) — EKP-MC
- [API Design](../architecture/api-design.md) — EKP-AP
- [Integration Patterns](../architecture/integration-patterns.md) — EKP-IN
- [Security Fundamentals](../security/security-fundamentals.md) — EKP-SF
- [ADR Practices](../architecture/adr-practices.md) — EKP-AD
- [Symfony domain index](README.md)
