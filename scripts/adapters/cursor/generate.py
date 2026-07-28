"""Generate Cursor .mdc rules from EKP profiles and knowledge documents."""

import json
import re
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
ADAPTERS_DIR = SCRIPT_DIR.parent
if str(ADAPTERS_DIR) not in sys.path:
    sys.path.insert(0, str(ADAPTERS_DIR))

from common.extract import (
    CONCEPT_HEADING_RE,
    extract_concepts,
    extract_decision_flow,
)
from common.models import GeneratedRule
from common.paths import get_dist_path, get_repo_root

from cursor.mdc_writer import write_mdc_file
from cursor.naming import (
    concept_filename,
    decision_flow_filename,
    foundation_filename,
    orchestrator_filename,
)

ORCHESTRATOR_PATH = "knowledge/ai/ai-assisted-development.md"
FOUNDATION_PATH = "knowledge/engineering/engineering-principles.md"
BLOCKING_AUTO_APPLY = ("block", "hard block")


def _strip_yaml_comments(text):
    # type: (str) -> str
    lines = []
    for line in text.splitlines():
        if line.lstrip().startswith("#"):
            continue
        lines.append(line)
    return "\n".join(lines)


def _parse_yaml_list(block, key):
    # type: (str, str) -> list
    """Parse a simple YAML list for a top-level or nested key."""
    pattern = r"^" + re.escape(key) + r":\s*\n((?:[ \t]+-\s+.+\n?)+)"
    match = re.search(pattern, block, re.MULTILINE)
    if not match:
        return []

    values = []
    for line in match.group(1).splitlines():
        item_match = re.match(r"^[ \t]+-\s+(.+)$", line)
        if item_match:
            values.append(item_match.group(1).strip())
    return values


def load_profile(profile_path):
    # type: (Path) -> dict
    """Load a minimal EKP profile YAML file without external dependencies."""
    text = _strip_yaml_comments(profile_path.read_text(encoding="utf-8"))

    name_match = re.search(r"^name:\s*(\S+)", text, re.MULTILINE)
    if not name_match:
        raise ValueError("Profile missing name: {}".format(profile_path))

    description_match = re.search(
        r"^description:\s*(.+)$", text, re.MULTILINE
    )

    knowledge = re.findall(
        r"^[ \t]*-[ \t]+(knowledge/[^\s#]+\.md)\s*$", text, re.MULTILINE
    )

    adapter_block_match = re.search(
        r"^adapter:\s*\n(?P<body>(?:[ \t].+\n?)+)", text, re.MULTILINE
    )
    adapter_priorities = []
    if adapter_block_match:
        adapter_priorities = _parse_yaml_list(
            adapter_block_match.group("body"), "adapter_priority"
        )

    if not adapter_priorities:
        adapter_priorities = ["high"]

    return {
        "name": name_match.group(1),
        "description": description_match.group(1).strip()
        if description_match
        else "",
        "knowledge": knowledge,
        "adapter_priorities": adapter_priorities,
    }


def load_json(path):
    # type: (Path) -> dict
    """Load a JSON file from disk."""
    return json.loads(path.read_text(encoding="utf-8"))


def read_knowledge_document(repo_root, relative_path):
    # type: (Path, str) -> str
    """Read a knowledge markdown file."""
    return (repo_root / relative_path).read_text(encoding="utf-8")


def _extract_section(markdown, heading):
    # type: (str, str) -> str
    """Extract a level-2 markdown section body."""
    match = re.search(
        r"^## " + re.escape(heading) + r"\s*$", markdown, re.MULTILINE
    )
    if not match:
        return ""

    start = match.end()
    next_heading = re.search(r"^## ", markdown[start:], re.MULTILINE)
    end = start + next_heading.start() if next_heading else len(markdown)
    return markdown[start:end].strip()


def _enforcement_constraints(enforcement_rules):
    # type: (list) -> list
    """Convert adapter enforcement rows into constraint directives."""
    constraints = []
    for row in enforcement_rules:
        auto_apply = row.get("auto_apply", "").lower()
        if not any(token in auto_apply for token in BLOCKING_AUTO_APPLY):
            continue
        step = row.get("step", "Step")
        notes = row.get("notes", "")
        if notes:
            constraints.append(
                "Step {} — {}. {}".format(step, auto_apply, notes)
            )
        else:
            constraints.append("Step {} — {}.".format(step, auto_apply))
    return constraints


