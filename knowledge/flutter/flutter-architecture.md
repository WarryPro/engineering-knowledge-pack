---
title: Flutter Architecture
domain: flutter
tags: [flutter, architecture, mobile, dart, widgets, navigation, state]
severity: recommended
applies_to: [mobile]
type: guide
role: architecture
depends_on:
  - knowledge/engineering/engineering-principles.md
implements:
  - EKP-P04
  - EKP-P05
  - EKP-P06
  - EKP-P09
related:
  - knowledge/engineering/engineering-principles.md
  - knowledge/architecture/layering-and-boundaries.md
  - knowledge/architecture/coupling-and-cohesion.md
  - knowledge/architecture/adr-practices.md
  - knowledge/architecture/integration-patterns.md
  - knowledge/engineering/error-handling.md
  - knowledge/security/security-fundamentals.md
  - knowledge/performance/performance-mindset.md
  - knowledge/testing/testing.md
  - knowledge/frontend/frontend-architecture.md
  - knowledge/nativescript/nativescript-architecture.md
  - knowledge/flutter/README.md
extends: []
concept_ids: [EKP-FL01, EKP-FL02, EKP-FL03, EKP-FL04, EKP-FL05, EKP-FL06, EKP-FL07, EKP-FL08, EKP-FL09]
adapter_priority: high
---

# Flutter Architecture

## Summary

Architecture-layer guidance for **Flutter** applications: declarative widget runtime, presentation/domain boundaries, state ownership, navigation, async/data boundaries, platform integration, project structure, and dependency evaluation. This document **applies** **EKP-P04**, **EKP-P05**, **EKP-P06**, and **EKP-P09**, and routes to L0 architecture, error-handling, security, testing, and performance guides—it does not redefine them, teach Dart syntax, or reproduce Flutter API documentation.

Apply when designing or reviewing Flutter app structure, state, navigation, platform code, or package choices. Web DOM / SSR architecture belongs in [`frontend-architecture.md`](../frontend/frontend-architecture.md) (EKP-FE). NativeScript native UI belongs in [`nativescript-architecture.md`](../nativescript/nativescript-architecture.md) (EKP-NS). Relax per **EKP-P02** for throwaway spikes with documented expiry.

## Context

Flutter defects are often mislabeled as “widget bugs” or “Dart issues” when the real failure is architectural: treating Flutter like a web SPA or NativeScript app, embedding business rules in widgets, duplicating server state without ownership, or coupling features to unvetted packages. Assistants amplify this by prescribing a single state-management library, scattering navigation across widgets, and generating platform-channel code without boundaries.

**Boundaries:**

| Concern | Owner | This document |
|---------|-------|---------------|
| System layers / contracts | `layering-and-boundaries.md` (EKP-LB) | Apply — do not redefine |
| Module coupling | `coupling-and-cohesion.md` (EKP-MC) | Apply at feature/package level |
| Architecture decisions | `adr-practices.md` (EKP-AD) | Apply for one-way platform choices |
| Integration contracts | `integration-patterns.md` (EKP-IN) | Cite for API/repository boundaries |
| Failure semantics | `error-handling.md` (EKP-EH) | Apply for async/error visibility |
| Authn/authz / secrets mindset | `security-fundamentals.md` (EKP-SF) | Apply at trust boundaries |
| Performance mindset | `performance-mindset.md` (EKP-PM) | Cite; measure before optimize |
| Verification philosophy | `testing.md` (EKP-TS) | Cite — tests define done |
| Web DOM / SSR / web a11y | `frontend-architecture.md` (EKP-FE) | **Out of scope** — conceptual parallel only |
| NativeScript native UI | `nativescript-architecture.md` (EKP-NS) | **Out of scope** — peer L2 vertical |
| TypeScript language | `typescript/` (EKP-TY) | **Out of scope** — Dart ≠ TypeScript |
| Dart language tutorial | Vendor docs | Out of scope — not an EKP L1 domain |
| Widget / API catalog | Vendor docs | Out of scope |

**Out of scope:** Flutter widget encyclopedia, Dart syntax reference, state-management package tutorials, Android/iOS native API documentation, store listing/ASO, generic mobile product strategy, golden-test how-to beyond architectural boundaries.

## EKP layer positioning

| Layer | Role | This document |
|-------|------|---------------|
| **Principles (L0)** | Why | Implements EKP-P04, P05, P06, P09 by reference |
| **Language (L1)** | — | No separate Dart L1; Dart architectural boundaries live here |
| **Framework (L2)** | Flutter application structure | **Primary** |

## Guidance

### EKP-FL01: Flutter is a declarative widget runtime, not a web DOM or native UI clone

