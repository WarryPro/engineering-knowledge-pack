---
title: Refactoring
domain: engineering
tags: [refactoring, structural-change, safety, procedures, ai-guidance]
severity: recommended
applies_to: [backend, frontend, api, mobile]
type: guide
role: procedure
depends_on:
  - knowledge/engineering/engineering-principles.md
implements:
  - EKP-P03
  - EKP-P10
related:
  - knowledge/engineering/engineering-principles.md
  - knowledge/engineering/clean-code.md
  - knowledge/engineering/solid.md
  - knowledge/engineering/design-patterns.md
  - knowledge/architecture/layering-and-boundaries.md
  - knowledge/architecture/decisions/README.md
  - knowledge/architecture/decisions/adr-0004-clean-code-position-in-knowledge-graph.md
extends: []
concept_ids: [EKP-RF01, EKP-RF02, EKP-RF03, EKP-RF04, EKP-RF05, EKP-RF06, EKP-RF07]
adapter_priority: high
---

# Refactoring

## Summary

Stack-agnostic **procedures** for changing code structure in small, reversible, level-appropriate steps while **preserving behavior**. This document operationalizes **EKP-P03** (Prefer reversible decisions) and **EKP-P10** (Maintainability is a feature). It defines when and how to refactor—not what good code looks like (`clean-code.md`, `solid.md`) or which patterns to adopt (`design-patterns.md`).

Apply during implementation, code review, and AI-assisted editing. Infer **refactoring budget** from task type (**EKP-P02**). Never perform Level 3+ structural work or Level 4 architectural work without explicit approval. Level 4 requires an ADR.

## EKP layer positioning

| Layer | Role | Example documents | This document |
|-------|------|-------------------|---------------|
| **Principles** | Why — value judgments | `engineering-principles.md` (EKP-P01–P10) | Implements EKP-P03, EKP-P10 by reference |
| **Practices** | What good code looks like | `clean-code.md` (EKP-CC), `solid.md` (EKP-SL) | Target states — cite IDs only |
| **Procedures** | How to change structure safely | **this document** (EKP-RF) | Primary content |
| **Patterns** | Named reusable structures | `design-patterns.md` | Outcomes only — no tutorials |
| **Architecture** | System boundaries | `layering-and-boundaries.md`, ADRs | Level 4 escalation only |

Refactoring is a **procedure-layer** artifact per ADR-0004. Adapters (Cursor, Claude, Google Gravity, future tools) should extract the **AI Decision Flow** and **Risk Matrix** as high-priority rules.

## Anti-rewrite culture

Refactoring improves structure **incrementally** while behavior stays constant. **Rewriting** replaces a unit wholesale, often losing history, behavior parity, and reviewability.

| Approach | Definition | EKP stance |
|----------|------------|------------|
| **Refactoring** | Small, behavior-preserving structural steps | Default — Levels 1–3 within budget |
| **Incremental migration** | Phased replacement (e.g. strangler) | Level 4 — ADR, multi-iteration |
| **Rewrite** | Discard and rebuild module/system | Last resort — ADR, parallel run, full regression |

**Anti-patterns:**

- "Let's rewrite this module" when Level 1–2 changes suffice (**EKP-P03**).
- Big-bang cleanup PR touching dozens of files without phased plan (**EKP-RF02**).
- Using refactoring to chase theoretical perfection unrelated to the task (**EKP-P01**, **EKP-RF06**).

Prefer the **lowest refactoring level** capable of solving the stated problem. Escalate only when lower levels cannot meet the requirement without leaving the code worse.

## Refactoring Levels

Levels are a **risk taxonomy**, not a quality ladder. Higher level ≠ better — it means more governance.

### Level 1 — Local refactoring

**Examples:** Rename Variable, Rename Method, Rename Class, Extract Constant, Inline Variable, Simplify Boolean Expression

| Attribute | Detail |
|-----------|--------|
| Risk | Very low |
| Scope | Usually single file |
| Architectural impact | None |
| Testing | Unit on affected code; localized verification often sufficient |
| Targets | Often implements `clean-code.md` goals (EKP-CC) — cite ID only |

### Level 2 — Structural refactoring

**Examples:** Extract Method, Move Method, Move Function, Extract Interface, Extract Class, Introduce Parameter Object

| Attribute | Detail |
|-----------|--------|
| Risk | Medium |
| Scope | One to several files; internal API may shift |
| Architectural impact | Local structure only |
| Testing | Regression on affected modules required |
| Targets | Often moves toward `solid.md` goals (EKP-SL) — cite ID only |

### Level 3 — Module refactoring

