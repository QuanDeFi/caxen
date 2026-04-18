from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Dict, Iterable


def load_ryugraph_database(
    output_root: Path,
    repo_name: str,
    payload: Dict[str, object],
) -> Path:
    repo_output = output_root / repo_name
    repo_output.mkdir(parents=True, exist_ok=True)
    target = repo_output / "graph.db"
    if target.exists():
        target.unlink()

    with sqlite3.connect(target) as connection:
        cursor = connection.cursor()
        cursor.executescript(
            """
            CREATE TABLE metadata (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );

            CREATE TABLE nodes (
                node_id TEXT PRIMARY KEY,
                kind TEXT NOT NULL,
                repo TEXT NOT NULL,
                path TEXT,
                name TEXT,
                qualified_name TEXT,
                metadata_json TEXT NOT NULL
            );

            CREATE TABLE edges (
                edge_id TEXT PRIMARY KEY,
                type TEXT NOT NULL,
                source_node_id TEXT NOT NULL,
                target_node_id TEXT NOT NULL,
                path TEXT,
                metadata_json TEXT NOT NULL
            );

            CREATE TABLE symbol_summary_cache (
                node_id TEXT PRIMARY KEY,
                incoming_counts_json TEXT NOT NULL,
                outgoing_counts_json TEXT NOT NULL,
                direct_calls_json TEXT NOT NULL,
                reads_json TEXT NOT NULL,
                writes_json TEXT NOT NULL,
                refs_json TEXT NOT NULL,
                statements_json TEXT NOT NULL
            );

            CREATE TABLE neighbor_cache (
                node_id TEXT PRIMARY KEY,
                outgoing_edges_json TEXT NOT NULL,
                incoming_edges_json TEXT NOT NULL
            );

            CREATE INDEX idx_nodes_kind ON nodes(kind);
            CREATE INDEX idx_nodes_path ON nodes(path);
            CREATE INDEX idx_nodes_qname ON nodes(qualified_name);
            CREATE INDEX idx_edges_type ON edges(type);
            CREATE INDEX idx_edges_source ON edges(source_node_id);
            CREATE INDEX idx_edges_target ON edges(target_node_id);
            CREATE INDEX idx_edges_path ON edges(path);
            CREATE INDEX idx_symbol_summary_cache_node_id ON symbol_summary_cache(node_id);
            CREATE INDEX idx_neighbor_cache_node_id ON neighbor_cache(node_id);
            """
        )
        cursor.executemany(
            "INSERT INTO metadata(key, value) VALUES (?, ?)",
            [
                ("schema_version", str(payload["schema_version"])),
                ("repo", str(payload["repo"])),
                ("generated_at", str(payload["generated_at"])),
                ("summary_json", json.dumps(payload.get("summary", {}))),
                ("graph_backend", "sqlite_graph"),
            ],
        )
        cursor.executemany(
            """
            INSERT INTO nodes(node_id, kind, repo, path, name, qualified_name, metadata_json)
            VALUES (:node_id, :kind, :repo, :path, :name, :qualified_name, :metadata_json)
            """,
            dedupe_rows([flatten_node_row(row) for row in payload.get("nodes", [])], key="node_id"),
        )
        cursor.executemany(
            """
            INSERT INTO edges(edge_id, type, source_node_id, target_node_id, path, metadata_json)
            VALUES (:edge_id, :type, :source_node_id, :target_node_id, :path, :metadata_json)
            """,
            dedupe_rows([flatten_edge_row(row) for row in payload.get("edges", [])], key="edge_id"),
        )
        cursor.executemany(
            """
            INSERT INTO symbol_summary_cache(
                node_id,
                incoming_counts_json,
                outgoing_counts_json,
                direct_calls_json,
                reads_json,
                writes_json,
                refs_json,
                statements_json
            )
            VALUES(
                :node_id,
                :incoming_counts_json,
                :outgoing_counts_json,
                :direct_calls_json,
                :reads_json,
                :writes_json,
                :refs_json,
                :statements_json
            )
            """,
            build_symbol_summary_cache_rows(payload),
        )
        cursor.executemany(
            """
            INSERT INTO neighbor_cache(
                node_id,
                outgoing_edges_json,
                incoming_edges_json
            )
            VALUES(
                :node_id,
                :outgoing_edges_json,
                :incoming_edges_json
            )
            """,
            build_neighbor_cache_rows(payload),
        )
        connection.commit()

    write_graph_manifest(repo_output, payload)
    for filename in ("graph.json", "ryugraph.json"):
        try:
            (repo_output / filename).unlink()
        except FileNotFoundError:
            pass
    return target


def write_graph_manifest(repo_output: Path, payload: Dict[str, object]) -> None:
    manifest = {
        "schema_version": str(payload.get("schema_version") or ""),
        "repo": str(payload.get("repo") or ""),
        "generated_at": str(payload.get("generated_at") or ""),
        "graph_backend": "sqlite_graph",
        "artifacts": {
            "graph_db": "graph.db",
        },
        "summary": payload.get("summary", {}),
        "features": {
            "symbol_summary_cache": True,
            "neighbor_cache": True,
            "json_exports": False,
        },
    }
    target = repo_output / "graph_manifest.json"
    target.write_text(json.dumps(manifest, indent=2, sort_keys=False) + "\n", encoding="utf-8")


def flatten_node_row(row: Dict[str, object]) -> Dict[str, object]:
    metadata = dict(row)
    for key in ("node_id", "kind", "repo", "path", "name", "qualified_name"):
        metadata.pop(key, None)
    return {
        "node_id": row["node_id"],
        "kind": row["kind"],
        "repo": row["repo"],
        "path": row.get("path"),
        "name": row.get("name"),
        "qualified_name": row.get("qualified_name"),
        "metadata_json": json.dumps(metadata),
    }


