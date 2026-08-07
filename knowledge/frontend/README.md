# Frontend

Frontend architecture, UI patterns, and user-facing concerns.

## Scope

- Component architecture and composition
- State management (client-side stores, server state)
- Accessibility (a11y) and responsive design
- CSS architecture and design systems
- Framework usage (React, Vue, etc.) at the application level

## Does not belong here

- TypeScript language features → see `typescript/`
- Flutter mobile UI → see `flutter/`
- API design and backend concerns → see `architecture/`

## Boundary with `typescript/`

| Topic | Domain |
|-------|--------|
| Type narrowing, generics, `strict` config | `typescript/` |
| React/Vue component architecture, state management | `frontend/` |
| Shared types between API and UI | `typescript/` (type design) + link to `frontend/` |

When a document spans both, place it in the domain of the primary concern and link to the other.

## Published

- [frontend-architecture.md](frontend-architecture.md) — EKP-FE01–FE08; depends on EKP-TY; applies EKP-P04, P05, P06, P09
