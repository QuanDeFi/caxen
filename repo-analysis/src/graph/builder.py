from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List

from symbols.indexer import stable_id, timestamp_now


def build_graph_artifact(symbol_index: Dict[str, object]) -> Dict[str, object]:
    repo_name = symbol_index["repo"]
    edge_counts: Dict[str, int] = {}
    file_node_ids: Dict[str, str] = {}
    nodes: List[Dict[str, object]] = []
    edges: List[Dict[str, object]] = []
    node_ids = set()
    reference_nodes: Dict[str, str] = {}

    repo_node_id = stable_id("repo", repo_name)
    append_node(
        nodes,
        node_ids,
        {
            "node_id": repo_node_id,
            "kind": "repository",
            "repo": repo_name,
            "name": repo_name,
        },
    )

    for file_record in symbol_index["files"]:
        node_id = stable_id("file", repo_name, file_record["path"])
        file_node_ids[file_record["path"]] = node_id
        append_node(
            nodes,
            node_ids,
            {
                "node_id": node_id,
                "kind": "file",
                "repo": repo_name,
                "path": file_record["path"],
                "crate": file_record["crate"],
                "module_path": file_record["module_path"],
                "language": file_record["language"],
            },
        )
        append_edge(
            edges,
            edge_counts,
            make_edge(
                "CONTAINS",
                repo_node_id,
                node_id,
                repo_name,
                path=file_record["path"],
            ),
        )

    for symbol in symbol_index["symbols"]:
        append_node(
            nodes,
            node_ids,
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
                "visibility": symbol["visibility"],
                "is_test": symbol["is_test"],
            },
        )
        parent_node = symbol["container_symbol_id"] or file_node_ids[symbol["path"]]
        edge_type = "CONTAINS" if symbol["container_symbol_id"] else "DEFINES"
        append_edge(
            edges,
            edge_counts,
            make_edge(
                edge_type,
                parent_node,
                symbol["symbol_id"],
                repo_name,
                path=symbol["path"],
            ),
        )

        if symbol["kind"] == "impl":
            target_node_id = resolve_target_node(
                nodes,
                node_ids,
                reference_nodes,
                repo_name,
                symbol.get("resolved_impl_target_symbol_id"),
                symbol.get("resolved_impl_target_qualified_name") or symbol.get("impl_target"),
                "type_ref",
            )
            if target_node_id:
                append_edge(
                    edges,
                    edge_counts,
                    make_edge(
                        "REFERENCES",
                        symbol["symbol_id"],
                        target_node_id,
                        repo_name,
                        path=symbol["path"],
                        role="impl_target",
                    ),
                )

            trait_node_id = resolve_target_node(
                nodes,
                node_ids,
                reference_nodes,
                repo_name,
                symbol.get("resolved_impl_trait_symbol_id"),
                symbol.get("resolved_impl_trait_qualified_name") or symbol.get("impl_trait"),
                "trait_ref",
            )
            if trait_node_id:
                append_edge(
                    edges,
                    edge_counts,
                    make_edge(
                        "IMPLEMENTS",
                        symbol["symbol_id"],
                        trait_node_id,
                        repo_name,
                        path=symbol["path"],
                    ),
                )

    for import_record in symbol_index["imports"]:
        target_node_id = resolve_target_node(
            nodes,
            node_ids,
            reference_nodes,
            repo_name,
            import_record.get("target_symbol_id"),
            import_record.get("target_qualified_name") or import_record.get("normalized_target") or import_record.get("target"),
            "module_ref",
        )
        if not target_node_id:
            continue
        source_node_id = import_record["container_symbol_id"] or file_node_ids[import_record["path"]]
        append_edge(
            edges,
            edge_counts,
            make_edge(
                "IMPORTS",
                source_node_id,
                target_node_id,
                repo_name,
                path=import_record["path"],
                visibility=import_record["visibility"],
            ),
        )

    for reference in symbol_index.get("references", []):
        target_node_id = resolve_target_node(
            nodes,
            node_ids,
            reference_nodes,
            repo_name,
            reference.get("target_symbol_id"),
            reference.get("target_qualified_name") or reference.get("qualified_name_hint"),
            "symbol_ref",
        )
        if not target_node_id:
            continue
        source_node_id = reference["container_symbol_id"] or file_node_ids[reference["path"]]
        edge_type = "CALLS" if reference["kind"] == "call" else "USES"
        append_edge(
            edges,
            edge_counts,
            make_edge(
                edge_type,
                source_node_id,
                target_node_id,
                repo_name,
                path=reference["path"],
                line=reference["span"]["start_line"],
                kind=reference["kind"],
            ),
        )

    return {
        "schema_version": "0.2.0",
        "repo": repo_name,
        "generated_at": timestamp_now(),
        "nodes": nodes,
        "edges": edges,
        "summary": {
            "nodes": len(nodes),
            "edges": len(edges),
            "edge_counts": [
                {
                    "type": edge_type,
                    "count": count,
                }
                for edge_type, count in sorted(edge_counts.items())
            ],
        },
    }


def append_edge(edges: List[Dict[str, object]], edge_counts: Dict[str, int], edge: Dict[str, object]) -> None:
    edges.append(edge)
    edge_counts[edge["type"]] = edge_counts.get(edge["type"], 0) + 1


def append_node(nodes: List[Dict[str, object]], node_ids: set[str], node: Dict[str, object]) -> None:
    if node["node_id"] in node_ids:
        return
    node_ids.add(node["node_id"])
    nodes.append(node)


def ensure_reference_node(
    nodes: List[Dict[str, object]],
    node_ids: set[str],
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
    append_node(
        nodes,
        node_ids,
        {
            "node_id": node_id,
            "kind": kind,
            "repo": repo_name,
            "name": qualified_name.split("::")[-1],
            "qualified_name": qualified_name,
        },
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


def resolve_target_node(
    nodes: List[Dict[str, object]],
    node_ids: set[str],
    reference_nodes: Dict[str, str],
    repo_name: str,
    target_symbol_id: str | None,
    target_qualified_name: str | None,
    fallback_kind: str,
) -> str | None:
    if target_symbol_id:
        return target_symbol_id
    if not target_qualified_name:
        return None
    return ensure_reference_node(nodes, node_ids, reference_nodes, repo_name, target_qualified_name, fallback_kind)


def write_graph_artifact(output_root: Path, repo_name: str, payload: Dict[str, object]) -> None:
    repo_output = output_root / repo_name
    repo_output.mkdir(parents=True, exist_ok=True)
    target = repo_output / "graph.json"
    with target.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, sort_keys=False)
        handle.write("\n")
