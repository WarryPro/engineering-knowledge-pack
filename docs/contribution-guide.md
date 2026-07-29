# Contribution Guide

How to contribute engineering knowledge, rules, profiles, and tooling to EKP.

## Who can contribute

Anyone with engineering experience to share. You do not need to use any specific AI tool. You do need to follow the [style guide](style-guide.md) and write content that includes reasoning, not just prescriptions.

## Contribution workflow

### 1. Propose (for significant changes)

Open an issue before writing if your contribution:

- Adds a new knowledge domain or subdirectory
- Introduces a new document template or metadata field
- Changes the adapter architecture or profile format
- Covers a controversial or team-specific practice presented as universal guidance

For straightforward additions (a new knowledge document in an existing domain), you may skip this step and go directly to a pull request.

### 2. Author

1. Identify the correct domain in `knowledge/` — read the domain `README.md` (see [folder-structure.md](folder-structure.md))
2. Copy the relevant template from `templates/`
3. Write the document following the [style guide](style-guide.md)
4. Place it in the correct directory:
   - Guides: `knowledge/<domain>/<topic>.md`
   - ADRs: `knowledge/architecture/decisions/adr-<number>-<topic>.md` (zero-padded number, e.g. `adr-0004-clean-code-position-in-knowledge-graph.md`)
   - Checklists: `knowledge/<domain>/checklists/<name>.md`
5. Run validation: `py -3 scripts/validate/validate.py` (see [`DEVELOPMENT.md`](../DEVELOPMENT.md))

### 3. Self-review

Use this checklist before opening a PR:

- [ ] Single concern per document
- [ ] Frontmatter complete (`title`, `domain`, `tags`, `severity`, `applies_to`)
- [ ] Summary, context, guidance, and trade-offs sections present
- [ ] No tool-specific syntax in knowledge documents
- [ ] Internal links use relative paths and resolve correctly
- [ ] No duplication of existing content (search `knowledge/` first)
- [ ] Tone is direct; no filler

### 4. Pull request

- Use a descriptive title: `Add knowledge: transaction boundary rules`
- Describe what the document covers and why it is needed
- Reference related issues if applicable
- Keep PRs focused: one document or one logical change per PR when possible

### 5. Review

Maintainers review for:

- **Accuracy** — is the engineering guidance correct?
- **Clarity** — can a mid-level engineer apply this?
- **Scope** — does it belong in this domain? Is it too broad or too narrow?
- **Structure** — does it follow templates and style guide?
- **Neutrality** — is it tool-agnostic and free of vendor bias?

## What to contribute

### Knowledge documents (primary)

The most valuable contribution. Write about practices you have applied, reviewed, or seen fail in production.

Good candidates:

- A pattern your team adopted with documented trade-offs
- A review criterion that catches real bugs
- An architectural boundary that prevented a class of problems
- A technology-specific convention with clear rationale

### Profiles

Compose existing knowledge into a context-specific bundle. Profiles do not introduce new guidance—they select and prioritize existing documents.

### Rules

Only after the corresponding knowledge document exists. Tool-specific rules are **generated** by adapters into `dist/<profile>/`—do not treat `rules/` as the deployable source. See [`adapter-architecture.md`](adapter-architecture.md).

### Scripts and adapters

Follow existing patterns in `scripts/`. New adapters must:

- Be deterministic (same input → same output)
- Document their input/output format
- Include at least a basic test or example run

### Examples

Demonstrate EKP usage with realistic (but anonymized) scenarios. Examples are not knowledge—they illustrate how knowledge is applied.

## What not to contribute

- **Filler or placeholder content** — no "TODO: add content here" documents
- **Tool-specific rules without knowledge backing** — rules must trace to a knowledge document
- **Opinion without reasoning** — "always use X" without explaining when and why
- **Duplicated content** — link to the canonical document instead
- **Secrets or internal identifiers** — anonymize company-specific details

## Document lifecycle

```
Draft → PR review → Merged → Maintained
```

### Maintenance expectations

- Knowledge documents are living documents, not write-once artifacts
- If a practice becomes outdated, update the document or mark it with an advisory severity
- Breaking changes to guidance (e.g., changing `required` to `advisory`) should be noted in CHANGELOG.md

## Branch naming

```
knowledge/<domain>-<topic>     # New knowledge document
fix/<description>              # Corrections to existing content
profile/<name>                 # New or updated profile
script/<description>           # Tooling changes
docs/<description>             # Meta-documentation changes
```

## Getting help

- Read [vision.md](vision.md) and [architecture.md](architecture.md) for project context
- Open an issue with the `question` label for guidance on where content belongs
- Reference existing documents in similar domains as models
