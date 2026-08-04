---
title: TypeScript Fundamentals
domain: typescript
tags: [typescript, language, typing, strict, modules, runtime]
severity: recommended
applies_to: [frontend, backend, api]
type: guide
role: practice
depends_on:
  - knowledge/engineering/engineering-principles.md
implements:
  - EKP-P04
  - EKP-P05
  - EKP-P06
  - EKP-P07
  - EKP-P09
related:
  - knowledge/engineering/engineering-principles.md
  - knowledge/engineering/solid.md
  - knowledge/engineering/error-handling.md
  - knowledge/engineering/clean-code.md
  - knowledge/testing/testing.md
  - knowledge/architecture/layering-and-boundaries.md
  - knowledge/frontend/frontend-architecture.md
  - knowledge/typescript/README.md
extends: []
concept_ids: [EKP-TY01, EKP-TY02, EKP-TY03, EKP-TY04, EKP-TY05, EKP-TY06, EKP-TY07, EKP-TY08]
adapter_priority: high
---

# TypeScript Fundamentals

## Summary

Language-layer guidance for **TypeScript** as used in application code: strict typing, structural types, safe narrowing, module boundaries, and the gap between compile-time guarantees and runtime behavior. This document **applies** **EKP-P04** (Explicit), **EKP-P05** (Local reasoning), **EKP-P06** (Own the boundary), **EKP-P07** (Fail fast), and **EKP-P09** (Compose)—it does not redefine those principles.

Apply when writing or reviewing TypeScript modules, shared types, or compiler configuration. UI architecture belongs in [`frontend-architecture.md`](../frontend/frontend-architecture.md) (EKP-FE). Relax per **EKP-P02** for throwaway scripts with no shared consumers.

## Context

TypeScript defects often look like “framework bugs” but originate in language misuse: `any` erosion, unchecked external data, mutable shared types, and assumptions that types survive at runtime. Assistants amplify this by emitting `as` casts and loose configs unless constrained.

**Boundaries:**

| Concern | Owner | This document |
|---------|-------|---------------|
| Engineering principles | `engineering-principles.md` (EKP-P) | Cite only |
| Class/module design | `solid.md` (EKP-SL) | Cite — do not restate SOLID |
| Failure contracts | `error-handling.md` (EKP-EH) | Cite; map TS errors to EH |
| Naming / readability | `clean-code.md` (EKP-CC) | Cite |
| Verification philosophy | `testing.md` (EKP-TS) | Cite — **EKP-TS** = Testing namespace |
| System layers / HTTP | `layering-and-boundaries.md` (EKP-LB) | Cite |
| Component/state/UI architecture | `frontend-architecture.md` (EKP-FE) | Out of scope |
| PHP / Symfony stacks | `php/`, `symfony/` | Out of scope — no cross-stack deps |

**Out of scope:** Full TypeScript handbook, every `tsconfig` flag, framework component APIs, build/deploy pipelines (`devops/`).

## EKP layer positioning

| Layer | Role | This document |
|-------|------|---------------|
| **Principles (L0)** | Why | Implements EKP-P04–P07, P09 by reference |
| **Language (L1)** | How TypeScript expresses principles | **Primary** |
| **Frontend (L2)** | UI architecture | Escalation → EKP-FE |

## Guidance

### EKP-TY01: Treat strict mode as the default contract

**Implements:** EKP-P04, EKP-P05

**Applies:** EKP-CC (clarity), EKP-SL (interfaces as contracts)

**Intent:** `strict` (and related flags) turn type discipline on by default—opt out only with documented reason, not by accident.

**Rules:**

- Prefer `strict: true` in shared packages and application codebases.
- Do not disable `strictNullChecks` or `noImplicitAny` to “unblock” a PR—fix types or narrow scope.
- Document project-wide exceptions in ADR or `tsconfig` comments with owner and expiry.
- New code should compile clean under the strictest config the project claims.

**Good:** Shared `tsconfig.strict.json` extended by apps.

**Bad:** `// @ts-nocheck` on production modules; `strict: false` in library consumed by others.

**Review signals:** Growing `any`; `@ts-ignore` without ticket; per-file strict opt-out.

