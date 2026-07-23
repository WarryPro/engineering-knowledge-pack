---
title: SOLID
domain: engineering
tags: [solid, class-design, responsibility, dependencies, practices]
severity: recommended
applies_to: [backend, frontend, api, mobile]
type: guide
role: practice
depends_on:
  - knowledge/engineering/engineering-principles.md
implements:
  - EKP-P05
  - EKP-P09
related:
  - knowledge/engineering/engineering-principles.md
  - knowledge/engineering/clean-code.md
  - knowledge/engineering/refactoring.md
  - knowledge/engineering/design-patterns.md
  - knowledge/architecture/layering-and-boundaries.md
  - knowledge/architecture/decisions/adr-0004-clean-code-position-in-knowledge-graph.md
extends: []
concept_ids: [EKP-SL01, EKP-SL02, EKP-SL03, EKP-SL04, EKP-SL05]
---

# SOLID

## Summary

Stack-agnostic class and module design heuristics: Single Responsibility, Open/Closed, Liskov Substitution, Interface Segregation, and Dependency Inversion. This document operationalizes **EKP-P05** (Local reasoning) and **EKP-P09** (Compose, do not accumulate) at the structural level. SOLID in EKP is a **review framework**, not a compliance checklist.

Apply during design and code review. Relax per **EKP-P02** (Proportionality) for prototypes, data carriers, and low-lifespan code. Do not refactor toward SOLID during incidents without documented follow-up (**EKP-P03**).

## Context

Poor class and module design spreads change across the codebase. A class with mixed responsibilities forces every feature touching one concern to risk breaking another. Hidden dependencies make units impossible to reason about locally (**EKP-P05**). Monolithic structures resist change without modification (**EKP-P09**).

[Engineering Principles](engineering-principles.md) define *why* local reasoning and composition matter. This document defines *how* to evaluate class and module structure. Every practice traces to an **EKP-SL** concept ID and EKP-P05 or EKP-P09.

**Boundaries:**

| Layer | Document | Unit of analysis |
|-------|----------|------------------|
| Function/file readability | `clean-code.md` (EKP-CC) | Names, functions, formatting |
| Class/module structure | **this document** (EKP-SL) | Responsibilities, dependencies, substitutability |
| System structure | `layering-and-boundaries.md` | Layers, services, integration contracts |

**Out of scope:** naming and formatting (`clean-code.md`), structural change procedures (`refactoring.md`), named patterns (`design-patterns.md`), framework DI configuration (`symfony/`, stack domains), microservices/CQRS/hexagonal architecture (`architecture/`).

## Guidance

### Anti-dogmatism

SOLID is widely misapplied. EKP treats these heuristics as **tools for judgment**, not laws.

| Dogma | EKP position |
|-------|--------------|
| Every class needs an interface | **False.** Introduce an abstraction when you have multiple implementations, a required test seam, or stable extension points—not by default. Unnecessary interfaces add indirection without benefit (**EKP-P02**). |
| SRP means one method per class | **False.** SRP means one **reason to change**. A cohesive 150-line class with a single responsibility is valid. Split when *reasons to change* diverge, not when line count exceeds a threshold. |
| DIP equals dependency injection frameworks | **False.** DIP means high-level policy depends on abstractions, not concretions. Constructor injection makes dependencies visible; Symfony, Spring, and NestJS containers are **implementation mechanisms**—documented in stack guides, not here. |
| OCP must be applied everywhere | **False.** Extension points (interfaces, hooks, plugins) carry **indirection cost**: more types, more navigation, harder onboarding. Add OCP when change frequency justifies the abstraction (**EKP-P02**). |
| DTOs and records need full SOLID | **False.** Data carriers with no behavior exist to transfer state. Applying SRP/OCP/ISP to `OrderDto` is meaningless. Evaluate SOLID on units that **own behavior and change**. |
| Refactor to SOLID during incidents | **Forbidden without justification.** Incident response optimizes for reversibility and speed (**EKP-P03**). Structural cleanup belongs in a follow-up ticket—not mixed into a hotfix PR. |

When SOLID and delivery pressure conflict, document the deviation. Undocumented shortcut is inconsistency; documented shortcut is engineering judgment.

---

### EKP-SL01: Single Responsibility Principle (SRP)

**Implements:** EKP-P05

**Intent:** A class or module should have only one reason to change—one axis of responsibility that stakeholders care about independently.

