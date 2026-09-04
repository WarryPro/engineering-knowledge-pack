# EKP Evaluation Foundation

Repository evidence infrastructure for the **Evaluation MVP (`v0.17`)**.

This tree is **not** part of the Consumer CLI. There is no `ekp eval` command. Evaluation assets and tooling stay in the repository (`evals/**`, `scripts/evals/**`) and are **not** shipped in the installed Consumer wheel.

## Purpose

EKP's core product claim is that providing its engineering knowledge improves AI-assisted engineering decisions compared with the same model working without that knowledge.

Structural validation and Consumer lifecycle safety are necessary but not sufficient. Evaluation produces **evidence** of knowledge effect — not keyword matching and not LLM-as-judge as the sole authority.

## What v0.17 evaluates (and what it does not)

| In scope | Out of scope (later / deferred) |
|----------|----------------------------------|
| Knowledge-effect: same task, model, fixture, shared instruction; EKP context absent vs present | Cursor `.mdc` activation / IDE runtime behavior |
| Profile-**selected** engineering knowledge | Dumping all canonical documents into context |
| Human blind rubric scoring | Copilot / Antigravity / Claude runtime delivery |

v0.17 may claim evidence about **EKP's profile-selected engineering knowledge**. It must **not** claim it measured Cursor integration effectiveness or the effect of dumping all documentation into context.

## Fair baseline

Baseline and treatment share: model/configuration, sampling settings, shared system instruction, task, fixture, project files, fresh session, output limits, and **no external tools**.

Evidence-grade run metadata records `sampling.reasoning_effort` when the selected model/provider exposes reasoning control (`string` = explicit configured value; `null` = not applicable/unavailable). Pairing requires exact equality of reasoning effort (and other sampling fields) across baseline and treatment. This is configuration capture only — not a claim about any reference model run or evidence result.

The only intended independent variable is whether selection-equivalent EKP evaluation context is present.

## Treatment contract (selection-equivalent)

Treatment context is **not** “concatenate every Markdown file listed by the profile.”

Operational contract (**renderer version 2**, implemented):

```text
load profile
→ resolve composed knowledge documents
→ resolve profile adapter priorities
→ use canonical generation indexes
→ select_manifest_rules(...)
→ extract selected canonical semantic units
→ render them deterministically in adapter-neutral, identity-neutral form
```

Renderer versions:

```text
v1 = selection-equivalent initial renderer
v2 = selection-equivalent + identity-neutral presentation
```

Model-visible `context.md` must not expose EKP brand names or internal concept IDs; audit identity remains in `units.json` / `request.json`.

Reuse selection/extract/profile resolution from `scripts/adapters/common/` (for example `profile_loader`, `profile_resolve`, `selection`, `extract`). Do **not** depend on Cursor writers, Cursor frontmatter, activation metadata, or Cursor runtime.

Model-visible semantic categories:

```text
foundation-summary
foundation-principle
decision-flow
selected-concept
```

Semantic units appear **once**. Deterministic order: orchestrator flow → foundation summary → principles P01–P10 → remaining document flows (profile knowledge order) → remaining selected concepts (`select_manifest_rules` order). Missing selected concepts are a hard preparation failure.

## Preparation and run capture

Offline commands (no provider execution):

```bash
python scripts/validate/validate.py --generate-index
python scripts/evals/prepare.py --all
python scripts/evals/prepare.py --scenario <scenario-id>
python scripts/evals/import_run.py --package <prepared-condition-dir> --response <file> --execution <meta.json> --output <dir>
```

Generated request packages (gitignored) live under:

```text
dist/evals/prepared/<scenario-id>/{baseline,treatment}/
  request.json
  system_instruction.md
  participant.md
  context.md
  units.json
```

Contracts frozen for renderer v2:

