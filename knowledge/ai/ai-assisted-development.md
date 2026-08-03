---
title: AI-Assisted Development
domain: ai
tags: [ai, ai-assisted, development, governance, verification, cursor]
severity: required
applies_to: [backend, frontend, api, mobile, devops]
type: guide
role: practice
depends_on:
  - knowledge/engineering/engineering-principles.md
implements:
  - EKP-P01
  - EKP-P03
  - EKP-P10
related:
  - knowledge/engineering/refactoring.md
  - knowledge/testing/testing.md
  - knowledge/engineering/error-handling.md
  - knowledge/security/security-fundamentals.md
  - knowledge/architecture/layering-and-boundaries.md
  - knowledge/architecture/adr-practices.md
  - knowledge/architecture/api-design.md
  - knowledge/architecture/coupling-and-cohesion.md
  - knowledge/architecture/integration-patterns.md
  - knowledge/database/database-design.md
  - knowledge/engineering/clean-code.md
extends: []
concept_ids: [EKP-AI01, EKP-AI02, EKP-AI03, EKP-AI04, EKP-AI05, EKP-AI06, EKP-AI07, EKP-AI08, EKP-AI09, EKP-AI10, EKP-AI11, EKP-AI12]
adapter_priority: high
---

# AI-Assisted Development

## Summary

Stack-agnostic **practice-layer** guidance for using AI coding assistants responsibly during design, implementation, and review. AI assistants generate syntax quickly but lack engineering judgment unless given explicit constraints. This document defines *how* humans and AI should work together—not how to configure Cursor, Copilot, or Claude rule files.

This document operationalizes **EKP-P01** (Solve the actual problem), **EKP-P03** (Prefer reversible decisions), and **EKP-P10** (Maintainability is a feature). It is the **orchestration layer** for all other EKP knowledge: before applying refactoring, testing, error-handling, or architecture guidance, an AI assistant must pass the flows defined here.

Apply on every AI-assisted task. Relax per **EKP-P02** (Proportionality) only for throwaway spikes with documented discard date. Tool-specific rule syntax, adapter scripts, and profile YAML belong in `rules/`, `scripts/`, and `profiles/`—not here.

This document does not teach safe structural change (`refactoring.md`), verification strategy (`testing.md`), failure semantics (`error-handling.md`), naming hygiene (`clean-code.md`), or system boundaries (`layering-and-boundaries.md`).

## Context

AI coding assistants are now default tools in many engineering workflows. They excel at boilerplate, local refactors, and exploring unfamiliar code. They fail predictably at scope control, implicit assumptions, security boundaries, and knowing when *not* to change code.

Without governance, teams experience:

- **Scope smuggling** — a bugfix PR becomes an architecture migration.
- **False completion** — the assistant claims "done" without tests or verification.
- **Generic advice** — suggestions that ignore project conventions and EKP principles.
- **Silent risk** — secrets in prompts, missing error handling, untested structural change.
- **Review debt** — large diffs that are hard to validate because intent was never stated.

[Engineering Principles](../engineering/engineering-principles.md) define *why* proportionality, reversibility, and maintainability matter. This document defines *how* AI assistants must behave to honor those principles. Every practice traces to an **EKP-AI** concept ID.

**Why AI-assisted development requires governance:**

| Risk | Without governance | With EKP-AI |
|------|-------------------|-------------|
| Wrong problem solved | Feature built; ticket unchanged | EKP-AI01 scope gate |
| Unread codebase | Changes conflict with conventions | EKP-AI02 exploration gate |
| Over-engineering | New abstractions "for cleanliness" | EKP-AI03 proportionality |
| Irreversible change | Big-bang refactor in one PR | EKP-AI04, EKP-AI11 incremental path |
| Untested change | Green chat, red production | EKP-AI05 tests define done |
| Unverifiable output | "I updated the code" | EKP-AI12 completion contract |

**Boundaries:**

