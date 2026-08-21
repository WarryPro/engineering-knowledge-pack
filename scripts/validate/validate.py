#!/usr/bin/env python3
"""
EKP validation CLI v2.3.

Validates knowledge documents, generates indexes, and supports incremental
validation tiers for scale.

Run from repository root: py -3 scripts/validate/validate.py

Dependencies: pip install -r scripts/validate/requirements.txt
Requires Python 3.6+.
"""

import argparse
import re
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from modules.adapter_validate import validate_adapter_metadata
from modules.adr_validate import validate_adr_index
from modules.concept_body_validate import validate_concept_body
from modules.concept_validate import validate_concepts
from modules.git_changes import (
    changed_knowledge_guides,
    get_changed_files,
    requires_full_graph_validation,
)
from modules.graph_validate import validate_graph
from modules.index_generate import write_indexes
from modules.lifecycle_validate import validate_lifecycle
from modules.models import DocumentNode
from modules.namespace_validate import validate_namespaces
from modules.principle_validate import validate_principles
from modules.profile_validate import validate_profiles
from modules.readme_validate import validate_readmes
from modules.related_validate import validate_related_paths
from modules.reporting import ValidationResult
from modules.reports import (
    print_adapters_report,
    print_concepts_report,
    print_graph_report,
    print_principle_report,
)
from modules.scale_report import print_scale_report
from modules.schema_validate import validate_schema

REPO_ROOT = Path(__file__).resolve().parents[2]
KNOWLEDGE_DIR = REPO_ROOT / "knowledge"
PROFILES_DIR = REPO_ROOT / "profiles"
DIST_DIR = REPO_ROOT / "dist"

REQUIRED_FIELDS = {"title", "domain", "tags", "severity", "applies_to"}
VALID_SEVERITIES = {"required", "recommended", "advisory"}
VALID_DOMAINS = {
    "engineering", "architecture", "php", "symfony", "flutter",
    "typescript", "frontend", "nativescript", "database", "security", "testing",
    "performance", "devops", "ai",
}

LINK_RE = re.compile(r"\[[^\]]+\]\(([^)]+)\)")
SKIP_LINK_PREFIXES = ("http://", "https://", "mailto:", "#")

TIERS = ("structural", "graph", "registry", "all")


def collect_knowledge_files():
    # type: () -> list
    return sorted(
        p for p in KNOWLEDGE_DIR.rglob("*.md")
        if p.name != "README.md" and not p.name.startswith("adr-")
    )


def validate_legacy_fields(node):
    # type: (DocumentNode) -> list
    errors = []
    rel = node.path
    fm = node.frontmatter

    missing = REQUIRED_FIELDS - set(fm.keys())
    if missing:
        errors.append(
            "{}: missing frontmatter fields: {}".format(rel, ", ".join(sorted(missing)))
        )

    domain = fm.get("domain")
    if isinstance(domain, str):
        if domain not in VALID_DOMAINS:
            errors.append("{}: invalid domain '{}'".format(rel, domain))
        expected = Path(rel).relative_to("knowledge").parts[0]
        if domain != expected and not (
            domain == "architecture" and "decisions" in Path(rel).parts
        ):
            errors.append(
                "{}: domain '{}' does not match directory '{}'".format(
                    rel, domain, expected
                )
            )

    severity = fm.get("severity")
    if isinstance(severity, str) and severity not in VALID_SEVERITIES:
        errors.append("{}: invalid severity '{}'".format(rel, severity))

    tags = fm.get("tags")
    if isinstance(tags, list) and len(tags) == 0:
        errors.append("{}: tags must contain at least one item".format(rel))

    applies_to = fm.get("applies_to")
    if isinstance(applies_to, list) and len(applies_to) == 0:
        errors.append("{}: applies_to must contain at least one item".format(rel))

    return errors


