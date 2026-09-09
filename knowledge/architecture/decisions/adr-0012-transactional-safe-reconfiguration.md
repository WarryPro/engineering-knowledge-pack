# ADR-0012: Transactional Safe Reconfiguration

## Status

Accepted

## Date

2026-09-09

## Context

Through v0.19, Consumer lifecycle could install, status-inspect, update, and uninstall a composition or legacy-profile project, including multi-assistant ownership under one `install.json`. Changing requested components or assistants after install by editing `.ekp/project.yaml` produced `CONFIGURATION_DRIFT`, and `ekp update` correctly refused silent reconfiguration.

v0.20 must provide an authorized path to change project intent without adopting manual drift, without auto-migrating legacy profiles, and without weakening transactional safety (exact-byte config replacement, managed-file races, manifest-last commit).

Workspaces / monorepos remain out of scope for this decision and are deferred to v0.21.

## Decision

### Desired-state configure

Public `ekp configure` replaces project intent with **exact** desired component and assistant sets (not add/remove deltas). Both dimensions are required in noninteractive mode (`--yes` or `--dry-run`). Interactive mode may obtain missing dimensions from the user, defaulting to **current persisted intent** only (never detection; never Cursor injection).

### HEALTHY composition-only

Configure is eligible only for composition installations that are HEALTHY at the running package version. It refuses NOT_INSTALLED, legacy-profile, VERSION_MISMATCH, INCOMPLETE, MODIFIED, CONFIGURATION_DRIFT, and INVALID. No force, drift adoption, repair+configure, or legacy→composition migration.

### Semantic vs exact-byte config identity

- `configuration_sha256` remains the **semantic** normalized ProjectConfig hash (`schema_version: 1`), persisted in `install.json` and used for compatibility with v0.19 goldens.
- Exact `project.yaml` content SHA-256 is a **physical** transactional CAS / rollback identity only. It is not exposed as a persistent user configuration or manifest schema field.

### Same-plan prepare / apply

Configure prepares a `LifecyclePlan` once, renders it, optionally confirms, then applies that **same** prepared operation. A second assembly after confirmation is forbidden. Semantic NOOP skips assembly and confirmation.

### Manifest last + same-version ownership transition

Configure may change assistant ownership at the same package version through an authorized transition. Managed-file CREATE/WRITE/DELETE/NOOP apply transactionally; `install.json` is written last. Modified owned files and unmanaged collisions refuse mutation.

### Manual drift still refused

Editing `project.yaml` outside `ekp configure` remains configuration drift. The correct flow is HEALTHY → `ekp configure`, not “edit YAML then ask EKP to adopt it.”

### Schema1 retained

ProjectConfig and InstallManifest `schema_version` remain `1`. Workspaces deferred to v0.21.

## Consequences

### Positive

- Users can add/remove assistants and components safely without hand-editing YAML
- Physical CAS preserves exact-byte rollback semantics while semantic hashes stay v0.19-compatible
- Update and configure stay distinct: update synchronizes package resources; configure changes intent

### Negative / trade-offs

- Legacy-profile projects cannot reconfigure without a separate migration product decision
- VERSION_MISMATCH still requires `ekp update` before configure
- Interactive blank NOOP is intentional; empty cleared selections refuse rather than uninstalling

## Related

- ADR-0010 — project composition and assistant separation
- ADR-0011 — Consumer deployer abstraction
- `docs/deployment.md` — lifecycle command responsibilities
- `docs/roadmap.md` — v0.20 Safe Reconfiguration; v0.21 workspaces
