---
title: ADR Practices
domain: architecture
tags: [adr, decisions, governance, architecture, documentation]
severity: recommended
applies_to: [backend, frontend, api, mobile]
type: guide
role: procedure
depends_on:
  - knowledge/engineering/engineering-principles.md
implements:
  - EKP-P03
  - EKP-P06
related:
  - knowledge/engineering/engineering-principles.md
  - knowledge/engineering/refactoring.md
  - knowledge/architecture/layering-and-boundaries.md
  - knowledge/architecture/decisions/README.md
  - knowledge/architecture/README.md
extends: []
concept_ids: [EKP-AD01, EKP-AD02, EKP-AD03, EKP-AD04, EKP-AD05, EKP-AD06, EKP-AD07]
adapter_priority: medium
---

# ADR Practices

## Summary

Stack-agnostic **procedure-layer** guidance for writing, maintaining, and linking Architecture Decision Records (ADRs). This document operationalizes **EKP-P03** (Prefer reversible decisions) and **EKP-P06** (Own the boundary) for **one-way architectural choices**—when the decision itself must be recorded, not how layers or APIs are designed.

Apply when a structural choice is hard to reverse, contested, or will be questioned later. Relax per **EKP-P02** (Proportionality) when the change is cheap to undo or covered by existing EKP knowledge.

Location and naming rules live in [`decisions/README.md`](decisions/README.md). This document defines the **process and judgment**—not the content of any specific decision.

## Context

Teams forget why systems look the way they do. Without ADRs, reversibility is guessed, AI assistants propose structural rewrites without context, and Level 4 refactors ship inside feature PRs (**EKP-RF07**, **EKP-LB16**).

[Engineering Principles](../engineering/engineering-principles.md) require explicit rationale for one-way doors. [Refactoring](../engineering/refactoring.md) requires an ADR before Level 4 work. This document defines *how* to author and govern ADRs.

**Boundaries:**

| Concern | Owner document | This document |
|---------|----------------|---------------|
| ADR process, lifecycle, when to write | **this document** (EKP-AD) | Primary content |
| ADR file location and naming | `decisions/README.md` | Reference only |
| Level 4 refactoring trigger | `refactoring.md` (EKP-RF07) | Cite — do not duplicate |
| Architecture change governance rule | `layering-and-boundaries.md` (EKP-LB16) | Cite — do not duplicate |
| Layer design, API shape, integration style | Sibling architecture guides | Out of scope |
| Decision record template fields | `templates/decision-record-template.md` | Reference only |

**Out of scope:** compliance frameworks (PCI, SOC2), tooling (adr-tools), project-specific topology, stack-specific architecture.

## Guidance

### EKP-AD01: When to write an ADR

**Implements:** EKP-P03, EKP-P06

**Intent:** Record decisions that are costly to reverse or need shared team memory.

**Write an ADR when:**

- Service boundaries, persistence technology, or public API strategy changes.
- Multiple valid approaches existed and the choice affects future work.
- Level 4 refactoring is planned (**EKP-RF07**).
- Knowledge graph boundaries or document ownership change (see ADR-0004 pattern).

**Good:** ADR before splitting monolith into two deployables with shared database.

**Bad:** ADR for renaming a private helper function.

---

### EKP-AD02: When not to write an ADR

**Implements:** EKP-P02

**Intent:** Avoid ceremony that exceeds problem significance.

**Do not write an ADR when:**

- Existing EKP guide already answers the question (cite the guide instead).
- Change is reversible within a sprint without data migration.
- Spike or prototype with documented discard date.
- Routine implementation within agreed conventions.

**Good:** Link to `clean-code.md` for naming convention—no ADR.

**Bad:** ADR to justify every new REST endpoint.

---

### EKP-AD03: Minimum ADR structure

**Implements:** EKP-P04

**Intent:** Every ADR answers: context, decision, and consequences—nothing more is required for validity.

**Required sections:**

| Section | Purpose |
|---------|---------|
| **Status** | Proposed, Accepted, Deprecated, Superseded |
| **Context** | Forces and constraints driving the decision |
| **Decision** | What was chosen |
| **Consequences** | Trade-offs accepted (positive and negative) |

**Optional but valuable:** Alternatives considered, Compliance notes, Related links.

Use `templates/decision-record-template.md`. Do not restate EKP principles—link to concept IDs.

---

### EKP-AD04: ADR lifecycle

**Implements:** EKP-P03

**Intent:** ADRs are living records with explicit status—not immutable lore.

**Rules:**

- New decisions start as **Proposed** until reviewed and **Accepted**.
- **Deprecated** when no longer recommended but history matters.
- **Superseded** when replaced by a newer ADR (link both directions).
- Do not delete Accepted ADRs—update status instead.

---

### EKP-AD05: Superseding without erasing history

**Implements:** EKP-P03

**Intent:** Teams learn from past decisions—even wrong ones.

**Rules:**

- New ADR states which ADR it supersedes and **why** context changed.
- Old ADR status → Superseded; add forward link to replacement.
- If migration is required, consequences section lists migration owner and verification.

---

### EKP-AD06: Link ADRs to the knowledge graph

**Implements:** EKP-P06

**Intent:** ADRs connect to guides they specialize or override—not isolated documents.

**Rules:**

- `Related` section links to EKP guides the decision constrains or extends.
- Downstream guides cite ADR numbers when project-specific choice diverges from default EKP guidance.
- Store under `knowledge/architecture/decisions/` per `decisions/README.md`.

---

### EKP-AD07: ADRs and AI-assisted work

**Implements:** EKP-P03

**Intent:** AI assistants propose ADR drafts for structural change—they do not auto-apply Level 4 work.

**Rules:**

- Level 4 / one-way door: draft ADR outline; await human acceptance (**EKP-AI07**, **EKP-LB16**).
- Do not implement service extraction, schema replacement, or permission model rewrite until ADR is Accepted.
- ADR draft in chat is not Accepted—explicit human approval required.

## When not to apply

Skip ADR process when **all** apply:

- Change is Level 1–3 refactoring per **EKP-RF** with no new boundary.
- No new team alignment needed; guide already covers the technique.
- Lifespan is throwaway per **EKP-P02**.

## Trade-offs

| Benefit | Cost |
|---------|-------|
| Preserves rationale for one-way doors (**EKP-P03**) | Authoring and review time |
| Blocks scope smuggling in PRs (**EKP-LB16**) | Perceived slowdown on “small” structural changes |
| AI proposes structure before code | Extra step for agents |

**When this document is insufficient:**

- Where to store ADRs → `decisions/README.md`
- Refactoring levels → `refactoring.md` (EKP-RF)
- Layer/boundary rules → `layering-and-boundaries.md` (EKP-LB)

## Related

- [Architecture decisions index](decisions/README.md)
- [Refactoring](../engineering/refactoring.md) — EKP-RF07 Level 4
- [Layering and Boundaries](layering-and-boundaries.md) — EKP-LB16
- [Engineering Principles](../engineering/engineering-principles.md)
- [Architecture domain index](README.md)
