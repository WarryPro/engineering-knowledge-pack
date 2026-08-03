---
title: Document Title
domain: php  # language or framework domain (php, symfony, typescript, frontend, …)
tags: []
severity: recommended
applies_to: [backend]  # narrow to stack audience
type: guide
role: practice  # language: practice | framework system structure: architecture
depends_on:
  - knowledge/engineering/engineering-principles.md
  # Framework guides also depend on language fundamentals (requires graph exception under V2).
implements:
  - EKP-P04  # list principles applied — do not redefine them
related:
  - knowledge/engineering/engineering-principles.md
  # Mandatory: at least one L0 related link; L2 must related L1 language guide
extends: []
concept_ids: []  # EKP-PH## / EKP-SY## / EKP-TY## / EKP-FE## — one namespace per owner doc
adapter_priority: high
---

# Document Title

## Summary

One paragraph: which stack, when to apply, and which L0 principles this **applies** (not redefines).

## Context

Stack-specific problem. What fails if ignored. Explicit **Boundaries** table vs L0 and peer tech domains.

| Concern | Owner | This document |
|---------|-------|---------------|
| Principle / practice (L0) | `engineering/…` or `architecture/…` | Cite / apply only |
| Language idiom (L1) | `php/` or `typescript/` | Primary if L1; prerequisite if L2 |
| Framework structure (L2) | `symfony/` or `frontend/` | Primary if L2 |

**Out of scope:** Official framework encyclopedias, version changelogs, vendor tutorials.

## EKP layer positioning

| Layer | Role | This document |
|-------|------|---------------|
| **Principles (L0)** | Why | Implements listed EKP-P## by reference |
| **Language (L1)** | How the language expresses principles | Primary for language guides |
| **Framework (L2)** | How the framework structures systems | Primary for framework guides |

## Guidance

### EKP-XX01: Concept title

**Implements:** EKP-P0N

**Applies:** EKP-LB0N / EKP-SF0N (cite existing concept IDs — do not invent duplicates)

**Intent:** …

**Rules:**

- …

**Good:** …

**Bad:** …

**Review signals:** …

---

## AI Decision Flow

Stack-specific routing after `ai-assisted-development.md` steps 1–3 when the change is in this technology.

```
1. …
```

## When not to apply

- …

## Trade-offs

| Benefit | Cost |
|---------|------|
| … | … |

## Related

- [Engineering Principles](../engineering/engineering-principles.md) — EKP-P
- (L2) Language fundamentals guide — required
- Relevant L0 architecture / security / testing guides
