# EKP Examples

Educational samples that demonstrate EKP document formats and review workflows.

**These are not production decisions.** They do not live in `knowledge/` and are not part of the validated knowledge graph unless explicitly referenced for illustration.

## Contents

| Example | Purpose |
|---------|---------|
| [adr-0001-example-service-boundary.md](adr-0001-example-service-boundary.md) | ADR structure (Status, Context, Decision, Consequences) |
| [checklists/architecture-review.md](checklists/architecture-review.md) | Architecture review criteria (EKP-LB, EKP-AD) |
| [checklists/api-review.md](checklists/api-review.md) | HTTP API review criteria (EKP-AP) |

## How to use

- Copy templates from [`templates/`](../templates/) for new project artifacts.
- For real EKP ADRs, use `knowledge/architecture/decisions/` and follow [`adr-practices.md`](../knowledge/architecture/adr-practices.md).
- For knowledge guides, use `knowledge/<domain>/` and run validation per [`DEVELOPMENT.md`](../DEVELOPMENT.md).

## What not to put here

- Technology tutorials (PHP, Symfony, Docker, etc.)
- Sample application code
- Production architecture decisions for the EKP project itself (those belong in `decisions/`)
