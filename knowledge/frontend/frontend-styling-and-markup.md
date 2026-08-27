---
title: Frontend Styling and Markup
domain: frontend
tags: [frontend, html, css, styling, accessibility, responsive, design-tokens]
severity: recommended
applies_to: [frontend]
type: guide
role: architecture
depends_on:
  - knowledge/engineering/engineering-principles.md
implements:
  - EKP-P02
  - EKP-P03
  - EKP-P04
  - EKP-P05
  - EKP-P06
  - EKP-P09
related:
  - knowledge/engineering/engineering-principles.md
  - knowledge/frontend/frontend-architecture.md
  - knowledge/typescript/typescript-fundamentals.md
  - knowledge/architecture/adr-practices.md
  - knowledge/architecture/layering-and-boundaries.md
  - knowledge/testing/testing.md
  - knowledge/performance/performance-mindset.md
  - knowledge/frontend/README.md
extends: []
concept_ids: [EKP-FE09, EKP-FE10, EKP-FE11, EKP-FE12, EKP-FE13, EKP-FE14, EKP-FE15, EKP-FE16]
adapter_priority: high
---

# Frontend Styling and Markup

## Summary

Architecture-layer guidance for **web markup, styling decisions, layout/responsive strategy, operational accessibility, and UI verification boundaries**. This document **applies** **EKP-P02**, **EKP-P03**, **EKP-P04**, **EKP-P05**, **EKP-P06**, and **EKP-P09**. It complements [`frontend-architecture.md`](frontend-architecture.md) (EKP-FE01–FE08)—it does not redefine component/state architecture or teach React/Vue/Angular, Bootstrap/Tailwind, SCSS, or CSS-in-JS APIs.

Apply when choosing or reviewing HTML structure, CSS/styling approach, layout/responsive behavior, interactive a11y, or how UI behavior is tested. TypeScript language rules belong in [`typescript-fundamentals.md`](../typescript/typescript-fundamentals.md) (EKP-TY). Generic verification philosophy belongs in [`testing.md`](../testing/testing.md) (EKP-TS). Measure-first performance belongs in [`performance-mindset.md`](../performance/performance-mindset.md) (EKP-PM). Relax per **EKP-P02** for throwaway UI spikes with documented expiry.

## Context

Assistants often invent a second styling stack, prefer familiar frameworks over repository convention, escalate specificity with global overrides, prescribe arbitrary breakpoints, or replace native HTML with custom widgets. Markup and styling failures are usually **decision** failures: ignoring existing architecture, over-abstracting, or treating accessibility as polish.

**Boundaries:**

| Concern | Owner | This document |
|---------|-------|---------------|
| Component/state/async UI architecture | `frontend-architecture.md` (EKP-FE01–FE08) | Complementary — cite |
| TypeScript typing / runtime parse | `typescript-fundamentals.md` (EKP-TY) | Cite when relevant |
| Verification philosophy | `testing.md` (EKP-TS) | Cite — FE16 is a thin UI boundary |
| Performance mindset | `performance-mindset.md` (EKP-PM) | Cite — do not redefine |
| One-way FE architecture ADRs | EKP-FE08 / `adr-practices.md` | Apply for global styling stack changes |
| Framework tutorials (React/Vue/Angular) | Vendor docs | **Out of scope** |
| CSS/framework encyclopedias | Vendor docs | **Out of scope** |
| Flutter / NativeScript | `flutter/`, `nativescript/` | **Out of scope** |

**Out of scope:** Property reference tables, browser support matrices, WCAG success-criteria catalogs, design-tool workflows, component-library catalogs, test-runner tutorials.

## EKP layer positioning

| Layer | Role | This document |
|-------|------|---------------|
| **Principles (L0)** | Why | Implements EKP-P02–P06, P09 by reference |
| **Language (L1)** | TypeScript | Escalation → EKP-TY when needed |
| **Frontend (L2)** | Markup / styling / layout / a11y ops | **Primary** (with EKP-FE01–FE08) |

## Guidance

### EKP-FE09: Prefer semantic HTML and native capabilities

**Implements:** EKP-P06, EKP-P04

**Applies:** EKP-FE06

**Intent:** Prefer semantic HTML and native browser controls before custom widgets or generic containers.

**Rules:**

