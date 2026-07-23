# ADR-0004: Clean Code Position in the EKP Knowledge Graph

## Status

Accepted

## Date

2026-07-24

## Context

EKP organizes engineering knowledge in layers: principles, practices, patterns, and procedures. Without explicit separation, contributors and AI adapters conflate these layers—restating principles in practice documents, embedding class-design guidance in readability guides, or generating rules from the wrong source.

This produces three failure modes:

1. **Duplication** — the same guidance appears in multiple documents and drifts apart over time.
2. **Ambiguous AI output** — adapters cannot determine whether a directive is a judgment (principle), a technique (practice), a named structure (pattern), or a step-by-step process (procedure).
3. **Composition errors** — profiles include overlapping documents that reinforce the same ideas with different wording, increasing token cost without increasing decision quality.

`knowledge/engineering/engineering-principles.md` is approved as the foundation (`role: foundation`, `depends_on: []`). Before authoring `knowledge/engineering/clean-code.md`, the repository must record where that document sits in the knowledge graph and how it relates to sibling documents (`solid`, `refactoring`, `design-patterns`).

EKP needs separation between:

| Layer | Purpose | Stability | Example |
|-------|---------|-----------|---------|
| **Principles** | Durable value judgments and decision frameworks | High — rare changes | EKP-P04: Explicit over implicit |
| **Practices** | Concrete, repeatable techniques that operationalize principles | Medium — evolves with craft | Naming conventions, function size heuristics |
| **Patterns** | Named, reusable solutions to recurring design problems | Medium — catalog grows | Strategy, Factory, Observer |
| **Procedures** | Step-by-step processes for changing or verifying structure | Medium — evolves with tooling | Extract Method, safe refactoring sequence |

Clean Code is a practice-layer document. It is not a principle (it prescribes techniques), not a pattern catalog (it does not name reusable structures), and not a procedure (it does not define change sequences—that is refactoring).

## Decision

**Clean Code is a downstream engineering practice document.**

It lives at `knowledge/engineering/clean-code.md`, one level below the foundation, and operationalizes a subset of engineering principles at source-code unit level (function, file surface, naming, hygiene).

### Knowledge graph position

```
engineering-principles (foundation)
        │
        ├── clean-code          (practice — EKP-P04, EKP-P10)
        ├── solid               (practice — EKP-P05, EKP-P09)
        ├── refactoring         (procedure — EKP-P03, EKP-P10)
        └── design-patterns     (patterns — EKP-P09)
```

### Decision details

1. **`engineering-principles` is the foundation**
   - Apex of the engineering knowledge hierarchy.
   - Contains EKP-P01 through EKP-P10 only.
   - No upstream `depends_on` dependencies.
   - Downstream documents reference principles by ID; they do not restate them.

2. **`clean-code` is a practice layer document**
   - `role: practice`
   - `depends_on: [knowledge/engineering/engineering-principles.md]`
   - `implements: [EKP-P04, EKP-P10]`
   - Scope: naming, readability, comments, and code hygiene at function/file level.
   - `severity: recommended` — practices apply with context; not every rule applies to generated code, configs, or one-off scripts.

3. **`solid`, `refactoring`, and `design-patterns` are siblings with explicit boundaries**

   | Document | Layer | Scope | Must not overlap with clean-code |
   |----------|-------|-------|----------------------------------|
   | `solid` | Practice | Class/module responsibility, dependency direction | Class design, interfaces, DIP — not naming or function length |
   | `refactoring` | Procedure | When and how to change structure safely | Extract/Rename/Move steps — not readability heuristics |
   | `design-patterns` | Patterns | Named reusable structures (Strategy, Factory, etc.) | Pattern catalog — not naming conventions |

   Sibling documents share a single upstream dependency (`engineering-principles`) except:
   - `refactoring` weakly depends on `clean-code` and `solid` as **target states** for structural change.
   - `design-patterns` depends on `solid` as a prerequisite for pattern application.

