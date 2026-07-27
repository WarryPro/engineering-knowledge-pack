"""Generate machine-readable indexes for adapters."""

import json
import re
from pathlib import Path

from .namespace_validate import load_namespace_registry, namespace_key_for_concept

HEADING_TITLE_RE = re.compile(
    r"^### (EKP-(?:[A-Z]{2}\d{2}|P(?:0[1-9]|10))):\s*(.+)$",
    re.MULTILINE,
)


def _concept_title(node, concept_id):
    # type: (object, str) -> str
    for match in HEADING_TITLE_RE.finditer(node.body):
        if match.group(1) == concept_id:
            return match.group(2).strip()
    return node.title


def _knowledge_relative(path):
    # type: (str) -> str
    if path.startswith("knowledge/"):
        return path[len("knowledge/") :]
    return path


def generate_concept_index(nodes, registry=None):
    # type: (list, dict) -> dict
    if registry is None:
        registry = load_namespace_registry()

    index = {}
    for node in nodes:
        priority = node.frontmatter.get("adapter_priority")
        for concept_id in node.concept_ids:
            ns_key = namespace_key_for_concept(concept_id)
            entry = {
                "title": _concept_title(node, concept_id),
                "document": node.path,
                "namespace": ns_key,
                "domain": node.domain,
                "role": node.role,
                "severity": node.frontmatter.get("severity", ""),
            }
            if priority is not None:
                entry["adapter_priority"] = priority
            index[concept_id] = entry
    return index


def generate_knowledge_graph(nodes):
    # type: (list) -> dict
    graph_nodes = []
    edges = []

    for node in nodes:
        graph_nodes.append(
            {
                "id": node.path,
                "role": node.role,
                "domain": node.domain,
                "title": node.title,
            }
        )

        for dep in node.depends_on:
            edges.append(
                {
                    "from": _knowledge_relative(node.path),
                    "to": _knowledge_relative(dep),
                    "type": "depends_on",
                }
            )

        for rel in node.related:
            edges.append(
                {
                    "from": _knowledge_relative(node.path),
                    "to": _knowledge_relative(rel),
                    "type": "related",
                }
            )

    return {"nodes": graph_nodes, "edges": edges}


def generate_adapter_manifest(nodes):
    # type: (list) -> dict
    principles = set()
    rules = []

    for node in nodes:
        for principle_id in node.implements:
            principles.add(principle_id)

        priority = node.frontmatter.get("adapter_priority", "medium")
        for concept_id in node.concept_ids:
            rules.append(
                {
                    "concept": concept_id,
                    "source": node.path,
                    "priority": priority,
                }
            )

    return {
        "principles": sorted(principles),
        "rules": rules,
    }


def write_indexes(nodes, output_dir):
    # type: (list, Path) -> dict
    """Write all index files to output_dir. Returns paths written."""
    output_dir.mkdir(parents=True, exist_ok=True)
    written = {}

    concept_index = generate_concept_index(nodes)
    concept_path = output_dir / "concept-index.json"
    concept_path.write_text(
        json.dumps(concept_index, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    written["concept_index"] = str(concept_path)

    graph = generate_knowledge_graph(nodes)
    graph_path = output_dir / "knowledge-graph.json"
    graph_path.write_text(json.dumps(graph, indent=2) + "\n", encoding="utf-8")
    written["knowledge_graph"] = str(graph_path)

    manifest = generate_adapter_manifest(nodes)
    manifest_path = output_dir / "adapter-manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    written["adapter_manifest"] = str(manifest_path)

    return written