- Choose elements for meaning (headings, lists, landmarks, forms)—not for default appearance alone.
- Prefer native controls (`button`, `a`, form inputs) before custom clickable `div`/`span` widgets.
- Use links for navigation and buttons for actions; do not conflate them for styling convenience.
- Associate labels with controls; connect errors and help text to fields intentionally.
- Avoid unnecessary wrapper elements that exist only to satisfy a styling preference.
- Prefer progressive enhancement: capable baseline behavior first; optional enhancements when justified.
- Prefer native semantics over recreating the same behavior with ARIA on non-semantic elements.

**Good:** A submit control is a `button`; a field has a visible `label`; a nav landmark wraps primary navigation.

**Bad:** `div onClick` as primary action; icon-only control with no accessible name; ARIA roles used to paper over non-semantic markup.

**Review signals:** Interactive non-semantic elements; missing label association; markup shaped purely by stylesheet convenience.

---

### EKP-FE10: Styling architecture is an architectural decision

**Implements:** EKP-P03, EKP-P09

**Applies:** EKP-FE08, EKP-AD

**Intent:** Inspect and follow the repository’s established styling architecture before adding or inventing a mechanism.

**Rules:**

- Before styling, identify what the project already uses (native CSS, SCSS, Modules, utilities, framework, CSS-in-JS, tokens, component kit).
- Prefer continuing the existing paradigm over introducing a second one.
- Treat **global** styling-stack changes as architectural decisions—document with ADR when blast radius is high (cite EKP-FE08).
- Distinguish local style tweaks from architecture changes; do not “quietly” adopt a new stack in one feature.
- **Anti-bias:** Do not introduce Tailwind, Bootstrap, SCSS, CSS-in-JS, CSS Modules, or another styling stack merely because the assistant is familiar with it.

**Decision categories (not tutorials):**

| Mechanism | Prefer when | Avoid when |
|-----------|-------------|------------|
| Native CSS | Default when sufficient; modern CSS/custom properties meet needs | Introducing it as a parallel system against an established stack |
| SCSS | Project already uses it; existing mixins/partials provide real value | Adding to greenfield work from preference alone |
| CSS Modules | Strong isolation is required and tooling already exists | Fighting an established global/utility/framework architecture |
| Utility CSS | Project already standardizes on it | Introducing a utility framework casually |
| CSS frameworks | Project already adopted one | Adding a framework because it is familiar |
| CSS-in-JS | Architecture/tooling already calls for it | Introducing beside an established CSS system without strong reason |
| Component libraries | Project already has a kit | Introducing a second kit casually |

**Good:** New feature reuses the project’s existing CSS Modules + tokens.

**Bad:** PR adds Tailwind to a SCSS codebase “for speed”; second component library imported for one screen.

**Review signals:** New styling toolchain in an isolated PR; unanswered “why this mechanism?”; conflicting paradigms in adjacent features.

---

### EKP-FE11: Prefer the simplest styling mechanism that fits

**Implements:** EKP-P02

**Applies:** EKP-FE10

**Intent:** Prefer the simplest styling mechanism that satisfies the requirement and fits existing architecture (**EKP-P02**).

**Escalation order:**

1. Existing project convention (EKP-FE10)
2. Native / simple mechanism within that convention
3. Existing abstraction (tokens, shared classes, design-system primitives)
4. More complex mechanism only when justified by evidence or clear constraints

**Rules:**

- Do not abstract for a single selector or one-off value.
- Do not introduce a preprocessor, framework, or CSS-in-JS layer for trivial styling needs.
- Do not tokenize everything “for consistency” when values are not shared (**EKP-FE13**).
- Complexity requires a stated reason—preference is not enough.

**Good:** A one-line spacing tweak uses an existing token or local rule in the current system.

**Bad:** New design-token package and utility framework for a single badge style.

**Review signals:** Architecture complexity without evidence; “future flexibility” with no second consumer.

---

### EKP-FE12: Own cascade, specificity, and style boundaries

**Implements:** EKP-P05, EKP-P04

**Applies:** EKP-FE10

**Intent:** Styles need clear ownership; cascade and specificity must stay intentional and locally reasoned.

**Rules:**

- Prefer low specificity and predictable scoping tied to component/feature ownership.
- Keep global styles intentional and documented—not accidental leakage.
- Avoid selector wars, deep selector chains, and escalating specificity to “win.”
- Treat `!important` as exception-only with a documented reason.
- Do not fix local styling problems with increasingly global overrides.

**Debugging approach:**