| Concern | Owner document / domain | This document |
|---------|-------------------------|---------------|
| AI workflow orchestration and gates | **this document** (EKP-AI) | Primary content |
| Safe structural change procedures | `refactoring.md` (EKP-RF) | Escalation — Decision Flow |
| Verification philosophy | `testing.md` (EKP-TS) | Escalation — tests define done |
| Failure semantics | `error-handling.md` (EKP-EH) | Escalation — error paths |
| System/integration boundaries | `layering-and-boundaries.md` (EKP-LB) | Escalation — boundary detection |
| Readable code | `clean-code.md` (EKP-CC) | Cross-reference only |
| Security deep practices | `security/security-fundamentals.md` (EKP-SF) | EKP-AI08 minimum bar; route to EKP-SF Decision Flow |
| HTTP API design | `architecture/api-design.md` (EKP-AP) | Route from EKP-AI10 — API Decision Flow |
| Schema/migrations/transactions | `database/database-design.md` (EKP-DB) | Route from EKP-AI10 |
| Module/package structure | `architecture/coupling-and-cohesion.md` (EKP-MC) | Route from EKP-AI10 |
| Cross-service integration style | `architecture/integration-patterns.md` (EKP-IN) | Route from EKP-AI10 |
| ADR / Level 4 governance | `architecture/adr-practices.md` (EKP-AD) | Route from EKP-AI10 |
| PHP language design | `php/php-fundamentals.md` (EKP-PH) | Route from EKP-AI10 — Phase 4 |
| Symfony application structure | `symfony/symfony-architecture.md` (EKP-SY) | Route from EKP-AI10 — Phase 4 |
| Tool rule file format | `rules/cursor/`, adapters | Out of scope — derived output |

**Out of scope:** prompt engineering tutorials for specific LLMs, model selection, token budgeting, RAG pipeline design, embedding indexes, automatic code-fix bots, CI adapter configuration.

## EKP layer positioning

| Layer | Role | Example documents | This document |
|-------|------|-------------------|---------------|
| **Principles** | Why — value judgments | `engineering-principles.md` (EKP-P01–P10) | Implements EKP-P01, EKP-P03, EKP-P10 |
| **Practices** | What good AI-assisted work looks like | **this document** (EKP-AI), `testing.md`, `error-handling.md` | Primary content |
| **Patterns** | Named structures | `design-patterns.md` (EKP-DP) | Escalation after scope/layer classification |
| **Procedures** | How to change structure safely | `refactoring.md` (EKP-RF) | Escalation for Level 2+ structural work |
| **Architecture** | System boundaries | `layering-and-boundaries.md` (EKP-LB) | Escalation for cross-boundary change |
| **Adapters** | Generated tool rules | `rules/cursor/` (Phase 3A+) | Consumes this document first |

**Relationship with adapters:**

```
engineering-principles (EKP-P)
        │
        ▼
ai-assisted-development (EKP-AI)  ◄── orchestrator — adapters extract Decision Flow first
        │
        ├──► refactoring.md (EKP-RF)     — structural change
        ├──► testing.md (EKP-TS)         — verification
        ├──► error-handling.md (EKP-EH)  — failure paths
        ├──► layering-and-boundaries.md (EKP-LB) — system boundaries
        └──► clean-code.md (EKP-CC)      — readability targets
```

AI-assisted development is a **practice-layer** artifact in the `ai` domain. Adapters (Cursor, Claude, Copilot, future tools) must extract the **AI Decision Flow** as the highest-priority `alwaysApply` constraint before any sibling document rules.

## Guidance

### EKP-AI01: Scope to the stated task

**Implements:** EKP-P01

**Intent:** AI assistants must implement what was asked—not what would be architecturally interesting. Scope expansion during implementation is a defect unless it addresses a discovered constraint tied to the stated task.

**Rules:**

