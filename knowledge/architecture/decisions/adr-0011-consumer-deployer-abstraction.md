# ADR-0011: Consumer Deployer Abstraction

## Status

Accepted

## Date

2026-09-05

## Context

EKP v0.18 introduced project composition (ADR-0010) and kept Consumer filesystem deployment inside `CursorDeployService`. Adapter generation already supports four assistants (`cursor`, `copilot`, `claude`, `antigravity`) via `AdapterRegistry`, but Consumer lifecycle hard-codes Cursor paths (`.cursor/rules/*.mdc`), planning, atomic writes, and ownership.

v0.19 must support managed Consumer deployment for multiple assistants without duplicating collision planning, atomic CREATE/RESTORE, rollback, or ownership-manifest logic per assistant. Treating adapters as deployers would conflate **generation** (canonical knowledge → assistant bundle) with **deployment** (bundle → consumer filesystem).

## Decision

### Adapter ≠ Deployer

| Registry | Responsibility |
|----------|----------------|
| `ComponentRegistry` | Technology composition (`components/**`, dependency closure, `ResolvedComposition`) |
| `AdapterRegistry` | Assistant-specific **generation** (canonical selected knowledge → adapter bundle) |
| `DeployRegistry` | Assistant-specific **Consumer filesystem deployment** mapping |

Adapters remain generators. They do **not** own consumer collision planning, filesystem ownership, install manifests, or lifecycle transactions.

### Deployer contract

A Deployer is a thin assistant-specific mapping layer:

```text
assistant id
bundle subdirectory expected
bundle-file validation
assistant-specific consumer target mapping
→ DesiredManagedFile[]
```

A Deployer does **not** own `project.yaml`, `install.json`, generic collision planning, CREATE/RESTORE, atomic writes, rollback, or lifecycle state.

### DesiredManagedFile

One generic immutable model carries project-relative target path, assistant id (`adapter`), assembled bundle `source_path`, and expected `sha256`. No technology/component data belongs on this model. Paths must use existing EKP safe-path semantics (no absolute paths, `..`, or escaping). The model must support both assistant directories (e.g. `.cursor/rules/foo.mdc`) and root files (e.g. `CLAUDE.md`).

### Shared deployment engine

One shared managed-file planner/applier owns:

```text
DesiredManagedFile[] → FileOperation[]
first-install / reinstall planning
symlink and path safety
directory planning
atomic CREATE / RESTORE
hash verification
created-file / created-directory tracking
rollback
ManagedFile creation
```

Forbidden: four parallel `*DeployService` classes that duplicate planning, atomic writes, rollback, and collision logic.

### Transaction and ownership

- One transaction across selected assistants (when multi-assistant Consumer install is enabled later)
- One ownership manifest (`install.json`)
- Duplicate desired targets (same path, same or different adapters) are conflicts / programming errors — no last-writer-wins

### v0.19 target assistants

```text
cursor
copilot
claude
antigravity
```

**Phase AX-A** implements Consumer deployment only for **Cursor** (`DeployRegistry` registers `cursor` only). Public Consumer support (`SUPPORTED_PROJECT_ASSISTANTS`, CLI, project config) remains Cursor-only until later phases. Copilot / Claude / Antigravity managed deployers follow in AX-B+.

`DeployRegistry` is the long-term authoritative SoT for managed Consumer assistant capability. Do not introduce a second managed-assistant list.

## Rationale

- Separates STACK (components) from ASSISTANT (adapters/deployers) per ADR-0010
- Reuses proven Cursor safety (TOCTOU, atomic writes, rollback) for future assistants
- Keeps adapter generators unchanged and contributor multi-output assembly green
- Avoids premature public multi-assistant install while proving Cursor parity on the shared engine

## Alternatives considered

### Per-assistant DeployService clones

Duplicate planning/apply/rollback for each assistant. Rejected: high drift risk and forbidden by AX-A architecture.

### Adapter owns deployment

Fold consumer path mapping into adapter generators. Rejected: adapters must stay generation-only; Consumer collision and ownership are lifecycle concerns.

### Broaden public Consumer support in the same change as the abstraction

Rejected: AX-A proves Cursor parity on the shared engine first; public multi-assistant activation is a later phase.

## Consequences

### Positive

- Clear Adapter ≠ Deployer boundary
- Shared safety semantics for all future managed assistants
- Cursor remains a thin deployer + compatibility facade with zero Consumer behavior change in AX-A

### Negative

- Temporary dual surface: `CursorDeployService` facade over shared engine until later retirement
- Non-Cursor Consumer deployers deferred (AX-B)

### Risks

- Incomplete extraction could leave Cursor-specific assumptions in the shared engine — mitigated by synthetic root-file and assistant-x tests

## Compliance

- ADR index lists ADR-0011 as Accepted
- `DeployRegistry` registers only implemented deployers (Cursor in AX-A)
- Shared engine has no hard-coded `.cursor/rules` / `*.mdc` knowledge
- Cursor composition/legacy install parity gates remain green
- No public `--assistant`, project-config assistant expansion, or non-Cursor deployers in AX-A

## Related

- [ADR-0009: Adapter dispatch architecture](./adr-0009-adapter-dispatch-architecture.md)
- [ADR-0010: Project composition and assistant separation](./adr-0010-project-composition-and-assistant-separation.md)
- [ADR practices](../adr-practices.md)