def _flow_directives(flow_text):
    # type: (str) -> list
    """Split a decision flow into directive lines."""
    directives = []
    for line in flow_text.splitlines():
        stripped = line.strip()
        if stripped:
            directives.append(stripped)
    return directives


def build_orchestrator_rule(flow):
    # type: (object) -> GeneratedRule
    """Build the always-on orchestrator GeneratedRule."""
    directives = _flow_directives(flow.decision_flow)
    constraints = _enforcement_constraints(flow.enforcement_rules)

    return GeneratedRule(
        name=orchestrator_filename(),
        description="EKP master AI decision flow — apply before any implementation",
        always_apply=True,
        directives=directives,
        constraints=constraints,
        references=[
            "`{}` — AI Decision Flow".format(flow.source_document),
            "`{}` — EKP-AI01 through EKP-AI12".format(flow.source_document),
        ],
    )


def build_foundation_rule(markdown, source_path):
    # type: (str, str) -> GeneratedRule
    """Build the always-on engineering principles GeneratedRule."""
    summary = _extract_section(markdown, "Summary")
    summary_lines = [
        line.strip()
        for line in summary.splitlines()
        if line.strip() and not line.strip().startswith("|")
    ]

    directives = []
    if summary_lines:
        directives.append(summary_lines[0])

    for match in CONCEPT_HEADING_RE.finditer(markdown):
        concept_id = match.group(1)
        if not concept_id.startswith("EKP-P"):
            continue

        title = match.group(2).strip()
        body_start = match.end()
        next_match = CONCEPT_HEADING_RE.search(markdown, body_start)
        body_end = next_match.start() if next_match else len(markdown)
        body = markdown[body_start:body_end].strip()

        first_paragraph = ""
        for line in body.splitlines():
            stripped = line.strip()
            if not stripped:
                continue
            if stripped.startswith("- ") or stripped.startswith("**"):
                break
            first_paragraph = stripped
            break

        directive = "{} — {}".format(concept_id, title)
        if first_paragraph:
            directive = "{} — {}".format(directive, first_paragraph)
        directives.append(directive)

    return GeneratedRule(
        name=foundation_filename(),
        description="EKP engineering principles — required decision framework",
        always_apply=True,
        directives=directives,
        constraints=[
            "Every technical decision must consider EKP-P01 through EKP-P10.",
            "Deviation requires documented rationale.",
        ],
        references=[
            "`{}` — Engineering Principles".format(source_path),
        ],
    )


def build_decision_flow_rule(flow):
    # type: (object) -> GeneratedRule
    """Build a document-level decision flow GeneratedRule."""
    directives = _flow_directives(flow.decision_flow)
    constraints = _enforcement_constraints(flow.enforcement_rules)

    return GeneratedRule(
        name=flow.document_path,
        description="EKP decision flow — {}".format(flow.title),
        always_apply=False,
        directives=directives,
        constraints=constraints,
        references=["`{}` — AI Decision Flow".format(flow.source_document)],
    )


def build_concept_rule(concept, concept_index_entry):
    # type: (object, dict) -> GeneratedRule
    """Build a concept-level GeneratedRule."""
    concept_id = concept.concept_id
    title = concept.title
    description = "{} — {}".format(concept_id, title)

    directives = []
    if concept.intent:
        directives.append(concept.intent)
    directives.extend(concept.rules)

    constraints = []
    preferences = []

    if concept.good_examples:
        preferences.append("Good: {}".format(concept.good_examples))
    if concept.bad_examples:
        preferences.append("Bad: {}".format(concept.bad_examples))

    if concept_id == "EKP-AI08":
        constraints = list(concept.rules)
        directives = [concept.intent] if concept.intent else []

    references = ["`{}` — {}".format(concept.source_document, concept_id)]
    if concept.implements:
        references.append("Implements: {}".format(", ".join(concept.implements)))

    severity = concept_index_entry.get("severity")
    if severity:
        references.append("Severity: {}".format(severity))

    return GeneratedRule(
        name=concept_filename(concept_id, title),
        description=description,
        always_apply=False,
        directives=directives,
        constraints=constraints,
        references=references,
    ), preferences


