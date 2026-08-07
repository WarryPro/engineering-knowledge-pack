# Knowledge Review Checklist

Use for pull requests that add or materially change knowledge guides, namespaces, profiles, or graph rules.

Copy into the PR description or check items as you review.

## Human review (semantic)

- [ ] **1.** Does this concept already exist elsewhere? (Check concept index / related guides.)
- [ ] **2.** Is this a **new** concept, or a technology-specific **application** of an existing L0 concept?
- [ ] **3.** Does this content belong in **Foundation** instead of a tech domain?
- [ ] **4.** Is graph depth justified? (Target L2 → L1 → L0; avoid deeper chains.)
- [ ] **5.** Does another guide already cover the same **meaning**? (Duplication check.)
- [ ] **6.** Is technology leaking into Foundation, or Foundation being redefined in tech guides?
- [ ] **7.** Are examples **engineering decisions** (Good/Bad), not vendor tutorials or API catalogues?
- [ ] **8.** Are `depends_on` (prerequisites) and `related` (citations) correct?
- [ ] **9.** Is profile scope justified? (New or changed profile paths.)
- [ ] **10.** Is a **CHANGELOG** `[Unreleased]` entry required?

## Definition of Done

- [ ] Namespace registered in `schema/concept-namespaces.json` (if new namespace)
- [ ] `py -3 scripts/validate/validate.py` — **PASS**, **0 warnings** target
- [ ] Domain `README.md` index updated (`## Published` or equivalent)
- [ ] `engineering-principles.md` `related` updated if guide `depends_on` foundation
- [ ] `ai-assisted-development.md` EKP-AI10 updated if guide is routable
- [ ] Affected profiles: `assemble --verify` locally
- [ ] `CHANGELOG.md` `[Unreleased]` updated (if user-visible change)
- [ ] ADR filed when required (see [governance.md](../docs/governance.md#adr-policy))

## ADR required?

| Change | ADR? |
|--------|------|
| Typo / clarity, same semantics | No |
| New guide in existing domain | Usually no |
| New domain directory (L1/L2/L3) | **Yes** |
| Graph exception (new pattern) | **Yes** |
| Schema breaking change | **Yes** |
| Deprecate published guide | **Yes** |
| Change `cursor-core` | **Yes** + explicit approval |