---

### EKP-TY02: Model types structurally, reason about shapes

**Implements:** EKP-P05, EKP-P04

**Applies:** EKP-SL (abstractions), EKP-LB (contracts)

**Intent:** TypeScript uses **structural** typing—compatibility is by shape, not declaration site. Design explicit shapes for boundaries.

**Rules:**

- Prefer named types/interfaces at module boundaries over anonymous object types in public APIs.
- Avoid “duck typing by accident”—if two shapes align but mean different things, brand or separate types.
- Do not rely on excess property checks alone for security or authorization semantics.
- Shared DTOs between UI and API belong in typed modules with clear ownership (cite EKP-LB).

**Good:** `interface CreateOrderRequest { … }` exported from a contracts package.

**Bad:** `function handle(data: { id: string })` duplicated with incompatible optional fields across files.

**Review signals:** Identical shapes with different meanings; silent widening via structural assignability.

---

### EKP-TY03: Ban `any`; prefer `unknown` at trust boundaries

**Implements:** EKP-P06, EKP-P07

**Applies:** EKP-EH (failure visibility), EKP-SF02 (validate at boundary)

**Intent:** `any` disables the type system; external data is `unknown` until narrowed or validated.

**Rules:**

- Do not introduce `any` in application code—use `unknown` + narrowing or typed parsers.
- Replace `any` in legacy code incrementally when touched (cite EKP-RF).
- JSON.parse, DOM events, third-party callbacks: treat as `unknown` or typed wrapper.
- Never cast `as SomeType` on external input without validation (runtime or schema).

**Good:** `const data: unknown = JSON.parse(raw); const order = parseOrder(data);`

**Bad:** `(response as Order).total` on fetch body; `Record<string, any>` for API models.

**Review signals:** `any` in new files; assertion chains without guards; eslint `@typescript-eslint/no-explicit-any` disabled locally.

---

### EKP-TY04: Use `readonly` to protect shared models

**Implements:** EKP-P04, EKP-P09

**Applies:** EKP-P05 (local reasoning)

**Intent:** Mutable shared types hide change blast radius—especially props, config, and domain snapshots passed across layers.

**Rules:**

- Prefer `readonly` properties on DTOs and view models passed downward.
- Use `ReadonlyArray<T>` / `readonly T[]` for collections that must not be mutated by consumers.
- Deep immutability is not automatic—document when shallow `readonly` is insufficient.
- Do not mutate objects received as function parameters unless API explicitly documents mutation.

**Good:** `interface UserView { readonly id: string; readonly name: string }`

**Bad:** Mutating `props.user.name` inside a child module.

**Review signals:** Shared objects mutated in place; “defensive copy” missing at trust boundaries.

---

### EKP-TY05: Encode decisions with discriminated unions

**Implements:** EKP-P04, EKP-P07

**Applies:** EKP-EH (explicit outcomes), EKP-CC (clarity)

**Intent:** Replace boolean flags and optional fields with tagged unions so invalid states are unrepresentable.

**Rules:**

- Model loading/error/success UI states as discriminated unions when they drive control flow.
- Prefer `kind` or `type` discriminator field consistent across the codebase.
- Exhaustiveness checking (`switch` + `never`) for union handling—do not leave default fall-through silent.
- Do not simulate unions with parallel optional fields (`error?: …; data?: …`) when states are mutually exclusive.

**Good:** `type LoadState = { status: 'loading' } | { status: 'error'; message: string } | { status: 'ok'; data: T }`

**Bad:** `{ loading?: boolean; error?: string; data?: T }` with ambiguous combinations.

**Review signals:** Impossible states reachable; missing `never` branch in review.

---

### EKP-TY06: Keep module boundaries explicit

**Implements:** EKP-P06, EKP-P09

**Applies:** EKP-MC (module coupling), EKP-LB (dependency direction)

**Intent:** Files and packages are architecture units—public API vs internal modules must be clear.

**Rules:**

- Export intentionally from package entry points; avoid deep imports into `src/internal/`.
- Prefer ESM `import`/`export`; document exceptions for CJS interop.
- Circular module dependencies are a design smell—break cycles with interfaces or shared kernel types.
- Side effects belong at composition root, not in shared utility modules.

