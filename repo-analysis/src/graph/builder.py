from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List

from symbols.indexer import stable_id, timestamp_now


def build_graph_artifact(symbol_index: Dict[str, object]) -> Dict[str, object]:
    repo_name = symbol_index["repo"]
    file_node_ids: Dict[str, str] = {}
    nodes: List[Dict[str, object]] = []
    edges: List[Dict[str, object]] = []
    reference_nodes: Dict[str, str] = {}

    repo_node_id = stable_id("repo", repo_name)
    nodes.append(
        {
            "node_id": repo_node_id,
            "kind": "repository",
            "repo": repo_name,
            "name": repo_name,
        }
    )

    for file_record in symbol_index["files"]:
        node_id = stable_id("file", repo_name, file_record["path"])
        file_node_ids[file_record["path"]] = node_id
        nodes.append(
            {
                "node_id": node_id,
                "kind": "file",
                "repo": repo_name,
                "path": file_record["path"],
                "crate": file_record["crate"],
                "module_path": file_record["module_path"],
                "language": file_record["language"],
            }
        )
        edges.append(
            make_edge(
                "CONTAINS",
                repo_node_id,
                node_id,
                repo_name,
                path=file_record["path"],
            )
        )

    for symbol in symbol_index["symbols"]:
        nodes.append(
            {
                "node_id": symbol["symbol_id"],
                "kind": symbol["kind"],
                "repo": repo_name,
                "path": symbol["path"],
                "name": symbol["name"],
                "qualified_name": symbol["qualified_name"],
                "crate": symbol["crate"],
                "module_path": symbol["module_path"],
                "language": symbol["language"],
            }
        )
        parent_node = symbol["container_symbol_id"] or file_node_ids[symbol["path"]]
        edge_type = "CONTAINS" if symbol["container_symbol_id"] else "DEFINES"
        edges.append(
            make_edge(
                edge_type,
                parent_node,
                symbol["symbol_id"],
                repo_name,
                path=symbol["path"],
            )
        )

        if symbol["kind"] == "impl" and symbol.get("impl_target"):
            target_node_id = ensure_reference_node(nodes, reference_nodes, repo_name, symbol["impl_target"], "type_ref")
            edges.append(
                make_edge(
                    "REFERENCES",
                    symbol["symbol_id"],
                    target_node_id,
                    repo_name,
                    path=symbol["path"],
                    role="impl_target",
                )
            )
        if symbol["kind"] == "impl" and symbol.get("impl_trait"):
            trait_node_id = ensure_reference_node(nodes, reference_nodes, repo_name, symbol["impl_trait"], "trait_ref")
            edges.append(
                make_edge(
                    "IMPLEMENTS",
                    symbol["symbol_id"],
                    trait_node_id,
                    repo_name,
                    path=symbol["path"],
                )
            )

    for import_record in symbol_index["imports"]:
        target_node_id = ensure_reference_node(
            nodes,
            reference_nodes,
            repo_name,
            import_record["target"],
            "module_ref",
        )
        source_node_id = import_record["container_symbol_id"] or file_node_ids[import_record["path"]]
        edges.append(
            make_edge(
                "IMPORTS",
                source_node_id,
                target_node_id,
                repo_name,
                path=import_record["path"],
                visibility=import_record["visibility"],
            )
        )

    return {
        "schema_version": "0.1.0",
        "repo": repo_name,
        "generated_at": timestamp_now(),
        "nodes": nodes,
        "edges": edges,
        "summary": {
            "nodes": len(nodes),
            "edges": len(edges),
        },
    }


def ensure_reference_node(
    nodes: List[Dict[str, object]],
    reference_nodes: Dict[str, str],
    repo_name: str,
    qualified_name: str,
    kind: str,
) -> str:
    node_id = reference_nodes.get(qualified_name)
    if node_id:
        return node_id

    node_id = stable_id("ref", repo_name, qualified_name)
    reference_nodes[qualified_name] = node_id
    nodes.append(
        {
            "node_id": node_id,
            "kind": kind,
            "repo": repo_name,
            "name": qualified_name,
            "qualified_name": qualified_name,
        }
    )
    return node_id


def make_edge(edge_type: str, source: str, target: str, repo_name: str, **metadata: object) -> Dict[str, object]:
    return {
        "edge_id": stable_id("edge", repo_name, edge_type, source, target, json.dumps(metadata, sort_keys=True)),
        "type": edge_type,
        "from": source,
        "to": target,
        "metadata": metadata,
    }


def write_graph_artifact(output_root: Path, repo_name: str, payload: Dict[str, object]) -> None:
    repo_output = output_root / repo_name
    repo_output.mkdir(parents=True, exist_ok=True)
    target = repo_output / "graph.json"
    with target.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, sort_keys=False)
        handle.write("\n")