**Implements:** EKP-P04, EKP-P05

**Applies:** EKP-LB (delivery vs domain), EKP-PM (rebuild boundaries)

**Intent:** Flutter builds UI through a **declarative widget tree** reconciled by the framework. It is not a browser DOM application, not interchangeable with web frontend guidance, and not the same runtime model as NativeScript native UI.

**Rules:**

- Design against widgets, elements, and render objects—not HTML/CSS/DOM assumptions or NativeScript page models.
- Do not import web-frontend architecture (semantic HTML, SSR/hydration, browser-only APIs) as the default mental model for Flutter clients.
- Treat “it works in React/Vue web” as insufficient evidence for Flutter structure correctness.
- Understand that rebuild scope is an architectural surface—cite **EKP-PM** before large widget-tree rewrites.

**Good:** Screen composed of focused widgets; rebuild boundaries considered at feature level.

**Bad:** DOM/event-delegation assumptions; copying web SPA folder myths without Flutter navigation and state ownership.

**Review signals:** `document`/`window` metaphors in reviews; “just like our web app” justifications for Flutter structure.

---

### EKP-FL02: Widgets and screens own presentation, not business policy

**Implements:** EKP-P05, EKP-P06

**Applies:** EKP-LB01–LB04, EKP-FE01 (conceptual parallel)

**Intent:** Widgets, screens, and presentation-layer types capture intent and render state—they must not embed durable business rules.

**Rules:**

- Keep widgets thin: receive view models/state, emit intents/events, navigate; put policy in testable application/domain modules.
- Do not call remote APIs or encode pricing/authorization rules inside leaf widgets when a feature boundary exists.
- Shared UI widgets must not import feature-specific domain types.
- When Flutter framework types leak into domain modules, document the exception and exit plan.

**Good:** `OrderSummary` receives immutable view state; totals calculated in a tested use-case or domain service.

**Bad:** Tax and discount rules inside a `onPressed` handler in a stateless widget.

**Review signals:** HTTP clients constructed in widget `build` methods; domain exceptions thrown from presentation code without a boundary.

---

### EKP-FL03: Classify state and assign a single owner

**Implements:** EKP-P04, EKP-P05, EKP-P07

**Applies:** EKP-LB, EKP-EH, EKP-FE02 (conceptual parallel), EKP-NS05 (conceptual parallel)

**Intent:** Local UI state, ephemeral interaction state, shared application state, and server/cache state have different lifetimes and owners. Each mutable source must have exactly one authoritative owner.

**Rules:**

- Classify state before choosing a mechanism: local widget state, ephemeral UI (tabs, scroll), shared in-app state, remote/server-backed state.
- Do not mirror server data into editable local copies without an explicit sync/invalidation strategy.
- Avoid duplicating the same identifier across widget fields, global stores, and repository caches.
- Document who may write each class of state and who observes it.

**Good:** Feature scope owns order draft; repository owns server list; widget owns ephemeral animation controller.

**Bad:** Same `selectedId` duplicated across widget state, inherited widget, and provider with manual sync.

**Review signals:** “We update it in three places to stay consistent”; conflicting writes after navigation.

---

### EKP-FL04: Choose state-management approach by architectural need, not popularity

**Implements:** EKP-P04, EKP-P05, EKP-P09

**Applies:** EKP-AD (one-way decisions), EKP-MC, EKP-NS08 (conceptual parallel)

**Intent:** State-management libraries and patterns (InheritedWidget, ChangeNotifier, Riverpod, Bloc, etc.) are **integration choices**. The decision is driven by ownership, testability, and feature scale—not by defaulting to the most popular package.

**Rules:**

- Select a pattern when classification (EKP-FL03) and boundaries (EKP-FL02) are clear—do not adopt a global store “just in case.”
- Prefer the simplest mechanism that preserves single ownership and testability; escalate complexity with documented trade-offs (**EKP-AD**).
- Do not let a state-management package API dictate domain structure—domain modules stay framework-agnostic where practical.
- Record one-way decisions when adopting a team-wide state approach; revisit when feature count or test pain exceeds the documented threshold.
- Generic package tutorials belong in vendor docs—not in EKP.

**Good:** Small feature uses local state + repository; larger feature adopts Bloc/Riverpod after an ADR cites test and ownership needs.

**Bad:** Mandating Provider/Riverpod/Bloc org-wide with no classification or boundary analysis.

**Review signals:** Domain types importing package-specific base classes everywhere; “we picked X because the tutorial did.”

---

### EKP-FL05: Own navigation and route architecture explicitly

**Implements:** EKP-P04, EKP-P05

**Applies:** EKP-MC, EKP-LB, EKP-NS03 (conceptual parallel)

