---
title: Design Patterns
domain: engineering
tags: [design-patterns, structure, composition, tradeoffs, catalog]
severity: recommended
applies_to: [backend, frontend, api, mobile]
type: guide
role: pattern
depends_on:
  - knowledge/engineering/engineering-principles.md
  - knowledge/engineering/solid.md
implements:
  - EKP-P09
  - EKP-P02
  - EKP-P05
related:
  - knowledge/engineering/engineering-principles.md
  - knowledge/engineering/solid.md
  - knowledge/engineering/clean-code.md
  - knowledge/engineering/refactoring.md
  - knowledge/architecture/layering-and-boundaries.md
  - knowledge/architecture/decisions/README.md
  - knowledge/architecture/decisions/adr-0004-clean-code-position-in-knowledge-graph.md
extends: []
concept_ids: [EKP-DP01, EKP-DP02, EKP-DP03, EKP-DP04, EKP-DP05, EKP-DP06, EKP-DP07, EKP-DP08, EKP-DP09, EKP-DP10, EKP-DP11, EKP-DP12, EKP-DP13, EKP-DP14, EKP-DP15, EKP-DP16, EKP-DP17, EKP-DP18]
adapter_priority: high
---

# Design Patterns

## Summary

Stack-agnostic **named pattern catalog**: recurring structural solutions for class and module collaborations, with explicit trade-offs and selection heuristics. This document operationalizes **EKP-P09** (Compose, do not accumulate), **EKP-P02** (Proportionality), and **EKP-P05** (Local reasoning). A pattern is a **named trade-off**, not a mandatory template.

Apply during design and code review when a **recurring** structural problem is identified. Relax per **EKP-P02** for prototypes, scripts, and low-lifespan code. Do not introduce patterns speculatively or during incidents without documented follow-up (**EKP-P03** — see `refactoring.md`).

This document does not teach SOLID (`solid.md`), refactoring procedures (`refactoring.md`), naming hygiene (`clean-code.md`), or system architecture (`layering-and-boundaries.md`).

## Context

Experienced engineers reach for named structures when variation, adaptation, or collaboration complexity recurs. Inexperienced teams—and AI assistants—often apply patterns by name without identifying the problem, producing indirection without benefit (**EKP-P02**).

[Engineering Principles](engineering-principles.md) define *why* composition and proportionality matter. [SOLID](solid.md) defines *how* to evaluate class structure before patterns apply. This document names *which* structural collaboration fits a recurring problem and *what it costs*. Every entry traces to an **EKP-DP** concept ID.

**Boundaries:**

| Layer | Document | Unit of analysis |
|-------|----------|------------------|
| Function/file readability | `clean-code.md` (EKP-CC) | Names, functions, formatting |
| Class/module structure | `solid.md` (EKP-SL) | Responsibilities, dependencies |
| Named collaborations | **this document** (EKP-DP) | Recurring structural solutions |
| Safe structural change | `refactoring.md` (EKP-RF) | Step sequences, risk levels |
| System structure | `layering-and-boundaries.md` | Layers, services, contracts |

**Out of scope:** SOLID letter definitions (`solid.md`), refactoring steps (`refactoring.md`), framework DI wiring (`symfony/`, stack domains), enterprise architecture (CQRS, event sourcing, microservices — `architecture/`), exhaustive Gang of Four catalog, performance and security patterns (`performance/`, `security/`).

## EKP layer positioning

| Layer | Role | Example documents | This document |
|-------|------|-------------------|---------------|
| **Principles** | Why — value judgments | `engineering-principles.md` (EKP-P01–P10) | Implements EKP-P02, EKP-P05, EKP-P09 by reference |
| **Practices** | What good structure looks like | `clean-code.md` (EKP-CC), `solid.md` (EKP-SL) | Prerequisite — cite EKP-SL IDs only |
| **Patterns** | Named reusable structures | **this document** (EKP-DP) | Primary content |
| **Procedures** | How to change structure safely | `refactoring.md` (EKP-RF) | Entry points — cite procedure names only |
| **Architecture** | System boundaries | `layering-and-boundaries.md`, ADRs | Escalation when pattern scope exceeds module |

