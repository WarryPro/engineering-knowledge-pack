---
title: Engineering Principles
domain: engineering
tags: [principles, decision-making, tradeoffs, standards, foundation]
severity: required
applies_to: [backend, frontend, api, mobile, devops]
type: guide
role: foundation
related:
  - knowledge/engineering/clean-code.md
  - knowledge/engineering/solid.md
  - knowledge/engineering/refactoring.md
  - knowledge/engineering/design-patterns.md
  - knowledge/engineering/error-handling.md
  - knowledge/architecture/layering-and-boundaries.md
  - knowledge/architecture/decisions/README.md
  - knowledge/architecture/decisions/adr-0004-clean-code-position-in-knowledge-graph.md
extends: []
depends_on: []
concept_ids: [EKP-P01, EKP-P02, EKP-P03, EKP-P04, EKP-P05, EKP-P06, EKP-P07, EKP-P08, EKP-P09, EKP-P10]
---

# Engineering Principles

## Summary

This document defines the universal engineering principles that govern how software is designed, built, reviewed, and maintained across all technology stacks in EKP. It explains how senior engineers make technical decisions under uncertainty, when to apply each principle, and when deliberate deviation is justified. Every other knowledge document in this repository derives its authority from these principles.

`severity: required` means every technical decision **must consider** these principles—not that every principle **must be applied literally** in every context. Deviation with documented rationale is valid engineering judgment.

## Document metadata

Per `schema/knowledge-frontmatter.schema.json`:

| Field | Required | Value in this document |
|-------|----------|------------------------|
| `title` | Yes | Engineering Principles |
| `domain` | Yes | `engineering` (matches directory) |
| `tags` | Yes | Discovery and filtering tags |
| `severity` | Yes | `required` — must be considered in decisions |
| `applies_to` | Yes | Contexts where principles apply |
| `type` | No | `guide` — decision framework, not a checklist |
| `related` | No | Downstream knowledge this document enables |
| `role` | No | `foundation` — apex of the engineering knowledge hierarchy |
| `concept_ids` | No | Stable identifiers (`EKP-P01`–`EKP-P10`) for cross-references |
| `depends_on` | No | Empty — no upstream knowledge dependencies |
| `extends` | No | Reserved for documents that specialize this one |

## Context

Engineering teams face the same failure modes regardless of stack: solutions that solve the wrong problem, abstractions that outlive their purpose, decisions made without recorded rationale, and principles applied as dogma without regard for context.

Without shared principles, code review becomes a contest of personal preference. AI assistants amplify this problem—they generate syntactically correct code that violates structural boundaries because they lack explicit decision-making criteria.

These principles are not a checklist to maximize. They are a **decision framework**: a shared vocabulary for evaluating trade-offs, a baseline for review, and a reference for humans and AI assistants when no stack-specific guidance exists.

### Principles, heuristics, practices, and rules in EKP

EKP uses four terms with distinct roles. Do not conflate them.

| Term | What it is | Stability | Where it lives | Example |
|------|------------|-----------|----------------|---------|
| **Principle** | A durable value judgment about how to build software | Stable — changes rarely, with broad review | `knowledge/` (this document) | EKP-P02: Match solution complexity to problem significance |
| **Heuristic** | A principle applied in context; may be overridden with rationale | Stable principle, situational application | Expressed through principles + deviation table | Prefer reversibility—except in regulated audit trails |
| **Practice** | A concrete, repeatable technique that operationalizes a principle | Evolves with stack and tooling | `knowledge/<domain>/` guides | Boundary validation (implements EKP-P06) |
| **Rule** | A concise, enforceable directive for AI assistants | Generated — regenerated when knowledge changes | `rules/<tool>/` (Phase 5) | "Validate all external payloads at the API boundary" |

**Layering in EKP:**

```
Principles (this document)
    ↓ operationalized by
Knowledge practices (clean-code, solid, refactoring, architecture…)
    ↓ transformed by adapters (Phase 5)
Rules (Cursor, Copilot, Claude)
    ↓ composed by
Profiles (scoped bundles for teams/stacks)
```