**Intent:** Routes, stacks, deep links, and auth-gated flows are architectural surfaces—not accidental side effects of widget callbacks or domain services.

**Rules:**

- Centralize navigation decisions in a clear owner (router/coordinator/service)—avoid scatter across unrelated widgets.
- Model back-stack, nested navigation, and deep-link entry points explicitly for critical flows (checkout, auth, settings).
- Do not bury navigation side effects inside domain services that should stay UI-agnostic.
- Account for platform differences (Android back, iOS gesture, web URL) where the product ships on multiple targets.
- Treat authentication redirects and session expiry as navigation concerns with explicit routes—not ad hoc `Navigator.push` chains.

**Good:** Feature coordinator exposes `goToOrderDetail(id)`; router table documents deep-link targets.

**Bad:** Domain “place order” use-case directly pushes routes; auth checks duplicated in every screen widget.

**Review signals:** Navigation imports deep in domain packages; broken deep links after refactor; inconsistent back behavior across platforms.

---

### EKP-FL06: Define async and data boundaries with visible failure modes

**Implements:** EKP-P04, EKP-P05, EKP-P07

**Applies:** EKP-EH, EKP-IN, EKP-FE05 (conceptual parallel), EKP-TS

**Intent:** Network, persistence, and cache access belong behind repositories or gateways with explicit loading, empty, error, and success semantics. Async work must respect lifecycle and cancellation.

**Rules:**

- Place API clients, DTO mapping, and persistence behind narrow repository/gateway interfaces—widgets and domain depend on contracts, not HTTP details.
- Model loading/empty/error/ready explicitly for user-visible async flows (**EKP-EH**).
- Cancel or ignore stale async results when the route is popped or a newer request supersedes the old one.
- Keep serialization and DTO types at the data boundary—do not leak wire formats into domain models without justification.
- Apply **EKP-TS** for test boundaries: unit-test repositories and use-cases with fakes; widget-test only where presentation wiring adds risk.

**Good:** Repository returns discriminated async state; use-case tested with fake gateway; widget displays explicit error UI.

**Bad:** `http.get` in widget `initState`; silent catch blocks; domain model fields named after JSON keys from one endpoint.

**Review signals:** Race updates after fast navigate-away; untested retry logic; exceptions swallowed before UI.

---

### EKP-FL07: Isolate platform integration behind explicit boundaries

**Implements:** EKP-P04, EKP-P06

**Applies:** EKP-LB, EKP-SF, EKP-AD, EKP-NS06, EKP-NS07 (conceptual parallels)

**Intent:** Platform channels, permissions, and native code are high-coupling surfaces. Feature code stays mostly platform-agnostic; native APIs stay behind adapters with defined failure modes.

**Rules:**

- Encapsulate platform-specific capabilities (camera, biometrics, file picker, background tasks) behind narrow ports/adapters.
- Request and handle permissions as product flows with denial and settings paths—not as afterthoughts.
- Keep `android/` and `ios/` (and other embedder folders) changes reviewed and owned—do not scatter silent native edits.
- Define behavior when a capability is unavailable (unsupported OS, denied permission, missing plugin).
- Do not document Java/Kotlin/Swift/Objective-C APIs here—only **where** native code may live and **how** it couples to Dart.

**Good:** `BiometricAuthPort` with platform implementations; feature code depends on the port; denial UX tested.

**Bad:** MethodChannel calls sprinkled through widgets; crashes on iOS-only code paths without guard.

**Review signals:** Platform imports in domain packages; permission prompts with no denial UX; undeclared minimum OS versions.

---

### EKP-FL08: Choose project structure by trade-offs, not dogma

**Implements:** EKP-P04, EKP-P05, EKP-P09

**Applies:** EKP-MC, EKP-LB, EKP-AD

**Intent:** Feature-first, layer-first, and hybrid layouts are valid when chosen for stated scalability, team, and testability reasons—not because a template said so.

**Rules:**

- Prefer **feature cohesion**: code that changes together lives together; shared kernels extracted only when a second consumer exists (**EKP-MC**).
- Keep `lib/` entry and composition root explicit—wiring dependencies at the app boundary, not inside leaf widgets.
- Separate shared design system / core utilities from feature modules with clear dependency direction (features may depend on core; not vice versa).
- Treat generated code (serialization, routing, localization) as build artifacts with owned regeneration steps—do not hand-edit without process.
- Document structure choice in an ADR when the team size or module count crosses a agreed threshold.

**Good:** `features/orders/` owns presentation + application + data for orders; `core/` holds shared theme and HTTP client factory.

**Bad:** Empty `data/domain/presentation` folders in every feature “because clean architecture”; god-`lib/` with no feature boundaries.