**Examples:** Split Module, Merge Modules, package restructuring, dependency direction cleanup, layer cleanup within codebase, remove cyclic dependencies

| Attribute | Detail |
|-----------|--------|
| Risk | High |
| Scope | Cross-package; multiple commits recommended |
| Architectural impact | Module graph — not system redesign |
| Testing | Broad regression + integration tests |
| Approval | Explicit approval required before AI auto-apply |

### Level 4 — Architectural refactoring

**Examples:** Strangler migration, extract service, replace persistence layer, hexagonal migration, modular monolith restructuring, event-driven migration

| Attribute | Detail |
|-----------|--------|
| Risk | Very high |
| Scope | System-wide; multi-iteration |
| Governance | **ADR required** (`knowledge/architecture/decisions/`) |
| Testing | Full regression + rollout strategy |
| AI rule | **Never** bundle into feature or bugfix work; propose plan only |

**Level selection rule:** Always attempt the **lowest level** capable of solving the stated problem.

## Guidance

### EKP-RF01: Behavior preservation

**Implements:** EKP-P03

**Intent:** Refactoring changes structure, not observable behavior. External inputs produce the same outputs, side effects, and error semantics before and after.

**Problem it solves:** "Cleanup" PRs that silently alter business logic—the most expensive defect class.

**Practices:**

- Define observable behavior before refactoring: inputs, outputs, side effects, error cases.
- Run verification after **every** step—not only at PR end.
- If behavior must change, it is **not** refactoring—it is a feature or bugfix with separate acceptance criteria (**EKP-P01**).
- Document "behavior preserved" in PR description for Level 2+ changes.

**Trade-offs:**

| Gain | Cost |
|------|------|
| Safe incremental improvement | Verification time per step |
| Reviewers can focus on structure | Requires tests or manual baseline |

**When NOT to apply strictly:**

- Prototype code marked for discard (**EKP-P02**).
- Generated code—regenerate instead of refactor.

**Example — avoid:** Extract Method and accidentally change sort order affecting API response.

**Example — prefer:** Run existing tests before and after Extract Method; confirm identical API contract.

**Review signals:** Test failures after "rename only" PR; changed API response without ticket; new edge case handled differently.

---

### EKP-RF02: Small steps

**Implements:** EKP-P03

**Intent:** Each step is a reversible two-way door. One refactoring per commit when possible.

**Problem it solves:** Large unreviewable diffs where defects hide and rollback is expensive.

**Practices:**

- One named refactoring per commit (or per logical step in a stacked PR).
- Each step leaves the codebase in a **green** state (build + tests).
- Prefer several small commits over one large refactor PR.
- Level 1 before Level 2; Level 2 before Level 3—do not skip levels without justification.
- Preserve git and blame history: prefer move/rename tooling over copy-delete.

**Trade-offs:**

| Gain | Cost |
|------|------|
| Easy rollback; clear review | More commits; integration branch noise |
| Bisect-friendly history | Slower than bulk edit |

**When NOT to apply strictly:**

- Mechanical rename across repo from automated tool—single commit acceptable if behavior unchanged and tests green.

**Review signals:** PR titled "misc cleanup" with 40 files; tests red mid-series; cannot describe single refactoring per commit.

---

### EKP-RF03: Tests as safety nets

**Implements:** EKP-P03, EKP-P10

**Intent:** No structural change without a verification mechanism proportional to risk level.

**Problem it solves:** Refactoring untested legacy and discovering regressions in production.

**Practices:**

| Level | Minimum test bar |
|-------|------------------|
| 1 | Unit tests on affected code, or manual verification for trivial renames |
| 2 | Unit + integration on affected modules |
| 3 | Broad regression + integration suite |
| 4 | Full regression per ADR test plan |

- **Precondition:** Tests green before starting. If none exist, write **characterization tests** capturing current behavior first.
- Do not delete tests to make refactor "pass."
- AI assistants: refuse Level 2+ if no verification path exists—propose tests first.

**Trade-offs:**

| Gain | Cost |
|------|------|
| Confident structural change | Upfront test authoring on legacy |

**When NOT to apply strictly:**

- Throwaway spike with explicit discard date.

**Review signals:** Large Extract Class with zero test changes; deleted failing test; "tests later" in PR.

---

### EKP-RF04: When to refactor

**Implements:** EKP-P03, EKP-P10 (references **EKP-P02** for budget)

**Intent:** Refactor when structural change reduces future cost **and** fits task scope and budget—not whenever code is imperfect.

**Problem it solves:** Endless cleanup without delivery; drive-by refactors; refactoring during incidents.

