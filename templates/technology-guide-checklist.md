# Technology Guide Authoring Checklist

Use before merging a Phase 4 (or later) technology knowledge guide. Copy into the PR description or run mentally during review.

## Scope

- [ ] Domain matches language (L1) or framework (L2) — not a new nested pack
- [ ] Does **not** redefine L0 principles (EKP-P, LB, SF, …); cites and applies them
- [ ] Boundaries table lists what belongs in L0 / peer tech domains
- [ ] No framework component encyclopedia or release-changelog content
- [ ] No tool-specific AI syntax (Cursor frontmatter, Copilot directives)

## Graph and namespaces

- [ ] Namespace registered in `schema/concept-namespaces.json` with this file as owner
- [ ] Concept IDs match approved prefixes (`EKP-PH`, `EKP-SY`, `EKP-TY`, `EKP-FE`, …)
- [ ] Does **not** use reserved collisions (`EKP-TS` = Testing, `EKP-SF` = Security)
- [ ] `depends_on` only downward (L2 → L1 → L0); no L0 → tech
- [ ] Framework → language `depends_on` has a documented V2 exception in `graph-rules.yaml` if roles disallow it
- [ ] Prefer `related:` for cross-stack links (e.g. Symfony ↛ Frontend)

## Content shape

- [ ] 6–10 concepts for a first guide; avoid >12 on wave-1 docs
- [ ] Each concept has Implements / Intent / Rules / Good / Bad (or equivalent)
- [ ] AI Decision Flow present for adapter extraction
- [ ] Related section includes ≥1 L0 link; L2 includes language guide link
- [ ] Domain README has a `## Published` (or other index section) entry

## Profiles and pipeline

- [ ] If profile-worthy: new `cursor-<stack>.yaml` with **explicit** knowledge list (no `extends`)
- [ ] `cursor-core.yaml` left unchanged unless explicitly approved
- [ ] `validate.py` PASS, 0 namespace/graph errors
- [ ] `assemble --verify` for affected profiles
- [ ] `dist/` not committed