Design patterns are a **pattern-layer** artifact per ADR-0004. Adapters (Cursor, Claude, Google Gravity, future tools) should extract the **AI Decision Flow** and **anti-cargo-cult rules** as high-priority constraints.

## Guidance

### EKP-DP01: Problem-first selection

**Implements:** EKP-P09

**Intent:** No pattern without a named, recurring problem. The pattern name follows the problem—it does not precede it.

**Rules:**

- State the problem in domain terms before naming a pattern: "payment calculation varies by region" not "we need Strategy."
- Require evidence of recurrence: second similar branch, second implementation, or documented near-term second variant.
- Reject pattern suggestions that only describe code shape without user-visible behavior change.

**Review signals:** PR introduces `*Factory` or `*Strategy` with one code path and no stated variation.

---

### EKP-DP02: Proportionality gate

**Implements:** EKP-P02

**Intent:** Pattern structure must not cost more than the problem it solves.

**Rules:**

- Count new types, files, and indirection layers introduced. If the count exceeds the variation count, reject the pattern.
- Prototypes and throwaway scripts: no pattern catalog entries unless lifespan extends to production.
- Match pattern depth to blast radius (**EKP-P02**): internal module patterns differ from cross-service patterns (escalate to architecture).

**Review signals:** Three new classes to wrap a single `if` branch; pattern in a one-off migration script.

---

### EKP-DP03: Simplicity default

**Implements:** EKP-P09, EKP-P05

**Intent:** Prefer plain composition—functions, parameters, small cohesive classes—before pattern scaffolding.

**Rules:**

- Try inline logic, parameterization, or a single extracted function before Strategy, Factory, or Observer.
- A pattern must **improve local reasoning** (**EKP-P05**). If tracing behavior requires more files than before, the pattern fails.
- Duplication of two lines is not a pattern problem; duplication of a **concept** across modules may be.

**Review signals:** Pattern introduced where a well-named function would suffice (see `clean-code.md` EKP-CC02).

---

### EKP-DP04: Convention alignment

**Implements:** EKP-P05

**Intent:** Follow existing project structure before introducing new pattern vocabulary.

**Rules:**

- If the codebase uses plain functions and data structs, do not introduce class-heavy patterns without team agreement.
- New pattern names must match domain language (EKP-CC01 applies inside pattern classes).
- When migrating legacy code, match surrounding style unless a refactor ticket explicitly introduces the pattern.

**Review signals:** First Strategy/Factory in a codebase with no other pattern usage; pattern naming inconsistent with domain terms.

---

### EKP-DP05: Creational patterns

**Implements:** EKP-P09

**Intent:** Orient selection for **object creation** trade-offs. Not an exhaustive creational taxonomy.

**Scope in EKP:** Factory (EKP-DP09), Builder (EKP-DP14). Out of catalog: Prototype, Abstract Factory as standalone entries—evaluate via Factory/Builder guidance.

**When category applies:** Object construction involves non-trivial rules, type selection, or stepwise assembly.

**When category does not apply:** Single constructor call with stable parameters—use constructor directly.

---

### EKP-DP06: Structural patterns

**Implements:** EKP-P09, EKP-P05

**Intent:** Orient selection for **composition and interface adaptation** without changing core behavior semantics.

**Scope in EKP:** Adapter (EKP-DP10), Decorator (EKP-DP11). Out of catalog: Proxy, Bridge, Composite, Facade as standalone entries—Facade-like module surfaces belong in `layering-and-boundaries.md` when they define system boundaries.

**When category applies:** Two incompatible interfaces must collaborate, or behavior must be extended without subclassing.

---

### EKP-DP07: Behavioral patterns

**Implements:** EKP-P09

**Intent:** Orient selection for **communication and responsibility assignment** among objects.