**When to refactor:**

- **Planned:** Dedicated tech-debt ticket with scoped budget.
- **Opportunistic:** In files already modified for the task, within budget (**EKP-RF06**).
- **Preparatory:** Short refactor to make a feature change safer—must be in scope or separate commit.

**When to defer:**

- Incident hotfix (**EKP-RF07**) — follow-up ticket.
- Unrelated modules — separate PR.
- No tests and no time for characterization tests — fix coverage first or defer.
- Level 3+ without approval.

#### Refactoring Budget

Every task has a reasonable structural change allowance (**EKP-P02**).

| Task type | Budget | Permitted levels | Exceeding budget |
|-----------|--------|------------------|------------------|
| Small bug fix | Minimal | Level 1 in touched code only | Level 2+ needs PR justification |
| Scoped feature | Moderate | Level 1–2 within feature boundary | Level 3+ needs approval |
| Tech-debt ticket | Allocated per ticket | Level 1–3 per ticket scope | Level 4 needs ADR |
| Legacy modernization | Large per project plan | All per plan | ADR for Level 4 phases |

AI assistants: when task type is ambiguous, assume **minimal** budget.

**Trade-offs:**

| Gain | Cost |
|------|------|
| Predictable delivery | Imperfect code may remain temporarily |
| Clear review expectations | Budget negotiation overhead |

**Review signals:** Bugfix PR with new service classes; feature PR with package split; "while I was here" without ticket.

---

### EKP-RF05: Named refactoring procedures

**Implements:** EKP-P10

**Intent:** Standardized step sequences for common structural changes. Catalog only—no textbook prose.

**Problem it solves:** Ad-hoc restructuring that misses verification steps.

#### Procedure catalog

| Procedure | Level | Steps (outline) |
|-----------|-------|-----------------|
| Rename Variable | 1 | 1. Rename 2. Fix references 3. Verify compile/tests |
| Rename Method/Function | 1 | 1. Rename 2. Update call sites 3. Verify tests |
| Rename Class/Type | 1 | 1. Rename 2. Update imports/references 3. Verify tests |
| Extract Constant | 1 | 1. Replace literal 2. Name constant 3. Verify behavior |
| Inline Variable | 1 | 1. Replace uses with expression 2. Remove declaration 3. Verify |
| Simplify Boolean Expression | 1 | 1. Apply equivalence 2. Verify branch coverage |
| Extract Method | 2 | 1. Ensure tests green 2. Extract block 3. Name by intent 4. Verify tests |
| Move Method/Function | 2 | 1. Copy to target 2. Delegate/adjust visibility 3. Update callers 4. Remove old 5. Verify |
| Extract Class | 2 | 1. Identify fields/methods cluster 2. Create class 3. Move members 4. Update references 5. Verify |
| Extract Interface | 2 | 1. Identify client needs 2. Create interface 3. Implement 4. Type clients 5. Verify — justify per EKP-SL04 |
| Introduce Parameter Object | 2 | 1. Group parameters 2. Create type 3. Replace signature 4. Update callers 5. Verify |
| Split Module | 3 | 1. Plan boundaries 2. Approval 3. Move in phases 4. Integration tests each phase |
| Merge Modules | 3 | 1. Plan dependency result 2. Approval 3. Consolidate 4. Full regression |
| Remove cyclic dependency | 3 | 1. Map cycle 2. Approval 3. Break via extraction or inversion 4. Integration tests |
| Introduce Strategy (procedure name) | 2 | 1. Extract variation 2. Inject 3. Verify — pattern detail in `design-patterns.md` |

Full catalog: Fowler, *Refactoring* (2nd ed.) — external reference.

**Review signals:** Skipped verification step; Extract Interface with one implementation and no justification.

---

### EKP-RF06: Opportunistic refactoring and scope smuggling

**Implements:** EKP-P10 (references **EKP-P01**)

**Intent:** Improve code you touch—without expanding task scope.

#### Definition

**Scope smuggling:** Structural changes beyond what the stated task requires, framed as cleanup or architecture improvement.

#### Allowed (within budget)

| Context | Allowed | Example |
|---------|---------|---------|
| Bugfix in function | Level 1 on edited lines | Rename misleading local in same function |
| Feature in module | Level 2 supporting feature | Extract Method for new branch clarity |
| Same file already modified | Level 1–2 boy scout | Remove dead code in file (EKP-CC06) |

#### Prohibited