**Problem it solves:** Mixed responsibilities couple unrelated change triggers. Modifying payment logic breaks reporting because both live in the same class. Reviewers cannot predict blast radius.

**Good practices:**

- Identify **reasons to change** by stakeholder or capability: "changes when tax rules change," "changes when UI layout changes."
- Split when two independent business rules evolve on different schedules in the same unit.
- Apply SRP at **module and package** level in non-OOP code—a Go package exporting unrelated concerns violates SRP.
- Co-locate behavior with the data it operates on when they share one reason to change.

**Trade-offs:**

| Gain | Cost |
|------|------|
| Localized change; smaller blast radius | More classes/modules; navigation overhead |
| Clearer ownership in review | Risk of over-splitting cohesive logic |

**When NOT to apply strictly:**

- Data transfer objects, configuration records, and generated structs—no behavior, no reasons to change beyond schema.
- Facades that intentionally coordinate a single use case (one reason: "orchestrate checkout").
- Prototypes where structure will be discarded (**EKP-P02**).

**Examples — avoid:**

```text
class OrderService {
  validateOrder()
  calculateTax()
  sendConfirmationEmail()
  generatePdfInvoice()
  saveToDatabase()
}
// Reasons to change: tax law, email templates, PDF format, persistence schema
```

**Examples — prefer:**

```text
class OrderService {
  placeOrder()  // orchestrates single use case
}
// TaxCalculator, NotificationService, InvoiceRenderer, OrderRepository — separate reasons
```

**Review signals:**

- "Changing X forced me to edit unrelated method Y in the same class."
- Class name is a conjunction: `UserAndBillingManager`.
- Test setup requires mocking unrelated dependencies to test one method.

---

### EKP-SL02: Open/Closed Principle (OCP)

**Implements:** EKP-P09

**Intent:** Units should be open for extension but closed for modification—new behavior added without editing stable, tested code.

**Problem it solves:** Every new feature edits a central `switch` or `if-else` chain, re-running regression risk on existing paths. The module becomes a change bottleneck.

**Good practices:**

- Introduce extension points where **variation is proven**: payment providers, export formats, pricing rules.
- Prefer **composition and registration** over growing conditional logic.
- Keep the extension mechanism simple—one interface or callback registry, not a plugin framework for two variants.
- Default implementation lives alongside the abstraction; extensions register explicitly.

**Trade-offs:**

| Gain | Cost |
|------|------|
| Existing behavior stays untouched when adding variants | Indirection: more types, harder trace for new readers |
| Easier parallel development per variant | Speculative extension points before variants exist (**YAGNI**) |

**When NOT to apply strictly:**

- Only one implementation exists and none is planned—do not create `PaymentProcessor` + `DefaultPaymentProcessor` for one path (**EKP-P02**).
- Variation is configuration data, not behavior—a lookup table beats a class hierarchy.
- Lifespan is a one-off script or migration.

**OCP indirection cost:** Each extension point adds at least one abstraction, one indirection at the call site, and one more file to navigate. Pay this cost when the **frequency of new variants** exceeds the **cost of modifying the original**. If you add a variant once per year, a `switch` may be cheaper.

**Examples — avoid:**

```text
function calculateShipping(order, type) {
  if (type == "standard") { ... }
  else if (type == "express") { ... }
  // every new carrier edits this function
}
```

**Examples — prefer:**

```text
interface ShippingStrategy { cost(order) }
// StandardShipping, ExpressShipping registered in a map by type
// New carrier = new class, no edit to existing carriers
```

**Review signals:**

- Growing `switch`/`match` on the same variable across releases.
- "I had to modify tested code to add a new variant."
- Plugin interface with only one implementation and no roadmap for a second.

---

### EKP-SL03: Liskov Substitution Principle (LSP)

**Implements:** EKP-P05

**Intent:** Subtypes must be substitutable for their base type without altering correctness—callers depend on behavior contracts, not accidental implementation details.

**Problem it solves:** Overrides that strengthen preconditions, weaken postconditions, or throw unexpected errors break callers silently. Polymorphism becomes a defect source.

**Good practices:**

- Subtypes must honor the **behavioral contract** of the base: same inputs produce compatible outcomes.
- Do not override a method to throw `UnsupportedOperationException` for valid base operations.
- Preconditions: subtype may not require *more* from the caller. Postconditions: subtype must deliver *at least* what the base promised.
- Prefer composition over inheritance when behavior diverges significantly (see EKP-P09).