This document contains **principles only**. It does not prescribe naming conventions, class design patterns, or refactoring techniques—that is the role of downstream knowledge documents. Rules derived from this document will be **sparse and judgment-oriented**; specific enforceable directives come from practices that reference these principles.

## Guidance

### How senior engineers make technical decisions

Senior engineers do not start with solutions. They start by constraining the problem.

**Decision process:**

1. **Clarify the problem** — What breaks if we do nothing? Who is affected? What is the acceptable failure mode?
2. **Identify constraints** — Time, budget, team skill, regulatory requirements, existing system boundaries, operational capacity.
3. **Classify reversibility** — Is this a one-way door (hard to undo) or a two-way door (cheap to change)? Invest disproportionate effort in one-way doors.
4. **Enumerate alternatives** — At least two viable options. "Do nothing" and "rewrite everything" are valid endpoints, not strawmen.
5. **Evaluate trade-offs explicitly** — For each option: what you gain, what you sacrifice, what new risks you introduce.
6. **Choose the smallest sufficient change** — The option that solves the stated problem without introducing unnecessary complexity.
7. **Record the decision** — When the choice is non-obvious or hard to reverse, document context, alternatives, and rationale (see ADRs in `knowledge/architecture/decisions/`).
8. **Define verification** — How will you know the decision worked? What signals indicate it failed?

A decision without acceptance criteria is a guess with extra steps.

### EKP-P01: Solve the actual problem

Address the root cause or the stated requirement—not the symptom, not the interesting adjacent problem, not the problem you wish you had.

- Define acceptance criteria before implementation.
- Resist scope expansion during implementation unless the new scope addresses a discovered constraint.
- If the problem is unclear, invest in clarification before code.

**Signals you are off track:** The PR solves something the ticket never mentioned. The abstraction exists "for future use" with no concrete consumer. The fix requires three other systems to change.

### EKP-P02: Proportionality

Match solution complexity to problem significance, lifespan, and blast radius.

| Factor | Lean toward simplicity | Lean toward structure |
|--------|------------------------|----------------------|
| Lifespan | Script, prototype, experiment | Core domain, long-lived API |
| Blast radius | Internal tool, isolated module | Payment, auth, data migration |
| Change frequency | Stable requirements | High-churn business rules |
| Team size | Solo or pair | Multiple teams, shared codebase |

A one-off data fix does not need a framework. A payment boundary does not belong in a controller method.

### EKP-P03: Prefer reversible decisions

When two options are equally viable, choose the one that is cheaper to change later.

- Defer irreversible choices until you have evidence.
- Use feature flags, interface boundaries, and configuration over hard-coded branching where rollback matters.
- Separate "decide" from "commit"—prototype behind an interface before baking in a dependency.
- Safe structural change procedures are defined in `refactoring.md` (EKP-RF01–EKP-RF07).

One-way doors deserve design review. Two-way doors deserve speed.

### EKP-P04: Explicit over implicit

Make contracts, assumptions, and failure modes visible—not inferred from convention or tribal knowledge.

- State what must remain true and what must never happen.
- Prefer typed contracts and schema validation over unchecked assumptions.
- Naming and readability practices that implement this principle are defined in `clean-code.md` (EKP-CC01–EKP-CC08).

Implicit behavior is a liability. The next engineer—or the AI assistant—will not infer what you assumed.

### EKP-P05: Local reasoning

A unit of code should be understandable without loading the entire system into working memory.

- Limit side effects and hidden dependencies.
- Avoid shared mutable state across boundaries without a documented concurrency model.
- Class and module decomposition is defined in `solid.md` (EKP-SL01–EKP-SL05).
- System-level boundaries and architectural ownership are defined in `knowledge/architecture/layering-and-boundaries.md` (EKP-LB01–EKP-LB16).

If you cannot explain what a unit does in two sentences, it likely does too much.

### EKP-P06: Own the boundary

