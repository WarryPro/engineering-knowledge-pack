---
title: Clean Code
domain: engineering
tags: [clean-code, naming, readability, hygiene, practices]
severity: recommended
applies_to: [backend, frontend, api, mobile]
type: guide
role: practice
depends_on:
  - knowledge/engineering/engineering-principles.md
implements:
  - EKP-P04
  - EKP-P10
related:
  - knowledge/engineering/engineering-principles.md
  - knowledge/engineering/solid.md
  - knowledge/engineering/refactoring.md
  - knowledge/engineering/error-handling.md
  - knowledge/architecture/layering-and-boundaries.md
  - knowledge/architecture/decisions/adr-0004-clean-code-position-in-knowledge-graph.md
extends: []
concept_ids: [EKP-CC01, EKP-CC02, EKP-CC03, EKP-CC04, EKP-CC05, EKP-CC06, EKP-CC07, EKP-CC08]
---

# Clean Code

## Summary

Stack-agnostic practices for readable, hygienic source code at function and file level: naming, function shape, parameters, control flow, comments, dead code, magic values, and formatting consistency. This document operationalizes **EKP-P04** (Explicit over implicit) and **EKP-P10** (Maintainability is a feature). It does not cover class design, structural refactoring, or design patterns—see sibling documents.

Apply during implementation and code review. Relax standards per **EKP-P02** (Proportionality) for throwaway scripts, generated code, and one-off migrations.

## Context

Code is read far more often than it is written. Poor readability increases review time, defect escape rate, and onboarding cost. AI assistants amplify readability problems—they generate syntactically valid code with misleading names, deep nesting, and comment noise.

[Engineering Principles](engineering-principles.md) define *why* explicit, maintainable code matters. This document defines *how* to write it at the unit level. Every practice here traces to EKP-P04 or EKP-P10 by concept ID.

**Out of scope:** class/module responsibility (`solid.md`), safe structural change (`refactoring.md`), named patterns (`design-patterns.md`), stack-specific linter rules (`php/`, `typescript/`).

## Guidance

### EKP-CC01: Naming

**Implements:** EKP-P04

**Intent:** Names reveal purpose and domain meaning. A reader should understand *what* a unit does without reading its body.

**Practices:**

- Name functions and variables for **intent**, not implementation (`getActiveUsers()` not `getListFromDb()`).
- Use **domain language** from the problem space, not framework jargon, unless the framework term is the domain term.
- Booleans read as predicates: `isActive`, `hasPermission`, `canRetry`—not `flag`, `status`, `check`.
- Avoid abbreviations unless they are universal in the codebase (`id`, `url`) or documented in the domain glossary.
- Files and modules match their primary export or responsibility.
- Constants for fixed domain values; avoid scattering string literals (see EKP-CC07).

**Trade-offs:**

| Gain | Cost |
|------|------|
| Faster comprehension in review and debugging | Longer identifiers; verbosity in hot paths |
| AI assistants infer correct usage from names | Renaming has wide diff impact |

**When not to apply strictly:**

- Throwaway prototypes (EKP-P02) — short names acceptable if lifespan is hours.
- Generated code — do not hand-edit names; configure the generator.
- Well-known mathematical or algorithmic variables (`i`, `j`, `dx`) in small, local loops.

**Example — avoid:**

```text
function process(d) { ... }           // opaque parameter
const temp = user.accountStatus == 1  // magic boolean
```

**Example — prefer:**

```text
function suspendOverdueAccounts(accounts) { ... }
const isAccountActive = user.accountStatus === AccountStatus.Active
```

---

### EKP-CC02: Functions

**Implements:** EKP-P04, EKP-P10

**Intent:** A function does one thing at one level of abstraction. The reader grasps its purpose without scrolling.

**Practices:**

