---
title: PHP Fundamentals
domain: php
tags: [php, language, composer, psr, typing, runtime]
severity: recommended
applies_to: [backend, api]
type: guide
role: practice
depends_on:
  - knowledge/engineering/engineering-principles.md
implements:
  - EKP-P04
  - EKP-P05
  - EKP-P06
  - EKP-P07
  - EKP-P09
  - EKP-P10
related:
  - knowledge/engineering/engineering-principles.md
  - knowledge/engineering/solid.md
  - knowledge/engineering/error-handling.md
  - knowledge/engineering/clean-code.md
  - knowledge/testing/testing.md
  - knowledge/architecture/layering-and-boundaries.md
  - knowledge/symfony/symfony-architecture.md
  - knowledge/php/README.md
extends: []
concept_ids: [EKP-PH01, EKP-PH02, EKP-PH03, EKP-PH04, EKP-PH05, EKP-PH06, EKP-PH07, EKP-PH08]
adapter_priority: high
---

# PHP Fundamentals

## Summary

Language-layer guidance for **modern PHP** as used in application code: typing, nullability, Composer boundaries, PSR conventions, runtime configuration, and testable units. This document **applies** **EKP-P04** (Explicit), **EKP-P05** (Local reasoning), **EKP-P06** (Own the boundary), **EKP-P07** (Fail fast), **EKP-P09** (Compose), and **EKP-P10** (where testability/design-for-change applies)—it does not redefine those principles.

Apply when writing or reviewing PHP outside a single framework tutorial. Framework structure belongs in [`symfony-architecture.md`](../symfony/symfony-architecture.md) (EKP-SY). Relax per **EKP-P02** for throwaway scripts with no shared consumers.

## Context

PHP defects often look like “framework issues” but originate in language misuse: untyped public APIs, silent `null`, global mutable state, and Composer packages that leak infrastructure into domain code. Assistants amplify this by emitting untyped helpers and service-locator style statics unless constrained.

**Boundaries:**

| Concern | Owner | This document |
|---------|-------|---------------|
| Engineering principles | `engineering-principles.md` (EKP-P) | Cite only |
| Class responsibility / DIP | `solid.md` (EKP-SL) | Cite — do not restate SOLID |
| Failure contracts | `error-handling.md` (EKP-EH) | Cite; map PHP errors to EH |
| Naming / function hygiene | `clean-code.md` (EKP-CC) | Cite |
| Verification philosophy | `testing.md` (EKP-TS) | Cite |
| System layers / HTTP boundaries | `layering-and-boundaries.md` (EKP-LB) | Cite |
| Symfony DI, HttpKernel, bundles | `symfony-architecture.md` (EKP-SY) | Out of scope |
| SQL/schema design | `database-design.md` (EKP-DB) | Out of scope |

**Out of scope:** Full PHP language manual, PECL extension catalogs, version upgrade changelogs, Symfony-specific wiring.

## EKP layer positioning

| Layer | Role | This document |
|-------|------|---------------|
| **Principles (L0)** | Why | Implements EKP-P04–P07, P09 by reference |
| **Language (L1)** | How PHP expresses principles | **Primary** |
| **Framework (L2)** | Symfony structure | Escalation → EKP-SY |

## Guidance

### EKP-PH01: Make types part of the contract

**Implements:** EKP-P04, EKP-P05

**Applies:** EKP-CC (clarity), EKP-SL (interfaces as contracts)

**Intent:** Public PHP APIs should declare parameter, return, and property types so callers reason locally without reading implementations.

**Rules:**

- Prefer parameter and return types on public and protected methods.
- Prefer typed properties for durable state; avoid untyped public properties.
- Use `void`, nullable types, and union types deliberately—not as decoration.
- Do not weaken types at inheritance boundaries without an explicit reason.

**Good:** `public function find(UserId $id): ?User`

**Bad:** `public function find($id)` returning mixed arrays and objects.

**Review signals:** Public API without types; `mixed` everywhere; array shapes undocumented.

---

### EKP-PH02: Treat null and failure as explicit

**Implements:** EKP-P04, EKP-P07