def generate(profile_name="cursor-core", output_dir=None):
    # type: (str, Path) -> list
    """
    Generate Cursor .mdc rules for a profile.

    Returns a sorted list of written file paths.
    """
    repo_root = get_repo_root()
    profile_path = repo_root / "profiles" / "{}.yaml".format(profile_name)
    profile = load_profile(profile_path)

    concept_index = load_json(get_dist_path() / "concept-index.json")
    manifest = load_json(get_dist_path() / "adapter-manifest.json")

    if output_dir is None:
        output_dir = get_dist_path() / profile_name / "cursor"
    else:
        output_dir = Path(output_dir)

    if output_dir.exists():
        for existing in output_dir.glob("*.mdc"):
            existing.unlink()
    output_dir.mkdir(parents=True, exist_ok=True)

    knowledge_set = set(profile["knowledge"])
    priorities = set(profile["adapter_priorities"])
    markdown_cache = {}
    written = []

    def get_markdown(path):
        # type: (str) -> str
        if path not in markdown_cache:
            markdown_cache[path] = read_knowledge_document(repo_root, path)
        return markdown_cache[path]

    if ORCHESTRATOR_PATH not in knowledge_set:
        raise ValueError("Profile must include orchestrator document.")

    orchestrator_flow = extract_decision_flow(
        get_markdown(ORCHESTRATOR_PATH), ORCHESTRATOR_PATH
    )
    if orchestrator_flow is None:
        raise ValueError("Orchestrator document missing AI Decision Flow.")

    orchestrator_rule = build_orchestrator_rule(orchestrator_flow)
    orchestrator_path = output_dir / orchestrator_filename()
    write_mdc_file(
        orchestrator_path,
        orchestrator_rule,
        ORCHESTRATOR_PATH,
        "EKP AI Orchestrator",
    )
    written.append(str(orchestrator_path))

    if FOUNDATION_PATH in knowledge_set:
        foundation_markdown = get_markdown(FOUNDATION_PATH)
        foundation_rule = build_foundation_rule(
            foundation_markdown, FOUNDATION_PATH
        )
        foundation_path = output_dir / foundation_filename()
        write_mdc_file(
            foundation_path,
            foundation_rule,
            FOUNDATION_PATH,
            "EKP Engineering Principles",
        )
        written.append(str(foundation_path))

    flow_sequence = 10
    for document_path in profile["knowledge"]:
        if document_path in (ORCHESTRATOR_PATH, FOUNDATION_PATH):
            continue

        flow = extract_decision_flow(get_markdown(document_path), document_path)
        if flow is None:
            continue

        flow_rule = build_decision_flow_rule(flow)
        filename = decision_flow_filename(document_path, flow_sequence)
        flow_sequence += 1
        output_path = output_dir / filename
        write_mdc_file(
            output_path,
            flow_rule,
            document_path,
            "{} Decision Flow".format(flow.title),
        )
        written.append(str(output_path))

    manifest_rules = [
        entry
        for entry in manifest.get("rules", [])
        if entry.get("priority") in priorities
        and entry.get("source") in knowledge_set
    ]
    manifest_rules.sort(key=lambda entry: entry.get("concept", ""))

    for entry in manifest_rules:
        concept_id = entry["concept"]
        source_path = entry["source"]
        concepts = extract_concepts(get_markdown(source_path), source_path)
        concept = next(
            (item for item in concepts if item.concept_id == concept_id), None
        )
        if concept is None:
            continue

        index_entry = concept_index.get(concept_id, {})
        concept_rule, preferences = build_concept_rule(concept, index_entry)
        filename = concept_filename(concept.concept_id, concept.title)
        output_path = output_dir / filename
        write_mdc_file(
            output_path,
            concept_rule,
            source_path,
            "{} — {}".format(concept.concept_id, concept.title),
            preferences=preferences or None,
        )
        written.append(str(output_path))

    return sorted(written)


def main(argv=None):
    # type: (list) -> int
    """CLI entry point for Cursor rule generation."""
    profile_name = "cursor-core"
    if argv is None:
        argv = sys.argv[1:]

    for index, arg in enumerate(argv):
        if arg == "--profile" and index + 1 < len(argv):
            profile_name = argv[index + 1]

    written = generate(profile_name=profile_name)
    print("Generated Cursor rules:")
    for path in written:
        print("  {}".format(path))
    return 0


if __name__ == "__main__":
    sys.exit(main())
