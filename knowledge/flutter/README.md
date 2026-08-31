# Flutter

Flutter and Dart mobile and cross-platform UI development.

## Scope

- Flutter application architecture (widget runtime, boundaries, state, navigation)
- Platform integration and package evaluation boundaries
- Project structure trade-offs for Flutter codebases
- Dart architectural boundaries in Flutter context (not a Dart language tutorial)

## Does not belong here

- Generic TypeScript patterns → see `typescript/`
- Web frontend architecture → see `frontend/`
- NativeScript native mobile (TypeScript) → see `nativescript/`
- General UI accessibility principles → see `frontend/`
- Dart syntax tutorial, widget catalog, package encyclopedia → vendor docs

## Boundary with `frontend/` and `nativescript/`

| Topic | Domain |
|-------|--------|
| Browser DOM, semantic HTML, SSR/hydration, web a11y | `frontend/` |
| NativeScript native UI, navigation, plugins, platforms | `nativescript/` |
| Flutter declarative widget tree, Dart/Flutter app structure | `flutter/` |
| Generic verification philosophy | `testing/` (EKP-TS) |

## Published

- [flutter-architecture.md](flutter-architecture.md) — EKP-FL01–FL09; depends on EKP-P; applies EKP-P04, P05, P06, P09
