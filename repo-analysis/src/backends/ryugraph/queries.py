from __future__ import annotations

import json
import sqlite3
from collections import deque
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

from search.indexer import search_documents
from symbols.indexer import stable_id


EDGE_DEFAULTS = {
    "who_imports": ("IMPORTS",),
    "callers_of": ("CALLS",),
    "callees_of": ("CALLS",),
    "implements_of": ("IMPLEMENTS",),
    "inherits_of": ("INHERITS",),
    "reads_of": ("READS",),
    "writes_of": ("WRITES",),
    "refs_of": ("REFS", "REFERENCES"),
}
EDGE_DIRECTIONS = {
    "who_imports": "incoming",
    "callers_of": "incoming",
    "callees_of": "outgoing",
    "implements_of": "incoming",
    "inherits_of": "outgoing",
    "reads_of": "outgoing",
    "writes_of": "outgoing",
    "refs_of": "outgoing",
}


@dataclass(frozen=True)
class RyuGraphBackend:
    graph_root: Path
    repo_name: str

    @property
    def sqlite_path(self) -> Path:
        return self.graph_root / self.repo_name / "graph.sqlite3"

    def execute(self, request: Dict[str, object]) -> Optional[Dict[str, object]]:
        if not self.sqlite_path.exists():
            return None

        operation = str(request.get("operation") or "neighbors")
        limit = max(int(request.get("limit") or 20), 1)
        depth = max(int(request.get("depth") or 1), 0)
        direction = str(request.get("direction") or EDGE_DIRECTIONS.get(operation, "both"))
        edge_types = tuple(str(item) for item in (request.get("edge_types") or EDGE_DEFAULTS.get(operation, ())))
        node_kinds = tuple(str(item) for item in (request.get("node_kinds") or ()))

        with sqlite3.connect(self.sqlite_path) as connection:
            connection.row_factory = sqlite3.Row
            seeds = resolve_seed_nodes(connection, self.graph_root, self.repo_name, request.get("seed") or request.get("query"), limit=max(limit, 10))
            payload = {
                "repo": self.repo_name,
                "operation": operation,
                "graph_backend": "sqlite_graph",
                "request": {
                    "direction": direction,
                    "edge_types": list(edge_types),
                    "depth": depth,
                    "limit": limit,
                    "node_kinds": list(node_kinds),
                    "seed": request.get("seed") or request.get("query"),
                },
                "seeds": [describe_sqlite_node(seed) for seed in seeds],
            }
            if operation == "where_defined":
                payload["results"] = [describe_sqlite_node(seed) for seed in seeds[:limit]]
                return payload
            if operation == "statement_slice":
                payload["results"] = build_statement_slice(
                    connection,
                    seeds,
                    limit=limit,
                    window=max(int(request.get("window") or 8), 1),
                )
                return payload
            if operation == "path_between":
                targets = resolve_seed_nodes(connection, self.graph_root, self.repo_name, request.get("target"), limit=max(limit, 10))
                payload["targets"] = [describe_sqlite_node(target) for target in targets]
                payload["results"] = build_shortest_paths(
                    connection,
                    seeds,
                    targets,
                    edge_types=edge_types,
                    direction=direction,
                    node_kinds=node_kinds,
                    limit=limit,
                )
                return payload
            if operation == "symbol_summary":
                payload["results"] = build_symbol_summaries(connection, seeds, limit=limit)
                return payload
            payload["results"] = build_neighbors(
                connection,
                seeds,
                direction=direction,
                edge_types=edge_types,
                node_kinds=node_kinds,
                depth=depth,
                limit=limit,
            )
            return payload


def resolve_seed_nodes(
    connection: sqlite3.Connection,
    graph_root: Path,
    repo_name: str,
    seed: object,
    *,
    limit: int,
) -> List[sqlite3.Row]:
    if seed is None:
        return []
    if isinstance(seed, dict):
        if seed.get("node_id"):
            return list(load_nodes_by_id(connection, [str(seed["node_id"])]).values())
        if seed.get("symbol_id"):
            return list(load_nodes_by_id(connection, [str(seed["symbol_id"])]).values())
        if seed.get("qualified_name"):
            return resolve_seed_nodes(connection, graph_root, repo_name, str(seed["qualified_name"]), limit=limit)
        if seed.get("name"):
            return resolve_seed_nodes(connection, graph_root, repo_name, str(seed["name"]), limit=limit)
        if seed.get("path"):
            return resolve_seed_nodes(connection, graph_root, repo_name, str(seed["path"]), limit=limit)
        return []
    if not isinstance(seed, str):
        return []
    query = seed.strip()
    if not query:
        return []

    direct = resolve_direct_nodes(connection, repo_name, query, limit=limit)
    if direct:
        return direct

    results = search_documents(graph_root.parent / "search", repo_name, query, limit=max(limit * 4, 40))
    node_ids: List[str] = []
    seen = set()
    for result in results:
        node_id = search_result_to_node_id(repo_name, result)
        if not node_id or node_id in seen:
            continue
        seen.add(node_id)
        node_ids.append(node_id)
    return list(load_nodes_by_id(connection, node_ids[:limit]).values())


