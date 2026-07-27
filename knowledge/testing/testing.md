---
title: Testing
domain: testing
tags: [testing, verification, reliability, quality, change-safety]
severity: recommended
applies_to: [backend, frontend, api, mobile]
type: guide
role: practice
depends_on:
  - knowledge/engineering/engineering-principles.md
implements:
  - EKP-P03
  - EKP-P10
related:
  - knowledge/engineering/engineering-principles.md
  - knowledge/engineering/refactoring.md
  - knowledge/engineering/error-handling.md
  - knowledge/engineering/clean-code.md
  - knowledge/architecture/layering-and-boundaries.md
  - knowledge/testing/README.md
extends: []
concept_ids: [EKP-TS01, EKP-TS02, EKP-TS03, EKP-TS04, EKP-TS05, EKP-TS06, EKP-TS07, EKP-TS08, EKP-TS09, EKP-TS10, EKP-TS11, EKP-TS12]
adapter_priority: high
---

# Testing

## Summary

Stack-agnostic **practice-layer** guidance for verification philosophy: why tests exist, what to verify, at which boundary, and how much testing a change deserves. Tests are **executable knowledge**—they describe expected behavior and protect future change (**EKP-P10**). They provide confidence that structural change is reversible and observable (**EKP-P03**).

This document operationalizes **EKP-P03** (Prefer reversible decisions) and **EKP-P10** (Maintainability is a feature). It defines *how* to think about verification—not how to configure PHPUnit, Jest, CI pipelines, or mock libraries.

Apply during implementation, refactoring preparation, and code review. Relax per **EKP-P02** (Proportionality) for throwaway spikes and scripts with documented discard date. Framework test syntax and CI wiring belong in stack domains and `devops/`.

This document does not teach safe structural change (`refactoring.md`), failure semantics (`error-handling.md`), naming hygiene (`clean-code.md`), or system boundary contracts (`layering-and-boundaries.md`).

## Context

Code changes constantly. Without verification, every edit is a gamble: regressions surface in production, refactors stall, and teams lose the ability to improve structure safely. Testing is not a quality checkbox—it is how maintainable systems **know** they still work.

[Engineering Principles](../engineering/engineering-principles.md) define *why* reversibility and maintainability matter. This document defines *how* to build confidence through tests. Every practice traces to an **EKP-TS** concept ID and **EKP-P03** or **EKP-P10**.

**Boundaries:**

| Concern | Owner document / domain | This document |
|---------|----------------------|---------------|
| Verification philosophy and test strategy | **this document** (EKP-TS) | Primary content |
| Safe structural change procedures | `refactoring.md` (EKP-RF) | Related — EKP-RF03 cites test nets |
| Failure semantics and error contracts | `error-handling.md` (EKP-EH) | Related — tests verify failure behavior |
| Readable test names and structure | `clean-code.md` (EKP-CC) | Cross-reference only |
| System/integration boundary contracts | `layering-and-boundaries.md` (EKP-LB) | Escalation for cross-service verification |
| Framework test APIs (PHPUnit, Jest, PyTest) | Stack domains (`php/`, `typescript/`) | Out of scope |
| CI pipeline configuration | `devops/` | Out of scope |
| Load/stress testing | `performance/` | Out of scope |
| Security testing | `security/` | Out of scope |

**Out of scope:** test runner configuration, assertion library syntax, snapshot tooling tutorials, deployment smoke-test playbooks, coverage gate thresholds in CI YAML.

## EKP layer positioning

| Layer | Role | Example documents | This document |
|-------|------|-------------------|---------------|
| **Principles** | Why — value judgments | `engineering-principles.md` (EKP-P01–P10) | Implements EKP-P03, EKP-P10 by reference |
| **Practices** | What good verification looks like | **this document** (EKP-TS), `clean-code.md`, `error-handling.md` | Primary content |
| **Patterns** | Named structures | `design-patterns.md` (EKP-DP) | Related — test seams at pattern boundaries |
| **Procedures** | How to change structure safely | `refactoring.md` (EKP-RF) | Related — tests enable EKP-RF03 |
| **Architecture** | System boundaries | `layering-and-boundaries.md` (EKP-LB) | Contract verification escalation |