| Pattern | Example |
|---------|---------|
| Unrelated module refactor | "Add field" + extract three new services elsewhere |
| Architecture in bugfix | Null fix + hexagonal restructure |
| Level 3+ without approval | Package split bundled in feature PR |
| Speculative interfaces | New interface with single impl, no test seam |

**PR example — approve:** "Added `discountCode`; renamed `calc` → `calculateLineTotal` in same method (EKP-RF06, Level 1)."

**PR example — reject:** "Added `discountCode`; extracted `PricingService`, `DiscountEngine` from unrelated checkout."

**Review signals:** Files changed unrelated to ticket; PR description omits structural work; "also cleaned up architecture."

---

### EKP-RF07: Incidents, rewrites, and escalation

**Implements:** EKP-P03

**Intent:** Incidents optimize for speed and reversibility. Structural work waits. Level 4 requires ADR.

**Problem it solves:** Hotfix PRs that become undeclared rewrites; AI-driven architecture migrations in feature work.

**Rules:**

- **Incidents:** No Level 2+ refactoring in hotfix PR. Level 1 only if essential to the fix. Document follow-up ticket for structural cleanup.
- **Rewrites:** Require ADR or explicit modernization approval. Parallel run or strangler when possible—not big-bang delete.
- **Level 4:** Never auto-apply. Propose ADR, phases, test plan. Route to `layering-and-boundaries.md` — do not teach architecture here.
- **SOLID gaps:** Diagnose with EKP-SL IDs in follow-up ticket—do not refactor toward SOLID in hotfix (**EKP-P03**).

**Trade-offs:**

| Gain | Cost |
|------|------|
| Fast incident recovery | Temporary structural debt |
| Governed large change | ADR and planning overhead |

**Review signals:** Hotfix + new package structure; "rewrite module" without ADR; strangler plan inside feature PR.

## Risk Matrix

Objective signals for reviewers and adapters.

| Refactoring | Level | Risk | Typical scope | Testing expectation | Review requirement |
|-------------|-------|------|---------------|---------------------|-------------------|
| Rename Variable | 1 | Very low | Single file | Unit on affected code | Standard PR |
| Rename Method/Function | 1 | Low | 1–few files | Call-site regression | Standard PR |
| Extract Constant | 1 | Very low | Single file | Unit | Standard PR |
| Extract Method | 2 | Medium | 1–2 files | Unit + integration if public | Behavior preserved noted |
| Move Method/Function | 2 | Medium | 2+ files | Integration | Reviewer confirms no behavior change |
| Extract Class | 2 | Medium–high | Several files | Module integration | Explicit refactor note |
| Extract Interface | 2 | Medium | Several files | Consumer + impl tests | Justify per EKP-SL04 |
| Introduce Parameter Object | 2 | Medium | 2+ files | Call-site tests | Standard PR |
| Split Module | 3 | High | Package tree | Broad regression | Approval; phased commits |
| Dependency direction cleanup | 3 | High | Cross-package | Integration + contracts | Senior/architect review |
| Remove cyclic dependency | 3 | High | Cross-package | Integration suite | Senior review |
| Rewrite Module | 3–4 | Very high | Module+ | Full suite; parallel if possible | ADR or modernization approval |
| Architectural migration | 4 | Critical | System | Full regression + rollout | **ADR required** |

**Adapter rule:** Risk "High" and above → block automatic application without human approval.

## AI Decision Flow

Canonical sequence for Cursor, Claude, Google Gravity, and future EKP adapters. Extract verbatim for rules in Phase 5.

```
1. Can the requested change be implemented safely WITHOUT refactoring?
   → YES: Implement directly. Stop.

2. Would Level 1 refactoring significantly improve readability
   for the code being touched?
   → YES: Perform Level 1 only. Stay within task scope and budget.
   → NO: Go to 3.

3. Would Level 2 improve maintainability for the stated requirement?
   → YES: Only if tests are green AND within task scope/budget.
          Prefer separate commit. State behavior preserved (EKP-RF01).
   → NO: Go to 4.

4. Would Level 3 or Level 4 be required?
   → YES: Do NOT perform automatically.
          Explain trade-offs, scope, tests, and governance.
          Level 4: ADR required. Await explicit approval.
   → NO: Implement without further structural change.

5. Never expand scope because "the architecture could be cleaner."
   → Violates EKP-P01 and EKP-RF06. Prohibited.
```

**Adapter enforcement:**

| Step | Auto-apply | Notes |
|------|------------|-------|
| 1 | Yes | Default |
| 2 | Yes, in scope | Level 1 only |
| 3 | Conditional | Tests green + budget |
| 4 | Block | Human gate |
| 5 | Hard block | Scope smuggling |

