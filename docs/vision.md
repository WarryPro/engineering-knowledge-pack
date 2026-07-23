# Vision

## Why EKP exists

Software engineering knowledge is fragmented. It lives in blog posts, internal wikis, code review comments, architecture decision records, and the heads of experienced engineers. When that knowledge is needed—during design, implementation, review, or incident response—it is often unavailable, inconsistent, or reduced to vague platitudes.

Engineering Knowledge Pack (EKP) exists to collect, structure, and maintain that knowledge in a form that is:

- **Explicit** — decisions and practices are written down with reasoning, not assumed.
- **Actionable** — guidance can be applied during real engineering work.
- **Maintainable** — content has clear ownership, structure, and review expectations.
- **Portable** — not locked to a single tool, team, or vendor.

## The problem it solves

### Knowledge loss

When senior engineers leave a team, their judgment leaves with them. EKP captures the *why* behind practices—not just the *what*—so teams can onboard faster and make consistent decisions without rediscovering the same mistakes.

### Inconsistent standards

Without a shared reference, every engineer applies their own interpretation of "best practice." Code review becomes a debate of personal preference rather than alignment with agreed principles. EKP provides a neutral, versioned baseline that teams can adopt, adapt, or fork.

### AI assistants without engineering context

AI coding assistants are powerful at generating syntax but weak at engineering judgment. They default to generic patterns, miss project-specific constraints, and cannot distinguish between acceptable shortcuts and architectural violations unless given explicit context.

EKP supplies that context: security boundaries, naming conventions, error-handling philosophy, testing expectations, and technology-specific guidance written by engineers who understand the trade-offs.

### Tool churn

Teams that embed engineering knowledge directly into Cursor Rules, Copilot instructions, or Claude Skills create vendor lock-in. When the tool changes, the knowledge must be rewritten. EKP inverts this: knowledge is authored once in a tool-agnostic format; adapters transform it for each target platform.

## Why AI assistants need engineering context

An AI assistant without engineering context will:

- Propose architectures that violate established boundaries.
- Generate code that passes linting but fails review on design grounds.
- Miss security implications that are obvious to a senior engineer.
- Apply patterns from one stack incorrectly to another.
- Optimize for local correctness over system-wide maintainability.

Engineering context does not mean "more tokens." It means **structured, prioritized guidance** that reflects how experienced engineers actually think: principles first, constraints second, implementation patterns third.

EKP is designed to be consumed selectively. A profile for a Symfony backend team should not load Flutter widget guidance. An adapter should surface only what is relevant to the current task.

## Why this project is not tied to Cursor

Cursor is one consumer of engineering knowledge, not the authority that defines it. The same knowledge must serve:

- GitHub Copilot and Copilot Workspace
- Claude (Skills, Projects, system prompts)
- JetBrains AI Assistant
- Custom internal tooling and CI pipelines
- Human engineers reading documentation directly

Tying knowledge to Cursor Rules would:

1. **Couple content to a specific syntax** — Cursor rule formats evolve independently of engineering practices.
2. **Discourage contribution** — contributors who do not use Cursor would be excluded.
3. **Complicate testing** — there is no standard way to validate whether a Cursor rule correctly encodes a principle.
4. **Fragment the ecosystem** — each tool would need its own fork of the same ideas.

EKP keeps knowledge in plain markdown with a defined document structure. The `rules/` directory holds tool-specific outputs; the `scripts/` directory will hold transformation logic. Knowledge remains the stable core; adapters are replaceable edges.

## Guiding principles

1. **Knowledge before rules** — never author a rule without a knowledge document that justifies it.
2. **Reasoning over prescription** — explain trade-offs; avoid cargo-cult checklists.
3. **Small, focused documents** — one concern per file; compose via profiles.
4. **Open by default** — MIT licensed, community-driven, vendor-neutral.