Testing is a **practice-layer** artifact in the `testing` domain per EKP roadmap. Adapters (Cursor, Claude, Google Gravity, future tools) should extract the **AI Decision Flow** as a high-priority constraint.

## Guidance

### EKP-TS01: Tests are executable knowledge

**Implements:** EKP-P10

**Intent:** Tests document behavior that the team relies on. They are living specification—not proof of bug-free code.

**Rules:**

- A test should answer: *what behavior must remain true after this change?*
- Tests protect **maintainability** by making change reviewable: green suite = behavior preserved within test scope.
- Tests do **not** guarantee absence of defects—they bound known risk and catch regressions in covered behavior.
- Delete or update tests when requirements change—stale tests are misleading documentation.

**Good:** Test names state behavior: `rejects_order_when_inventory_insufficient`.

**Bad:** Test named `testHandler` with assertions that only check non-null return.

**Review signals:** Tests with no clear behavioral claim; suite green but production behavior wrong because tests assert implementation trivia.

---

### EKP-TS02: Test pyramid and proportional verification

**Implements:** EKP-P03, EKP-P10

**Intent:** Match test type and count to feedback speed, cost, and confidence needs—not to a fixed ratio diagram.

**Layers (conceptual):**

| Layer | Scope | Strength | Cost |
|-------|-------|----------|------|
| **Unit** | Single unit in isolation | Fast feedback; pinpoints failure | May miss integration defects |
| **Integration** | Modules collaborating | Catches wiring and contract bugs | Slower; more setup |
| **End-to-end** | System path as user/deploy sees it | Highest confidence on critical paths | Slowest; brittle if overused |

**Rules:**

- Prefer many fast unit tests for pure logic; fewer integration tests for seams; minimal E2E for critical user journeys.
- The pyramid is a **heuristic**, not law—a data pipeline may justify more integration tests than a CRUD API.
- E2E tests are expensive—reserve for paths where unit/integration cannot represent real risk (**EKP-P02** proportionality).

**Review signals:** Hundreds of E2E tests for logic easily covered at unit level; zero integration tests on a service with three adapters.

---

### EKP-TS03: Test the behavior, not the implementation

**Implements:** EKP-P10

**Intent:** Tests should survive internal refactors that preserve observable behavior.

**Rules:**

- Structure tests as **Given / When / Then** (or equivalent): setup, action, observable outcome.
- Assert on **outputs, state, and side effects** the caller cares about—not private methods or internal call order unless that order is the contract.
- Refactoring that breaks tests without changing external behavior indicates **implementation-coupled tests**—fix the tests, not the refactor goal.

**Good:** Given cart with one item, when checkout completes, then order total matches item price plus tax.

**Bad:** Assert mock received `save()` exactly once on internal repository method after rename.

**Review signals:** Tests import private symbols; tests fail on Extract Method with identical API behavior.

---

### EKP-TS04: Choose the correct testing boundary

**Implements:** EKP-P03, EKP-P10

**Intent:** Test at the lowest boundary that still captures the risk—no lower (misses defect), no higher (slow and vague).

| Boundary | When to use |
|----------|-------------|
| **Unit** | Pure logic, algorithms, domain rules without I/O |
| **Module** | Collaboration within deployable (handler + in-memory fake port) |
| **System** | Cross-module or cross-service path; contract between components |

**Rules:**

- Crossing a **deployable or team boundary** requires contract-level verification—escalate boundary definition to `layering-and-boundaries.md` (EKP-LB), not ad-hoc test hacks.
- Do not unit-test framework wiring that integration tests already cover.
- API contract tests belong at the boundary the contract defines (EKP-LB08).

**Review signals:** Unit test spins up real database; no test at service boundary where failures occur in production.

---

### EKP-TS05: Characterization tests for existing systems

**Implements:** EKP-P03

**Intent:** Before changing untested legacy, capture **current** behavior as a safety net—even if that behavior is imperfect.

**Rules:**

- Characterization tests document what the system **does today**, not what it **should** do.
- Required precondition for Level 2+ refactoring when no tests exist—see `refactoring.md` EKP-RF03 (cite only; procedures stay there).
- Accept imperfect assertions initially; tighten when requirements are clarified.
- Do not delete characterization tests to green a refactor—update when behavior intentionally changes.