## AI-specific guidance

Rules for all coding assistants consuming EKP knowledge. Reference sibling documents by ID only.

### Universal rules

- Never rewrite an entire module if Level 1–2 solves the problem (**EKP-P03**).
- Prefer several incremental commits over one large refactor PR (**EKP-RF02**).
- Avoid speculative abstractions and interfaces with a single implementation unless test seam or planned second variant (**EKP-P02**, EKP-SL04).
- Do not mix formatting-only changes with structural refactors in one commit (EKP-CC08).
- Optimize for **reviewability** over theoretical perfection (**EKP-P10**).
- State behavior preservation explicitly in summaries (**EKP-RF01**).
- Infer **refactoring budget** from task; default to minimal.
- Choose the **lowest capable level** when uncertain.

### Cursor

- Apply AI Decision Flow before multi-file extracts.
- Use Risk Matrix to gate Level 3+ suggestions in agent mode.
- Do not auto-apply refactors across files not mentioned in the user request.

### Claude

- When proposing structural change, list level, budget fit, and tests required.
- Separate "recommended refactor" from "required for task" in responses.
- Escalate Level 4 to ADR proposal text, not implementation.

### Google Gravity

- Bind refactor scope to explicit user task boundaries.
- Prefer inline Level 1 improvements over new files when sufficient.
- Block architectural migration suggestions unless user explicitly requests modernization.

### Future adapters

- Map `adapter_priority: high` frontmatter to Decision Flow + Risk Matrix first.
- Emit rules from EKP-RF IDs, not principle prose (EKP-P03/P10 referenced, not restated).

## Review signals

| Signal | Verdict | Concept |
|--------|---------|---------|
| Single-purpose commit; tests green; level matches budget | Good refactoring | EKP-RF02, EKP-RF04 |
| "Add field" + three new classes elsewhere | Scope smuggling | EKP-RF06 |
| New interface, one impl, no seam | Unnecessary abstraction | EKP-RF06, EKP-SL04 |
| "Rewrite module" in feature PR | Rewrite temptation | EKP-RF07 |
| Level 1 rename with unit test update | Good refactoring | EKP-RF01, EKP-RF03 |
| Hotfix + Extract Class | Incident violation | EKP-RF07 |
| 50-file cleanup, no phases | Big-bang / anti-rewrite | EKP-RF02, EKP-RF07 |

## Trade-offs

Consistent refactoring discipline improves long-term maintainability. It is not free.

| Benefit | Cost |
|---------|------|
| Reversible, reviewable change (**EKP-P03**) | Slower than bulk edit |
| Lower regression risk with test nets | Upfront characterization tests on legacy |
| Shared vocabulary (EKP-RF, Levels) for AI and humans | Learning curve |
| Incremental debt reduction (**EKP-P10**) | Imperfect structure may remain until budget allows |

**When this document is insufficient:**

- Readability targets → `clean-code.md` (EKP-CC)
- Structural quality diagnosis → `solid.md` (EKP-SL)
- Pattern structure after refactor → `design-patterns.md`
- System boundaries and Level 4 design → `layering-and-boundaries.md` + ADR

## Knowledge graph position

| Field | Value |
|-------|-------|
| `role` | `procedure` |
| `depends_on` | `engineering-principles.md` |
| `implements` | EKP-P03, EKP-P10 |
| `concept_ids` | EKP-RF01–EKP-RF07 |
| `adapter_priority` | high — Decision Flow + Risk Matrix |
| Siblings (targets) | `clean-code.md`, `solid.md` |
| Siblings (outcomes) | `design-patterns.md` |
| Escalation | `layering-and-boundaries.md`, ADRs (Level 4) |

```
engineering-principles
        │
        ├── clean-code (practice) ──► Level 1 targets
        ├── solid (practice) ──────► Level 2–3 targets
        ├── refactoring (procedure) ◄── this document
        └── design-patterns (patterns)
```

## Related

- [Engineering Principles](engineering-principles.md) — EKP-P01–P10 foundation
- [Clean Code](clean-code.md) — function/file readability (EKP-CC)
- [SOLID](solid.md) — class/module design targets (EKP-SL)
- [ADR-0004: Knowledge graph layering](../architecture/decisions/adr-0004-clean-code-position-in-knowledge-graph.md)
- [Architecture decision records](../architecture/decisions/README.md)
- [Design Patterns](design-patterns.md) — named pattern catalog (EKP-DP)
- [Layering and Boundaries](../architecture/layering-and-boundaries.md) — Level 4 escalation (EKP-LB)
- [Engineering domain index](README.md)
