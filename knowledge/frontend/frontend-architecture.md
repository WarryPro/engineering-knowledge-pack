---
title: Frontend Architecture
domain: frontend
tags: [frontend, architecture, components, state, accessibility, ui]
severity: recommended
applies_to: [frontend, api]
type: guide
role: architecture
depends_on:
  - knowledge/engineering/engineering-principles.md
  - knowledge/typescript/typescript-fundamentals.md
implements:
  - EKP-P04
  - EKP-P05
  - EKP-P06
  - EKP-P09
related:
  - knowledge/engineering/engineering-principles.md
  - knowledge/typescript/typescript-fundamentals.md
  - knowledge/architecture/layering-and-boundaries.md
  - knowledge/architecture/coupling-and-cohesion.md
  - knowledge/architecture/api-design.md
  - knowledge/security/security-fundamentals.md
  - knowledge/performance/performance-mindset.md
  - knowledge/testing/testing.md
  - knowledge/frontend/README.md
extends: []
concept_ids: [EKP-FE01, EKP-FE02, EKP-FE03, EKP-FE04, EKP-FE05, EKP-FE06, EKP-FE07, EKP-FE08]
adapter_priority: high
---

# Frontend Architecture

## Summary

Architecture-layer guidance for **client-side UI systems**: component boundaries, state ownership, composition, presentation vs domain separation, async UI, accessibility, and rendering boundaries. This document **applies** **EKP-P04**, **EKP-P05**, **EKP-P06**, and **EKP-P09**, and routes to L0 architecture/security/testing guides—it does not replace them or teach React/Vue/Angular.

Apply when designing or reviewing UI structure, data flow, and integration with APIs. TypeScript language rules belong in [`typescript-fundamentals.md`](../typescript/typescript-fundamentals.md) (EKP-TY). Relax per **EKP-P02** for throwaway UI spikes with documented expiry.

## Context

Frontend failures are often boundary failures: business rules in view components, global mutable UI state, unowned async flows, and presentation layers that know persistence details. Assistants generate “god components” and prop-drilling fixes with global stores unless constrained.

**Boundaries:**

| Concern | Owner | This document |
|---------|-------|---------------|
| TypeScript typing, modules, runtime parse | `typescript-fundamentals.md` (EKP-TY) | Prerequisite — cite |
| System layers / API contracts | `layering-and-boundaries.md` (EKP-LB) | Apply — do not redefine |
| Module coupling | `coupling-and-cohesion.md` (EKP-MC) | Apply at feature/package level |
| HTTP API shape | `api-design.md` (EKP-AP) | Cite for client consumption |
| Authn/authz mindset | `security-fundamentals.md` (EKP-SF) | Apply in UI gates |
| Performance mindset | `performance-mindset.md` (EKP-PM) | Cite for render/load trade-offs |
| Verification | `testing.md` (EKP-TS) | Cite — tests define done |
| PHP/Symfony/backend stacks | `php/`, `symfony/` | **Out of scope** — no cross-stack deps |
| Framework tutorials (React/Vue/Angular) | Vendor docs | Out of scope |

**Out of scope:** Component library catalogs, CSS framework encyclopedias, design tool workflows, mobile Flutter (`flutter/`). Markup, styling architecture decisions, layout/responsive principles, and operational a11y beyond this guide’s FE06 baseline belong in [`frontend-styling-and-markup.md`](frontend-styling-and-markup.md) (EKP-FE09–FE16).

## EKP layer positioning

| Layer | Role | This document |
|-------|------|---------------|
| **Principles (L0)** | Why | Implements EKP-P04, P05, P06, P09 by reference |
| **Language (L1)** | TypeScript | Depends on EKP-TY |
| **Frontend (L2)** | UI architecture | **Primary** |

## Guidance

### EKP-FE01: Components own UI; not business policy

**Implements:** EKP-P05, EKP-P06

**Applies:** EKP-LB01–LB04, EKP-TY04

**Intent:** UI components render and capture intent—they do not embed domain rules that belong in application or domain layers.

**Rules:**

- Keep components thin: props in, events out; domain decisions in hooks/services/stores with tests.
- Do not call HTTP clients directly from leaf presentation components when a feature boundary exists.
- Shared presentation components must not import feature-specific domain types.
- When framework types leak inward, document exception and exit plan.

