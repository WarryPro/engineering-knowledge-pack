# Architecture

System design, structural patterns, and architectural decision-making.

## Scope

- Layering and boundaries (hexagonal, clean architecture, CQRS)
- Coupling, cohesion, and dependency direction
- Architectural patterns and when to use them
- Architecture decision records (ADRs)

## Does not belong here

- Technology-specific implementation → see stack domains (`symfony/`, `frontend/`, etc.)
- Database schema design → see `database/`
- Project meta-documentation → see `docs/architecture.md`

## Document types

| Type | Location | Template |
|------|----------|----------|
| Guide | `knowledge/architecture/<topic>.md` | `templates/knowledge-document-template.md` |
| Decision record | `knowledge/architecture/decisions/adr-<number>-<topic>.md` | `decision-record-template.md` |
| Checklist | `knowledge/architecture/checklists/<name>.md` | `templates/review-checklist-template.md` |

Set `type: decision-record` in frontmatter for ADRs.