**Scope in EKP:** Strategy (EKP-DP08), Observer (EKP-DP12), Command (EKP-DP15). Out of catalog: State, Template Method, Chain of Responsibility—apply DP01–DP04 heuristics case by case.

**When category applies:** Algorithm or notification behavior varies independently of the object that triggers it.

---

### EKP-DP08: Strategy

**Implements:** EKP-P09, EKP-P02

**Intent:** Encapsulate interchangeable algorithms behind a common interface so callers depend on the abstraction, not the variant.

**Problem signal:** Growing `if/else` or `switch` on type/category for the **same operation** with multiple algorithms; new variants added on independent schedules.

**SOLID linkage:** OCP extension point (**EKP-SL02**); each strategy should have one reason to change (**EKP-SL01**).

**When to use:** Two or more real algorithms (or one plus documented imminent second); callers should not know which algorithm runs.

**When not to use:** Single algorithm forever; variation is configuration, not algorithm—use parameters or policy object without full Strategy hierarchy.

**Refactoring entry point:** Introduce Strategy procedure in `refactoring.md` (EKP-RF05).

**Good:** `PricingStrategy` with `StandardPricing` and `PromotionalPricing`; checkout depends on `PricingStrategy` interface.

**Bad:** `PricingStrategy` with only `DefaultPricing` and no second variant planned.

---

### EKP-DP09: Factory

**Implements:** EKP-P09, EKP-P02

**Intent:** Centralize object creation when construction logic, type selection, or dependency wiring is non-trivial.

**Problem signal:** `new` scattered with duplicated setup; creation depends on runtime configuration; multiple concrete types implement same role.

**SOLID linkage:** Supports DIP when factory returns abstraction (**EKP-SL05**). Simple Factory and Abstract Factory are one EKP entry—choose based on whether **family** of related objects is created together.

**When to use:** Creation rules change independently of consumers; testing requires substituting created objects.

**When not to use:** `UserFactory.create(name, email)` wrapping `new User(name, email)` with no extra logic (**EKP-DP16**).

**Refactoring entry point:** Extract Class + constructor consolidation via Level 2 procedures in `refactoring.md`.

**Good:** `PaymentGatewayFactory` selects implementation from config and injects credentials.

**Bad:** Factory class with one `create()` that only calls `new`.

---

### EKP-DP10: Adapter

**Implements:** EKP-P05, EKP-P09

**Intent:** Translate one interface into another so existing code works with incompatible APIs without modifying either side's core logic.

**Problem signal:** Third-party SDK or legacy module exposes API your domain cannot depend on directly; in-process interface mismatch.

**SOLID linkage:** Preserves LSP for the target interface (**EKP-SL03**); keeps dependency direction toward abstraction (**EKP-SL05**).

**When to use:** Wrapping external library; bridging legacy module to new domain port.

**When not to use:** Problem is **service boundary** or network contract—escalate to `layering-and-boundaries.md` and ADRs, not an in-process Adapter.

**Good:** `StripePaymentAdapter` implements domain `PaymentPort` using Stripe SDK.

**Bad:** Adapter that reimplements half the SDK—consider whether the dependency should be replaced instead.

---

### EKP-DP11: Decorator

**Implements:** EKP-P09, EKP-P02

**Intent:** Add responsibilities to an object dynamically by wrapping it, without subclassing every combination.

**Problem signal:** Multiple optional behaviors stack on a core service (logging, caching, metrics); subclass explosion if using inheritance.

**SOLID linkage:** Favors composition over inheritance (**EKP-P09**); each decorator should be SRP-compliant (**EKP-SL01**).

**When to use:** Behaviors are optional, combinable, and orthogonal to core logic.

**When not to use:** Single optional behavior—use composition in constructor or a single wrapper class; two decorators max before evaluating if core design is wrong.

**Good:** `CachingNotifier` wraps `EmailNotifier` wraps `SmsNotifier` core—each layer optional.

**Bad:** Decorator chain five deep where a pipeline or explicit composition root would be clearer (**EKP-P05**).

