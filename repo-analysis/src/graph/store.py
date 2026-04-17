from __future__ import annotations

import json
import sqlite3
from collections import Counter, defaultdict
from pathlib import Path
from typing import Dict, Iterable


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

    return target


def backfill_graph_query_cache(sqlite_path: Path) -> None:
    with sqlite3.connect(sqlite_path) as connection:
        connection.row_factory = sqlite3.Row
        cursor = connection.cursor()
        cursor.executescript(
            """
            CREATE TABLE IF NOT EXISTS symbol_summary_cache (
                node_id TEXT PRIMARY KEY,
                incoming_counts_json TEXT NOT NULL,
                outgoing_counts_json TEXT NOT NULL,
                direct_calls_json TEXT NOT NULL,
                reads_json TEXT NOT NULL,
                writes_json TEXT NOT NULL,
                refs_json TEXT NOT NULL,
                statements_json TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS neighbor_cache (
                node_id TEXT PRIMARY KEY,
                outgoing_edges_json TEXT NOT NULL,
                incoming_edges_json TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_symbol_summary_cache_node_id ON symbol_summary_cache(node_id);
            CREATE INDEX IF NOT EXISTS idx_neighbor_cache_node_id ON neighbor_cache(node_id);
            DELETE FROM symbol_summary_cache;
            DELETE FROM neighbor_cache;
            """
        )
        rows = list(build_symbol_summary_cache_rows_from_sqlite(connection))
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
            rows,
        )
        neighbor_rows = list(build_neighbor_cache_rows_from_sqlite(connection))
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
            neighbor_rows,
        )
        connection.commit()


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

CACHEABLE_NEIGHBOR_EDGE_TYPES = {
    "CALLS",
    "DECLARES",
    "DEFINES",
    "IMPLEMENTS",
    "IMPORTS",
    "INHERITS",
    "NEIGHBOR",
    "OVERRIDES",
    "READS",
    "REFS",
    "REFERENCES",
    "SUMMARIZED_BY",
    "TESTS",
    "USES",
    "USES_TYPE",
    "WRITES",
}
MAX_NEIGHBOR_CACHE_EDGES_PER_DIRECTION = 256


def build_symbol_summary_cache_rows(payload: Dict[str, object]) -> list[Dict[str, object]]:
    node_by_id = {node["node_id"]: node for node in payload.get("nodes", [])}
    outgoing: dict[str, list[dict[str, object]]] = defaultdict(list)
    incoming: dict[str, list[dict[str, object]]] = defaultdict(list)
    for edge in payload.get("edges", []):
        outgoing[edge["from"]].append(edge)
        incoming[edge["to"]].append(edge)
    for node_id in outgoing:
        outgoing[node_id].sort(key=edge_sort_key)
    for node_id in incoming:
        incoming[node_id].sort(key=edge_sort_key)

    rows = []
    for node in payload.get("nodes", []):
        if node.get("kind") in NON_SYMBOL_NODE_KINDS:
            continue
        node_id = str(node["node_id"])
        rows.append(
            {
                "node_id": node_id,
                "incoming_counts_json": json.dumps(edge_counter(incoming.get(node_id, [])), sort_keys=True),
                "outgoing_counts_json": json.dumps(edge_counter(outgoing.get(node_id, [])), sort_keys=True),
                "direct_calls_json": json.dumps(collect_edge_target_ids(outgoing.get(node_id, []), node_by_id, {"CALLS"})),
                "reads_json": json.dumps(collect_edge_target_ids(outgoing.get(node_id, []), node_by_id, {"READS"})),
                "writes_json": json.dumps(collect_edge_target_ids(outgoing.get(node_id, []), node_by_id, {"WRITES"})),
                "refs_json": json.dumps(collect_edge_target_ids(outgoing.get(node_id, []), node_by_id, {"REFS", "REFERENCES"})),
                "statements_json": json.dumps(collect_statement_ids(outgoing.get(node_id, []), node_by_id)),
            }
        )
    return rows