Every interface between systems, teams, or layers has an owner responsible for contract stability, error semantics, and versioning.

- Define what crosses the boundary: data shape, error codes, idempotency guarantees, timeout behavior.
- Validate at the boundary. Do not trust upstream input because "it's internal."
- Version or evolve contracts deliberately. Breaking changes require migration paths.
- Boundary ownership and integration contracts are defined in `knowledge/architecture/layering-and-boundaries.md` (EKP-LB01–EKP-LB16).

Leaky abstractions are boundary failures. "It usually works" is not a contract.

### EKP-P07: Fail fast and visibly

Errors should surface at the point of failure—or as close as possible—with enough context to diagnose.

- Do not swallow exceptions and return defaults unless the default is a documented, safe business outcome.
- Log with correlation identifiers across service boundaries.
- Prefer structured errors over boolean success flags that hide failure reason.
- In user-facing paths, fail gracefully; in internal pipelines, fail loudly.
- Error handling practices are defined in `error-handling.md` (EKP-EH01–EKP-EH12).

Silent failure is the most expensive bug class. It compounds until production data is wrong.

### EKP-P08: Evidence before optimization

Do not optimize without measurement. Do not measure without a hypothesis.

- Profile or instrument before rewriting hot paths.
- State the performance target (latency, throughput, memory) and the acceptable trade-off (complexity, cost).
- Optimize the bottleneck, not the code you find most interesting.

Premature optimization wastes time. Optimizing the wrong layer wastes time and adds complexity.

### EKP-P09: Compose, do not accumulate

Prefer small, composable units over monolithic structures that accrete unrelated responsibility.

- Extract when duplication represents a **concept**, not a coincidence.
- Class design heuristics (composition vs inheritance, dependency direction) are defined in `solid.md` (EKP-SL01–EKP-SL05).
- Named pattern catalog is defined in `design-patterns.md` (EKP-DP01–EKP-DP18).

Composition scales. Structures that grow by accumulation do not.

### EKP-P10: Maintainability is a feature

Optimize for the cost of change over the cost of initial authorship.

- Keep changes reviewable and scoped to the stated problem.
- Structural change procedures are defined in `refactoring.md` (EKP-RF01–EKP-RF07).
- Code hygiene practices are defined in `clean-code.md` (EKP-CC01–EKP-CC08).

Technical debt is a loan. Unacknowledged debt is insolvency.

### When principles must not be applied blindly

Principles are heuristics, not laws. Deliberate deviation is valid when you can articulate **why** the context overrides the default.

| Situation | Principle under pressure | Valid deviation |
|-----------|--------------------------|-----------------|
| Time-critical incident | EKP-P02, EKP-P03 | Minimal hotfix with documented follow-up ticket |
| Throwaway prototype | EKP-P10, EKP-P04 | Speed to validate hypothesis; discard or harden before production |
| Regulated domain (health, finance) | EKP-P03, EKP-P01 | Mandatory audit trails, approved patterns that add ceremony |
| Legacy system with no tests | EKP-P05, EKP-P09 | Narrow seam for change; strangler pattern over big-bang rewrite |
| Known temporary bridge | EKP-P06 | Explicitly marked technical debt with expiry condition |
| Strong team convention elsewhere | EKP-P04 | Follow local convention when migrating; document divergence |

**Red flags for blind application:**

- "We always do it this way" without current justification.
- Refactoring unrelated code because a principle "suggests" a cleaner shape.
- Blocking delivery to achieve theoretical purity when the business cost of delay exceeds the technical cost of debt.
- Applying production standards to scripts that run once and are deleted.

Deviation requires **documented rationale**—in the PR description, an ADR, or a ticket comment. Undocumented deviation is not engineering judgment; it is inconsistency.

### Anti-patterns