- Implement only behavior required by the current user request or ticket acceptance criteria.
- If scope is ambiguous, ask clarifying questions before writing code.
- Do not add features, abstractions, or refactors not required to complete the stated task.
- Do not solve adjacent problems "while you're in the file" unless the user explicitly expands scope.
- When scope grows, stop and confirm the new scope before continuing.

**Good:** User asks for email validation on a form field; assistant adds validation and tests for that field only.

**Bad:** User asks for email validation; assistant refactors the entire form module and extracts three new services.

**Review signals:** PR diff touches files unrelated to the ticket; commit message does not map to stated task.

---

### EKP-AI02: Read before write

**Implements:** EKP-P05

**Intent:** AI assistants must understand existing code, conventions, and tests before proposing changes. Generation without exploration produces conflicts with project patterns.

**Rules:**

- Read relevant existing files before editing or creating code.
- Identify project conventions: naming, directory structure, error handling style, test patterns.
- Search for existing utilities before introducing new helpers or dependencies.
- Do not assume file contents—verify imports, types, and interfaces.
- For multi-file tasks, list files to inspect before making changes.

**Good:** Assistant reads `OrderService`, existing tests, and error types before adding a new validation method.

**Bad:** Assistant creates a new `Utils` class without checking whether the project already has a validation helper.

**Review signals:** New code duplicates existing functions; imports reference removed symbols; style inconsistent with surrounding file.

---

### EKP-AI03: Proportional change size

**Implements:** EKP-P02

**Intent:** Match the size and complexity of AI-generated change to problem significance, lifespan, and blast radius—not to the assistant's capacity to rewrite large areas.

**Rules:**

- Prefer the smallest change that solves the stated problem.
- Do not rewrite entire modules when a localized edit suffices.
- Scale structural ambition to task lifespan (prototype vs. core domain).
- Flag when a small request implies disproportionately large change.
- Default to one concern per response unless the user requests a batch.

**Good:** Bugfix in one method with one test update.

**Bad:** "Fix null check" triggers extraction of four classes and a new package.

**Review signals:** Line count >> problem significance; unrelated files modified; new dependencies for trivial fix.

---

### EKP-AI04: Prefer reversible steps

**Implements:** EKP-P03

**Intent:** AI-assisted work must preserve the ability to roll back or review incrementally. Irreversible steps require explicit human approval.

**Rules:**

- Prefer incremental, reviewable steps over single large transformations.
- Before structural change, confirm tests exist or propose characterization tests (see `testing.md`, EKP-TS05).
- Route Level 2+ refactoring to `refactoring.md` Decision Flow—do not auto-apply Level 3+.
- Separate behavior changes from structural changes when possible.
- State what behavior must remain true after the change.

**Good:** Extract method in one commit; run tests; proceed to next step in follow-up.

**Bad:** Rename, move, and restructure twelve files in one agent turn with no test updates.

**Review signals:** No test delta on structural PR; mixed refactor + feature without separation; "big bang" diff.

---

### EKP-AI05: Tests define done

**Implements:** EKP-P03, EKP-P10

**Intent:** AI assistants must not claim completion without appropriate verification. "Done" means behavior is protected by tests or explicit justification for omission.

**Rules:**

- For behavior changes, add or update tests that assert the new or preserved behavior.
- If tests are not added, state why existing coverage is sufficient (cite test names or EKP-TS concepts).
- Run tests when possible before claiming completion.
- Route test strategy questions to `testing.md` Decision Flow.
- Do not delete tests to make a change "pass" unless requirements changed.

**Good:** Assistant adds unit test for new validation rule and reports test command result.

**Bad:** Assistant says "implementation complete" with no mention of tests on a logic change.

**Review signals:** Logic change, zero test delta; deleted tests without requirement change; flaky suite ignored.

---

### EKP-AI06: Cite EKP concept IDs

**Implements:** EKP-P04

**Intent:** AI recommendations must be traceable to governed knowledge—not generic "best practices." Concept IDs make reasoning auditable in review.

**Rules:**

