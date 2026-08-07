## Summary

<!-- What does this PR change and why? -->

## Type

- [ ] Knowledge document
- [ ] Profile
- [ ] Documentation (docs/)
- [ ] Tooling (scripts/, schema/)
- [ ] Other

## Checklist

- [ ] Follows the [style guide](docs/style-guide.md)
- [ ] Uses the correct template from `templates/`
- [ ] Single concern per knowledge document
- [ ] Frontmatter complete (`title`, `domain`, `tags`, `severity`, `applies_to`)
- [ ] No tool-specific syntax in knowledge documents
- [ ] Internal links resolve correctly
- [ ] Validation passes: `py -3 scripts/validate/validate.py`

## Governance

- [ ] Scope matches PR type (no unrelated changes)
- [ ] [Knowledge review checklist](templates/knowledge-review-checklist.md) completed (knowledge/profile/graph changes)
- [ ] Affected profiles: `assemble --verify` run locally (if profiles/knowledge changed)
- [ ] Graph / namespace changes reviewed per [governance.md](docs/governance.md)
- [ ] Documentation updated (README, roadmap, DEVELOPMENT as needed)
- [ ] `CHANGELOG.md` `[Unreleased]` updated (if user-visible)
- [ ] ADR filed when required (new domain, schema breaking, graph exception pattern, deprecation — see governance.md)

## Related issues

<!-- Link issues if applicable: Fixes #123 -->