| Anti-pattern | What it looks like | Why it fails |
|--------------|-------------------|--------------|
| **Cargo cult architecture** | Adopting microservices, event sourcing, or CQRS because a conference talk recommended it | Adds operational and cognitive cost without a problem that requires it |
| **Premature abstraction** | Factory-of-factory patterns before the second use case exists | Hides simple logic; wrong abstraction is harder to remove than duplication |
| **Gold plating** | Configurable, plugin-based solution for a fixed requirement | Pays complexity cost forever for flexibility never used |
| **Principle shopping** | Citing "simplicity" to avoid necessary structure, or "clean architecture" to justify over-engineering | Principles become rhetorical weapons, not decision tools |
| **Review by vibe** | "This doesn't feel right" without referencing criteria | Blocks progress; teaches nothing; does not scale |
| **Implicit context** | "Everyone knows payments go through the legacy module" | Knowledge leaves with people; AI assistants cannot infer it |
| **Error erasure** | `catch (Exception e) { return null; }` | Hides defects; corrupts downstream state |
| **Scope smuggling** | Unrelated refactor bundled into a bugfix PR | Increases review burden; obscures risk; blocks rollback |
| **Documentation theater** | README that restates obvious code without decisions or constraints | Creates maintenance burden without decision value |

## Trade-offs

Applying these principles consistently produces predictable systems and reviewable decisions. It is not free.

| Benefit | Cost |
|---------|------|
| Faster onboarding—shared vocabulary reduces debate | Upfront time to document decisions and constraints |
| Fewer structural defects in production | Slower initial delivery vs. unconstrained hacking |
| AI assistants produce structurally aligned code when given this context | Principles require judgment; over-rigid enforcement blocks valid shortcuts |
| Reversible decisions reduce rollback pain | Two-way door discipline can feel bureaucratic for trivial changes |
| Explicit boundaries catch integration defects early | Ceremony at boundaries can feel heavy for small teams |

**When this document is insufficient:** Stack-specific patterns, security controls, and architectural structures are covered in other EKP domains. This document does not replace ADRs, threat models, or performance budgets—it provides the lens through which those artifacts are evaluated.

## Examples

### Example 1: Proportionality in practice

**Situation:** A reporting script runs once per month, reads a CSV export, and emails a summary to three people.

**Avoid:**

```python
# Building a plugin architecture for one report format
class ReportProcessorFactory:
    def create(self, format: str) -> ReportProcessor: ...
```

**Prefer:**

```python
# Direct, readable, disposable if requirements change
def monthly_sales_summary(csv_path: str) -> str:
    rows = parse_csv(csv_path)
    return format_summary(aggregate(rows))
```

If the script becomes a product with multiple consumers and formats, **then** introduce structure—with a ticket and acceptance criteria.

### Example 2: Deliberate deviation with rationale

**Situation:** Production incident—payment webhooks are failing due to a null field introduced by a partner change.

**Deviation:** Hotfix adds a defensive default for the null field directly in the webhook handler, bypassing the usual "map at boundary into domain value object" pattern.

**Valid because:**

- EKP-P03 (reversibility): two-way door; can refactor after incident.
- EKP-P02 (proportionality): blast radius is revenue; speed outweighs purity.
- Documented: PR links to incident ticket; follow-up ticket created to move mapping to boundary.

**Invalid without documentation:** Same hotfix merged with message "quick fix" and no follow-up.

### Example 3: Decision record trigger

**Situation:** Team must choose between synchronous REST calls and an event queue for order fulfillment notifications.

**One-way door elements:** Partner SLAs, retry semantics, operational monitoring model, team familiarity with queue operations.

**Senior engineer action:** Write an ADR comparing options on latency, failure isolation, operational cost, and rollback. Implement the chosen path behind an interface so the notification mechanism can be swapped if evidence contradicts the decision.

## References

These principles align with established engineering practice. They are synthesized for EKP decision-making, not copied verbatim.

