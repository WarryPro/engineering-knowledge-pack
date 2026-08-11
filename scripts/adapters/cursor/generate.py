"""Generate Cursor .mdc rules from EKP profiles and knowledge documents."""

import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
ADAPTERS_DIR = SCRIPT_DIR.parent
if str(ADAPTERS_DIR) not in sys.path:
    sys.path.insert(0, str(ADAPTERS_DIR))

from common.extract import extract_concepts, extract_decision_flow
from common.paths import get_dist_path, get_repo_root
from common.profile_loader import load_profile_by_name
from common.selection import (
    load_generation_indexes,
    markdown_cache_for_profile,
    select_manifest_rules,
)

from cursor.mdc_writer import write_mdc_file
from cursor.normalize import (
    build_concept_rule,
    build_decision_flow_rule,
    build_foundation_rule,
    build_orchestrator_rule,
)

ORCHESTRATOR_PATH = "knowledge/ai/ai-assisted-development.md"
FOUNDATION_PATH = "knowledge/engineering/engineering-principles.md"

ADAPTER_NAME = "cursor"


def generate(profile_name="cursor-core", output_dir=None, profile=None, repo_root=None):
    # type: (str, Path, dict, Path) -> list
    """
    Generate Cursor .mdc rules for a profile.

    Pipeline: extract → selection → normalization → Cursor writer.

    Returns a sorted list of written file paths.
    """
    root = repo_root or get_repo_root()
    if profile is None:
        profile = load_profile_by_name(profile_name, repo_root=root)

    concept_index, manifest = load_generation_indexes(root / "dist")

    if output_dir is None:
        output_dir = get_dist_path() / profile_name / ADAPTER_NAME
    else:
        output_dir = Path(output_dir)

    if output_dir.exists():
        for existing in output_dir.glob("*.mdc"):
            existing.unlink()
    output_dir.mkdir(parents=True, exist_ok=True)

    knowledge_set = set(profile["knowledge"])
    get_markdown = markdown_cache_for_profile(root, profile["knowledge"])
    written = []

    if ORCHESTRATOR_PATH not in knowledge_set:
        raise ValueError("Profile must include orchestrator document.")

    orchestrator_flow = extract_decision_flow(
        get_markdown(ORCHESTRATOR_PATH), ORCHESTRATOR_PATH
    )
    if orchestrator_flow is None:
        raise ValueError("Orchestrator document missing AI Decision Flow.")

    orchestrator_rule = build_orchestrator_rule(orchestrator_flow)
    orchestrator_path = output_dir / orchestrator_rule.name
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
        foundation_path = output_dir / foundation_rule.name
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

        flow_rule = build_decision_flow_rule(flow, flow_sequence)
        flow_sequence += 1
        output_path = output_dir / flow_rule.name
        write_mdc_file(
            output_path,
            flow_rule,
            document_path,
            "{} Decision Flow".format(flow.title),
        )
        written.append(str(output_path))

    manifest_rules = select_manifest_rules(
        manifest,
        profile["knowledge"],
        profile["adapter_priorities"],
    )

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
        output_path = output_dir / concept_rule.name
        write_mdc_file(
            output_path,
            concept_rule,
            source_path,
            "{} — {}".format(concept.concept_id, concept.title),
            preferences=preferences or None,
        )
        written.append(str(output_path))

    return sorted(written)


# Backward-compatible alias for callers expecting load_profile on this module.
def load_profile(profile_path):
    # type: (Path) -> dict
    """Load a profile (delegates to common.profile_loader)."""
    from common.profile_loader import load_profile as _load_profile

    return _load_profile(profile_path)


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