**Good:** Golden-file or snapshot of API response for known input before Extract Class on legacy handler.

**Bad:** Large refactor on zero-test module with manual "I clicked around" verification only.

**Review signals:** Refactor PR with no test delta on previously untested module; characterization test deleted because output "looked wrong" without ticket.

---

### EKP-TS06: Test doubles and isolation

**Implements:** EKP-P10

**Intent:** Doubles (mocks, stubs, fakes) **control boundaries** so the unit under test can be exercised deterministically.

| Double | Purpose |
|--------|---------|
| **Stub** | Returns canned responses; no behavior verification |
| **Fake** | Working simplified implementation (in-memory repo) |
| **Mock** | Verifies interactions; use sparingly |

**Rules:**

- Use doubles for **unstable, slow, or external** dependencies—not to avoid constructing real collaborators when cheap.
- Prefer **fake** over **mock** when behavior verification matters more than call counting.
- Doubles are not a substitute for integration tests at real seams.

**Review signals:** Mock of value object or pure function; mock verifies internal call sequence unrelated to contract.

---

### EKP-TS07: Avoid over-mocking

**Implements:** EKP-P10

**Intent:** Over-mocking couples tests to implementation; harmless refactors break the suite.

**Symptoms:**

- Tests break when private method renamed but public behavior unchanged.
- Every collaborator mocked including trivial pass-through types.
- Tests assert interaction order on non-contract internals.

**Rules:**

- Prefer **state verification** (outcome) over **interaction verification** (method called) unless interaction is the contract.
- If removing a mock makes the test simpler and still fast, remove it.
- Hard-to-test units often signal design problems—cite EKP-SL for diagnosis, not testing workarounds.

**Review signals:** Test file longer than production file due to mock setup; refactor blocked by mock expectation churn.

---

### EKP-TS08: Test data ownership

**Implements:** EKP-P10

**Intent:** Test data must be **deterministic, isolated, and owned** by the test—no hidden shared state.

**Rules:**

- Each test creates or resets data it needs; no reliance on execution order.
- Use factories or builders for readable setup—naming follows EKP-CC01 where applicable.
- Shared fixtures are acceptable when read-only and documented; mutable shared fixtures cause flakes.
- Avoid production database copies with PII—use synthetic data.

**Review signals:** Test passes alone, fails in suite; random IDs without seed; tests mutate global singleton.

---

### EKP-TS09: Flaky tests are reliability failures

**Implements:** EKP-P03, EKP-P10

**Intent:** A flaky test destroys trust in the suite—teams ignore red builds and miss real regressions.

**Common causes:**

- Timing assumptions (`sleep`, race without synchronization).
- Shared mutable state across tests.
- Dependence on external services, network, or wall clock without control.
- Non-deterministic ordering assertions.

**Rules:**

- Fix or quarantine flaky tests immediately—do not retry-until-green in CI as permanent policy.
- Inject clocks, random seeds, and async boundaries for determinism.
- Flaky E2E may indicate missing boundary contract (EKP-LB13)—not only test bug.

**Review signals:** `@retry` on test without ticket; intermittent CI failures accepted as normal.

---

### EKP-TS10: Coverage is a signal, not a target

**Implements:** EKP-P10

**Intent:** Coverage measures **lines exercised**, not **behavior verified**. High coverage can miss critical paths; low coverage can hide risk.

**Rules:**

- Use coverage to find **untested code paths**, not as a merge gate for its own sake.
- 100% line coverage does not imply correct assertions.
- Critical domains (payments, auth, data migration) deserve explicit behavioral tests regardless of coverage percentage.
- Evidence-based optimization of test investment aligns with **EKP-P08** (future `performance/` domain)—do not implement P08 here.

**Review signals:** Coverage increased with empty or trivial assertions; untested error branches in revenue path despite high overall percentage.

---

### EKP-TS11: Testing cost must match change risk

**Implements:** EKP-P03, EKP-P10 (references **EKP-P02**)

**Intent:** Testing effort is proportional to blast radius, lifespan, and change frequency—not uniform across all code.