- **Reversible vs. irreversible decisions** — Amazon "one-way door / two-way door" decision framework (Bezos, circa 2015). Useful for calibrating design review depth.
- **Local reasoning** — Parnas, "On the Criteria To Be Used in Decomposing Systems into Modules" (1972). Foundation for modularity and information hiding.
- **Composition over inheritance** — Gamma et al., *Design Patterns* (GoF, 1994). Favor object composition over class inheritance.
- **Fail fast** — Shore & Warden, *The Art of Agile Development* (2008). Early failure reduces debugging cost.
- **YAGNI** — Beck, *Extreme Programming Explained* (1999). Build what is needed now; avoid speculative generality.
- **Evidence-based optimization** — Knuth, "Structured Programming with go to Statements" (1974). "Premature optimization is the root of all evil"—in context of ignoring structure, not avoiding measurement.

## Knowledge graph

### Concept identifiers

| ID | Principle | Primary failure mode addressed |
|----|-----------|-------------------------------|
| EKP-P01 | Solve the actual problem | Building the wrong thing |
| EKP-P02 | Proportionality | Over- or under-engineering |
| EKP-P03 | Prefer reversible decisions | Irreversible mistakes |
| EKP-P04 | Explicit over implicit | Tribal knowledge and hidden assumptions |
| EKP-P05 | Local reasoning | Changes with system-wide blast radius |
| EKP-P06 | Own the boundary | Integration defects and contract drift |
| EKP-P07 | Fail fast and visibly | Silent corruption |
| EKP-P08 | Evidence before optimization | Wasted optimization effort |
| EKP-P09 | Compose, do not accumulate | Monolithic, rigid structures |
| EKP-P10 | Maintainability is a feature | Rising cost of change |

### Dependencies

This document has **no upstream knowledge dependencies** (`depends_on: []`). It is the apex of the engineering knowledge hierarchy.

### Downstream knowledge (builds upon this document)

| Document | Status | Principles it operationalizes | Scope |
|----------|--------|------------------------------|-------|
| [clean-code.md](clean-code.md) | Published | EKP-P04, EKP-P10 | Naming, readability, code hygiene (EKP-CC) |
| [solid.md](solid.md) | Published | EKP-P05, EKP-P09 | Class design and dependency management (EKP-SL) |
| [refactoring.md](refactoring.md) | Published | EKP-P03, EKP-P10 | Safe structural change procedures (EKP-RF) |
| [design-patterns.md](design-patterns.md) | Published | EKP-P02, EKP-P05, EKP-P09 | Named pattern catalog (EKP-DP) |
| [error-handling.md](error-handling.md) | Published | EKP-P07 | Failure handling practice (EKP-EH) |

### Architecture layer (builds upon principles)

| Document | Layer | Status |
|----------|-------|--------|
| [layering-and-boundaries.md](../architecture/layering-and-boundaries.md) | architecture | Published |

Downstream documents must reference this document in their `related` frontmatter and must not restate principles—only operationalize them.

### Related concepts

- **Heuristics** — situational application of principles (see deviation table)
- **Practices** — stack-agnostic techniques in `knowledge/engineering/`
- **ADRs** — decision records for one-way doors (`knowledge/architecture/decisions/`)
- **Rules** — AI directives derived from practices, not from principles directly

## Related

- Domain index: [engineering/README.md](README.md)
- [Clean Code](clean-code.md) — readability and hygiene practices (EKP-CC; EKP-P04, EKP-P10)
- [SOLID](solid.md) — class/module design practices (EKP-SL; EKP-P05, EKP-P09)
- [Refactoring](refactoring.md) — safe structural change procedures (EKP-RF; EKP-P03, EKP-P10)
- [Design Patterns](design-patterns.md) — named pattern catalog (EKP-DP; EKP-P02, EKP-P05, EKP-P09)
- [Error Handling](error-handling.md) — failure handling practice (EKP-EH; EKP-P07)
- [Layering and Boundaries](../architecture/layering-and-boundaries.md) — system structure and integration contracts (EKP-LB; EKP-P05, EKP-P06)
- Decision records: [architecture/decisions/README.md](../architecture/decisions/README.md)
- [ADR-0004: Clean Code position in knowledge graph](../architecture/decisions/adr-0004-clean-code-position-in-knowledge-graph.md)
