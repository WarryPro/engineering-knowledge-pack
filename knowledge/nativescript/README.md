# NativeScript

NativeScript native mobile application architecture on TypeScript.

## Scope

- NativeScript application and runtime model (native UI, not DOM)
- Page/view boundaries, navigation, and lifecycle
- Platform (Android/iOS) isolation, plugins, and bridges
- NativeScript + UI-framework integration (e.g. NativeScript-Vue) as an in-vertical choice
- Build/debug/device engineering concerns specific to NativeScript

## Does not belong here

- TypeScript language features → see `typescript/`
- Web frontend / DOM / SSR architecture → see `frontend/`
- Flutter / Dart mobile UI → see `flutter/`
- Generic Vue / Angular / React tutorials → vendor docs (not separate EKP domains)
- General engineering practices → see `engineering/`

## Boundary with `frontend/` and `flutter/`

| Topic | Domain |
|-------|--------|
| Browser DOM, semantic HTML, SSR/hydration, web a11y | `frontend/` |
| NativeScript native UI, navigation, plugins, platforms | `nativescript/` |
| Flutter / Dart widgets and channels | `flutter/` |
| TypeScript strict typing and modules | `typescript/` |

NativeScript-Vue (or other UI frameworks under NativeScript) is an **integration choice inside this vertical**, not a separate EKP technology domain.

## Published

- [nativescript-architecture.md](nativescript-architecture.md) — EKP-NS01–NS09; depends on EKP-TY; applies EKP-P04, P05, P06, P09
