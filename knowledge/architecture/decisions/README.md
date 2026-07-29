# Architecture Decision Records

ADRs capture significant architectural decisions with context, alternatives, and consequences.

## Location

**Canonical path:** `knowledge/architecture/decisions/`

ADRs are knowledge artifacts. They live under `knowledge/architecture/decisions/`, not in a separate top-level `adr/` directory. Do not create ADRs outside this path.

## Naming

`adr-<number>-<short-title>.md`

- Use **zero-padded four-digit** numbers: `adr-0001`, `adr-0002`, …
- Use **kebab-case** for the title slug
- Numbers are sequential within this directory. Do not reuse numbers.

Examples:

- `adr-0004-clean-code-position-in-knowledge-graph.md`
- `adr-0005-use-event-sourcing.md`

## Template

Copy from `templates/decision-record-template.md`.

ADRs follow the decision record structure (Status, Context, Decision, Rationale, Alternatives, Consequences, Compliance, Related). Knowledge frontmatter is optional for ADRs; if added, set:

```yaml
type: decision-record
domain: architecture
```

## Index

| ADR | Title | Status |
|-----|-------|--------|
| [adr-0004](adr-0004-clean-code-position-in-knowledge-graph.md) | Clean Code position in the EKP knowledge graph | Accepted |

## When to write an ADR

See [adr-practices.md](../adr-practices.md) (EKP-AD01) for the full process. Summary:

- The decision is hard to reverse
- Multiple valid approaches existed
- The rationale will be questioned later
- Teams need alignment on structural choices
- Knowledge graph boundaries or document ownership must be recorded

## When not to write an ADR

See [adr-practices.md](../adr-practices.md) (EKP-AD02). Summary:

- Routine implementation choices covered by existing knowledge
- Temporary or easily reversible decisions

## Related

- [Architecture domain README](../README.md)
- [ADR practices](../adr-practices.md) — EKP-AD process guide
- [Decision record template](../../../../templates/decision-record-template.md)