- Keep functions **short enough to hold in working memory** — typically under 30–40 lines; shorter when logic is dense.
- One level of abstraction per function: do not mix HTTP parsing, business rules, and persistence in one body.
- Prefer **flat, sequential steps** over deeply nested logic (see EKP-CC04).
- Extract when a block needs a name to be understood—but defer structural extraction procedures to `refactoring.md`.
- Side effects should be obvious from the name (`save`, `send`, `delete`) or avoided at this level.

**Trade-offs:**

| Gain | Cost |
|------|------|
| Local reasoning within a file | More functions; navigation overhead |
| Smaller review units | Risk of premature extraction (address in review, not by dogma) |

**When not to apply strictly:**

- Cohesive linear scripts where splitting would obscure flow (EKP-P02).
- Performance-critical hot paths where inlining is measured and justified (EKP-P08 — document the exception).

**Example — avoid:**

```text
function handleRequest(req) {
  // 80 lines: validate, transform, query DB, format response, log, metrics
}
```

**Example — prefer:**

```text
function handleRequest(req) {
  const command = parseCreateOrderCommand(req)
  const order = createOrder(command)
  return formatOrderResponse(order)
}
```

---

### EKP-CC03: Parameters

**Implements:** EKP-P04, EKP-P10

**Intent:** Parameters define a function's contract. Unclear or excessive parameters hide coupling and increase misuse.

**Practices:**

- Prefer **three or fewer** parameters. Beyond three, group related data into a typed object or value structure.
- Avoid boolean parameters that switch behavior (`send(user, true)`). Use named alternatives or separate functions unless the flag is universal (`isDryRun`).
- Order parameters consistently across the codebase: required inputs first, optional/config last.
- Do not pass `null` to mean "use default" unless the language idiomatically requires it—prefer explicit option types or overloads at the language layer.
- Output parameters (mutating arguments for return values) are a readability smell—prefer return values.

**Trade-offs:**

| Gain | Cost |
|------|------|
| Clear call sites | Parameter objects add types/boilerplate |
| Fewer misuse bugs | Splitting functions may duplicate shared setup |

**When not to apply strictly:**

- Language/framework callbacks with fixed signatures you do not control.
- Thin wrappers around external APIs where parameter shape is imposed.

**Example — avoid:**

```text
function createInvoice(customer, items, true, false, null) { ... }
```

**Example — prefer:**

```text
function createInvoice(request: CreateInvoiceRequest) { ... }
// CreateInvoiceRequest: { customer, items, sendEmail, applyDiscount }
```

---

### EKP-CC04: Control flow

**Implements:** EKP-P04, EKP-P10

**Intent:** Control flow should express the happy path clearly. Nesting and indirection hide defects.

**Practices:**

- **Guard clauses** first: return or throw early on invalid preconditions; keep the main path unindented.
- Limit nesting to **three levels** maximum. Refactor or extract when deeper.
- Prefer explicit `if/else` over nested ternaries beyond one level.
- `switch`/`match` for discrete value dispatch; avoid long `if-else` chains on the same variable.
- Loops: body should be short; complex iteration logic deserves a named function.

**Trade-offs:**

| Gain | Cost |
|------|------|
| Readable happy path | Early returns can feel scattered in validation-heavy functions |
| Fewer missed edge cases | Guard-heavy functions need consistent error semantics (see [error-handling.md](error-handling.md)) |

**When not to apply strictly:**

- Table-driven or data-driven dispatch where nesting is replaced by lookup.
- Performance-sensitive inner loops where extraction is measured as costly.

**Example — avoid:**

```text
function getDiscount(user) {
  if (user) {
    if (user.isActive) {
      if (user.tier === "gold") {
        return 0.2
      }
    }
  }
  return 0
}
```

**Example — prefer:**

```text
function getDiscount(user) {
  if (!user || !user.isActive) return 0
  if (user.tier === "gold") return 0.2
  return 0
}
```

---

### EKP-CC05: Comments

**Implements:** EKP-P04

**Intent:** Comments explain *why* code exists, not *what* it does. The code itself should express *what*.

**Practices:**