**Trade-offs:**

| Gain | Cost |
|------|------|
| Safe polymorphism; trustworthy abstractions | Restricts inheritance hierarchies; may push toward composition |
| Clearer contracts in review | Behavioral contracts are harder to verify than syntax |

**When NOT to apply strictly:**

- Sealed hierarchies where substitution is intentionally limited by design (document the constraint).
- Internal package-private subclasses not used polymorphically.

**Examples — avoid:**

```text
class Bird { fly() }
class Penguin extends Bird {
  fly() { throw Error("cannot fly") }  // violates LSP for callers of Bird
}
```

**Examples — prefer:**

```text
interface Flyable { fly() }
class Sparrow implements Flyable { ... }
class Penguin { swim() }  // no false IS-A relationship
```

**Review signals:**

- Override throws "not supported" for a valid base operation.
- Caller checks concrete type before calling: `if (x instanceof SpecialCase)`.
- Subclass requires callers to know implementation details to use safely.

---

### EKP-SL04: Interface Segregation Principle (ISP)

**Implements:** EKP-P05, EKP-P09

**Intent:** Clients should not depend on methods they do not use. Prefer small, role-specific interfaces over fat general-purpose ones.

**Problem it solves:** Fat interfaces force implementors to stub unused methods and couple clients to unrelated changes. Every implementor breaks when any method changes.

**Good practices:**

- Split interfaces by **caller role**: `ReadableOrder`, `WritableOrder`—not one `Order` with twelve methods.
- If an implementor leaves methods empty or throws "not implemented," the interface is too fat.
- Role interfaces can compose at the call site when a client needs multiple roles.
- At module level: export minimal public surface; keep internals private.

**Trade-offs:**

| Gain | Cost |
|------|------|
| Implementors only provide what they use | More interface types; assembly at call sites |
| Changes isolated to affected clients | Risk of interface proliferation (over-segregation) |

**When NOT to apply strictly:**

- Single cohesive object where all methods genuinely serve one client (rare at scale).
- Language constraints that penalize many small types without benefit.

**Not every class needs an interface:** ISP applies when you **have** an abstraction. A concrete `CsvExporter` with one caller and no test seam does not need `ExporterInterface` until a second implementation or mock boundary appears.

**Examples — avoid:**

```text
interface Worker {
  work(); eat(); sleep(); attendMeeting(); fileExpenses()
}
class Robot implements Worker {
  eat() { throw Error("not applicable") }
}
```

**Examples — prefer:**

```text
interface Workable { work() }
interface ExpenseReportable { fileExpenses() }
class Robot implements Workable { ... }
class Human implements Workable, ExpenseReportable { ... }
```

**Review signals:**

- Implementor methods that throw "not supported" or are empty stubs.
- Client imports an interface but calls only one of eight methods.
- Interface changes break implementors that never used the changed method.

---

### EKP-SL05: Dependency Inversion Principle (DIP)

**Implements:** EKP-P09

**Intent:** High-level modules define the abstractions they need; low-level modules implement them. Both depend on the abstraction—not on each other directly.

**Problem it solves:** Business logic imports database drivers, HTTP clients, and file paths directly. Policy cannot be tested or reused without infrastructure. Changes ripple upward.

**Good practices:**

- High-level policy depends on **abstractions** (interfaces, protocols) it owns or co-owns with the domain.
- Low-level details (SQL, REST, filesystem) implement those abstractions in outer layers—see `layering-and-boundaries.md` for where layers sit.
- Make dependencies **visible**: constructor parameters, factory arguments—not hidden lookups.
- Abstractions named for domain capability: `OrderRepository`, not `MySqlAdapter`.

**DIP is not dependency injection frameworks:** DIP is a **design rule**. Constructor injection is one way to make dependencies explicit. Symfony `services.yaml`, NestJS modules, and Spring `@Autowired` are **wiring mechanisms**—they implement DIP but do not define it. Stack guides document container configuration; this document defines the dependency direction rule.

**Trade-offs:**

| Gain | Cost |
|------|------|
| Testable policy without infrastructure | More types; mapping between abstraction and implementation |
| Swappable implementations | Wrong abstraction locks you in as surely as concrete coupling |

**When NOT to apply strictly:**