**Good:** `package.json` `"exports"` maps public API.

**Bad:** `import { helper } from '../../deep/internal/util'` from another package.

**Review signals:** Barrel files re-exporting everything; circular imports flagged by tooling.

---

### EKP-TY07: Know what the compiler proves—and what it does not

**Implements:** EKP-P05, EKP-P08

**Applies:** EKP-TS (evidence before claims)

**Intent:** Types erase at runtime—compiler success is not proof of correct behavior or performance.

**Rules:**

- Do not claim “type-safe” for IO boundaries without runtime validation where data is external.
- Generics document relationships—they do not add runtime checks.
- `enum` vs `const` object unions: choose consciously for bundle and runtime semantics.
- Measure before optimizing types for compile speed only (**EKP-P08**).

**Good:** Schema validation (zod/io-ts/etc.) at API edge + TS types derived or aligned.

**Bad:** “TypeScript guarantees this API response shape” with no runtime check.

**Review signals:** Trust in compile-time only for security or payment paths.

---

### EKP-TY08: Validate at runtime boundaries

**Implements:** EKP-P06, EKP-P07

**Applies:** EKP-LB09, EKP-SF02, EKP-EH

**Intent:** TypeScript ends where untrusted data enters—parse, validate, then narrow to typed domain.

**Rules:**

- HTTP, WebSocket, `localStorage`, query params, message events: validate before domain use.
- Centralize parsers per boundary type; do not scatter ad-hoc `as` casts.
- Map parse failures to explicit error contracts (cite EKP-EH)—no silent defaults.
- Configuration and env vars: parse at bootstrap; inject typed values inward.

**Good:** `parseConfig(env)` returns `Result<AppConfig, ConfigError>`.

**Bad:** `const port = Number(process.env.PORT!)` without validation or default policy.

**Review signals:** `as` on `request.body`; non-null assertion `!` on external fields.

## AI Decision Flow

For TypeScript language-level changes. Run after `ai-assisted-development.md` steps 1–3. UI architecture routes to **EKP-FE**.

```
1. Language vs UI architecture?
   → NO, component/state/rendering: escalate to frontend-architecture.md (EKP-FE). Stop here.
   → YES: continue.

2. Strict contract (EKP-TY01)
   → New `any` or strict opt-out: reject or justify.

3. External data (EKP-TY03, EKP-TY08)
   → unknown + validate; no bare `as` on IO.

4. Shared models (EKP-TY04)
   → Prefer readonly; no silent mutation of shared shapes.

5. Control-flow types (EKP-TY05)
   → Prefer discriminated unions over flag soup.

6. Module boundaries (EKP-TY06)
   → No deep imports; break cycles.

7. Compiler vs runtime (EKP-TY07)
   → Do not claim safety without runtime boundary checks where needed.
```

| ID | Rule |
|----|------|
| **TY-AI-01** | Do not introduce `any` in new application code. |
| **TY-AI-02** | External input must be validated before typed domain use. |
| **TY-AI-03** | UI architecture questions route to EKP-FE—not this guide. |

## When not to apply

- Pure config/build tooling with no shared types (**EKP-P02**).
- Generated `.d.ts` consumers where types are owned by the generator.
- Frontend component structure — use EKP-FE.

## Trade-offs

| Benefit | Cost |
|---------|------|
| Strict types reduce integration defects | Upfront typing effort at boundaries |
| Discriminated unions clarify control flow | Refactor cost when states evolve |
| Runtime validation adds safety | Boilerplate at IO edges |

## Related

- [Engineering Principles](../engineering/engineering-principles.md) — EKP-P
- [SOLID](../engineering/solid.md) — EKP-SL
- [Error Handling](../engineering/error-handling.md) — EKP-EH
- [Testing](../testing/testing.md) — EKP-TS (Testing)
- [Layering and Boundaries](../architecture/layering-and-boundaries.md) — EKP-LB
- [Frontend Architecture](../frontend/frontend-architecture.md) — EKP-FE (L2)
- [TypeScript domain index](README.md)