- Write comments for: non-obvious business rules, regulatory constraints, performance workarounds, external system quirks.
- Do not comment obvious code (`// increment i` above `i++`).
- Keep comments **adjacent** to the code they describe; delete comments when code changes.
- `TODO`/`FIXME` must include a ticket reference or owner—bare `TODO` is debt without accountability.
- Public API surface: document contracts, preconditions, and error behavior. Internal functions: comment only when intent is not recoverable from names.

**Trade-offs:**

| Gain | Cost |
|------|------|
| Preserved context for future readers | Comments drift from code; maintenance burden |
| Onboarding speed for domain quirks | Noise when overused |

**When not to apply strictly:**

- Generated files — comment at generation template, not output.
- Legal/license headers required by policy.
- Temporary spike code marked for deletion (EKP-P02).

**Example — avoid:**

```text
// Loop through users
for (const user of users) { ... }
```

**Example — prefer:**

```text
// Partner API returns inactive users; filter client-side until PROJ-482 ships
const activeUsers = users.filter(u => u.status !== "archived")
```

---

### EKP-CC06: Dead code

**Implements:** EKP-P10

**Intent:** Dead code is misleading inventory. It suggests behavior that does not run and blocks confident deletion.

**Practices:**

- Delete unused functions, variables, imports, and branches—do not comment them out "for later."
- Remove feature flags and their branches once the rollout is complete.
- Unreachable code after `return`/`throw` is a defect—remove it.
- If code must be preserved for reference, it lives in version control history, not the active tree.

**Trade-offs:**

| Gain | Cost |
|------|------|
| Smaller cognitive load; accurate codebase map | Lose quick local rollback to deleted snippet (git recovers) |
| Cleaner diffs in review | Requires confidence that deletion is safe (tests help) |

**When not to apply strictly:**

- Staged rollout where flag removal is scheduled with a ticket—document expiry.
- API deprecation windows where `@deprecated` markers are required by policy (remove at announced date).

**Example — avoid:**

```text
// old implementation - keep for reference
// function calculateTax(amount) { ... }

function calculateTax(amount) { ... }
```

**Example — prefer:** Delete the old implementation. Reference the PR or commit in the ticket if history matters.

---

### EKP-CC07: Magic values

**Implements:** EKP-P04

**Intent:** Literal values embedded in logic hide meaning and scatter change points.

**Practices:**

- Replace unexplained literals with **named constants** (`MAX_RETRY_ATTEMPTS = 3`).
- Group related constants (status codes, thresholds, timeouts) in one module or enum-like structure.
- Comments alone do not fix magic values—a named constant is the fix.
- Configuration that varies by environment belongs in configuration, not hard-coded literals.

**Trade-offs:**

| Gain | Cost |
|------|------|
| Single change point; self-documenting thresholds | Indirection for trivial one-off values |
| Safer refactors | Constant proliferation if over-applied |

**When not to apply strictly:**

- `0`, `1`, `-1` in obvious contexts (`array[0]`, `count + 1`, loop increments).
- Mathematical or physical constants with conventional symbols (`Math.PI`).
- Test fixtures where literal values *are* the data under test.

**Example — avoid:**

```text
if (retryCount > 3) { ... }
setTimeout(callback, 86400000)
```

**Example — prefer:**

```text
const MAX_RETRY_ATTEMPTS = 3
const ONE_DAY_MS = 24 * 60 * 60 * 1000

if (retryCount > MAX_RETRY_ATTEMPTS) { ... }
setTimeout(callback, ONE_DAY_MS)
```

---

### EKP-CC08: Formatting principles

**Implements:** EKP-P04, EKP-P10

**Intent:** Consistent formatting removes style debates from review and lets diffs show meaningful changes.

**Practices:**

- **Automate formatting** — use formatters and linters; do not argue spaces vs tabs in review.
- One statement per line for clarity; break long lines at logical boundaries.
- Group related declarations; separate logical blocks with a single blank line.
- Import/using order: standard library, third party, local—consistent across the project.
- Align formatting rules with stack-specific guides in `knowledge/php/`, `knowledge/typescript/`, etc.—this document states principles only.

