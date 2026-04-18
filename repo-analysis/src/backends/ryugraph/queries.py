from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence


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
        edge_types = tuple(request.get("edge_types") or EDGE_DEFAULTS.get(operation, ()))

        seed_rows = self._resolve_seed_rows(request.get("seed") or request.get("query"), limit=max(limit, 10))
        if not seed_rows:
            return {
                "repo": self.repo_name,
                "operation": operation,
                "graph_backend": "ryugraph",
                "request": {
                    "direction": direction,
                    "edge_types": list(edge_types),
                    "depth": depth,
                    "limit": limit,
                    "node_kinds": list(request.get("node_kinds") or ()),
                    "seed": request.get("seed") or request.get("query"),
                },
                "seeds": [],
                "results": [],
            }

        seeds = [self._describe_node(row) for row in seed_rows]
        payload = {
            "repo": self.repo_name,
            "operation": operation,
            "graph_backend": "ryugraph",
            "request": {
                "direction": direction,
                "edge_types": list(edge_types),
                "depth": depth,
                "limit": limit,
                "node_kinds": list(request.get("node_kinds") or ()),
                "seed": request.get("seed") or request.get("query"),
            },
            "seeds": seeds,
        }

        if operation == "where_defined":
            payload["results"] = seeds[:limit]
            return payload

        if operation in {"neighbors", "callers_of", "callees_of", "who_imports", "implements_of", "inherits_of", "reads_of", "writes_of", "refs_of"}:
            payload["results"] = self._neighbors(seed_rows, direction=direction, edge_types=edge_types, limit=limit)
            return payload

        if operation == "symbol_summary":
            payload["results"] = self._symbol_summaries(seed_rows, limit=limit)
            return payload

        return None

    def _resolve_seed_rows(self, seed: object, *, limit: int) -> List[sqlite3.Row]:
        if seed is None:
            return []

        with sqlite3.connect(self.sqlite_path) as connection:
            connection.row_factory = sqlite3.Row
            if isinstance(seed, dict):
                if seed.get("node_id"):
                    row = connection.execute(
                        "SELECT node_id, kind, repo, path, name, qualified_name, metadata_json FROM nodes WHERE node_id = ?",
                        [str(seed["node_id"])],
                    ).fetchone()
                    return [row] if row else []
                if seed.get("symbol_id"):
                    row = connection.execute(
                        "SELECT node_id, kind, repo, path, name, qualified_name, metadata_json FROM nodes WHERE node_id = ?",
                        [str(seed["symbol_id"])],
                    ).fetchone()
                    return [row] if row else []
                if seed.get("path"):
                    rows = connection.execute(
                        """
                        SELECT node_id, kind, repo, path, name, qualified_name, metadata_json
                        FROM nodes
                        WHERE path = ?
                        ORDER BY node_id
                        LIMIT ?
                        """,
                        [str(seed["path"]), int(limit)],
                    ).fetchall()
                    return list(rows)
                if seed.get("qualified_name"):
                    rows = connection.execute(
                        """
                        SELECT node_id, kind, repo, path, name, qualified_name, metadata_json
                        FROM nodes
                        WHERE qualified_name = ?
                        ORDER BY node_id
                        LIMIT ?
                        """,
                        [str(seed["qualified_name"]), int(limit)],
                    ).fetchall()
                    return list(rows)
                if seed.get("name"):
                    rows = connection.execute(
                        """
                        SELECT node_id, kind, repo, path, name, qualified_name, metadata_json
                        FROM nodes
                        WHERE name = ?
                        ORDER BY node_id
                        LIMIT ?
                        """,
                        [str(seed["name"]), int(limit)],
                    ).fetchall()
                    return list(rows)

            if not isinstance(seed, str):
                return []

            query = seed.strip()
            if not query:
                return []

            direct = connection.execute(
                "SELECT node_id, kind, repo, path, name, qualified_name, metadata_json FROM nodes WHERE node_id = ?",
                [query],
            ).fetchone()
            if direct:
                return [direct]

            rows = connection.execute(
                """
                SELECT node_id, kind, repo, path, name, qualified_name, metadata_json
                FROM nodes
                WHERE qualified_name = ? OR name = ? OR path = ?
                ORDER BY node_id
                LIMIT ?
                """,
                [query, query, query, int(limit)],
            ).fetchall()
            if rows:
                return list(rows)

            wildcard = f"%{query}%"
            fuzzy = connection.execute(
                """
                SELECT node_id, kind, repo, path, name, qualified_name, metadata_json
                FROM nodes
                WHERE qualified_name LIKE ? OR name LIKE ? OR path LIKE ?
                ORDER BY node_id
                LIMIT ?
                """,
                [wildcard, wildcard, wildcard, int(limit)],
            ).fetchall()
            return list(fuzzy)

    def _neighbors(
        self,
        seeds: Sequence[sqlite3.Row],
        *,
        direction: str,
        edge_types: Sequence[str],
        limit: int,
    ) -> List[Dict[str, object]]:
        with sqlite3.connect(self.sqlite_path) as connection:
            connection.row_factory = sqlite3.Row
            neighbors: List[Dict[str, object]] = []
            seen = set()
            for seed in seeds:
                seed_id = str(seed["node_id"])
                for edge in self._load_edges(connection, seed_id, direction=direction, edge_types=edge_types, limit=limit * 2):
                    target_id = str(edge["target_node_id"])
                    if direction == "incoming":
                        target_id = str(edge["source_node_id"])
                    elif direction == "both":
                        target_id = str(edge["target_node_id"])
                        if str(edge["source_node_id"]) != seed_id:
                            target_id = str(edge["source_node_id"])

                    if target_id in seen:
                        continue
                    seen.add(target_id)
                    node = connection.execute(
                        "SELECT node_id, kind, repo, path, name, qualified_name, metadata_json FROM nodes WHERE node_id = ?",
                        [target_id],
                    ).fetchone()
                    if node is None:
                        continue
                    metadata = json.loads(edge["metadata_json"] or "{}")
                    neighbors.append(
                        {
                            **self._describe_node(node),
                            "edge": {
                                "edge_id": edge["edge_id"],
                                "type": edge["type"],
                                "from": edge["source_node_id"],
                                "to": edge["target_node_id"],
                                "metadata": metadata,
                            },
                        }
                    )
                    if len(neighbors) >= limit:
                        return neighbors
            return neighbors

    def _symbol_summaries(self, seeds: Sequence[sqlite3.Row], *, limit: int) -> List[Dict[str, object]]:
        with sqlite3.connect(self.sqlite_path) as connection:
            connection.row_factory = sqlite3.Row
            summaries: List[Dict[str, object]] = []
            for seed in seeds:
                row = connection.execute(
                    """
                    SELECT node_id, incoming_counts_json, outgoing_counts_json, direct_calls_json,
                           reads_json, writes_json, refs_json, statements_json
                    FROM symbol_summary_cache
                    WHERE node_id = ?
                    """,
                    [str(seed["node_id"])],
                ).fetchone()
                if row is None:
                    continue
                summaries.append(
                    {
                        "node_id": row["node_id"],
                        "incoming_counts": json.loads(row["incoming_counts_json"] or "{}"),
                        "outgoing_counts": json.loads(row["outgoing_counts_json"] or "{}"),
                        "direct_calls": json.loads(row["direct_calls_json"] or "[]"),
                        "reads": json.loads(row["reads_json"] or "[]"),
                        "writes": json.loads(row["writes_json"] or "[]"),
                        "refs": json.loads(row["refs_json"] or "[]"),
                        "statements": json.loads(row["statements_json"] or "[]"),
                    }
                )
                if len(summaries) >= limit:
                    break
            return summaries

    @staticmethod
    def _load_edges(
        connection: sqlite3.Connection,
        node_id: str,
        *,
        direction: str,
        edge_types: Sequence[str],
        limit: int,
    ) -> Iterable[sqlite3.Row]:
        params: List[object] = []
        edge_filter = ""
        if edge_types:
            placeholders = ",".join("?" for _ in edge_types)
            edge_filter = f" AND type IN ({placeholders})"
            params.extend(edge_types)

        if direction == "outgoing":
            query = (
                "SELECT edge_id, type, source_node_id, target_node_id, metadata_json FROM edges "
                "WHERE source_node_id = ?" + edge_filter + " ORDER BY type, target_node_id LIMIT ?"
            )
            return connection.execute(query, [node_id, *params, int(limit)]).fetchall()
        if direction == "incoming":
            query = (
                "SELECT edge_id, type, source_node_id, target_node_id, metadata_json FROM edges "
                "WHERE target_node_id = ?" + edge_filter + " ORDER BY type, source_node_id LIMIT ?"
            )
            return connection.execute(query, [node_id, *params, int(limit)]).fetchall()

        outgoing = connection.execute(
            (
                "SELECT edge_id, type, source_node_id, target_node_id, metadata_json FROM edges "
                "WHERE source_node_id = ?" + edge_filter + " ORDER BY type, target_node_id LIMIT ?"
            ),
            [node_id, *params, int(limit)],
        ).fetchall()
        incoming = connection.execute(
            (
                "SELECT edge_id, type, source_node_id, target_node_id, metadata_json FROM edges "
                "WHERE target_node_id = ?" + edge_filter + " ORDER BY type, source_node_id LIMIT ?"
            ),
            [node_id, *params, int(limit)],
        ).fetchall()
        return [*outgoing, *incoming]

    @staticmethod
    def _describe_node(row: sqlite3.Row) -> Dict[str, object]:
        metadata = json.loads(row["metadata_json"] or "{}")
        return {
            "node_id": row["node_id"],
            "kind": row["kind"],
            "repo": row["repo"],
            "path": row["path"],
            "name": row["name"],
            "qualified_name": row["qualified_name"],
            **metadata,
        }
