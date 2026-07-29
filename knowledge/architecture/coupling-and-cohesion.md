---
title: Coupling and Cohesion
domain: architecture
tags: [coupling, cohesion, modules, packages, structure]
severity: recommended
applies_to: [backend, frontend, api, mobile]
type: guide
role: architecture
depends_on:
  - knowledge/engineering/engineering-principles.md
implements:
  - EKP-P05
  - EKP-P09
related:
  - knowledge/engineering/engineering-principles.md
  - knowledge/engineering/solid.md
  - knowledge/engineering/design-patterns.md
  - knowledge/engineering/refactoring.md
  - knowledge/architecture/layering-and-boundaries.md
  - knowledge/architecture/README.md
extends: []
concept_ids: [EKP-MC01, EKP-MC02, EKP-MC03, EKP-MC04, EKP-MC05, EKP-MC06, EKP-MC07]
adapter_priority: medium
---

# Coupling and Cohesion

## Summary

Stack-agnostic **architecture-layer** guidance for **module and package** structure: coupling types, cohesion signals, and when to split or merge deployable units of code. This document operationalizes **EKP-P05** (Local reasoning) and **EKP-P09** (Compose, do not accumulate) at the **module boundary**—between class-level design and system-level layering.

Apply during package design, module extraction, and architecture review. Relax per **EKP-P02** for small codebases where module ceremony exceeds benefit.

**Unit of analysis:** package, module, namespace, or logical bounded area—not individual classes (`solid.md`) and not service topology (`layering-and-boundaries.md`).

## Context

Poor module boundaries produce change amplification: a one-line fix touches five packages because responsibilities leaked across module edges. Class-level SOLID compliance does not prevent a `billing` package from importing `admin.ui` internals.

**Boundaries:**

| Concern | Unit | Owner document |
|---------|------|----------------|
| Function/file readability | Function, file | `clean-code.md` (EKP-CC) |
| Class responsibility, DIP | Class, interface | `solid.md` (EKP-SL) |
| Named in-process structures | Class collaborations | `design-patterns.md` (EKP-DP) |
| **Module/package coupling & cohesion** | **Module, package** | **this document (EKP-MC)** |
| Layers, services, integration contracts | System | `layering-and-boundaries.md` (EKP-LB) |
| Safe structural change steps | Procedure | `refactoring.md` (EKP-RF) |

**Out of scope:** microservice decomposition defaults, service mesh, layer definitions (EKP-LB), class-level SRP (EKP-SL01).

## Guidance

### EKP-MC01: Module-level coupling and cohesion

**Implements:** EKP-P05

**Intent:** **Coupling** = how much modules depend on each other's internals. **Cohesion** = how related responsibilities within a module are.

**Rules:**

- Prefer modules where internal elements change together (high cohesion).
- Prefer dependencies on stable, narrow module APIs—not internal folders.
- If changing module A routinely requires editing module B's private code, boundaries are wrong.

---

### EKP-MC02: Coupling types

**Implements:** EKP-P05

**Intent:** Name coupling to diagnose fixes—not all coupling is equal.

| Type | Signal | Mitigation direction |
|------|--------|---------------------|
| **Data** | Shared DTOs across unrelated modules | Narrow shared kernel or mapping at boundary |
| **Control** | Module A dictates B's workflow | Invert dependency; shared interface |
| **Temporal** | Modules must load/init together | Explicit lifecycle or merge modules |
| **External** | Many modules reach same third-party detail | Adapter module (cite EKP-DP, not tutorial) |

Do not restate integration patterns between **services**—see `integration-patterns.md` when published.

---

### EKP-MC03: Cohesion heuristics

**Implements:** EKP-P09

**Intent:** A module should have a clear reason to change.

**Strong cohesion signals:**

- Module name matches business capability or technical capability (e.g. `pricing`, `auth-tokens`).
- Public API is small; internals are private.
- Tests for module run without unrelated modules' databases.

**Weak cohesion signals:**

- `utils`, `helpers`, `common` growing without ownership.
- Module contains unrelated feature folders with no shared concept.

---

### EKP-MC04: Signs of a poorly split module

**Implements:** EKP-P05

**Intent:** Detect splits that increase cost without improving reasoning.

**Signals:**

- Feature envy: most changes touch two modules for one user story.
- Circular package dependencies.
- "Reach through" imports (`billing` imports `admin.internal.models`).
- Identical DTOs duplicated because modules cannot share a narrow contract.

**Escalate to EKP-LB** when split implies new **service** or **team** boundary—not merely new folder.

---

### EKP-MC05: When to extract a module

**Implements:** EKP-P02, EKP-P09

**Intent:** Extract when independent evolution or test isolation justifies boundary cost.

**Extract when:**

- Submodule has distinct release cadence or ownership candidate.
- Tests require heavy setup from unrelated domains.
- Clear API surface can be defined with &lt;10 public entry points.

**Require ADR** when extraction changes deployable units (**EKP-AD01**, **EKP-LB16**).

---

### EKP-MC06: When not to extract

**Implements:** EKP-P02

**Intent:** Premature modularization is as harmful as a god package.

**Do not extract when:**

- Team size is one or two; navigation cost exceeds benefit.
- No second consumer for the "reusable" module.
- Spike code with discard date.
- Extraction only to satisfy aesthetic "clean architecture" without pain point.

---

### EKP-MC07: Review signals

**Implements:** EKP-P05

| Signal | Verdict |
|--------|---------|
| Change localized to one module with stable public API | Good boundary |
| New feature adds only public API calls to neighbor | Good coupling |
| Circular module import | Fix before merge |
| Third `utils` subfolder in one sprint | Cohesion debt |

## When not to apply

Skip module restructuring analysis when:

- Codebase has &lt;10 source files or single deployable with one team (**EKP-P02**).
- Change is Level 1–2 refactor inside one package (**EKP-RF**).
- Problem is network/service boundary—use **EKP-LB** first.

## Trade-offs

| Benefit | Cost |
|---------|------|
| Local reasoning within modules (**EKP-P05**) | More packages to navigate |
| Clear ownership candidates | Initial extraction effort |
| Test isolation | API design upfront |

## Related

- [SOLID](../engineering/solid.md) — class-level design (EKP-SL)
- [Layering and Boundaries](layering-and-boundaries.md) — system layers (EKP-LB)
- [Refactoring](../engineering/refactoring.md) — change procedure (EKP-RF)
- [Architecture domain index](README.md)