def resolve_direct_nodes(connection: sqlite3.Connection, repo_name: str, query: str, *, limit: int) -> List[sqlite3.Row]:
    if query.startswith("sym:"):
        return list(load_nodes_by_id(connection, [query]).values())
    rows = connection.execute(
        """
        SELECT node_id, kind, repo, path, name, qualified_name, metadata_json
        FROM nodes
        WHERE node_id = ? OR qualified_name = ? OR name = ? OR path = ?
        ORDER BY kind, COALESCE(path, ''), COALESCE(qualified_name, ''), COALESCE(name, '')
        LIMIT ?
        """,
        [query, query, query, query, limit],
    ).fetchall()
    if rows:
        return rows
    lowered = query.lower()
    rows = connection.execute(
        """
        SELECT node_id, kind, repo, path, name, qualified_name, metadata_json
        FROM nodes
        WHERE lower(COALESCE(qualified_name, '')) = ?
           OR lower(COALESCE(name, '')) = ?
           OR lower(COALESCE(path, '')) = ?
        ORDER BY kind, COALESCE(path, ''), COALESCE(qualified_name, ''), COALESCE(name, '')
        LIMIT ?
        """,
        [lowered, lowered, lowered, limit],
    ).fetchall()
    return rows


def build_neighbors(
    connection: sqlite3.Connection,
    seeds: Sequence[sqlite3.Row],
    *,
    direction: str,
    edge_types: Sequence[str],
    node_kinds: Sequence[str],
    depth: int,
    limit: int,
) -> List[Dict[str, object]]:
    allowed_edge_types = set(edge_types)
    allowed_node_kinds = set(node_kinds)
    queue = deque((str(seed["node_id"]), 0, "seed") for seed in seeds)
    seen_nodes = {str(seed["node_id"]) for seed in seeds}
    seen_results = set()
    results: List[Dict[str, object]] = []
    while queue and len(results) < limit:
        node_id, current_depth, arrived_via = queue.popleft()
        if current_depth >= max(depth, 1):
            continue
        for neighbor_id, edge_payload in query_adjacency(connection, node_id, direction=direction, edge_types=allowed_edge_types):
            neighbor_row = load_nodes_by_id(connection, [neighbor_id]).get(neighbor_id)
            if neighbor_row is None:
                continue
            if allowed_node_kinds and str(neighbor_row["kind"]) not in allowed_node_kinds:
                continue
            key = (neighbor_id, str(edge_payload["type"]), str(edge_payload["direction"]), current_depth + 1)
            if key in seen_results:
                continue
            seen_results.add(key)
            results.append(
                {
                    "depth": current_depth + 1,
                    "direction": str(edge_payload["direction"]),
                    "edge_type": str(edge_payload["type"]),
                    "arrived_via": arrived_via,
                    **describe_sqlite_node(neighbor_row),
                    "edge_metadata": dict(edge_payload["metadata"]),
                }
            )
            if neighbor_id not in seen_nodes:
                seen_nodes.add(neighbor_id)
                queue.append((neighbor_id, current_depth + 1, str(edge_payload["type"])))
            if len(results) >= limit:
                break
    results.sort(key=lambda item: (int(item["depth"]), str(item["edge_type"]), str(item.get("path") or ""), str(item.get("qualified_name") or item.get("name") or "")))
    return results[:limit]