- When applying EKP guidance, cite the relevant concept ID (e.g., EKP-AI01, EKP-TS03, EKP-RF02).
- Prefer citing sibling document concepts over restating principle prose.
- When recommending a pattern or refactor, name the EKP concept that justifies it.
- If no EKP concept applies, state that explicitly and flag for human review.
- Do not invent EKP IDs—use only IDs defined in published knowledge documents.

**Good:** "Per EKP-EH04, this exception should preserve the error code at the boundary."

**Bad:** "Best practice is to always use a repository pattern here."

**Review signals:** Vague "clean code" advice with no ID; invented concept names; principle restated without downstream practice.

---

### EKP-AI07: Human gate for high-risk work

**Implements:** EKP-P01, EKP-P03

**Intent:** Some changes are too risky for autonomous AI application. The assistant must stop, explain trade-offs, and await explicit approval.

**Rules:**

- Do not auto-apply Level 3+ refactoring (see `refactoring.md` Risk Matrix).
- Do not auto-apply Level 4 architectural change—propose ADR draft instead (EKP-LB16, EKP-RF07).
- Do not modify authentication, authorization, payment, or data migration logic without explicit user approval.
- Present alternatives, risks, and verification plan before high-risk implementation.
- When in doubt, block and ask—do not guess on irreversible decisions.

**Good:** Assistant explains migration risk, lists rollback plan, and waits for "proceed" before schema change.

**Bad:** Assistant rewrites auth middleware in agent mode because user mentioned "login bug."

**Review signals:** Security-sensitive paths changed without discussion; ADR-worthy change with no ADR; Risk Matrix High/Critical auto-applied.

---

### EKP-AI08: No secrets in prompts or output

**Implements:** EKP-P07

**Intent:** AI assistants must not expose, request, or embed credentials, tokens, or private keys in prompts, code, logs, or chat output.

**Rules:**

- Never paste API keys, passwords, connection strings, or tokens into generated code as literals.
- Use environment variables or existing secret management patterns in the project.
- Redact secrets if found in files during exploration—do not repeat them in summaries.
- Warn the user if they paste secrets into chat.
- Do not commit `.env` files or credential artifacts.

**Good:** Assistant uses `process.env.DATABASE_URL` and references existing config pattern.

**Bad:** Assistant hardcodes `sk-live-...` in example code or echoes a key from `.env`.

**Review signals:** Literal secrets in diff; credentials in log statements; new committed secret files.

---

### EKP-AI09: Review diffs, not intentions

**Implements:** EKP-P10

**Intent:** AI assistants and reviewers must evaluate actual changes—files touched, behavior diff, test delta—not the assistant's stated intent.

**Rules:**

- Summaries must list files changed and behavior impact—not only high-level intent.
- Call out behavior changes vs. refactor-only changes explicitly.
- Highlight deletions, permission changes, and public API modifications.
- Do not claim "no behavior change" without test or reasoning support.
- Encourage diff review before merge; assistant should make diffs reviewable in size.

**Good:** "Changed `validateEmail` to reject plus-addresses; updated `EmailValidatorTest.testRejectsPlusAddress`."

**Bad:** "Improved validation" with no file list or test mention.

**Review signals:** Summary contradicts diff; silent API change; large diff with vague description.

---

### EKP-AI10: Escalate to sibling documents

**Implements:** EKP-P05

**Intent:** This document orchestrates—it does not replace domain-specific EKP knowledge. Classify the problem and route to the correct sibling Decision Flow.

**Rules:**

