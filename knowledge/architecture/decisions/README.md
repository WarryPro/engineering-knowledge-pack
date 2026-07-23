# Architecture Decision Records

ADRs capture significant architectural decisions with context, alternatives, and consequences.

## Naming

`adr-<number>-<short-title>.md` — e.g. `adr-001-use-event-sourcing.md`

Numbers are sequential within this directory. Do not reuse numbers.

## Template

Copy from `templates/decision-record-template.md`. Set frontmatter:

```yaml
type: decision-record
domain: architecture
```

## When to write an ADR

- The decision is hard to reverse
- Multiple valid approaches existed
- The rationale will be questioned later
- Teams need alignment on structural choices

## When not to write an ADR

- Routine implementation choices covered by existing knowledge
- Temporary or easily reversible decisions