def build_statement_slice(
    connection: sqlite3.Connection,
    seeds: Sequence[sqlite3.Row],
    *,
    limit: int,
    window: int,
) -> List[Dict[str, object]]:
    statement_ids: List[str] = []
    seen = set()
    for seed in seeds:
        seed_id = str(seed["node_id"])
        if str(seed["kind"]) == "statement":
            candidate_ids = [seed_id]
            candidate_ids.extend(
                str(row[0])
                for row in connection.execute(
                    "SELECT target_node_id FROM edges WHERE source_node_id = ? AND type = 'CONTROL_FLOW' ORDER BY edge_id LIMIT ?",
                    [seed_id, window],
                )
            )
            candidate_ids.extend(
                str(row[0])
                for row in connection.execute(
                    "SELECT source_node_id FROM edges WHERE target_node_id = ? AND type = 'CONTROL_FLOW' ORDER BY edge_id LIMIT ?",
                    [seed_id, window],
                )
            )
        else:
            candidate_ids = [
                str(row[0])
                for row in connection.execute(
                    "SELECT target_node_id FROM edges WHERE source_node_id = ? AND type = 'CONTAINS' ORDER BY edge_id LIMIT ?",
                    [seed_id, window * 4],
                )
            ]
        rows = load_nodes_by_id(connection, candidate_ids)
        ordered = sorted((row for row in rows.values() if str(row["kind"]) == "statement"), key=statement_row_sort_key)
        for row in ordered[:window]:
            statement_id = str(row["node_id"])
            if statement_id in seen:
                continue
            seen.add(statement_id)
            statement_ids.append(statement_id)
            if len(statement_ids) >= limit:
                break
        if len(statement_ids) >= limit:
            break
    rows = load_nodes_by_id(connection, statement_ids)
    return [hydrate_statement(connection, rows[item]) for item in statement_ids if item in rows][:limit]


def build_shortest_paths(
    connection: sqlite3.Connection,
    seeds: Sequence[sqlite3.Row],
    targets: Sequence[sqlite3.Row],
    *,
    edge_types: Sequence[str],
    direction: str,
    node_kinds: Sequence[str],
    limit: int,
) -> List[Dict[str, object]]:
    if not seeds or not targets:
        return []
    allowed_edge_types = set(edge_types)
    allowed_node_kinds = set(node_kinds)
    target_ids = {str(target["node_id"]) for target in targets}
    results = []
    for seed in seeds:
        queue = deque([str(seed["node_id"])])
        parents: Dict[str, Tuple[Optional[str], Optional[Dict[str, object]]]] = {str(seed["node_id"]): (None, None)}
        found_target: Optional[str] = None
        while queue and found_target is None:
            current = queue.popleft()
            for neighbor_id, edge_payload in query_adjacency(connection, current, direction=direction, edge_types=allowed_edge_types):
                if neighbor_id in parents:
                    continue
                row = load_nodes_by_id(connection, [neighbor_id]).get(neighbor_id)
                if row is None:
                    continue
                if allowed_node_kinds and str(row["kind"]) not in allowed_node_kinds and neighbor_id not in target_ids:
                    continue
                parents[neighbor_id] = (current, edge_payload)
                if neighbor_id in target_ids:
                    found_target = neighbor_id
                    break
                queue.append(neighbor_id)
        if found_target is None:
            continue
        ordered_ids: List[str] = []
        ordered_edges: List[Dict[str, object]] = []
        cursor = found_target
        while cursor is not None:
            parent_id, parent_edge = parents[cursor]
            ordered_ids.append(cursor)
            if parent_edge is not None:
                ordered_edges.append(parent_edge)
            cursor = parent_id
        ordered_ids.reverse()
        ordered_edges.reverse()
        node_rows = load_nodes_by_id(connection, ordered_ids)
        results.append(
            {
                "source": describe_sqlite_node(seed),
                "target": describe_sqlite_node(node_rows[found_target]),
                "hop_count": len(ordered_edges),
                "nodes": [describe_sqlite_node(node_rows[node_id]) for node_id in ordered_ids if node_id in node_rows],
                "edges": ordered_edges,
            }
        )
        if len(results) >= limit:
            break
    results.sort(key=lambda item: (int(item["hop_count"]), str(item["target"].get("path") or ""), str(item["target"].get("qualified_name") or item["target"].get("name") or "")))
    return results[:limit]


