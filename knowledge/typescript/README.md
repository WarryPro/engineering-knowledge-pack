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

When a document spans both, place it in the domain of the primary concern and link to the other.

## Published

- [typescript-fundamentals.md](typescript-fundamentals.md) — EKP-TY01–TY08; applies EKP-P04–P07, P09