---

### EKP-DP12: Observer

**Implements:** EKP-P09, EKP-P05

**Intent:** Notify multiple dependents when state changes, without the subject knowing concrete observer types.

**Problem signal:** Multiple reactions to one event; producers must stay ignorant of consumers; listeners may be added over time.

**SOLID linkage:** OCP for new observers (**EKP-SL02**); subject should not grow a method per listener (**EKP-SL01**).

**When to use:** Two or more independent reactions; plausible future listeners; decoupling required within a module or bounded context.

**When not to use:** One listener, same module, direct call is clearer (**EKP-DP16**). System-wide event bus topology → `layering-and-boundaries.md`.

**Refactoring entry point:** Extract Method for handlers first; Observer only when dispatch indirection is justified.

**Good:** `OrderPlaced` notifies inventory, analytics, and email handlers registered at startup.

**Bad:** `orderPlaced` event with single synchronous listener in the same file.

---

### EKP-DP13: Repository

**Implements:** EKP-P05, EKP-P02

**Intent:** Mediate between domain and persistence, presenting a collection-like interface for domain objects.

**Problem signal:** Domain logic polluted with SQL/ORM calls; need to swap persistence or test domain without database; multiple persistence strategies for same aggregate.

**SOLID linkage:** DIP — domain depends on repository abstraction (**EKP-SL05**); persistence implements interface.

**When to use:** Domain must stay persistence-ignorant; integration tests need in-memory or fake persistence; ORM mapping complexity isolated.

**When not to use:** Simple CRUD with one table and no domain behavior—ORM/query layer directly (**EKP-DP16**). ORM specifics → `database/` stack guides.

**Good:** `OrderRepository` interface in domain; `DoctrineOrderRepository` in infrastructure.

**Bad:** `InMemoryUserRepository` over a hash map when the app has one SQLite table and no domain layer.

---

### EKP-DP14: Builder

**Implements:** EKP-P09, EKP-P02

**Intent:** Construct complex objects step by step when constructors would have too many parameters or optional combinations.

**Problem signal:** Constructor with many optional fields; invalid partial states possible; fluent assembly improves readability.

**SOLID linkage:** Keeps product class SRP-focused (**EKP-SL01**); separates construction from representation.

**When to use:** Many optional parameters; step order matters; same construction process produces different representations.

**When not to use:** Object has two required fields—use constructor or Parameter Object (Level 2 refactor in `refactoring.md`).

**Good:** `ReportBuilder` with `withTitle()`, `withSections()`, `build()` validating invariants before `Report` creation.

**Bad:** Builder for `Point(x, y)`.

---

### EKP-DP15: Command

**Implements:** EKP-P09, EKP-P05

**Intent:** Encapsulate a request as an object, enabling queuing, logging, undo, or dispatch separate from the invoker.

**Problem signal:** Operations need audit trail, async execution, undo/redo, or uniform dispatch (menu actions, job queue).

**SOLID linkage:** SRP — command object owns one operation (**EKP-SL01**); OCP for new commands without changing invoker (**EKP-SL02**).

**When to use:** Undo/redo; job queue; explicit audit of user actions; plugin-style command registration.

**When not to use:** Simple synchronous method call with no dispatch, logging, or undo requirements.

**Refactoring entry point:** Extract Method → Extract Class for command payload via Level 2 procedures.

**Good:** `PlaceOrderCommand` serialized to queue; handler idempotent; audit log stores command type + payload.

**Bad:** Command object that only wraps `service.doThing()` with no dispatch or audit benefit.

---

### EKP-DP16: Premature pattern introduction

**Implements:** EKP-P02

**Intent:** Catalog common misapplications where pattern vocabulary appears before the problem exists.