4. **Authoring constraint**
   - Every section in `clean-code.md` must map to at least one `EKP-CC` concept identifier and at least one of `EKP-P04` or `EKP-P10`.
   - Content that maps only to EKP-P05, EKP-P06, or EKP-P09 belongs in `solid`, `layering-and-boundaries`, or `design-patterns`.

## Rationale

A flat knowledge base—where principles, naming rules, SOLID, and refactoring live in one document or without declared dependencies—does not scale. Reviewers debate preference instead of referencing stable identifiers. AI adapters emit contradictory directives from overlapping sources.

Positioning `clean-code` as a practice-layer sibling:

- Preserves the foundation document as judgment-only (heuristics, trade-offs, deviation rules).
- Produces enforceable, stack-agnostic practices suitable for Phase 5 rule generation.
- Enables profile composition without redundant context (e.g., a "code review" profile selects principles + clean-code + solid without duplication).
- Establishes a repeatable pattern for all future engineering knowledge documents.

## Alternatives considered

### Single comprehensive "engineering standards" document

Combine principles, clean-code, SOLID, and refactoring into one file.

**Rejected.** Violates EKP single-concern document policy. Exceeds maintainable length. Adapters cannot selectively include guidance. Changes to naming conventions would require review of the entire foundation.

### clean-code as child of solid

Place `clean-code` downstream of `solid`, assuming readable code requires correct class design first.

**Rejected.** Readability and class design are orthogonal—a SOLID-compliant class can have poor names; a well-named function can violate SRP. Parallel sibling structure reflects this independence.

### clean-code at the same level as engineering-principles

Elevate clean-code to `role: foundation` alongside principles.

**Rejected.** Naming and hygiene are techniques, not value judgments. Elevating them blurs the principles vs practices distinction and encourages dogmatic enforcement without the deviation framework defined in the foundation.

### Defer graph decision until all documents exist

Author `clean-code.md` first, define relationships later.

**Rejected.** The first practice document sets precedent for the entire graph. Recording the decision before authoring prevents scope creep and duplication in the inaugural downstream document.

## Consequences

### Positive

- **Less duplication** — each layer owns a distinct concern; cross-references replace restatement.
- **Clearer AI generation** — adapters map principles → sparse judgment rules; practices → enforceable directives; patterns → structural templates; procedures → sequential guidance.
- **Better knowledge composition** — profiles select documents by layer without overlapping content; token budgets are spent on non-redundant context.

### Negative

- **Requires disciplined document ownership** — contributors must know where content belongs before authoring; misplaced content needs relocation during review.
- **Upfront graph maintenance** — new documents require ADR or explicit graph update when boundaries shift.
- **Authoring overhead** — each document needs `depends_on`, `implements`, and `related` metadata consistent with the graph.

### Risks

- **Boundary disputes** — edge cases (e.g., function length vs SRP) may spark debate about clean-code vs solid ownership. Mitigation: default to the document whose primary failure mode is addressed; escalate via ADR if recurring.
- **Metadata drift** — `related` paths to planned documents that do not yet exist. Mitigation: create documents in dependency order; validation will extend to graph integrity in Phase 5.

## Compliance

Adherence to this decision is verified by:

1. **PR review** — `clean-code.md` PR must include frontmatter matching the graph position defined here (`role: practice`, `depends_on`, `implements`).
2. **Content review** — no restatement of EKP-P01–P10; references by ID only.
3. **Scope review** — no SOLID, refactoring procedures, or design pattern catalog content in `clean-code.md`.
4. **Validation** — `py -3 scripts/validate/validate.py` must pass; future graph validator will check `depends_on` paths and `implements` consistency.
5. **Bidirectional consistency** — `engineering-principles.md` already lists `clean-code.md` in `related`; clean-code must list `engineering-principles.md` in `depends_on`.

## Related

- [Engineering Principles](../../engineering/engineering-principles.md) — foundation document (EKP-P01–P10)
- [Architecture decisions index](README.md) — ADR conventions for this directory
- Planned: `knowledge/engineering/clean-code.md`
- Planned: `knowledge/engineering/solid.md`
- Planned: `knowledge/engineering/refactoring.md`
- Planned: `knowledge/engineering/design-patterns.md`
