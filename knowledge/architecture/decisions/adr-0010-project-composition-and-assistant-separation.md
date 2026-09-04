# ADR-0010: Project Composition and Assistant Separation

## Status

Accepted

## Date

2026-09-04

## Context

EKP v0.17.0 Consumer installs a single `cursor-*` packaging profile. Multi-technology projects are treated as ambiguous failures. Historical `cursor-*` profiles encode both knowledge packaging and dependency composition via `includes`, while `ekp-*` profiles mainly change adapter `outputs`. Treating profiles as the composition engine would either force combinatorial profile explosion (`cursor-symfony-frontend-…`) or continue conflating stack identity with assistant packaging.

v0.18 requires a Project Composition Engine that answers “what engineering knowledge does this project need?” while preparing cleanly for multi-assistant Consumer lifecycle (v0.19) without rewriting knowledge Markdown or inventing combination profiles.

## Decision

### Components are the composition source of truth

Canonical project composition is a set of **technology components** (`core`, `php`, `symfony`, `typescript`, `frontend`, `devops`, `nativescript`, `flutter`, …) with explicit `requires` and **direct** `knowledge` contributions.

Forbidden: combinatorial profiles such as `cursor-symfony-frontend` or `ekp-symfony-frontend`.

### Stack and assistant are independent

```yaml
components:
  - symfony
  - frontend

assistants:
  - cursor
```

The component graph contains **zero** assistant-specific semantics. Components must not depend on `cursor`, `copilot`, `claude`, or `antigravity`.

### Direct knowledge contributions

Each component owns only its direct canonical knowledge paths. Dependencies supply their own knowledge through the `requires` graph. Composition does **not** use `knowledge_profile: cursor-*` resolution that would re-embed dependency composition already present in historical profiles.

Optional `legacy_profile` exists only for compatibility testing, parity verification, and legacy mapping. It must not determine dependency closure, assistant outputs, or canonical composition knowledge.

### Profiles remain compatibility / packaging presets

| Artifact | Role |
|----------|------|
| `components/*.yaml` | Canonical project composition |
| `cursor-*` profiles | Legacy/public compatibility packaging presets |
| `ekp-*` profiles | Contributor multi-adapter packaging presets |

Existing profile support remains in v0.18. No deprecation removal timeline in this release.

### Future project configuration (not implemented in AW-A)

```yaml
schema_version: 1
components: [symfony]
assistants: [cursor]
```

- `.ekp/project.yaml` = user/project intent (not EKP-managed uninstall target)
- `.ekp/install.json` = operational ownership (`schema_version = 1`; no schema 2 for v0.18)

Composed installs will use operational fields conceptually:

```text
profile = project-composition
mode = composition
configuration_sha256 = <normalized intent hash>
```

Mode comes from **install.json operational state**, not merely from the existence of `project.yaml`. Absent `mode` means **legacy-profile**. Stray yaml must not change update semantics.

For `mode = composition`, configuration drift (yaml hash ≠ `configuration_sha256`) yields status drift and **refuses silent reconfiguration** on update. Safe reconfiguration is v0.20.

v0.18 Consumer accepts only `cursor` as a managed assistant in project config. Copilot/Claude/Antigravity remain contributor adapters until v0.19.

### Future CLI / detection contracts (not implemented in AW-A)

- Repeatable `--component` for composed install; mutually exclusive with `--profile`
- Empty detection + `--yes` without `--component`/`--profile` → FAIL (no guessing)
- Detection reduction to minimal requested intent uses the component graph (retire duplicate `SPECIALIZATIONS` tables)
- Tool signals = evidence, not consent

## Rationale

- Avoids combinatorial profile explosion
- Separates stack composition from assistant deployment
- Keeps one dependency graph (components) instead of duplicating profile `includes` + resolver specializations
- Preserves v0.17 manifests and profile packaging for compatibility
- Reuses existing knowledge documents without a second generation engine

## Alternatives considered

### Combinatorial profiles

Rejected — exponential maintenance and coupling of stack×assistant.

### `knowledge_profile` pointing at resolved `cursor-*` profiles

Rejected — historical profiles already compose dependencies; using them as component knowledge duplicates graph semantics and blocks clean multi-component union.

### Profiles as the only composition primitives

Rejected — conflates packaging/assistant `outputs` with project stack intent.

### Manifest schema 2 for composition

Rejected for v0.18 — schema 1 remains; intent lives in `project.yaml`; additive operational fields suffice.

## Consequences

### Positive

- Deterministic closure and knowledge union for multi-stack projects
- Clear SoT for “Symfony requires PHP”
- Forward-compatible assistant field without multi-assistant deploy in v0.18
- Legacy `--profile` and v0.17 manifests remain supportable

### Negative

- Temporary dual representation: components + historical profiles (parity tested)
- Install/update integration deferred to later v0.18 phases
- Contributors must keep component direct knowledge and profile packaging aligned until profiles are further thinned

### Neutral

- Evaluation L1 remains optional and out of scope for composition architecture

## Compliance

- New components land under `components/` with `schema/component.schema.json`
- No assistant ids in component metadata
- Consumer install/lifecycle unchanged until later authorized phases
- ADR index updated when this ADR is accepted

## Related

- [ADR-0008](adr-0008-profile-composition-includes.md) — profile `includes` (packaging composition)
- [ADR-0009](adr-0009-adapter-dispatch-architecture.md) — adapter registry / outputs
- [ADR-0006](adr-0006-versioning-and-compatibility.md) — versioning & compatibility
