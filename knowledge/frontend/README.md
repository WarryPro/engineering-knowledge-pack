# Frontend

Frontend architecture, markup, styling decisions, and user-facing UI engineering concerns.

## Scope

- Component architecture, state ownership, and composition
- Presentation vs domain boundaries and async UI states
- Semantic HTML and native browser capabilities
- Styling architecture decisions (project-first; mechanism choice)
- CSS ownership: cascade, specificity, scoping
- Design tokens and theming axes
- Layout and responsive design principles
- Accessibility as architecture and operational interactive a11y
- UI verification boundaries (user-visible outcomes)

## Does not belong here

- TypeScript language features → see `typescript/`
- Framework tutorials (React, Vue, Angular, etc.) → vendor docs / future framework-specific profiles
- CSS framework or SCSS encyclopedias → vendor docs (decision rules only live here)
- Component-library catalogs → vendor docs / project kits
- Flutter mobile UI → see `flutter/`
- NativeScript native mobile UI → see `nativescript/`
- API design and backend concerns → see `architecture/`
- Generic testing philosophy → see `testing/` (frontend cites a thin UI boundary)
- Generic performance mindset → see `performance/` (frontend cites; does not redefine)

## Boundary with `typescript/`

| Topic | Domain |
|-------|--------|
| Type narrowing, generics, `strict` config | `typescript/` |
| UI architecture, markup, styling decisions, responsive layout | `frontend/` |
| Shared types between API and UI | `typescript/` (type design) + link to `frontend/` |

When a document spans both, place it in the domain of the primary concern and link to the other.

## Published

- [frontend-architecture.md](frontend-architecture.md) — EKP-FE01–FE08; depends on EKP-TY; applies EKP-P04, P05, P06, P09
- [frontend-styling-and-markup.md](frontend-styling-and-markup.md) — EKP-FE09–FE16; markup, styling decisions, layout/responsive, a11y ops, UI testing boundary