- Stable, universal primitives (`string`, `datetime`)—no abstraction needed.
- Single implementation with no test requirement and no anticipated variant—concrete dependency is acceptable (**EKP-P02**).
- Thin scripts and CLIs at the outermost edge.

**Examples — avoid:**

```text
class PlaceOrderHandler {
  placeOrder(cmd) {
    conn = MySqlConnection.fromEnv()  // policy depends on MySQL directly
    conn.execute("INSERT ...")
  }
}
```

**Examples — prefer:**

```text
class PlaceOrderHandler {
  constructor(orderRepository)  // depends on abstraction
  placeOrder(cmd) {
    orderRepository.save(cmd.toOrder())
  }
}
// MySqlOrderRepository implements OrderRepository in infrastructure layer
```

**Review signals:**

- Domain/business class imports infrastructure packages (ORM, HTTP client SDK).
- Unit test requires database or network to run.
- `new ConcreteService()` inside policy logic instead of injected abstraction.

---

### Composition vs inheritance

**Implements:** EKP-P09 (supporting guidance)

Prefer **composition** when behavior varies or combines. Use **inheritance** only for true IS-A relationships that satisfy LSP (EKP-SL03). Inheritance couples subclasses to parent implementation; composition localizes change.

This is not a design pattern catalog—see `design-patterns.md` for named structures. This is a default preference when choosing how to share behavior.

---

### Review signals (summary)

| Signal | Likely concept | Layer check |
|--------|----------------|-------------|
| Unrelated methods change together | EKP-SL01 | solid, not clean-code |
| Function name unclear | EKP-CC01 | clean-code, not solid |
| Growing switch for variants | EKP-SL02 | solid |
| Override throws "not supported" | EKP-SL03 | solid |
| Fat interface with stub methods | EKP-SL04 | solid |
| Domain imports database driver | EKP-SL05 | solid; layer boundary → architecture |
| API calls database directly | — | `layering-and-boundaries.md` |

Reference IDs in review: `"Violates EKP-SL01 — mixed persistence and notification responsibilities."`

## Trade-offs

Applying SOLID consistently improves structural maintainability. It is not free.

| Benefit | Cost |
|---------|------|
| Predictable change blast radius | More types and indirection |
| Testable policy without infrastructure | Upfront design time |
| Shared review vocabulary (EKP-SL01–05) | Learning curve; misuse as dogma |
| AI assistants generate structurally sound classes | Over-abstraction when applied blindly |

**When this document is insufficient:**

- Function readability → `clean-code.md`
- How to split a class safely → `refactoring.md`
- Strategy, Factory, Observer → `design-patterns.md`
- Service layers, API boundaries → `layering-and-boundaries.md`
- Container wiring → stack domains (`symfony/`, `typescript/`)

## Examples

### Combined review scenario

**Finding:** `ReportService` generates PDFs, queries the database, and sends Slack notifications. It implements `Exporter` with twelve methods; only `exportPdf` is used. Domain handlers construct `new PostgresClient()` directly.

| Issue | Concept | Diagnosis |
|-------|---------|-----------|
| PDF + DB + Slack in one class | EKP-SL01 | Multiple reasons to change |
| Twelve-method interface, one used | EKP-SL04 | Fat interface; split by role |
| `new PostgresClient()` in handler | EKP-SL05 | Policy depends on concretion |
| Method name `doStuff` | EKP-CC01 | **clean-code**, not solid |

Structural fix procedures belong in `refactoring.md`—this table diagnoses only.

## Knowledge graph

| Field | Value |
|-------|-------|
| `role` | `practice` |
| `depends_on` | `engineering-principles.md` |
| `implements` | EKP-P05, EKP-P09 |
| Siblings | `clean-code.md`, `refactoring.md`, `design-patterns.md` |
| Downstream | `design-patterns.md` (depends on solid per ADR-0004) |

## Related

- [Engineering Principles](engineering-principles.md) — EKP-P01–P10 foundation
- [Clean Code](clean-code.md) — function/file readability (EKP-CC)
- [ADR-0004: Clean Code position in knowledge graph](../architecture/decisions/adr-0004-clean-code-position-in-knowledge-graph.md)
- Planned: `knowledge/engineering/refactoring.md` — structural change procedures
- Planned: `knowledge/engineering/design-patterns.md` — named patterns (depends on this document)
- Planned: `knowledge/architecture/layering-and-boundaries.md` — system boundaries (EKP-P06)
- [Engineering domain index](README.md)
