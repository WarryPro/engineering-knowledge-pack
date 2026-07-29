# Database

Schema design, migrations, queries, and transaction management.

## Published

- [database-design.md](database-design.md) — EKP-DB; EKP-P03, EKP-P06, EKP-P10

## Scope

- Schema design and normalization trade-offs
- Migration strategies and rollback
- Query patterns and index design
- Transaction boundaries and isolation levels

## Does not belong here

- ORM-specific patterns → see stack domain (`symfony/`, etc.)
- General performance tuning → see `performance/`
- Security (SQL injection prevention) → see `security/` (link from here)
- API and service integration → see `architecture/integration-patterns.md`
