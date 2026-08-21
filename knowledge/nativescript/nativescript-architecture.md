---
title: NativeScript Architecture
domain: nativescript
tags: [nativescript, architecture, mobile, native-ui, typescript, navigation]
severity: recommended
applies_to: [mobile]
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
  - knowledge/architecture/adr-practices.md
  - knowledge/security/security-fundamentals.md
  - knowledge/performance/performance-mindset.md
  - knowledge/testing/testing.md
  - knowledge/nativescript/README.md
extends: []
concept_ids: [EKP-NS01, EKP-NS02, EKP-NS03, EKP-NS04, EKP-NS05, EKP-NS06, EKP-NS07, EKP-NS08, EKP-NS09]
adapter_priority: high
---

# NativeScript Architecture

## Summary

Architecture-layer guidance for **NativeScript** applications on TypeScript: native runtime and UI model, page boundaries, navigation, lifecycle, platform isolation, plugins/bridges, and UI-framework integration (with **NativeScript-Vue** as the primary concrete example). This document **applies** **EKP-P04**, **EKP-P05**, **EKP-P06**, and **EKP-P09**, and depends on [`typescript-fundamentals.md`](../typescript/typescript-fundamentals.md) (EKP-TY)—it does not redefine TypeScript or L0 principles.

Apply when designing or reviewing NativeScript app structure, navigation, platform code, or plugin boundaries. Web DOM / SSR architecture belongs in [`frontend-architecture.md`](../frontend/frontend-architecture.md) (EKP-FE). Flutter / Dart belongs in `flutter/` when published. Relax per **EKP-P02** for throwaway spikes with documented expiry.

## Context

NativeScript defects are often mislabeled as “Vue bugs” or “TypeScript issues” when the real failure is architectural: treating native UI like a browser DOM, embedding business rules in pages, leaking navigation into domain services, or coupling application code to uncontrolled native plugins. Assistants amplify this by generating web-style component trees and ignoring Android/iOS differences.

**Boundaries:**

| Concern | Owner | This document |
|---------|-------|---------------|
| TypeScript typing, modules, runtime parse | `typescript-fundamentals.md` (EKP-TY) | Prerequisite — cite |
| System layers / contracts | `layering-and-boundaries.md` (EKP-LB) | Apply — do not redefine |
| Module coupling | `coupling-and-cohesion.md` (EKP-MC) | Apply at feature/package level |
| Authn/authz / secrets mindset | `security-fundamentals.md` (EKP-SF) | Apply at trust boundaries |
| Performance mindset | `performance-mindset.md` (EKP-PM) | Cite; measure before optimize |
| Verification philosophy | `testing.md` (EKP-TS) | Cite — tests define done |
| Web DOM / SSR / web a11y | `frontend-architecture.md` (EKP-FE) | **Out of scope** — no dependency |
| Flutter / Dart | `flutter/` | **Out of scope** — separate L2 vertical |
| Generic Vue / Angular / React tutorials | Vendor docs | Out of scope — not EKP domains |

**Out of scope:** Full NativeScript API reference, plugin marketplaces, store listing/ASO, generic mobile product strategy, Vue/Angular/React language tutorials.

## EKP layer positioning

| Layer | Role | This document |
|-------|------|---------------|
| **Principles (L0)** | Why | Implements EKP-P04, P05, P06, P09 by reference |
| **Language (L1)** | TypeScript | Depends on EKP-TY |
| **Framework (L2)** | NativeScript application structure | **Primary** |

## Guidance

### EKP-NS01: NativeScript is a native runtime, not a browser DOM

**Implements:** EKP-P04, EKP-P05

**Applies:** EKP-LB (delivery vs domain), EKP-TY (types do not imply runtime DOM)

**Intent:** NativeScript renders **native UI** and runs on mobile runtimes. It is not a DOM application, not a WebView-first architecture by default, and not interchangeable with web frontend guidance.

**Rules:**