| Context | Testing stance |
|---------|----------------|
| Hotfix during incident | Minimal verification per `refactoring.md` EKP-RF07; follow-up tests in ticket |
| Throwaway spike | Smoke test or manual only; document discard |
| Core domain logic | Unit + integration on behavior; characterization before refactor |
| Cross-service change | Contract tests at boundary (EKP-LB); full regression per ADR if Level 4 |

**Rules:**

- Do not demand E2E suite for typo in comment; do not ship payment change with zero tests.
- Testing budget is negotiated like refactoring budget (**EKP-RF04** reference only).

**Review signals:** Payment module change with no test updates; week spent writing E2E for constant rename.

---

### EKP-TS12: Review signals for test quality

**Implements:** EKP-P10

**Intent:** Reviewers evaluate tests with the same rigor as production code.

**Review questions:**

| Question | Good sign | Bad sign |
|----------|-----------|----------|
| Does the test explain behavior? | Name and assertions match domain outcome | Opaque name; asserts non-null only |
| Is the boundary correct? | Unit for logic; integration at seam | Real DB in unit test |
| Is it stable? | Deterministic; isolated data | Order-dependent; time-sensitive |
| Does it protect realistic regression? | Would catch bug that motivated test | Trivial assertion always passes |
| Does it couple to implementation? | Survives internal refactor | Breaks on rename private method |

Reference concept IDs in review: `"Missing characterization per EKP-TS05 before EKP-RF03 refactor."`

## Testing anti-patterns

| Anti-pattern | Symptom | Alternative |
|--------------|---------|-------------|
| **Test everything** | Hundreds of meaningless assertions; trivial getters tested | Test important behavior and risk paths (EKP-TS11) |
| **Mock everything** | Every dependency mocked; tests verify wiring only | Mock unstable/external boundaries only (EKP-TS06) |
| **Coverage chasing** | Tests added to hit percentage without behavioral intent | Prioritize risk; use coverage as discovery tool (EKP-TS10) |
| **Testing implementation details** | Tests break on harmless refactor | Assert observable behavior (EKP-TS03) |
| **No tests before refactor** | Large structural PR, zero test delta | Characterization tests first (EKP-TS05, EKP-RF03) |
| **Ignored flaky tests** | CI retry or skipped suite | Fix root cause (EKP-TS09) |

## Relationship boundaries

### With `clean-code.md`

| This document | `clean-code.md` |
|---------------|-----------------|
| What to verify and at which boundary | Readable test names and structure (EKP-CC01, EKP-CC02) |
| Does not define naming or formatting rules | Cite EKP-CC when test code is unreadable |

### With `solid.md`

| This document | `solid.md` |
|---------------|------------|
| Tests reveal design pain (hard to isolate = mixed responsibilities) | Class/module design heuristics (EKP-SL) |
| Does not teach SOLID | Cite EKP-SL when untestability indicates SRP/DIP issues |

### With `refactoring.md`

| This document | `refactoring.md` |
|---------------|------------------|
| Safety nets, characterization, verification bars | Step sequences, levels, budgets (EKP-RF) |
| Enables EKP-RF03 | Does not duplicate refactor procedures |

### With `error-handling.md`

| This document | `error-handling.md` |
|---------------|---------------------|
| Assert expected failure outcomes in tests | Failure semantics and contracts (EKP-EH) |
| Verifies behavior | Defines what failure means |

### With `layering-and-boundaries.md`

| This document | `layering-and-boundaries.md` |
|---------------|------------------------------|
| Contract and integration tests across boundaries | Boundary ownership and contracts (EKP-LB) |
| Verifies agreed contracts | Defines what crosses the boundary |

## AI Decision Flow

Canonical sequence for Cursor, Claude, Google Gravity, and future EKP adapters.