| Misapplication | Symptom | Simpler alternative |
|----------------|---------|---------------------|
| Factory for one constructor | `ThingFactory.create(a, b)` → `new Thing(a, b)` | Direct construction |
| Repository without persistence complexity | CRUD over one table, no domain | ORM/repository framework defaults |
| Strategy with one algorithm | Single `DefaultStrategy` forever | Inline algorithm |
| Singleton as global state | Mutable `getInstance()` everywhere | Inject dependencies; immutable config |
| Observer for direct call | One listener, same module | Direct method invocation |

**Review signals:** New pattern types in PR with no second variant; pattern in hotfix PR (**EKP-P03**).

---

### EKP-DP17: Over-abstraction

**Implements:** EKP-P02, EKP-P05

**Intent:** Indirection without variation obscures behavior and raises maintenance cost.

**Rules:**

- Every abstraction layer must answer: "What variation or test seam does this enable?"
- Interfaces with one implementation require justification per **EKP-SL04** — not automatic pattern introduction.
- If removing the abstraction makes the code **easier** to read, the abstraction was wrong (**EKP-P05**).

**Review signals:** "Interface for testability" with no tests using a fake; abstract base class with one subclass.

---

### EKP-DP18: Pattern stacking

**Implements:** EKP-P02, EKP-P09

**Intent:** Multiple patterns in one change usually indicate speculative design or scope smuggling.

**Rules:**

- One pattern per change set unless patterns solve **distinct** recurring problems in the same module.
- Factory + Strategy + Observer in one PR → reject unless each is independently justified (**EKP-RF06** scope rules in `refactoring.md`).
- Prefer incremental introduction: Strategy first; Factory only if creation complexity follows.

**Review signals:** Feature PR adds four new pattern-named classes unrelated to stated requirement.

## AI Decision Flow

Canonical sequence for Cursor, Claude, Google Gravity, and future EKP adapters. Extract verbatim for rules in Phase 5.

```
1. Is there a stated, recurring structural problem (not just "cleaner code")?
   → NO: Do not suggest a pattern. Stop.

2. Would a simpler approach suffice (function, parameter, small class)?
   → YES: Implement simpler approach (EKP-DP03). Stop.

3. Does the codebase already use a convention for this problem?
   → YES: Follow convention (EKP-DP04). Stop.

4. Is SOLID structure sound for the units involved (EKP-SL)?
   → NO: Diagnose with EKP-SL IDs; fix via refactoring.md procedures. Stop.

5. Name the pattern, state trade-offs (types added, files touched, indirection).
   → If cost > benefit (EKP-DP02): Do not suggest. Stop.

6. Is the change within task scope and refactoring budget?
   → NO: Propose separately; link refactoring procedure (EKP-RF). Do not auto-apply.

7. Does the problem cross service/deployment boundaries?
   → YES: Escalate to layering-and-boundaries.md / ADR — not a class pattern. Stop.

8. Apply one pattern. Cite EKP-DP ID in explanation.
```

**Adapter enforcement:**

| Step | Auto-apply | Notes |
|------|------------|-------|
| 1–3 | Hard block on pattern | Default for AI |
| 4 | Suggest SOLID/refactor first | Cite EKP-SL |
| 5–6 | Conditional | Human review for new types |
| 7 | Block | Architecture gate |
| 8 | One pattern only | EKP-DP18 |

## AI-specific guidance

Rules for all coding assistants consuming EKP knowledge. Reference sibling documents by ID only.

### Universal rules

- **DP-AI-01:** Do not suggest a pattern without naming the recurring problem it solves.
- **DP-AI-02:** State trade-offs before introducing pattern structure (types, files, indirection).
- **DP-AI-03:** Prefer existing project conventions over new pattern vocabulary (**EKP-DP04**).
- **DP-AI-04:** Do not add abstraction layers without evidence of variation (**EKP-DP02**, EKP-SL04).
- **DP-AI-05:** One pattern per suggestion (**EKP-DP18**).
- **DP-AI-06:** Cite EKP-DP ID when recommending a pattern.
- **DP-AI-07:** Escalate cross-service concerns to architecture — do not solve with class patterns.
- **DP-AI-08:** Link `refactoring.md` procedure names for structural changes — do not inline extract/move steps.