- Design UI against native primitives and NativeScript layout/navigation models—not against HTML/CSS/DOM assumptions.
- Do not import web-frontend architecture (semantic HTML, SSR/hydration, browser-only APIs) as the default mental model.
- Treat “it works in the browser” as irrelevant evidence for NativeScript correctness.
- Keep Flutter/Dart patterns out of NativeScript reviews—different L2 vertical.

**Good:** Page composed of NativeScript UI elements with platform-aware layout.

**Bad:** Assuming CSS-box or DOM event semantics; copying web SPA folder myths without native navigation.

**Review signals:** DOM/`document` APIs in app code; “just like React web” justifications for native structure.

---

### EKP-NS02: Pages and components own presentation, not business policy

**Implements:** EKP-P05, EKP-P06

**Applies:** EKP-LB01–LB04, EKP-TY04

**Intent:** NativeScript pages/views and UI components capture intent and render state—they must not embed durable business rules.

**Rules:**

- Keep pages thin: bind view models, emit intents, navigate; put policy in testable application/domain modules.
- Do not call remote APIs or encode pricing/authorization rules inside leaf UI components when a feature boundary exists.
- Shared UI widgets must not import feature-specific domain types.
- When framework or NativeScript types leak into domain modules, document the exception and exit plan.

**Good:** `OrderSummary` receives a view model; totals calculated in a tested service.

**Bad:** Tax and discount rules inside a button handler on a NativeScript page.

**Review signals:** HTTP clients constructed in page code; domain exceptions thrown from UI templates.

---

### EKP-NS03: Own navigation and back-stack explicitly

**Implements:** EKP-P04, EKP-P05

**Applies:** EKP-MC (cohesion), EKP-LB (boundaries)

**Intent:** Navigation structure (frames/pages, forward/back, deep links) is an architectural surface—not an accidental side effect of UI widgets or domain services.

**Rules:**

- Centralize navigation decisions in a clear owner (router/service/coordinator)—avoid scatter across unrelated components.
- Model back-stack expectations explicitly for critical flows (checkout, auth, modal-like pages).
- Do not bury navigation side effects inside domain services that should stay UI-agnostic.
- Account for platform differences in back behavior; do not pretend Android and iOS are identical.

**Good:** Feature coordinator decides next page; pages request navigation via a narrow API.

**Bad:** Domain “place order” service directly pushes pages onto a frame.

**Review signals:** Navigation imports deep in domain packages; inconsistent back handling across platforms.

---

### EKP-NS04: Respect application and page lifecycle

**Implements:** EKP-P06, EKP-P07

**Applies:** EKP-EH (failure visibility), EKP-TY (resource lifetimes)

**Intent:** Application lifecycle and page/view lifecycle differ from browser page lifetime. Resources must be acquired and released against the correct lifecycle.

**Rules:**

- Distinguish app-level setup/teardown from page-level appear/disappear (or equivalent) hooks.
- Unsubscribe, cancel, and release native resources when pages leave the stack or the app backgrounds—do not assume SPA “component unmount” myths alone.
- Do not start long-lived listeners in page code without an owned cleanup path.
- Treat backgrounding and resume as first-class events for sensitive state (sessions, sensors, location).

**Good:** Page subscribes on appear and unsubscribes on disappear; app resumes re-validates session.

**Bad:** Global listeners registered per navigation with no removal; timers surviving destroyed pages.

**Review signals:** Leaked subscriptions after navigate-back; crashes only after deep navigation.

---

### EKP-NS05: Classify state and make async failure visible

**Implements:** EKP-P04, EKP-P05, EKP-P07

**Applies:** EKP-TY05 (discriminated states), EKP-EH, EKP-LB

**Intent:** Local UI state, application state, and remote/server state have different owners. Async work needs explicit pending/failure semantics and cleanup.

**Rules:**

- Place each piece of mutable state with one owner; do not mirror server data into editable copies without a sync strategy.
- Model loading/empty/error/ready explicitly for user-visible async flows (cite EKP-TY05).
- Cancel or ignore stale async results when the page is gone or the request is superseded.
- Surface native/permission failures to the user path—do not only `console.log`.