```
1. Is the behavior under test understood (inputs, action, expected outcome)?
   → NO: TS-AI-01 — Do not generate tests. Clarify behavior first. Stop.

2. Is this a behavior test or implementation test?
   → Implementation: TS-AI-02 — Rewrite to assert observable outcome. Stop if cannot.

3. Are mocks/doubles proposed?
   → YES: TS-AI-03 — Name the boundary reason (external, slow, non-deterministic).
   → NO boundary reason: Remove mock. Stop.

4. Is the goal coverage increase without stated risk?
   → YES: TS-AI-04 — Identify risk first. Stop.

5. Does the project have existing test conventions?
   → YES: TS-AI-05 — Follow them (structure, directory, naming).

6. Cite EKP-TS ID when recommending test strategy.

7. Is the problem a wrong service/module boundary?
   → YES: TS-AI-07 — Escalate to EKP-LB / ADR — not more mocks.

8. Is this a risky change on untested legacy?
   → YES: TS-AI-08 — Propose characterization tests (EKP-TS05) before structural change.
```

**Adapter rules:**

| ID | Rule |
|----|------|
| **TS-AI-01** | Do not generate tests before understanding behavior. |
| **TS-AI-02** | Prefer behavior tests over implementation tests. |
| **TS-AI-03** | Do not add mocks without a boundary reason. |
| **TS-AI-04** | Do not increase coverage without identifying risk. |
| **TS-AI-05** | Preserve existing testing conventions. |
| **TS-AI-06** | When suggesting tests, cite EKP-TS IDs. |
| **TS-AI-07** | Escalate architecture boundary problems to EKP-LB. |
| **TS-AI-08** | Use characterization tests before risky changes. |

## Review signals

| Signal | Verdict | Concept |
|--------|---------|---------|
| Clear Given/When/Then; stable; correct boundary | Good test | EKP-TS03, EKP-TS04 |
| Characterization added before legacy refactor | Good safety net | EKP-TS05, EKP-P03 |
| Mock of pure domain logic | Over-mocking | EKP-TS07 |
| Flaky test retried without fix | Reliability failure | EKP-TS09 |
| Coverage-only assertions | Coverage chasing | EKP-TS10 |
| No tests on high-risk change | Insufficient verification | EKP-TS11 |
| Test name `test1` | Hygiene issue | EKP-CC01 (`clean-code.md`) |

## Trade-offs

Disciplined testing improves maintainability and enables safe change. It is not free.

| Benefit | Cost |
|---------|------|
| Reversible structural change (**EKP-P03**) | Authoring and maintenance time |
| Executable specification (**EKP-P10**) | Suite execution time; flake management |
| Faster feedback on regressions | Upfront investment on legacy characterization |
| Shared review vocabulary (EKP-TS) | Learning curve; anti-pattern of over-testing |

**When this document is insufficient:**

- Refactoring steps and levels → `refactoring.md` (EKP-RF)
- Failure semantics to assert → `error-handling.md` (EKP-EH)
- Readable test code → `clean-code.md` (EKP-CC)
- Cross-service contract definition → `layering-and-boundaries.md` (EKP-LB)
- Framework syntax → stack domains (`php/`, `typescript/`, `symfony/`)
- CI gates and pipelines → `devops/`
- Load testing → `performance/`

## Knowledge graph position

| Field | Value |
|-------|-------|
| `role` | `practice` |
| `domain` | `testing` |
| `depends_on` | `engineering-principles.md` |
| `implements` | EKP-P03, EKP-P10 |
| `concept_ids` | EKP-TS01–EKP-TS12 |
| `adapter_priority` | high — AI Decision Flow |
| Siblings (related) | `refactoring.md`, `error-handling.md`, `clean-code.md` |
| Escalation | `layering-and-boundaries.md` (EKP-LB) |

```
engineering-principles
        │
        ├── engineering/ (practices, patterns, procedures)
        │
        └── testing/
                └── testing.md (practice) ◄── this document
```

## Related

- [Engineering Principles](../engineering/engineering-principles.md) — EKP-P01–P10 foundation
- [Refactoring](../engineering/refactoring.md) — structural change procedures (EKP-RF; EKP-RF03 safety nets)
- [Error Handling](../engineering/error-handling.md) — failure semantics (EKP-EH)
- [Clean Code](../engineering/clean-code.md) — readable test code (EKP-CC)
- [Layering and Boundaries](../architecture/layering-and-boundaries.md) — boundary contracts (EKP-LB)
- [Testing domain index](README.md)