**Good:** `OrderSummary` receives `OrderViewModel`; pricing rules live in `calculateOrderTotal`.

**Bad:** Tax calculation inside a button click handler in a list item component.

**Review signals:** API URLs in presentational files; domain exceptions thrown from JSX files.

---

### EKP-FE02: State has a single owner

**Implements:** EKP-P04, EKP-P05

**Applies:** EKP-MC01, EKP-TY05 (discriminated UI states)

**Intent:** Every piece of mutable UI state has one authoritative owner—avoid synchronized copies and ambiguous update paths.

**Rules:**

- Classify state: local UI, shared feature, server/cache, URL—place each in one owner.
- Lift state only when multiple siblings need it; do not lift prematurely to global store.
- Server state and client UI state are different concerns—do not mirror server data into editable local copies without sync strategy.
- Document ownership in feature README or module boundary when non-obvious.

**Good:** Server list from query cache; filter text in local component state.

**Bad:** Same `selectedId` in URL, context, and Redux with manual sync.

**Review signals:** `useEffect` chains syncing two stores; “source of truth” unclear in review.

---

### EKP-FE03: Compose UI from small, predictable units

**Implements:** EKP-P09, EKP-P05

**Applies:** EKP-CC (readability), EKP-MC (cohesion)

**Intent:** Composition beats inheritance and mega-components—build UIs from focused units with clear props contracts.

**Rules:**

- Prefer composition (children, slots, render props) over deep component hierarchies with implicit context.
- Split when a component handles unrelated concerns (layout + data fetch + form + modal).
- Props interfaces are public API—keep them stable and minimal.
- Avoid “utility” components that know every feature flag.

**Good:** `PageLayout` + `OrderFilters` + `OrderTable` composed in route shell.

**Bad:** 800-line `Dashboard.tsx` with embedded fetch, table, and modal logic.

**Review signals:** Prop drilling >4 levels without intentional boundary; god component growth.

---

### EKP-FE04: Separate presentation from domain

**Implements:** EKP-P05, EKP-P06

**Applies:** EKP-LB04, EKP-TY (typed view models)

**Intent:** Domain models and view models differ—map at the boundary so UI can evolve independently of backend shape.

**Rules:**

- Map API DTOs to view models at feature boundary (cite EKP-TY08 for parse/validate).
- Presentation components depend on view types, not raw transport shapes.
- Formatting, i18n, and display defaults belong in presentation layer.
- Do not expose persistence identifiers or internal flags to generic UI kit components.

**Good:** `toOrderRow(dto): OrderRow` before passing to table component.

**Bad:** Table columns bound directly to snake_case API fields across the app.

**Review signals:** Leaking `entity._internal` fields into shared UI; DTO types imported in design system package.

---

### EKP-FE05: Model async UI explicitly

**Implements:** EKP-P04, EKP-P07

**Applies:** EKP-EH, EKP-TY05, EKP-AP (loading/error semantics)

**Intent:** Loading, empty, error, and success are user-visible states—model them explicitly, not as afterthoughts.

**Rules:**

- Use discriminated unions or equivalent for async UI state (cite EKP-TY05).
- Every user-initiated async action has visible pending and failure feedback.
- Retry and cancellation behavior must be defined for long operations.
- Do not leave failed requests silent—map to EKP-EH-style user-visible errors.

**Good:** `status: 'loading' | 'error' | 'empty' | 'ready'` drives render branches.

**Bad:** Spinner never dismissed; errors only `console.error`.

**Review signals:** Missing error UI; double-submit on slow networks; race conditions on tab change.

---

### EKP-FE06: Accessibility is an architectural requirement

**Implements:** EKP-P06, EKP-P04

**Applies:** EKP-SF (inclusive safety), testing (EKP-TS)

**Intent:** a11y is not a polish pass—keyboard flow, semantics, and contrast affect correctness and compliance.

**Rules:**

- Interactive controls must be reachable and operable by keyboard.
- Prefer semantic HTML/native roles before custom widgets; document custom widget a11y contract.
- Labels, errors, and live regions for dynamic content must be associated correctly.
- Do not rely on color alone for critical state (cite proportional effort **EKP-P02** for internal-only tools).

**Good:** Form field with `label`, `aria-invalid`, and described error text.

**Bad:** `div onClick` as primary button with no role/tabIndex.

**Review signals:** Missing focus management in modals; icon-only buttons without labels.

---