**Good:** Feature store owns order draft; query layer owns server list; page owns ephemeral scroll position.

**Bad:** Same `selectedId` duplicated across page, global store, and plugin callback with manual sync.

**Review signals:** Race updates after fast navigate-away; silent permission denials.

---

### EKP-NS06: Isolate Android/iOS and permission boundaries

**Implements:** EKP-P04, EKP-P06

**Applies:** EKP-LB, EKP-SF (trust boundaries), EKP-AD (one-way platform choices)

**Intent:** Platforms are related, not identical. Platform APIs, permissions, and native project settings must stay behind explicit boundaries.

**Rules:**

- Encapsulate platform-specific APIs behind narrow modules; keep feature code mostly platform-agnostic.
- Request and handle permissions as product flows with denial paths—not as afterthoughts.
- Keep native project integration (Gradle/Xcode settings, entitlements) reviewed and owned—do not scatter silent edits.
- Prefer explicit platform branches or strategy objects over `#ifdef` sprawl across the domain.

**Good:** `NotificationGateway` with Android/iOS adapters; feature code depends on the gateway.

**Bad:** Feature services importing platform-only APIs directly in many files.

**Review signals:** Permission prompts with no denial UX; unchecked platform-only crashes.

---

### EKP-NS07: Contain plugins, bridges, and native surface area

**Implements:** EKP-P06, EKP-P09

**Applies:** EKP-MC, EKP-SF, EKP-P03 (reversibility)

**Intent:** Plugins and native bridges are high-coupling dependencies. Minimize and isolate native surface area; fail visibly when capabilities are missing.

**Rules:**

- Add plugins for a justified capability; record owners and upgrade constraints—do not accumulate “just in case” native deps.
- Isolate plugin-specific types and calls behind adapters; keep domain free of plugin SDKs where practical.
- Define behavior when a native capability is unavailable (missing plugin, unsupported OS, denied permission).
- Prefer fewer, well-understood native touchpoints over many shallow plugins.

**Good:** Single `BarcodeScannerPort` adapter wrapping one plugin; feature tests use a fake.

**Bad:** Plugin imports sprinkled through pages; app fails opaquely when the plugin is absent.

**Review signals:** Direct plugin calls in UI templates; undeclared native version pins.

---

### EKP-NS08: UI frameworks (e.g. NativeScript-Vue) are integration choices, not new domains

**Implements:** EKP-P05, EKP-P09

**Applies:** EKP-LB, EKP-MC, EKP-AD

**Intent:** Choosing NativeScript-Vue (or another UI framework on NativeScript) does **not** change the NativeScript runtime model and does **not** create a separate EKP technology domain.

**Rules:**

- Keep domain and application logic independent of Vue (or other UI framework) APIs—framework code stays in the delivery/UI layer.
- Component boundaries still follow EKP-NS02: presentation in components; policy outside.
- State ownership remains explicit (EKP-NS05)—do not let framework store patterns smuggle domain rules into UI-only modules.
- Do not treat NativeScript-Vue as justification to pull in web `frontend/` knowledge or to invent `nativescript-vue` / Vue namespaces.
- Generic Vue language/framework tutorials belong in vendor docs—not in this guide and not as EKP products.

**Good:** Vue SFCs bind view models; use-cases live in plain TypeScript modules tested without mounting UI.

**Bad:** Business workflows implemented only inside Vuex/Pinia actions tightly coupled to NativeScript page navigation.

**Review signals:** Domain packages importing Vue; “we need a Vue profile” requests for NativeScript apps.

**Explicit:** NativeScript-Vue is an integration choice **inside** the NativeScript vertical, not a separate EKP technology domain.

---

### EKP-NS09: Make build, device, and performance feedback loops engineering-owned

**Implements:** EKP-P04, EKP-P08

**Applies:** EKP-PM (measure first), EKP-TS (verification), EKP-AD

**Intent:** NativeScript delivery depends on reproducible native builds and honest performance evidence. Optimize with measurement, not folklore.

**Rules:**