- Baseline `context.md` is exactly **zero bytes**; `context_sha256` is the SHA-256 of empty bytes.
- Treatment `context.md` is the selected Engineering Context (not labeled as “EKP treatment”), with identity-neutral presentation (no product brand / internal concept IDs in model-visible text).
- `prompt_sha256` is SHA-256 of generated `participant.md` (normalized prompt **plus** lexicographic fixture serialization), not `prompt.md` alone.
- Baseline and treatment share identical system instruction and participant bytes; only context differs.
- Importer stores response bytes **exactly** as provided (no trim/rewrite) and binds `response_sha256` to those bytes.
- Condition, scenario, profile, EKP commit/version, and prompt/context hashes are taken from the prepared package and cannot be overridden by execution metadata.

Local tooling tests:

```bash
python -m unittest discover -s scripts/evals/tests -v
```

## Blind scoring and reporting (AT)

Offline tooling under `scripts/evals/` (no provider calls):

```text
imported condition-labelled runs
→ blind.py          (pair validation, salt/HMAC A/B assignment, rater packages)
→ human score sheets
→ score_import.py   (schema + binding + CF/preference checks; byte-preserving)
→ consensus.py      (condition reveal; improved/tied/regressed/disputed)
→ report.py         (deterministic report.md + report-summary.json)
```

Operator-private artifacts (`operator-private/mapping.json`, blinding salt) must stay hidden from raters during scoring. Rater packages contain participant/system/rubric/responses/templates only — never condition labels, context hashes, or EKP commit/version metadata.

Dual-rater evidence mode requires two distinct aliases (for example `rater-01` / `rater-02`) and `--require-raters 2` before consensus. Disputed is a legitimate final state (pairwise disagreement or critical-failure set disagreement). Absolute dimension disagreements alone do not force dispute.

AT implements this pipeline against **synthetic test data only**. It does **not** create `evals/evidence/**`, real model responses, or a published reference evidence pack (that remains AU).

Example synthetic flow:

```bash
python scripts/evals/blind.py --runs <runs-dir> --output <blind-dir> --salt <hex-for-tests>
python scripts/evals/score_import.py --score <sheet.yaml> --mapping <mapping.json> --output <scores-dir>
python scripts/evals/consensus.py --mapping <mapping.json> --scores <scores-dir> --output <consensus-dir> --require-raters 2
python scripts/evals/report.py --consensus <consensus-dir>/consensus --output <report-dir> \
  --evaluation-id <id> --ekp-version 0.17.0.dev0 --ekp-commit <sha> --model-config-id <id>
```

## Shared system instruction

Both conditions receive the exact same file: [`shared/system_instruction.md`](shared/system_instruction.md).

It is intentionally neutral. It must not encode EKP principles, concept IDs, or rubric hints.

## Prompt / rubric separation

| Artifact | Audience |
|----------|----------|
| `prompt.md` | Participant-visible task only |
| `rubric.yaml` | Evaluator-only |

Prompts must not contain critical-failure lists, score scales, desired outcomes, or EKP concept IDs. Rubrics never enter the model request.

## Provider-neutral execution

```text
offline prepare → execution request package
→ external model/provider execution
→ import response record
→ blind human scoring
→ report
```

No provider SDK is required in evaluation tooling. Live model calls are **not** part of CI.

## Session and tools

Evidence execution uses a **fresh session per response**. Never run baseline and treatment in the same conversation. MVP mode: **no external tools** (no browse/search/code execution asymmetry).

## Evidence-grade repetition

Default evidence protocol:

```text
8 scenarios × 2 conditions × 3 replicates = 48 responses / model configuration
```

That yields **24 blind pairs per rater**. With **2 independent raters**, about **48 pair ratings**. Rough human cost: ~8–15 minutes per pair → about **6.4–12 rater-hours** (order-of-magnitude only).

Smoke runs may use fewer replicates or scenarios. Release evidence uses the three-replicate protocol unless a later authorization changes it.

## Blind dual-rater model