- Function/name/readability issues → `clean-code.md` (EKP-CC). Stop after local fix.
- Class/module design → `solid.md` (EKP-SL). Stop after design guidance applied.
- Named pattern selection → `design-patterns.md` (EKP-DP). Stop after pattern choice.
- Structural change → `refactoring.md` (EKP-RF) Decision Flow.
- Verification → `testing.md` (EKP-TS) Decision Flow.
- Errors/failures → `error-handling.md` (EKP-EH).
- System/integration boundary → `layering-and-boundaries.md` (EKP-LB) Decision Flow.
- HTTP API add/change → `architecture/api-design.md` (EKP-AP) Decision Flow.
- Schema, migration, or transaction scope → `database/database-design.md` (EKP-DB).
- Module/package coupling or split → `architecture/coupling-and-cohesion.md` (EKP-MC).
- Cross-service messaging or sync/async choice → `architecture/integration-patterns.md` (EKP-IN).
- One-way door / Level 4 / ADR required → `architecture/adr-practices.md` (EKP-AD).
- Security-sensitive change (auth, PII, payment, secrets) → `security/security-fundamentals.md` (EKP-SF) Decision Flow.
- PHP language/module design (types, Composer, globals, config edge) → `php/php-fundamentals.md` (EKP-PH) Decision Flow.
- Symfony application structure (DI, thin controllers, modules, Messenger, Security wiring) → `symfony/symfony-architecture.md` (EKP-SY) Decision Flow.
- Do not duplicate sibling content—cite and route.

**Good:** "This is a Level 2 extract method refactor—applying EKP-RF Decision Flow step 3."

**Bad:** Assistant pastes entire SOLID explanation instead of linking to EKP-SL03.

**Review signals:** Wrong document cited; architecture advice for naming issue; test advice without EKP-TS reference.

---

### EKP-AI11: Incremental commits over big-bang changes

**Implements:** EKP-P03, EKP-P10

**Intent:** AI-assisted work should produce reviewable units of change. Big-bang diffs hide defects and block reversibility.

**Rules:**

- Prefer multiple focused commits or sequential agent steps over one monolithic change.
- Separate formatting, refactor, and behavior changes when feasible.
- Do not mix unrelated file changes in one response.
- When a task is large, propose a phased plan with checkpoints.
- Align with `refactoring.md` incremental discipline (EKP-RF02).

**Good:** Phase 1: characterization tests. Phase 2: extract method. Phase 3: rename—each verifiable.

**Bad:** Single response rewrites auth, database layer, and API DTOs for a typo fix.

**Review signals:** Unrelated concerns in one PR; cannot bisect failure; review skipped due to size.

---

### EKP-AI12: Verify before claiming done

**Implements:** EKP-P07, EKP-P10

**Intent:** Completion is a contract: scope addressed, changes listed, verification performed, risks stated. "Done" without verification is a process failure.

**Rules:**

- Before claiming completion, confirm: scope met, files changed, behavior preserved or updated, tests run or justified.
- Report verification commands run (test, lint, build) and their outcome when available.
- State remaining risks, follow-ups, or manual checks required.
- If verification failed, report failure—do not claim success.
- Use the completion template in AI Decision Flow step 8.

**Good:** "Scope: email validation added. Files: `UserForm.ts`, `UserForm.test.ts`. Tests: `npm test UserForm` — 14 passed. Risk: server-side validation still required."

**Bad:** "All done!" with no files, tests, or verification mentioned.

**Review signals:** False completion; tests not run; known failure ignored; no summary block.

## AI Decision Flow

Canonical sequence for Cursor, Claude, Google Gravity, and future EKP adapters. Extract verbatim for rules in Phase 3A. This flow runs **before** sibling document flows.