**Review signals:** Circular imports between features; shared folder becoming a dumping ground; untestable composition root.

---

### EKP-FL09: Evaluate dependencies before adding packages

**Implements:** EKP-P04, EKP-P06, EKP-P09

**Applies:** EKP-MC, EKP-AD, EKP-P03 (reversibility)

**Intent:** Pub.dev packages are coupling decisions. Add them for a justified capability with known ownership, compatibility, and exit cost—do not accumulate convenience dependencies.

**Rules:**

- Justify each new dependency: capability owned, alternatives considered, maintenance signal reviewed (activity, breaking changes, platform support).
- Prefer fewer, well-understood dependencies over many overlapping utilities (HTTP, state, routing, DI each need one clear owner).
- Isolate package-specific types behind adapters when the package might be replaced (**EKP-P03**).
- Avoid packages that force domain or widget layers to inherit framework-specific base classes without an ADR.
- Do not maintain an EKP package catalog—evaluate categories (routing, DI, serialization) not exhaustive lists.

**Good:** ADR records choice of routing package with rejection rationale; HTTP client wrapped behind internal interface.

**Bad:** Adding five utility packages for one feature; domain entities extending code-generated base classes from a discontinued library.

**Review signals:** Duplicate packages for the same concern; upgrade blocked by transitive deps; no owner for dependency updates.

---

## AI Decision Flow

For Flutter architecture changes. Run after `ai-assisted-development.md` steps 1–3. Web DOM/SSR issues are **not** this guide—use EKP-FE only for true web clients. NativeScript issues route to EKP-NS.

```
1. Runtime model (EKP-FL01)
   → DOM/web or NativeScript assumptions: reject; redesign for Flutter widget tree.

2. UI vs domain (EKP-FL02)
   → Business rules in widgets: extract to application/domain modules.

3. State ownership (EKP-FL03)
   → Duplicate or unowned state: classify and assign single owner.

4. State mechanism (EKP-FL04)
   → Package chosen without classification: decide need first; ADR if team-wide.

5. Navigation (EKP-FL05)
   → Navigation in domain or scattered widgets: introduce clear navigation owner.

6. Async / data (EKP-FL06)
   → HTTP in widgets or silent failures: repository boundary + explicit states.

7. Platform (EKP-FL07)
   → Platform APIs in feature core: isolate behind adapters; handle permissions.

8. Structure (EKP-FL08)
   → Folder dogma without trade-offs: align structure to feature cohesion and ADR.

9. Dependencies (EKP-FL09)
   → New package without justification: evaluate capability, coupling, exit cost.
```

| ID | Rule |
|----|------|
| **FL-AI-01** | Never treat Flutter as a browser DOM app or NativeScript clone. |
| **FL-AI-02** | Keep business policy out of widgets and screens. |
| **FL-AI-03** | Do not prescribe a single state-management package—classify state first. |
| **FL-AI-04** | Do not duplicate EKP-LB / EKP-EH / EKP-TS / EKP-PM—cite and route. |

## When not to apply

- Pure Dart CLI/server libraries with no Flutter UI — outside this L2 vertical.
- Web browser SPAs without Flutter — **EKP-FE**.
- NativeScript clients — **EKP-NS**.
- Throwaway prototypes with no shared consumers (**EKP-P02**) — document expiry.

## Trade-offs

| Benefit | Cost |
|---------|------|
| Widget/runtime clarity prevents web-pattern misuse | Requires unlearning DOM and imperative UI defaults |
| Explicit state and navigation ownership improves testability | More upfront design before coding features |
| Isolated platform/package boundaries reduce upgrade blast radius | More adapter and ADR overhead |

## Related

- [Engineering Principles](../engineering/engineering-principles.md) — EKP-P
- [Layering and Boundaries](../architecture/layering-and-boundaries.md) — EKP-LB
- [Coupling and Cohesion](../architecture/coupling-and-cohesion.md) — EKP-MC
- [ADR Practices](../architecture/adr-practices.md) — EKP-AD
- [Integration Patterns](../architecture/integration-patterns.md) — EKP-IN
- [Error Handling](../engineering/error-handling.md) — EKP-EH
- [Security Fundamentals](../security/security-fundamentals.md) — EKP-SF
- [Performance Mindset](../performance/performance-mindset.md) — EKP-PM
- [Testing](../testing/testing.md) — EKP-TS
- [Frontend Architecture](../frontend/frontend-architecture.md) — EKP-FE (web; conceptual parallel only)
- [NativeScript Architecture](../nativescript/nativescript-architecture.md) — EKP-NS (peer mobile L2)
- [Flutter domain index](README.md)
