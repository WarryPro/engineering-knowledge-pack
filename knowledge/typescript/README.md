# TypeScript

TypeScript language patterns, type system usage, and tooling.

## Scope

- Type definitions, generics, and utility types
- Strict mode configuration and compiler options
- Module systems (ESM, CommonJS)
- TypeScript tooling (tsc, eslint, tsconfig)

## Does not belong here

- Framework-specific UI patterns → see `frontend/`
- Build and deployment pipelines → see `devops/`
- General engineering practices → see `engineering/`

## Boundary with `frontend/`

| Topic | Domain |
|-------|--------|
| Type narrowing, generics, `strict` config | `typescript/` |
| React/Vue component architecture, state management | `frontend/` |
| Shared types between API and UI | `typescript/` (type design) + link to `frontend/` |

## Boundary with future TypeScript work

Reserved namespace for TypeScript guides: **EKP-TY** (do not use `EKP-TS` — reserved for Testing).