**Applies:** EKP-EH01–EH04 (failure semantics)

**Intent:** Absent values and failures must be visible at the call site—not buried in notices, empty strings, or falsy coercion.

**Rules:**

- Prefer `?Type`, null-safe operators with intent, or Result/exception patterns consistent with EKP-EH.
- Do not use `false` and `null` interchangeably for “missing.”
- Do not suppress errors with `@` in application code.
- Map transport/domain failures to the project’s error contract (cite EKP-EH)—do not invent a parallel PHP-only taxonomy here.

**Good:** Return `?User` or throw a domain exception when missing is exceptional.

**Bad:** Return `[]` or `""` for missing entities; ignore warnings with `@file_get_contents`.

**Review signals:** `@` operator; `empty()` used to hide type uncertainty; catch-all `catch (\Throwable)`.

---

### EKP-PH03: Keep Composer boundaries intentional

**Implements:** EKP-P06, EKP-P09

**Applies:** EKP-MC (module coupling), EKP-LB (dependency direction)

**Intent:** Dependencies are architecture. Packages enter the codebase through Composer—treat `composer.json` as a boundary map.

**Rules:**

- Prefer stable, maintained packages; record risky deps in review (cite EKP-SF07 for supply-chain awareness).
- Domain code should depend on abstractions you own—not on HTTP/ORM clients deep in entities.
- Avoid packages that force global state or static service location.
- Do not add a dependency to avoid writing a 20-line adapter without proportionality (**EKP-P02**).

**Good:** Thin adapter package/module wrapping a mail SDK.

**Bad:** Domain entities constructing `GuzzleHttp\Client` directly.

**Review signals:** New deps without justification; framework packages imported into pure domain folders.

---

### EKP-PH04: Follow PSR and project conventions explicitly

**Implements:** EKP-P04

**Applies:** EKP-CC (consistency)

**Intent:** Shared autoloading, coding style, and HTTP message interfaces reduce tribal knowledge.

**Rules:**

- Use PSR-4 autoloading aligned with directory structure.
- Prefer project coding standard (e.g. PSR-12) consistently—do not mix styles in one PR.
- Use PSR interfaces at boundaries when the project already adopted them (HTTP messages, logging, caching)—do not introduce parallel abstractions casually.
- Document intentional deviations.

**Good:** Namespace path matches `src/` PSR-4 map.

**Bad:** Class in random folder with classmap hacks; mixed brace/indent styles.

**Review signals:** Autoload failures “fixed” by require_once; style-only noise mixed with behavior changes.

---

### EKP-PH05: Prefer explicit state over hidden globals

**Implements:** EKP-P05, EKP-P04

**Applies:** EKP-SL (dependency direction)

**Intent:** Hidden global and static mutable state destroys local reasoning and testability.

**Rules:**

- Avoid `$GLOBALS`, ambient static registries, and writeable singletons for business state.
- Pass collaborators via constructors or parameters.
- Limit `static` to true immutable/shared constants or carefully reviewed caches.
- Request-scoped data belongs in explicit context objects—not ambient static bags.

**Good:** Services receive dependencies in the constructor.

**Bad:** `App::getContainer()->get(Mailer::class)` inside domain logic.

**Review signals:** Static mutable properties; hidden `new` of infrastructure in deep call stacks.

---

### EKP-PH06: Configuration is an edge concern

**Implements:** EKP-P04, EKP-P06

**Applies:** EKP-LB09 (validate at boundary), EKP-SF04 (secrets)

**Intent:** Environment and runtime config must enter the app at the edge, validated and injected—not scattered `getenv` calls in domain code.

**Rules:**

- Read env/config in bootstrap or dedicated config layer; inject values into services.
- Fail fast on missing required config at startup (**EKP-P07**).
- Never hardcode secrets; never log secrets (cite EKP-SF / EKP-LO).
- Prefer typed config objects over loose associative arrays when config is non-trivial.

**Good:** Validated `DatabaseConfig` injected into the connection factory.

**Bad:** `getenv('DB_PASS')` inside a repository method.