### Cursor

- Run AI Decision Flow before generating `*Factory`, `*Strategy`, or `*Repository` files.
- Do not auto-create pattern boilerplate in agent mode without user-stated variation problem.

### Claude

- Separate "pattern recommendation" from "required for task" in responses.
- Cap pattern explanations: problem, trade-off, one example — no textbook chapters.

### Google Gravity

- Bind pattern suggestions to explicit user task boundaries.
- Block enterprise pattern vocabulary (CQRS, event bus topology) unless user requests architecture work.

### Future adapters

- Map `adapter_priority: high` to AI Decision Flow + EKP-DP16 table first.
- Emit rules from EKP-DP IDs, not principle prose (EKP-P02/P05/P09 referenced, not restated).

## Review signals

| Signal | Verdict | Concept |
|--------|---------|---------|
| Problem stated; pattern name matches; one pattern; tests cover variants | Good pattern use | EKP-DP01, EKP-DP08–15 |
| Pattern without stated recurrence | Cargo cult | EKP-DP16 |
| Three new classes for one `if` branch | Over-abstraction | EKP-DP17 |
| Factory + Strategy + Observer in feature PR | Pattern stacking | EKP-DP18, EKP-RF06 |
| Repository over trivial CRUD | Misapplied Repository | EKP-DP16 |
| Cross-service "Adapter" without ADR | Wrong layer | Escalate architecture |
| Method names unclear inside pattern classes | Hygiene issue | EKP-CC01 (`clean-code.md`) |

## Trade-offs

A disciplined pattern catalog improves structural vocabulary and review consistency. It is not free.

| Benefit | Cost |
|---------|------|
| Shared names for recurring structures (**EKP-P09**) | Indirection and navigation overhead |
| Explicit trade-offs reduce cargo cult (**EKP-P02**) | Upfront problem analysis time |
| Composable extension points | Wrong pattern harder to remove than duplication |
| AI assistants cite stable IDs (EKP-DP) | Risk of over-suggestion without Decision Flow |

**When this document is insufficient:**

- Function readability → `clean-code.md` (EKP-CC)
- Class responsibility diagnosis → `solid.md` (EKP-SL)
- How to introduce structure safely → `refactoring.md` (EKP-RF)
- Service layers, API gateways, event topology → `layering-and-boundaries.md` + ADR
- Framework-specific wiring → stack domains (`symfony/`, `typescript/`, `database/`)

## Knowledge graph position

| Field | Value |
|-------|-------|
| `role` | `pattern` |
| `depends_on` | `engineering-principles.md`, `solid.md` (ADR-0004 exception) |
| `implements` | EKP-P02, EKP-P05, EKP-P09 |
| `concept_ids` | EKP-DP01–EKP-DP18 |
| `adapter_priority` | high — AI Decision Flow + cargo-cult table |
| Siblings | `clean-code.md` (practice), `refactoring.md` (procedure) |
| Prerequisite | `solid.md` (EKP-SL) |
| Escalation | `layering-and-boundaries.md`, ADRs |

```
engineering-principles
        │
        ├── solid (practice) ──────► prerequisite
        │       │
        │       └── design-patterns (patterns) ◄── this document
        ├── clean-code (practice)
        └── refactoring (procedure) ──► related outcomes
```

## Related

- [Engineering Principles](engineering-principles.md) — EKP-P01–P10 foundation
- [SOLID](solid.md) — class/module design prerequisite (EKP-SL)
- [Clean Code](clean-code.md) — function/file readability (EKP-CC)
- [Refactoring](refactoring.md) — structural change procedures (EKP-RF)
- [ADR-0004: Knowledge graph layering](../architecture/decisions/adr-0004-clean-code-position-in-knowledge-graph.md)
- [Architecture decision records](../architecture/decisions/README.md)
- [Layering and Boundaries](../architecture/layering-and-boundaries.md) — system boundaries (EKP-LB; EKP-P05, EKP-P06)
- [Engineering domain index](README.md)