Release evidence uses **two independent blind raters**. Each scores Response A/B with absolute dimension scores (0–3), critical failures, pairwise preference (`A` / `B` / `tie`), and a reason.

Score sheets must **not** contain condition labels (`baseline` / `treatment`).

## Pairwise consensus after reveal

| Consensus | Outcome |
|-----------|---------|
| Both prefer treatment | `improved` |
| Both prefer baseline | `regressed` |
| Both prefer tie | `tied` |
| Disagreement on preference **or** material critical-failure disagreement | `disputed` |

Do not average preferences into a fake consensus. Absolute scores support interpretation; they do not override pairwise consensus.

Optional adjudication may record a separate artifact while preserving original rater records. Adjudication is not required to erase all disputed cases.

Primary reporting shows **per-replicate** outcomes and **per-scenario replicate distributions** (for example `2 improved / 0 tied / 1 disputed / 0 regressed`). Do **not** collapse a scenario to a single winner via a hidden majority formula unless an explicit secondary contract is later defined.

Preferred L1 claim form:

> On evaluation set X using model/configuration Y, across N paired replicates, treatment produced I improved, T tied, R regressed, and D disputed outcomes under blind human scoring.

Then show per-scenario distributions. Avoid “EKP improved 6 of 8 scenarios” without an explicit scenario-level classification contract.

## Public L1 evidence inspectability

Claim **Level 1** requires a public evidence pack that includes:

- exact raw model response text used for scoring
- response SHA-256
- run metadata
- score references bound to those hashes

Hashes alone plus a private archive pointer are **insufficient** for L1. Providers that forbid public retention may be used experimentally but cannot be the sole L1 reference.

Before committing raw outputs: human privacy review (no secrets, customer data, PII, or sensitive paths). Do not silently edit a scored response. Sanitization, if ever needed, is a distinct artifact with an explicit transformation record — never pretend a sanitized hash is the original.

Baseline `context_sha256` is the SHA-256 of **empty bytes** (`e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`). Treatment uses the SHA-256 of the exact rendered context bytes.

## Authored / captured / generated

| Class | Examples |
|-------|----------|
| Authored | scenarios, prompts, rubrics, fixtures, schemas, shared instruction |
| Captured | model responses, run metadata, human score sheets |
| Generated | paired tables, Markdown/JSON reports (regenerable) |

## Context-size confound

Treatment adds tokens. Apparent gains may partly reflect instruction volume. Reports must record baseline/treatment sizes where available and disclose the confound. Do **not** invent token-normalized scores.

## Claim levels

| Level | Meaning |
|-------|---------|
| **L0** | Evaluation infrastructure exists (schemas, tooling, scenarios, offline validation) |
| **L1** | Public paired real-model evidence with inspectable responses and blind human scoring |

This foundation alone is **L0 in progress**. It does **not** authorize improvement claims.

## CI

CI validates evaluation artifacts **offline** and deterministically:

```bash
python scripts/evals/validate.py
```

No API keys, no paid model calls, no provider secrets.

Local structural tests:

```bash
python -m unittest discover -s scripts/evals/tests -v
```

## Versioning and immutability

Distinguish: scenario version, rubric version, evaluation protocol/tooling version, and EKP commit/version. Material scenario/rubric changes invalidate reinterpretation of prior scores under new definitions. Run records bind exact versions and hashes.

Published evidence is **immutable in meaning**. Corrections produce a **new evidence run and new report**, not silent rewriting of historical responses or scores.

## Report limitations (required later)

Future reports must disclose: public benchmark contamination risk, unequal context size, hosted-model drift, stochasticity, small sample size, human disagreement, and single-model scope when applicable. No statistical-significance theater on a small public set.

## Scenario layout (when authored)

```text
evals/scenarios/<scenario-id>/
  scenario.yaml
  prompt.md
  rubric.yaml
  fixture/          # optional miniature tree
```

Schemas live under [`schema/`](schema/). Real scenarios are authored in a later phase; zero scenarios is a valid foundation state.