def validate_markdown_links(node):
    # type: (DocumentNode) -> list
    errors = []
    path = REPO_ROOT / node.path

    for link_match in LINK_RE.finditer(node.body):
        target = link_match.group(1).strip()
        if target.startswith(SKIP_LINK_PREFIXES):
            continue
        resolved = (path.parent / target).resolve()
        if not resolved.exists():
            errors.append("{}: broken link to '{}'".format(node.path, target))

    return errors


def build_nodes(knowledge_files, result):
    # type: (list, ValidationResult) -> list
    nodes = []
    for path in knowledge_files:
        node, errors = DocumentNode.from_path(path, REPO_ROOT)
        if errors:
            result.add_errors(errors)
            continue
        if node is not None:
            nodes.append(node)
    return nodes


def load_nodes(result):
    # type: (ValidationResult) -> list
    return build_nodes(collect_knowledge_files(), result)


def _runs_tier(tier, name):
    # type: (str, str) -> bool
    if tier == "all":
        return True
    return tier == name


def run_structural(nodes, result, node_filter=None):
    # type: (list, ValidationResult, set) -> None
    targets = nodes
    if node_filter is not None:
        targets = [node for node in nodes if node.path in node_filter]

    for node in targets:
        result.add_errors(validate_legacy_fields(node))
        result.add_errors(validate_schema(node.frontmatter, node.path))
        lifecycle_errors, lifecycle_warnings = validate_lifecycle([node])
        result.add_errors(lifecycle_errors)
        result.add_warnings(lifecycle_warnings)
        result.add_errors(validate_markdown_links(node))


def run_graph(nodes, result, include_namespace_registry=False):
    # type: (list, ValidationResult, bool) -> None
    graph_errors, graph_warnings = validate_graph(nodes, REPO_ROOT)
    result.add_errors(graph_errors)
    result.add_warnings(graph_warnings)

    if include_namespace_registry:
        ns_errors, ns_warnings = validate_namespaces(nodes)
        result.add_errors(ns_errors)
        result.add_warnings(ns_warnings)


def run_registry(
    nodes,
    result,
    strict_adapters=False,
    node_filter=None,
    body_filter=None,
    incremental=False,
):
    # type: (list, ValidationResult, bool, set, set, bool) -> None
    result.add_errors(validate_concepts(nodes))

    related_targets = nodes
    if node_filter is not None:
        related_targets = [node for node in nodes if node.path in node_filter]
    result.add_errors(validate_related_paths(related_targets, REPO_ROOT))

    ns_errors, ns_warnings = validate_namespaces(nodes)
    result.add_errors(ns_errors)
    result.add_warnings(ns_warnings)

    body_targets = nodes
    if body_filter is not None:
        body_targets = [node for node in nodes if node.path in body_filter]
    result.add_warnings(validate_concept_body(body_targets))

    adapter_targets = nodes
    if node_filter is not None:
        adapter_targets = [node for node in nodes if node.path in node_filter]
    adapter_errors, adapter_warnings = validate_adapter_metadata(
        adapter_targets, strict_adapters=strict_adapters
    )
    result.add_errors(adapter_errors)
    result.add_warnings(adapter_warnings)

    if incremental:
        return

    principle_errors, principle_warnings = validate_principles(nodes)
    result.add_errors(principle_errors)
    result.add_warnings(principle_warnings)

    doc_paths = [node.path for node in nodes]
    readme_errors, readme_warnings = validate_readmes(REPO_ROOT, doc_paths)
    result.add_errors(readme_errors)
    result.add_warnings(readme_warnings)

    result.add_errors(validate_profiles(REPO_ROOT, PROFILES_DIR))
    result.add_errors(validate_adr_index(REPO_ROOT))