**Trade-offs:**

| Gain | Cost |
|------|------|
| Review focuses on logic, not style | Formatter churn in large repos on rule changes |
| Consistent cross-team readability | Initial tooling setup per project |

**When not to apply strictly:**

- Minified or machine-generated output.
- Files where manual formatting is required by an external spec (some protocol definitions).

**Example:** Do not hand-format a 500-line JSON config—use a formatter. Do not mix formatted and unformatted regions in the same file.

---

### Review signals

Cross-cutting indicators that clean-code practices are violated. Map findings to concept IDs in review comments.

| Signal | Likely concept | Action |
|--------|----------------|--------|
| "I had to re-read this three times" | EKP-CC01, EKP-CC02 | Clarify names or split function |
| "What does this parameter mean?" | EKP-CC03 | Name parameter or use object |
| "I got lost in the nesting" | EKP-CC04 | Guard clauses or extract |
| "This comment restates the code" | EKP-CC05 | Remove or rewrite for why |
| "Is this used anywhere?" | EKP-CC06 | Delete dead code |
| "What is 86400000?" | EKP-CC07 | Named constant |
| "Inconsistent style in this file" | EKP-CC08 | Run formatter |
| Diff mixes formatting with logic | EKP-CC08, EKP-P10 | Separate formatting commit or pre-format |

Reference principle IDs when escalating: "Violates EKP-P04 — implicit behavior via magic literal (EKP-CC07)."

## Trade-offs

Applying clean-code practices consistently improves review throughput and reduces misread intent. It is not free.

| Benefit | Cost |
|---------|------|
| Faster code review — criteria are explicit | Upfront time naming and structuring |
| AI-generated code aligns with team readability | Strict application slows throwaway work |
| Lower defect rate from misunderstood code | Formatter and linter maintenance |
| Shared vocabulary (EKP-CC01–CC08) in review | Learning curve for concept IDs |

**When this document is insufficient:**

- Class-level design → `solid.md`
- How to restructure code safely → `refactoring.md`
- System boundaries and API contracts → `layering-and-boundaries.md`
- Error handling semantics → [error-handling.md](error-handling.md)

Relax practices per **EKP-P02** when lifespan and blast radius are low. Document the exception in the PR when reviewers might otherwise object.

## Examples

### Combined review scenario

**Finding:** A 60-line function `handle()` processes a webhook with nested `if` blocks, a `flag` parameter, and literal `7` for retry days.

| Issue | Concept | Fix direction |
|-------|---------|---------------|
| Opaque name `handle` | EKP-CC01 | Rename to `processPaymentWebhook` |
| Function too long | EKP-CC02 | Split into parse, validate, persist steps |
| Boolean `flag` | EKP-CC03 | Named field in payload type |
| Deep nesting | EKP-CC04 | Guard clauses for invalid payloads |
| Literal `7` | EKP-CC07 | `const RETRY_WINDOW_DAYS = 7` |

Structural extraction steps belong in `refactoring.md`—this table diagnoses only.

## Knowledge graph

| Field | Value |
|-------|-------|
| `role` | `practice` |
| `depends_on` | `engineering-principles.md` |
| `implements` | EKP-P04, EKP-P10 |
| Siblings | `solid.md` (practice), `refactoring.md` (procedure) |

## Related

- [Engineering Principles](engineering-principles.md) — EKP-P01–P10 foundation
- [SOLID](solid.md) — class/module design (EKP-SL)
- [Refactoring](refactoring.md) — structural change procedures (EKP-RF; EKP-P03, EKP-P10)
- [Error Handling](error-handling.md) — failure handling practice (EKP-EH; EKP-P07)
- [Layering and Boundaries](../architecture/layering-and-boundaries.md) — system boundaries (EKP-LB; EKP-P05, EKP-P06)
- [ADR-0004: Clean Code position in knowledge graph](../architecture/decisions/adr-0004-clean-code-position-in-knowledge-graph.md)
- [Engineering domain index](README.md)