1. Identify the owning component/feature.
2. Identify the conflicting rule’s source.
3. Understand cascade/specificity—not just “what worked.”
4. Fix ownership or architecture.
5. Avoid compensating overrides.

**Good:** Feature owns its styles; conflict resolved by correcting ownership.

**Bad:** Global override and `!important` to beat a component rule nobody owns.

**Review signals:** Rising specificity; unexplained `!important`; “just override it” without ownership analysis.

---

### EKP-FE13: Centralize repeated visual decisions as tokens

**Implements:** EKP-P09, EKP-P04

**Applies:** EKP-FE10, EKP-FE12, EKP-FE08 (global theme)

**Intent:** When visual decisions repeat or represent a design-system axis, centralize them (e.g. CSS custom properties)—do not invent parallel palettes.

**Rules:**

- Tokenize shared colors, spacing, typography, radii, and elevations when they recur.
- Prefer the project’s existing token/design-system strategy; do not create a second token system.
- Do not tokenize one-off values or impose token bureaucracy on tiny UIs (**EKP-P02**).
- Prefer token-driven theming (including dark mode) when theming exists; follow project strategy.
- Global theme architecture may warrant an ADR (cite EKP-FE08).

**Good:** Shared spacing/color axes come from existing custom properties or design tokens.

**Bad:** Hardcoded parallel palette for dark mode; tokenizing a unique one-pixel nudge.

**Review signals:** Duplicate color constants; new theme system beside an existing one; tokens with a single consumer and no axis.

---

### EKP-FE14: Choose layout and responsive strategy intentionally

**Implements:** EKP-P02, EKP-P05

**Applies:** EKP-FE10, EKP-FE13

**Intent:** Layout and responsive behavior are engineering choices—mobile-first and content-driven by default, without arbitrary breakpoint dogma.

**Rules:**

- Default to **mobile-first** unless the project documents otherwise.
- Prefer **content-driven** breakpoints over device-name or brand-specific rules.
- Prefer fluid layouts over arbitrary fixed grids when content width varies.
- Use **Flexbox** for primarily one-dimensional layout; **Grid** for primarily two-dimensional layout.
- Use **container queries** when component-local adaptation is clearer; use **media queries** for viewport/environment adaptation.
- Do **not** prescribe universal breakpoint pixel tables—follow project breakpoints/tokens when they exist.
- Avoid device-specific hacks and user-agent/device-name CSS.
- Prefer existing typography/spacing scales or tokens for responsive type and space.

**Good:** Layout adapts when content requires it; Flex/Grid choice matches dimensionality; project breakpoint tokens reused.

**Bad:** “iPhone-only” CSS; invented breakpoint scale fighting the design system; Grid used for a simple horizontal button row without reason.

**Review signals:** Unexplained magic breakpoint numbers; UA sniffing; conflicting layout systems in one feature.

---

### EKP-FE15: Operational accessibility for interactive surfaces

**Implements:** EKP-P06, EKP-P04

**Applies:** EKP-FE06, EKP-FE09

**Intent:** Extend architectural a11y (EKP-FE06) with operational principles for interactive surfaces—without a WCAG encyclopedia.

**Rules:**

- Interactive controls must be keyboard operable; focus must be visible.
- Prefer semantic HTML/native controls (EKP-FE09) before custom widgets.
- **Dialogs:** on open, move focus appropriately; while open, keep focus within the modal when modal semantics require it; on close, restore focus to a meaningful invoking element when possible.
- **Route/view changes:** ensure keyboard and assistive-tech users can understand where focus moved.
- Associate form errors with fields; use live regions for critical dynamic status when needed—do not over-ARIA.
- Do not communicate important state through color alone.
- Respect `prefers-reduced-motion` for non-essential motion.
- Treat contrast as an engineering requirement for critical text and controls.
- Custom widgets require an explicit accessibility contract.

**Good:** Modal moves focus to its title/first focusable control and restores focus on close; field errors are programmatically associated.

**Bad:** Focus lost after dialog close; status only via red text color; custom listbox with no keyboard model.

**Review signals:** Missing focus management; color-only state; custom widget without a11y notes.

---

### EKP-FE16: Verify UI by user-visible outcomes

**Implements:** EKP-P10, EKP-P03

**Applies:** EKP-TS, EKP-FE05, EKP-FE06

**Intent:** Verify UI through **user-visible outcomes**, not implementation details. Keep this boundary thin—cite EKP-TS for pyramid, flakes, doubles, and proportionality.