def flatten_edge_row(row: Dict[str, object]) -> Dict[str, object]:
    metadata = dict(row.get("metadata", {}))
    return {
        "edge_id": row["edge_id"],
        "type": row["type"],
        "source_node_id": row["from"],
        "target_node_id": row["to"],
        "path": metadata.get("path"),
        "metadata_json": json.dumps(metadata),
    }


def dedupe_rows(rows: list[Dict[str, object]], *, key: str) -> list[Dict[str, object]]:
    deduped: list[Dict[str, object]] = []
    seen = set()
    for row in rows:
        row_key = row[key]
        if row_key in seen:
            continue
        seen.add(row_key)
        deduped.append(row)
    return deduped


NON_SYMBOL_NODE_KINDS = {
    "repository",
    "directory",
    "file",
    "package",
    "dependency",
    "test",
    "statement",
    "project_summary",
    "package_summary",
    "directory_summary",
    "file_summary",
    "symbol_summary",
    "module_ref",
    "symbol_ref",
    "trait_ref",
    "type_ref",
}


def build_symbol_summary_cache_rows(payload: Dict[str, object]) -> Iterable[Dict[str, object]]:
    node_by_id = {node["node_id"]: node for node in payload.get("nodes", [])}
    outgoing = {}
    incoming = {}
    for edge in payload.get("edges", []):
        outgoing.setdefault(edge["from"], []).append(edge)
        incoming.setdefault(edge["to"], []).append(edge)
    for node in payload.get("nodes", []):
        node_id = str(node.get("node_id") or "")
        if not node_id or str(node.get("kind") or "") in NON_SYMBOL_NODE_KINDS:
            continue
        yield {
            "node_id": node_id,
            "incoming_counts_json": json.dumps(edge_counter(incoming.get(node_id, []))),
            "outgoing_counts_json": json.dumps(edge_counter(outgoing.get(node_id, []))),
            "direct_calls_json": json.dumps(count_edge_targets(outgoing.get(node_id, []), node_by_id, "CALLS")),
            "reads_json": json.dumps(count_edge_targets(outgoing.get(node_id, []), node_by_id, "READS")),
            "writes_json": json.dumps(count_edge_targets(outgoing.get(node_id, []), node_by_id, "WRITES")),
            "refs_json": json.dumps(count_edge_targets(outgoing.get(node_id, []), node_by_id, "REFS", "REFERENCES")),
            "statements_json": json.dumps(statement_targets(outgoing.get(node_id, []), node_by_id)),
        }


def build_neighbor_cache_rows(payload: Dict[str, object]) -> Iterable[Dict[str, object]]:
    node_by_id = {node["node_id"]: node for node in payload.get("nodes", [])}
    outgoing = {}
    incoming = {}
    for edge in payload.get("edges", []):
        outgoing.setdefault(edge["from"], []).append(edge)
        incoming.setdefault(edge["to"], []).append(edge)
    for node in payload.get("nodes", []):
        node_id = str(node.get("node_id") or "")
        if not node_id:
            continue
        yield {
            "node_id": node_id,
            "outgoing_edges_json": json.dumps(
                [
                    edge_to_cache_entry(edge, node_by_id.get(str(edge.get("to") or "")))
                    for edge in outgoing.get(node_id, [])
                    if edge_to_cache_entry(edge, node_by_id.get(str(edge.get("to") or ""))) is not None
                ]
            ),
            "incoming_edges_json": json.dumps(
                [
                    edge_to_cache_entry(edge, node_by_id.get(str(edge.get("from") or "")))
                    for edge in incoming.get(node_id, [])
                    if edge_to_cache_entry(edge, node_by_id.get(str(edge.get("from") or ""))) is not None
                ]
            ),
        }


def edge_counter(edges: Iterable[Dict[str, object]]) -> Dict[str, int]:
    counts: Dict[str, int] = {}
    for edge in edges:
        edge_type = str(edge.get("type") or "")
        counts[edge_type] = counts.get(edge_type, 0) + 1
    return dict(sorted(counts.items()))


def count_edge_targets(edges: Iterable[Dict[str, object]], node_by_id: Dict[str, Dict[str, object]], *edge_types: str) -> list[str]:
    allowed = set(edge_types)
    values = []
    seen = set()
    for edge in edges:
        if str(edge.get("type") or "") not in allowed:
            continue
        target_id = str(edge.get("to") or "")
        target = node_by_id.get(target_id)
        if not target or target_id in seen:
            continue
        seen.add(target_id)
        values.append(target_id)
    return values


def statement_targets(edges: Iterable[Dict[str, object]], node_by_id: Dict[str, Dict[str, object]]) -> list[str]:
    values = []
    seen = set()
    for edge in edges:
        if str(edge.get("type") or "") != "CONTAINS":
            continue
        target_id = str(edge.get("to") or "")
        target = node_by_id.get(target_id)
        if not target or str(target.get("kind") or "") != "statement" or target_id in seen:
            continue
        seen.add(target_id)
        values.append(target_id)
    return values


def edge_to_cache_entry(edge: Dict[str, object], neighbor: Dict[str, object] | None) -> Dict[str, object] | None:
    if neighbor is None:
        return None
    return {
        "neighbor_id": neighbor["node_id"],
        "neighbor_kind": neighbor.get("kind"),
        "edge_type": edge.get("type"),
        "edge_metadata": dict(edge.get("metadata") or {}),
    }