def build_symbol_summaries(
    connection: sqlite3.Connection,
    seeds: Sequence[sqlite3.Row],
    *,
    limit: int,
) -> List[Dict[str, object]]:
    results = []
    seed_ids = [str(seed["node_id"]) for seed in seeds[:limit]]
    if not seed_ids:
        return []
    cache_rows = connection.execute(
        f"SELECT node_id, incoming_counts_json, outgoing_counts_json, direct_calls_json, reads_json, writes_json, refs_json, statements_json FROM symbol_summary_cache WHERE node_id IN ({','.join('?' for _ in seed_ids)})",
        seed_ids,
    ).fetchall()
    cache_by_id = {str(row["node_id"]): row for row in cache_rows}
    referenced_ids: set[str] = set()
    for row in cache_rows:
        for column in ("direct_calls_json", "reads_json", "writes_json", "refs_json", "statements_json"):
            referenced_ids.update(json.loads(row[column] or "[]"))
    node_rows = load_nodes_by_id(connection, list(set(seed_ids) | referenced_ids))
    for seed in seeds[:limit]:
        row = cache_by_id.get(str(seed["node_id"]))
        if row is None:
            continue
        described_seed = describe_sqlite_node(seed)
        direct_calls = hydrate_node_list(node_rows, json.loads(row["direct_calls_json"] or "[]"))
        reads = hydrate_node_list(node_rows, json.loads(row["reads_json"] or "[]"))
        writes = hydrate_node_list(node_rows, json.loads(row["writes_json"] or "[]"))
        refs = hydrate_node_list(node_rows, json.loads(row["refs_json"] or "[]"))
        statements = hydrate_statement_rows(node_rows, json.loads(row["statements_json"] or "[]"))
        results.append(
            {
                **described_seed,
                "incoming_edge_counts": json.loads(row["incoming_counts_json"] or "{}"),
                "outgoing_edge_counts": json.loads(row["outgoing_counts_json"] or "{}"),
                "direct_calls": direct_calls,
                "reads": reads,
                "writes": writes,
                "references": refs,
                "defining_statements": statements,
                "summary": summarize_symbol(described_seed, direct_calls, reads, writes, refs, statements),
            }
        )
    return results


def query_adjacency(
    connection: sqlite3.Connection,
    node_id: str,
    *,
    direction: str,
    edge_types: set[str],
) -> Iterable[Tuple[str, Dict[str, object]]]:
    clauses = []
    params: List[object] = []
    if edge_types:
        clauses.append(f"type IN ({','.join('?' for _ in edge_types)})")
        params.extend(sorted(edge_types))
    where = f"AND {' AND '.join(clauses)}" if clauses else ""
    if direction in {"outgoing", "both"}:
        for row in connection.execute(
            f"SELECT edge_id, type, target_node_id, metadata_json FROM edges WHERE source_node_id = ? {where} ORDER BY edge_id",
            [node_id, *params],
        ):
            yield str(row["target_node_id"]), {
                "edge_id": row["edge_id"],
                "type": row["type"],
                "direction": "outgoing",
                "metadata": json.loads(row["metadata_json"] or "{}"),
            }
    if direction in {"incoming", "both"}:
        for row in connection.execute(
            f"SELECT edge_id, type, source_node_id, metadata_json FROM edges WHERE target_node_id = ? {where} ORDER BY edge_id",
            [node_id, *params],
        ):
            yield str(row["source_node_id"]), {
                "edge_id": row["edge_id"],
                "type": row["type"],
                "direction": "incoming",
                "metadata": json.loads(row["metadata_json"] or "{}"),
            }


def hydrate_statement(connection: sqlite3.Connection, row: sqlite3.Row) -> Dict[str, object]:
    statement_id = str(row["node_id"])
    outgoing_rows = connection.execute("SELECT type, target_node_id FROM edges WHERE source_node_id = ? ORDER BY edge_id", [statement_id]).fetchall()
    incoming_rows = connection.execute("SELECT type, source_node_id FROM edges WHERE target_node_id = ? ORDER BY edge_id", [statement_id]).fetchall()
    referenced_ids = {str(item[1]) for item in outgoing_rows if item[1]} | {str(item[1]) for item in incoming_rows if item[1]}
    node_rows = load_nodes_by_id(connection, list(referenced_ids))
    metadata = json.loads(row["metadata_json"] or "{}")
    described = describe_sqlite_node(row)
    described["statement_id"] = statement_id
    described["text"] = metadata.get("text")
    described["container_symbol_id"] = metadata.get("container_symbol_id")
    described["container_qualified_name"] = metadata.get("container_qualified_name")
    described["line"] = int(str(described.get("name") or "0").split("@L")[-1]) if "@L" in str(described.get("name") or "") else 0
    described["defines"] = hydrate_node_list(node_rows, [str(item[1]) for item in outgoing_rows if str(item[0]) == "DEFINES"])
    described["reads"] = hydrate_node_list(node_rows, [str(item[1]) for item in outgoing_rows if str(item[0]) == "READS"])
    described["writes"] = hydrate_node_list(node_rows, [str(item[1]) for item in outgoing_rows if str(item[0]) == "WRITES"])
    described["refs"] = hydrate_node_list(node_rows, [str(item[1]) for item in outgoing_rows if str(item[0]) in {"REFS", "REFERENCES"}])
    described["calls"] = hydrate_node_list(node_rows, [str(item[1]) for item in outgoing_rows if str(item[0]) == "CALLS"])
    described["control_predecessors"] = hydrate_node_list(node_rows, [str(item[1]) for item in incoming_rows if str(item[0]) == "CONTROL_FLOW"])
    described["control_successors"] = hydrate_node_list(node_rows, [str(item[1]) for item in outgoing_rows if str(item[0]) == "CONTROL_FLOW"])
    return described