def run_validation(
    strict=False,
    tier="all",
    changed_only=False,
    strict_adapters=False,
):
    # type: (bool, str, bool, bool) -> int
    if not KNOWLEDGE_DIR.exists():
        print("No knowledge/ directory found.", file=sys.stderr)
        return 1

    knowledge_files = collect_knowledge_files()
    result = ValidationResult()

    if not knowledge_files:
        print("No knowledge documents to validate (foundation phase).")
        return 0

    nodes = build_nodes(knowledge_files, result)
    if not nodes:
        return result.print_report(strict=strict)

    node_filter = None
    body_filter = None
    incremental = False
    run_graph_tier = _runs_tier(tier, "graph")
    run_registry_tier = _runs_tier(tier, "registry")
    run_structural_tier = _runs_tier(tier, "structural")

    if changed_only:
        change_set = get_changed_files(REPO_ROOT)
        if change_set is None:
            print(
                "Warning: git unavailable; running full validation.",
                file=sys.stderr,
            )
        else:
            guides = changed_knowledge_guides(change_set)
            full_graph = requires_full_graph_validation(change_set)
            if not guides and not full_graph:
                print("Validation passed.")
                return 0

            if guides:
                node_filter = guides
                body_filter = guides

            if not full_graph:
                run_graph_tier = False
                incremental = True
            elif not guides:
                node_filter = None
                body_filter = None

    if run_structural_tier:
        run_structural(nodes, result, node_filter=node_filter)

    if run_graph_tier:
        include_registry = tier == "graph"
        run_graph(nodes, result, include_namespace_registry=include_registry)

    if run_registry_tier:
        run_registry(
            nodes,
            result,
            strict_adapters=strict_adapters,
            node_filter=node_filter if changed_only else None,
            body_filter=body_filter if changed_only else None,
            incremental=incremental,
        )

    if result.passed and not result.warnings:
        print("Validation passed.")
        return 0

    return result.print_report(strict=strict)


def run_generate_index(output_dir=None):
    # type: (Path) -> int
    result = ValidationResult()
    nodes = load_nodes(result)
    if result.errors:
        return result.print_report(strict=False)

    target = output_dir or DIST_DIR
    written = write_indexes(nodes, target)
    print("Generated indexes:")
    for key in sorted(written.keys()):
        print("  {}".format(written[key]))
    return 0


def run_report(report_name):
    # type: (str) -> int
    result = ValidationResult()
    nodes = load_nodes(result)

    if result.errors:
        return result.print_report(strict=False)

    if report_name == "principles":
        print_principle_report(nodes)
        return 0
    if report_name == "graph":
        print_graph_report(nodes)
        return 0
    if report_name == "concepts":
        print_concepts_report(nodes)
        return 0
    if report_name == "adapters":
        print_adapters_report(nodes)
        return 0
    if report_name == "scale":
        _, warnings = validate_adapter_metadata(nodes)
        body_warnings = validate_concept_body(nodes)
        print_scale_report(nodes, warnings + body_warnings)
        return 0

    print("Unknown report: {}".format(report_name), file=sys.stderr)
    return 1


def main():
    parser = argparse.ArgumentParser(description="Validate EKP knowledge documents")
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Treat warnings as errors (exit code 1)",
    )
    parser.add_argument(
        "--strict-adapters",
        action="store_true",
        help="Treat missing adapter_priority as error",
    )
    parser.add_argument(
        "--changed-only",
        action="store_true",
        help="Validate only git-changed files (graph full when needed)",
    )
    parser.add_argument(
        "--tier",
        choices=list(TIERS),
        default="all",
        help="Validation tier (default: all)",
    )
    parser.add_argument(
        "--generate-index",
        action="store_true",
        help="Generate dist/ indexes for adapters and exit",
    )
    parser.add_argument(
        "--report",
        choices=["principles", "graph", "concepts", "adapters", "scale"],
        help="Print a governance report and exit",
    )
    args = parser.parse_args()

    if args.generate_index:
        return run_generate_index()

    if args.report:
        return run_report(args.report)

    return run_validation(
        strict=args.strict,
        tier=args.tier,
        changed_only=args.changed_only,
        strict_adapters=args.strict_adapters,
    )


if __name__ == "__main__":
    sys.exit(main())