```
1. Scope verification
   Is the request scoped with clear acceptance criteria?
   → NO: EKP-AI01 — Ask for scope. Do not implement. Stop.

2. Repository exploration
   Have you read relevant code, tests, and conventions?
   → NO: EKP-AI02 — Explore first. Stop.

3. Change size evaluation
   Is the proposed change proportional to the problem (EKP-AI03)?
   → NO: Propose smaller approach. Stop if user insists on disproportionate change without approval.

4. Architecture boundary detection
   Does the change cross a service, team, or layer boundary?
   → YES: Route to layering-and-boundaries.md Decision Flow (EKP-LB). Stop auto-apply.
   → NO: Continue.

5. Testing requirement evaluation
   Does the change alter behavior or risk?
   → YES: Apply testing.md guidance (EKP-TS). Add/update tests or justify omission (EKP-AI05).
   → NO: State why existing coverage suffices.

6. Error handling evaluation
   Does the change touch failure paths, validation, or external I/O?
   → YES: Apply error-handling.md (EKP-EH). Define failure semantics before implementation.
   → NO: Continue.

7. Human approval gate
   Is risk High or Critical (refactoring Risk Matrix) or does change touch auth/payment/migration?
   → YES: EKP-AI07 — Explain trade-offs. Do NOT auto-apply. Await explicit approval.
   → NO: Continue.

8. Completion verification
   Summarize: scope met, files changed, behavior impact, tests/verification run, remaining risks.
   → Only after step 8 may the assistant claim completion (EKP-AI12).
```

**Adapter enforcement:**

| Step | Auto-apply | Notes |
|------|------------|-------|
| 1 — Scope | Block | Hard gate — EKP-AI01 |
| 2 — Exploration | Block | Hard gate — EKP-AI02 |
| 3 — Proportionality | Conditional | Smaller alternative required |
| 4 — Boundary | Route | Delegate to EKP-LB flow |
| 5 — Testing | Conditional | Tests or explicit justification |
| 6 — Errors | Conditional | EKP-EH contract required |
| 7 — Human gate | Hard block | EKP-AI07 — no auto-apply |
| 8 — Completion | Required | EKP-AI12 summary mandatory |

## AI-specific guidance

### Universal rules

- **AI-U-01:** Run this document's Decision Flow before any sibling EKP Decision Flow.
- **AI-U-02:** Cite EKP concept IDs in recommendations (EKP-AI06).
- **AI-U-03:** Never expand scope beyond the stated task (EKP-AI01, EKP-P01).
- **AI-U-04:** Read before write—explore codebase before generating (EKP-AI02).
- **AI-U-05:** Tests define done—no false completion (EKP-AI05, EKP-AI12).
- **AI-U-06:** Escalate to sibling documents by problem class (EKP-AI10).
- **AI-U-07:** Incremental changes over big-bang (EKP-AI11).
- **AI-U-08:** No secrets in prompts or output (EKP-AI08).
- **AI-U-09:** High-risk and Level 3+ work requires human approval (EKP-AI07).
- **AI-U-10:** Summarize diffs and verification, not intentions (EKP-AI09).

### Cursor

- Map `adapter_priority: high` on this document to **alwaysApply** orchestrator rule (`00-ekp-orchestrator.mdc` in Phase 3A).
- Apply AI Decision Flow steps 1–2 before agent mode multi-file edits.
- Use step 4 to route boundary questions to `layering-and-boundaries.md`—do not invent service layers.
- Use step 7 to block agent loops on auth, payment, schema migration, and Level 3+ refactors.
- Completion responses must include step 8 summary block in agent and chat modes.
- Do not auto-apply changes across files not mentioned in the user request unless exploration step justifies them and scope is confirmed.

### Future adapters

- Extract **AI Decision Flow** and **Adapter enforcement** table first—highest priority.
- Emit per-concept rules from EKP-AI01–EKP-AI12 `**Rules:**` sections.
- Map EKP-AI08 `**Rules:**` to hard **Constraints** (non-negotiable).
- Map step 7 enforcement to **Constraints** with `Never auto-apply...`.
- Do not restate EKP-P01/P03/P10 prose—reference concept IDs only.
- Sibling document flows (`EKP-RF`, `EKP-TS`, `EKP-LB`, `EKP-EH`) are invoked by reference from this orchestrator.

## Adapter metadata table

Documents which sections adapters should extract automatically in Phase 3A.