### EKP-FE07: Respect rendering and data-fetch boundaries

**Implements:** EKP-P05, EKP-P08

**Applies:** EKP-PM (measure before optimize), EKP-LB (boundaries)

**Intent:** Where and when you render/fetch determines performance and correctness—boundaries must be intentional.

**Rules:**

- Fetch at the lowest level that owns the data need—avoid waterfall without justification.
- Split code by route/feature boundary when bundle size affects users (**EKP-P08** evidence).
- Do not subscribe the entire app tree to high-frequency updates for a local widget.
- SSR/hydration boundaries (if used) are one-way doors—record ADR when adopting (EKP-AD).

**Good:** Route-level data loader; memoized list row for large collections after measurement.

**Bad:** Global store subscription causing full-app re-render on each keystroke in search.

**Review signals:** Unmeasured premature memoization; fetch-per-row N+1 in UI layer.

---

### EKP-FE08: Record one-way frontend architecture decisions

**Implements:** EKP-P03, EKP-P09

**Applies:** EKP-AD (ADR practices)

**Intent:** Client architecture choices (global store vs local, routing model, SSR, micro-frontends) are costly to reverse—document them.

**Rules:**

- Adopt global state library, micro-frontend split, or SSR framework as ADR when blast radius is high.
- Prefer reversible choices for early product (**EKP-P03**).
- Align folder structure with feature boundaries (cite EKP-MC)—not only with framework defaults.
- Deprecate patterns with migration note when superseded.

**Good:** ADR: “Use URL state for shareable filters; context for ephemeral panel UI.”

**Bad:** Introduce Redux + React Query + custom event bus in one PR without decision record.

**Review signals:** Third state library added; conflicting patterns in adjacent features.

## AI Decision Flow

For frontend architecture changes. Run after `ai-assisted-development.md` steps 1–3. TypeScript-only issues route to **EKP-TY** first.

```
1. TypeScript language vs UI structure?
   → Types/modules/unknown/strict: typescript-fundamentals.md (EKP-TY).
   → Component/state/rendering: continue.

2. Component vs domain (EKP-FE01)
   → Business rules in view: extract to feature service/hook.

3. State ownership (EKP-FE02)
   → Duplicate sources: consolidate owner; model async with EKP-TY05.

4. Composition (EKP-FE03)
   → God component: split by concern.

5. View models (EKP-FE04)
   → Raw DTO in UI kit: map at boundary.

6. Async UX (EKP-FE05)
   → Missing error/loading: add explicit states.

7. a11y (EKP-FE06)
   → Keyboard/semantics failures: fix before merge.

8. Fetch/render scope (EKP-FE07)
   → Measure if performance claim; narrow subscriptions.

9. One-way decisions (EKP-FE08)
   → New global pattern: require ADR (EKP-AD).
```

| ID | Rule |
|----|------|
| **FE-AI-01** | No domain policy embedded in leaf presentation components. |
| **FE-AI-02** | Do not teach React/Vue—apply architecture constraints only. |
| **FE-AI-03** | Do not duplicate EKP-LB / EKP-AP / EKP-SF—cite and route. |

## When not to apply

- Non-UI scripts or build tooling (**EKP-P02**).
- Pure TypeScript library with no UI — EKP-TY only.
- Native mobile Flutter — `flutter/` when published.

## Trade-offs

| Benefit | Cost |
|---------|------|
| Clear state ownership reduces bugs | More explicit modeling upfront |
| View models decouple UI from API churn | Mapping layer maintenance |
| a11y by default improves reach | Slightly slower initial delivery |

## Related

- [TypeScript Fundamentals](../typescript/typescript-fundamentals.md) — EKP-TY
- [Engineering Principles](../engineering/engineering-principles.md) — EKP-P
- [Layering and Boundaries](../architecture/layering-and-boundaries.md) — EKP-LB
- [Coupling and Cohesion](../architecture/coupling-and-cohesion.md) — EKP-MC
- [API Design](../architecture/api-design.md) — EKP-AP
- [Security Fundamentals](../security/security-fundamentals.md) — EKP-SF
- [Testing](../testing/testing.md) — EKP-TS
- [ADR Practices](../architecture/adr-practices.md) — EKP-AD
- [Frontend Styling and Markup](frontend-styling-and-markup.md) — EKP-FE09–FE16
- [Frontend domain index](README.md)