def load_nodes_by_id(connection: sqlite3.Connection, node_ids: Sequence[str]) -> Dict[str, sqlite3.Row]:
    normalized = [node_id for node_id in node_ids if node_id]
    if not normalized:
        return {}
    rows = connection.execute(
        f"SELECT node_id, kind, repo, path, name, qualified_name, metadata_json FROM nodes WHERE node_id IN ({','.join('?' for _ in normalized)})",
        normalized,
    ).fetchall()
    return {str(row["node_id"]): row for row in rows}


def hydrate_node_list(node_rows: Dict[str, sqlite3.Row], node_ids: Sequence[str]) -> List[Dict[str, object]]:
    return [describe_sqlite_node(node_rows[node_id]) for node_id in node_ids if node_id in node_rows]


def hydrate_statement_rows(node_rows: Dict[str, sqlite3.Row], statement_ids: Sequence[str]) -> List[Dict[str, object]]:
    results = []
    for node_id in statement_ids:
        row = node_rows.get(node_id)
        if row is None:
            continue
        metadata = json.loads(row["metadata_json"] or "{}")
        described = describe_sqlite_node(row)
        described["statement_id"] = described["node_id"]
        described["text"] = metadata.get("text")
        described["container_symbol_id"] = metadata.get("container_symbol_id")
        described["container_qualified_name"] = metadata.get("container_qualified_name")
        described["line"] = int(str(described.get("name") or "0").split("@L")[-1]) if "@L" in str(described.get("name") or "") else 0
        described["defines"] = []
        described["reads"] = []
        described["writes"] = []
        described["refs"] = []
        described["calls"] = []
        described["control_predecessors"] = []
        described["control_successors"] = []
        results.append(described)
    results.sort(key=lambda item: (str(item.get("path") or ""), int(item.get("line") or 0), str(item.get("statement_id") or "")))
    return results


def describe_sqlite_node(row: sqlite3.Row) -> Dict[str, object]:
    metadata = json.loads(row["metadata_json"] or "{}")
    payload = {
        "node_id": row["node_id"],
        "kind": row["kind"],
        "path": row["path"],
        "name": row["name"],
        "qualified_name": row["qualified_name"],
        "symbol_id": row["node_id"] if str(row["node_id"]).startswith("sym:") else None,
        "span": metadata.get("span"),
        "container_qualified_name": metadata.get("container_qualified_name"),
        "signature": metadata.get("signature"),
        "visibility": metadata.get("visibility"),
    }
    return payload


def search_result_to_node_id(repo_name: str, result: Dict[str, object]) -> str | None:
    symbol_id = str(result.get("symbol_id") or "")
    if symbol_id:
        return symbol_id
    if str(result.get("kind") or "") == "file" and result.get("path"):
        return stable_id("file", repo_name, str(result["path"]))
    return None


def statement_row_sort_key(row: sqlite3.Row) -> Tuple[str, int, int, str]:
    metadata = json.loads(row["metadata_json"] or "{}")
    span = metadata.get("span") or {}
    return (
        str(row["path"] or ""),
        int(span.get("start_line") or 0),
        int(span.get("start_column") or 0),
        str(row["node_id"] or ""),
    )


def summarize_symbol(
    node: Dict[str, object],
    direct_calls: Sequence[Dict[str, object]],
    reads: Sequence[Dict[str, object]],
    writes: Sequence[Dict[str, object]],
    refs: Sequence[Dict[str, object]],
    statements: Sequence[Dict[str, object]],
) -> str:
    return (
        f"{node.get('kind')} {node.get('qualified_name') or node.get('name')} in {node.get('path')}. "
        f"Calls={len(direct_calls)} Reads={len(reads)} Writes={len(writes)} Refs={len(refs)} Statements={len(statements)}."
    )
