from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Dict


def write_graph_database(output_root: Path, repo_name: str, payload: Dict[str, object]) -> Path:
    repo_output = output_root / repo_name
    repo_output.mkdir(parents=True, exist_ok=True)
    target = repo_output / "graph.sqlite3"
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

            CREATE INDEX idx_nodes_kind ON nodes(kind);
            CREATE INDEX idx_nodes_path ON nodes(path);
            CREATE INDEX idx_nodes_qname ON nodes(qualified_name);
            CREATE INDEX idx_edges_type ON edges(type);
            CREATE INDEX idx_edges_source ON edges(source_node_id);
            CREATE INDEX idx_edges_target ON edges(target_node_id);
            CREATE INDEX idx_edges_path ON edges(path);
            """
        )
        cursor.executemany(
            "INSERT INTO metadata(key, value) VALUES (?, ?)",
            [
                ("schema_version", str(payload["schema_version"])),
                ("repo", str(payload["repo"])),
                ("generated_at", str(payload["generated_at"])),
                ("summary_json", json.dumps(payload.get("summary", {}))),
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
        connection.commit()

    return target


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