| Section | Extract priority | Target output | Notes |
|---------|------------------|---------------|-------|
| Frontmatter `adapter_priority: high` | P0 | Bundle inclusion flag | Always in `cursor-core` profile |
| `## AI Decision Flow` | P0 | `alwaysApply` orchestrator `.mdc` | Verbatim steps + enforcement table |
| `### EKP-AI01`–`EKP-AI12` `**Rules:**` | P1 | Per-concept `.mdc` directives | One file per concept |
| `**Adapter enforcement:**` | P0 | `## Constraints` in orchestrator | Block/auto-apply matrix |
| `### Universal rules` (AI-U-*) | P1 | Orchestrator directives supplement | Merge if not redundant |
| `### Cursor` | P1 | Cursor-specific `.mdc` appendix | Tool section |
| `**Good:**` / `**Bad:**` | P2 | `## Preferences` | Optional examples |
| `**Review signals:**` | P3 | Not extracted initially | Human review only |
| `## Summary`, `## Context` | P3 | Not extracted | Human-readable only |

| Field | Value |
|-------|-------|
| `role` | `practice` |
| `depends_on` | `engineering-principles.md` |
| `implements` | EKP-P01, EKP-P03, EKP-P10 |
| `concept_ids` | EKP-AI01–EKP-AI12 |
| `adapter_priority` | high — Decision Flow + all EKP-AI concepts |
| Orchestrator | Yes — run before sibling flows |
| Siblings (escalation) | `refactoring.md`, `testing.md`, `error-handling.md`, `layering-and-boundaries.md`, `clean-code.md` |

## Review signals

| Signal | Verdict | Concept |
|--------|---------|---------|
| Scoped task; exploration before edit; tests updated | Good AI-assisted change | EKP-AI01, EKP-AI02, EKP-AI05 |
| Step 8 completion summary with verification | Good completion contract | EKP-AI12 |
| EKP IDs cited in recommendation | Traceable guidance | EKP-AI06 |
| Unrelated files in diff | Scope smuggling | EKP-AI01 |
| "Done" without tests on logic change | False completion | EKP-AI05, EKP-AI12 |
| Secret literal in generated code | Security defect | EKP-AI08 |
| Level 3+ refactor auto-applied | Human gate violation | EKP-AI07 |
| Big-bang multi-module rewrite | Incremental discipline failure | EKP-AI11 |

## Trade-offs

Governed AI assistance improves reviewability and reduces risk. It is not free.

| Benefit | Cost |
|---------|------|
| Fewer scope-smuggling and false-completion defects | Extra exploration and summary steps |
| Traceable reasoning via EKP IDs | Assistant responses slightly longer |
| Safer structural and boundary change | Human gates slow autonomous agent loops |
| Consistent escalation to sibling knowledge | Learning curve for concept ID vocabulary |

**When this document is insufficient:**

- Refactoring levels and budgets → `refactoring.md` (EKP-RF)
- Test strategy and pyramid → `testing.md` (EKP-TS)
- Error contracts → `error-handling.md` (EKP-EH)
- Layer and service boundaries → `layering-and-boundaries.md` (EKP-LB)
- Naming and readability → `clean-code.md` (EKP-CC)
- Security practices beyond secret handling → `security/security-fundamentals.md` (EKP-SF)

## Knowledge graph position

```
engineering-principles
        │
        ├── ai-assisted-development (practice) ◄── this document — orchestrator
        ├── refactoring (procedure)
        ├── testing (practice)
        ├── error-handling (practice)
        ├── clean-code (practice)
        └── layering-and-boundaries (architecture)
```

## Related documents

- [Engineering Principles](../engineering/engineering-principles.md) — EKP-P01–P10 foundation
- [Refactoring](../engineering/refactoring.md) — structural change procedures (EKP-RF)
- [Testing](../testing/testing.md) — verification philosophy (EKP-TS)
- [Error Handling](../engineering/error-handling.md) — failure semantics (EKP-EH)
- [Layering and Boundaries](../architecture/layering-and-boundaries.md) — system boundaries (EKP-LB)
- [Clean Code](../engineering/clean-code.md) — readability practices (EKP-CC)
- [AI domain index](README.md)