**Review signals:** Env reads deep in domain; default passwords in code; config arrays with unknown keys.

---

### EKP-PH07: Compose small units; avoid god classes

**Implements:** EKP-P09, EKP-P05

**Applies:** EKP-SL01–SL02, EKP-MC01

**Intent:** PHP codebases rot through mega-classes and include files that accumulate unrelated behavior.

**Rules:**

- Prefer small classes/functions with one reason to change (cite EKP-SL—do not redefine SRP here).
- Split when unrelated methods share only a file name.
- Prefer composition of collaborators over deep inheritance for behavior reuse.
- Do not use inheritance to share unrelated utilities.

**Good:** `InvoiceCalculator` + `InvoiceRepository` as separate types.

**Bad:** `InvoiceManager` with HTTP, SQL, PDF, and email in one class.

**Review signals:** Classes > ~300 lines with mixed concerns; inheritance for code sharing only.

---

### EKP-PH08: Design PHP units to be testable without a framework

**Implements:** EKP-P05, EKP-P10

**Applies:** EKP-TS (testing philosophy)

**Intent:** Domain and application logic should be verifiable with PHPUnit (or equivalent) without booting a full HTTP kernel—unless the subject *is* the kernel integration.

**Rules:**

- Inject dependencies that you need to fake or replace in tests.
- Prefer pure functions/value objects for calculation-heavy logic.
- Do not require a database for logic that is not persistence.
- Follow EKP-TS for what “done” means—this document only requires *design for test*.

**Good:** Calculator tested with in-memory fakes.

**Bad:** Business rule only reachable through a full web request in production bootstrap.

**Review signals:** `new` of concrete IO types inside logic; tests skipped because “needs Symfony.”

## AI Decision Flow

For PHP language-level changes. Run after `ai-assisted-development.md` steps 1–3. If the change is Symfony structure (DI, bundles, HttpKernel), route to **EKP-SY**.

```
1. Is this PHP language/module design (not framework wiring)?
   → NO, Symfony structure: escalate to symfony-architecture.md (EKP-SY). Stop here.
   → YES: continue.

2. Public contract typing (EKP-PH01)
   → Untyped public API: add types or justify exception.

3. Null / failure visibility (EKP-PH02)
   → Map to EKP-EH; no @ suppression; no false/null ambiguity.

4. Dependency / Composer impact (EKP-PH03)
   → New package or infra import in domain: flag boundary violation.

5. Globals / static mutable state (EKP-PH05)
   → Replace with injection.

6. Config reads (EKP-PH06)
   → Move to edge; validate; protect secrets (EKP-SF).

7. Size / cohesion (EKP-PH07)
   → God class: split; cite EKP-SL / EKP-MC — do not paste SOLID essay.

8. Testability (EKP-PH08)
   → Cannot unit-test without full boot: redesign seams; cite EKP-TS.
```

| ID | Rule |
|----|------|
| **PH-AI-01** | Do not emit untyped public APIs without justification. |
| **PH-AI-02** | Do not introduce static service location for business logic. |
| **PH-AI-03** | Framework architecture questions route to EKP-SY—not this guide. |

## When not to apply

- One-off CLI throwaway with documented deletion (**EKP-P02**).
- Generated code owned by a tool where types are imposed by the generator—follow generator contracts.
- Symfony container/routing/security wiring — use EKP-SY.

## Trade-offs

| Benefit | Cost |
|---------|------|
| Typed, explicit PHP reduces integration defects | Slightly more ceremony at API edges |
| Edge-loaded config improves security and testability | Bootstrap discipline required |
| Framework-free unit seams speed feedback | Requires intentional architecture |

## Related

- [Engineering Principles](../engineering/engineering-principles.md) — EKP-P
- [SOLID](../engineering/solid.md) — EKP-SL
- [Error Handling](../engineering/error-handling.md) — EKP-EH
- [Testing](../testing/testing.md) — EKP-TS
- [Layering and Boundaries](../architecture/layering-and-boundaries.md) — EKP-LB
- [Symfony Architecture](../symfony/symfony-architecture.md) — EKP-SY (L2)
- [PHP domain index](README.md)