def build_neighbor_cache_rows(payload: Dict[str, object]) -> list[Dict[str, object]]:
    node_by_id = {node["node_id"]: node for node in payload.get("nodes", [])}
    outgoing: dict[str, list[dict[str, object]]] = defaultdict(list)
    incoming: dict[str, list[dict[str, object]]] = defaultdict(list)
    for edge in payload.get("edges", []):
        if str(edge["type"]) not in CACHEABLE_NEIGHBOR_EDGE_TYPES:
            continue
        outgoing[edge["from"]].append(edge)
        incoming[edge["to"]].append(edge)
    for node_id in outgoing:
        outgoing[node_id].sort(key=edge_sort_key)
    for node_id in incoming:
        incoming[node_id].sort(key=edge_sort_key)

    rows = []
    for node in payload.get("nodes", []):
        if node.get("kind") in NON_SYMBOL_NODE_KINDS:
            continue
        node_id = str(node["node_id"])
        rows.append(
            {
                "node_id": node_id,
                "outgoing_edges_json": json.dumps(
                    serialize_neighbor_edges(outgoing.get(node_id, []), node_by_id, direction="outgoing")
                ),
                "incoming_edges_json": json.dumps(
                    serialize_neighbor_edges(incoming.get(node_id, []), node_by_id, direction="incoming")
                ),
            }
        )
    return rows


def build_symbol_summary_cache_rows_from_sqlite(connection: sqlite3.Connection) -> Iterable[Dict[str, object]]:
    node_kind_by_id = {
        str(row["node_id"]): str(row["kind"])
        for row in connection.execute("SELECT node_id, kind FROM nodes")
    }
    seedable_ids = {node_id for node_id, kind in node_kind_by_id.items() if kind not in NON_SYMBOL_NODE_KINDS}

    incoming_counts: dict[str, Counter[str]] = defaultdict(Counter)
    outgoing_counts: dict[str, Counter[str]] = defaultdict(Counter)
    direct_calls: dict[str, list[str]] = defaultdict(list)
    reads: dict[str, list[str]] = defaultdict(list)
    writes: dict[str, list[str]] = defaultdict(list)
    refs: dict[str, list[str]] = defaultdict(list)
    statements: dict[str, list[str]] = defaultdict(list)

    for row in connection.execute(
        "SELECT type, source_node_id, target_node_id, path, metadata_json FROM edges ORDER BY type, path, edge_id"
    ):
        edge_type = str(row["type"])
        source_id = str(row["source_node_id"])
        target_id = str(row["target_node_id"])

        if source_id in seedable_ids:
            outgoing_counts[source_id][edge_type] += 1
        if target_id in seedable_ids:
            incoming_counts[target_id][edge_type] += 1

        if source_id in seedable_ids:
            if edge_type == "CALLS":
                append_unique_limited(direct_calls[source_id], target_id, limit=10)
            elif edge_type == "READS":
                append_unique_limited(reads[source_id], target_id, limit=10)
            elif edge_type == "WRITES":
                append_unique_limited(writes[source_id], target_id, limit=10)
            elif edge_type in {"REFS", "REFERENCES"}:
                append_unique_limited(refs[source_id], target_id, limit=10)
            elif edge_type == "CONTAINS" and node_kind_by_id.get(target_id) == "statement":
                append_unique_limited(statements[source_id], target_id, limit=12)

    for node_id in sorted(seedable_ids):
        yield {
            "node_id": node_id,
            "incoming_counts_json": json.dumps(dict(sorted(incoming_counts.get(node_id, Counter()).items())), sort_keys=True),
            "outgoing_counts_json": json.dumps(dict(sorted(outgoing_counts.get(node_id, Counter()).items())), sort_keys=True),
            "direct_calls_json": json.dumps(direct_calls.get(node_id, [])),
            "reads_json": json.dumps(reads.get(node_id, [])),
            "writes_json": json.dumps(writes.get(node_id, [])),
            "refs_json": json.dumps(refs.get(node_id, [])),
            "statements_json": json.dumps(statements.get(node_id, [])),
        }