- Document how to produce Android/iOS development builds and which environment knobs matter; prefer reproducible configs over machine-local magic.
- Debug on emulator **and** representative devices when platform-specific failures appear; do not close issues on one platform only.
- Treat UI jank, bridge chatter, and main-thread overload as performance defects—measure before large rewrites (**EKP-PM**).
- Avoid unnecessary native round-trips and work on the UI thread; batch and defer non-critical work.
- Add NativeScript-specific tests only where they catch risks generic unit tests miss (navigation, plugin adapters, platform branches); otherwise apply **EKP-TS**.

**Good:** CI builds both platforms for release branches; perf claim backed by a trace or interaction metric.

**Bad:** “Feels faster” refactors; fixing Android-only crashes without iOS verification when both ship.

**Review signals:** Undocumented signing/env setup; performance PRs without measurement.

---

## AI Decision Flow

For NativeScript architecture changes. Run after `ai-assisted-development.md` steps 1–3. TypeScript-only issues route to **EKP-TY** first. Web DOM/SSR issues are **not** this guide—use EKP-FE only for true web clients.

```
1. Language vs NativeScript structure?
   → Types/modules/unknown/strict: typescript-fundamentals.md (EKP-TY).
   → Native UI/navigation/plugins/platforms: continue.

2. Runtime model (EKP-NS01)
   → DOM/web assumptions: reject; redesign for native UI.

3. UI vs domain (EKP-NS02)
   → Business rules in pages/components: extract to application/domain modules.

4. Navigation (EKP-NS03)
   → Navigation in domain or scattered widgets: introduce a clear navigation owner.

5. Lifecycle (EKP-NS04)
   → Leaked subscriptions/native resources: bind cleanup to app/page lifecycle.

6. State / async (EKP-NS05)
   → Duplicate sources or silent async failure: single owner + explicit states.

7. Platform (EKP-NS06)
   → Platform APIs in feature core: isolate behind adapters; handle permissions.

8. Plugins (EKP-NS07)
   → Uncontrolled plugin coupling: adapter + failure mode + dependency hygiene.

9. UI framework (EKP-NS08)
   → Vue (etc.) leaking into domain: push framework to UI layer; no new EKP domain.

10. Build / device / perf (EKP-NS09)
   → Unreproducible builds or unmeasured perf claims: fix feedback loop first.
```

| ID | Rule |
|----|------|
| **NS-AI-01** | Never treat NativeScript as a browser DOM app. |
| **NS-AI-02** | Keep business policy out of NativeScript pages/components. |
| **NS-AI-03** | NativeScript-Vue is an integration choice—not a separate EKP domain or reason to import EKP-FE. |
| **NS-AI-04** | Do not duplicate EKP-TY / EKP-LB / EKP-TS / EKP-PM—cite and route. |

## When not to apply

- Pure TypeScript libraries with no NativeScript runtime — **EKP-TY** only.
- Web browser SPAs — **EKP-FE**.
- Flutter / Dart clients — `flutter/` when published.
- Throwaway prototypes with no shared consumers (**EKP-P02**) — document expiry.

## Trade-offs

| Benefit | Cost |
|---------|------|
| Native runtime clarity prevents web-pattern misuse | Requires unlearning DOM defaults |
| Isolated plugins/platforms reduce upgrade blast radius | More adapter code |
| Framework-agnostic domain logic stays testable | Discipline against “put it in the component” shortcuts |

## Related

- [TypeScript Fundamentals](../typescript/typescript-fundamentals.md) — EKP-TY
- [Engineering Principles](../engineering/engineering-principles.md) — EKP-P
- [Layering and Boundaries](../architecture/layering-and-boundaries.md) — EKP-LB
- [Coupling and Cohesion](../architecture/coupling-and-cohesion.md) — EKP-MC
- [Security Fundamentals](../security/security-fundamentals.md) — EKP-SF
- [Performance Mindset](../performance/performance-mindset.md) — EKP-PM
- [Testing](../testing/testing.md) — EKP-TS
- [ADR Practices](../architecture/adr-practices.md) — EKP-AD
- [NativeScript domain index](README.md)