**Rules:**

- Prefer asserting visible loading/empty/error/success and interaction behavior users can observe.
- Include keyboard/a11y-critical behavior where risk warrants it.
- Reserve E2E for high-value or high-risk journeys; avoid E2E for trivial local behavior (**EKP-TS** / **EKP-P02**).
- Do not treat CSS class names or internal structure as the primary behavioral contract.
- Do not couple tests to private component implementation details.
- Do not invent test-runner tutorials here—route tooling questions to project standards and EKP-TS.

**Good:** Test that submit shows pending then success/error messaging the user sees.

**Bad:** E2E suite for class rename; assertions on internal CSS module hashes as behavior.

**Review signals:** Tests fail on harmless refactors; E2E count growing for unit-level logic.

## Performance and progressive enhancement (cite-only)

- Do not make CSS or layout performance claims without evidence—cite **EKP-PM** (measure first).
- Frontend render/fetch boundaries remain **EKP-FE07**—do not duplicate them here.
- Prefer a capable baseline; use feature detection / progressive enhancement when newer capabilities are optional.
- Do not introduce browser-specific hacks without evidence; do not maintain browser-support matrices in EKP.

## AI Decision Flow

For markup, styling, layout, and interactive a11y work. Run after `ai-assisted-development.md` steps 1–3. Component/state/async architecture routes to **EKP-FE01–FE08** first. TypeScript-only issues route to **EKP-TY**.

```
1. UI behavior and ownership?
   → Domain/state/composition: frontend-architecture.md (EKP-FE01–FE08).
   → Markup/styling/layout/a11y ops/testing boundary: continue.

2. Existing project conventions (EKP-FE10)
   → Identify current styling/markup architecture; prefer it.

3. Semantic / native capabilities (EKP-FE09)
   → Prefer native HTML/controls before custom widgets.

4. Reuse styling architecture and tokens (EKP-FE10, EKP-FE13)
   → Extend existing system; do not invent a parallel stack.

5. Simplest mechanism (EKP-FE11)
   → Escalate complexity only with justification (EKP-P02).

6. Style ownership (EKP-FE12)
   → Clear owner; fix cascade/specificity without global override wars.

7. Layout / responsive (EKP-FE14)
   → Mobile-first default; Flex vs Grid by dimensionality; content-driven breakpoints.

8. Accessibility (EKP-FE15 / EKP-FE06)
   → Keyboard, focus, dialogs, forms, motion, contrast before merge.

9. Verify user-visible behavior (EKP-FE16)
   → Cite EKP-TS; avoid implementation-detail tests.

10. Performance claims?
    → Cite EKP-PM; FE07 for render/fetch scope.

11. Global styling architecture change?
    → Require ADR when blast radius is high (EKP-FE08 / EKP-AD).
```

| ID | Rule |
|----|------|
| **FE-AI-04** | Do not introduce a styling stack from familiarity—follow the project. |
| **FE-AI-05** | Prefer semantic/native HTML before custom interactive widgets. |
| **FE-AI-06** | Do not duplicate EKP-TS / EKP-PM—cite and route. |
| **FE-AI-07** | Do not teach React/Vue/Angular or CSS framework APIs here. |

## When not to apply

- Non-UI scripts or build tooling alone (**EKP-P02**).
- Pure TypeScript libraries with no UI — EKP-TY only.
- Native mobile Flutter / NativeScript — those domains.
- Choosing a JS UI framework API — vendor docs / future framework profile; keep architecture constraints from EKP-FE01–FE08.

## Trade-offs

| Benefit | Cost |
|---------|------|
| Project-first styling reduces stack churn | Requires inspecting conventions before generating |
| Semantic HTML improves a11y by default | May need restyling vs “div-first” habits |
| Tokens improve consistency | Over-tokenization costs small UIs |
| Thin testing boundary avoids tool tutorials | Teams still need local test standards |

## Related

- [Frontend Architecture](frontend-architecture.md) — EKP-FE01–FE08
- [Engineering Principles](../engineering/engineering-principles.md) — EKP-P
- [TypeScript Fundamentals](../typescript/typescript-fundamentals.md) — EKP-TY
- [Testing](../testing/testing.md) — EKP-TS
- [Performance Mindset](../performance/performance-mindset.md) — EKP-PM
- [ADR Practices](../architecture/adr-practices.md) — EKP-AD
- [Frontend domain index](README.md)