def build_neighbor_cache_rows_from_sqlite(connection: sqlite3.Connection) -> Iterable[Dict[str, object]]:
    node_kind_by_id = {
        str(row["node_id"]): str(row["kind"])
        for row in connection.execute("SELECT node_id, kind FROM nodes")
    }
    seedable_ids = {node_id for node_id, kind in node_kind_by_id.items() if kind not in NON_SYMBOL_NODE_KINDS}
    outgoing: dict[str, list[dict[str, object]]] = defaultdict(list)
    incoming: dict[str, list[dict[str, object]]] = defaultdict(list)

    for row in connection.execute(
        "SELECT edge_id, type, source_node_id, target_node_id, path, metadata_json FROM edges ORDER BY type, path, edge_id"
    ):
        edge_type = str(row["type"])
        if edge_type not in CACHEABLE_NEIGHBOR_EDGE_TYPES:
            continue
        edge = {
            "edge_id": str(row["edge_id"]),
            "type": edge_type,
            "from": str(row["source_node_id"]),
            "to": str(row["target_node_id"]),
            "metadata": json.loads(row["metadata_json"] or "{}"),
        }
        if edge["from"] in seedable_ids:
            outgoing[edge["from"]].append(edge)
        if edge["to"] in seedable_ids:
            incoming[edge["to"]].append(edge)

    for node_id in seedable_ids:
        outgoing[node_id].sort(key=edge_sort_key)
        incoming[node_id].sort(key=edge_sort_key)
        yield {
            "node_id": node_id,
            "outgoing_edges_json": json.dumps(
                serialize_neighbor_edges(outgoing.get(node_id, []), node_kind_by_id, direction="outgoing")
            ),
            "incoming_edges_json": json.dumps(
                serialize_neighbor_edges(incoming.get(node_id, []), node_kind_by_id, direction="incoming")
            ),
        }


def edge_sort_key(edge: Dict[str, object]) -> tuple[str, str, str]:
    metadata = edge.get("metadata", {})
    return (
        str(edge["type"]),
        str(metadata.get("path") or ""),
        str(metadata.get("line") or 0),
    )


def edge_counter(edges: Iterable[Dict[str, object]]) -> Dict[str, int]:
    counts = Counter(str(edge["type"]) for edge in edges)
    return {edge_type: counts[edge_type] for edge_type in sorted(counts)}


def collect_edge_target_ids(
    edges: Iterable[Dict[str, object]],
    node_by_id: Dict[str, Dict[str, object]],
    edge_types: set[str],
) -> list[str]:
    results: list[str] = []
    seen = set()
    for edge in edges:
        if str(edge["type"]) not in edge_types:
            continue
        target_id = str(edge["to"])
        if target_id in seen or target_id not in node_by_id:
            continue
        seen.add(target_id)
        results.append(target_id)
        if len(results) >= 10:
            break
    return results


def collect_statement_ids(
    edges: Iterable[Dict[str, object]],
    node_by_id: Dict[str, Dict[str, object]],
) -> list[str]:
    results: list[str] = []
    seen = set()
    for edge in edges:
        if str(edge["type"]) != "CONTAINS":
            continue
        target_id = str(edge["to"])
        target = node_by_id.get(target_id)
        if not target or str(target.get("kind")) != "statement" or target_id in seen:
            continue
        seen.add(target_id)
        results.append(target_id)
        if len(results) >= 12:
            break
    return results


def append_unique_limited(values: list[str], value: str, *, limit: int) -> None:
    if value in values:
        return
    if len(values) >= limit:
        return
    values.append(value)


def serialize_neighbor_edges(
    edges: Iterable[Dict[str, object]],
    node_lookup: Dict[str, object],
    *,
    direction: str,
) -> list[Dict[str, object]]:
    results: list[Dict[str, object]] = []
    seen = set()
    for edge in edges:
        neighbor_id = str(edge["to"] if direction == "outgoing" else edge["from"])
        if neighbor_id not in node_lookup:
            continue
        key = (str(edge["type"]), neighbor_id)
        if key in seen:
            continue
        seen.add(key)
        results.append(
            {
                "edge_type": str(edge["type"]),
                "neighbor_id": neighbor_id,
                "edge_metadata": dict(edge.get("metadata", {})),
            }
        )
        if len(results) >= MAX_NEIGHBOR_CACHE_EDGES_PER_DIRECTION:
            break
    return results
