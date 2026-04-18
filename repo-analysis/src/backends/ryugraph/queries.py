from __future__ import annotations

import json
import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Dict, List, Optional, Sequence


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
    def ryugraph_path(self) -> Path:
        return self.graph_root / self.repo_name / "ryugraph.json"

    @property
    def sqlite_path(self) -> Path:
        return self.graph_root / self.repo_name / "graph.sqlite3"

    def execute(self, request: Dict[str, object]) -> Optional[Dict[str, object]]:
        graph = self._graph_payload(self.ryugraph_path, self.sqlite_path)
        if graph is None:
            return None

        operation = str(request.get("operation") or "neighbors")
        limit = max(int(request.get("limit") or 20), 1)
        depth = max(int(request.get("depth") or 1), 0)
        direction = str(request.get("direction") or EDGE_DIRECTIONS.get(operation, "both"))
        edge_types = tuple(request.get("edge_types") or EDGE_DEFAULTS.get(operation, ()))
        node_kinds = tuple(str(item) for item in (request.get("node_kinds") or ()))

        seeds = self._resolve_seed_nodes(graph, request.get("seed") or request.get("query"), limit=max(limit, 10))
        if not seeds:
            return {
                "repo": self.repo_name,
                "operation": operation,
                "graph_backend": "ryugraph",
                "request": {
                    "direction": direction,
                    "edge_types": list(edge_types),
                    "depth": depth,
                    "limit": limit,
                    "node_kinds": list(node_kinds),
                    "seed": request.get("seed") or request.get("query"),
                },
                "seeds": [],
                "results": [],
            }

        payload = {
            "repo": self.repo_name,
            "operation": operation,
            "graph_backend": "ryugraph",
            "request": {
                "direction": direction,
                "edge_types": list(edge_types),
                "depth": depth,
                "limit": limit,
                "node_kinds": list(node_kinds),
                "seed": request.get("seed") or request.get("query"),
            },
            "seeds": seeds,
        }

        if operation == "where_defined":
            payload["results"] = seeds[:limit]
            return payload

        if operation in {
            "neighbors",
            "callers_of",
            "callees_of",
            "who_imports",
            "implements_of",
            "inherits_of",
            "reads_of",
            "writes_of",
            "refs_of",
        }:
            payload["results"] = self._neighbors(
                graph,
                seeds,
                direction=direction,
                edge_types=edge_types,
                node_kinds=node_kinds,
                depth=depth,
                limit=limit,
            )
            return payload

        if operation == "symbol_summary":
            payload["results"] = self._symbol_summaries(graph, seeds, limit=limit)
            return payload

        return None

    @staticmethod
    @lru_cache(maxsize=16)
    def _graph_payload(ryugraph_path: Path, sqlite_path: Path) -> Optional[Dict[str, object]]:
        if ryugraph_path.exists():
            payload = json.loads(ryugraph_path.read_text(encoding="utf-8"))
            node_by_id = {node["node_id"]: node for node in payload.get("nodes", [])}
            outgoing: Dict[str, List[Dict[str, object]]] = {}
            incoming: Dict[str, List[Dict[str, object]]] = {}
            for edge in payload.get("edges", []):
                outgoing.setdefault(edge["from"], []).append(edge)
                incoming.setdefault(edge["to"], []).append(edge)
            return {"payload": payload, "node_by_id": node_by_id, "outgoing": outgoing, "incoming": incoming}

        # PR-5 default disables sqlite hot-path reads.
        if os.environ.get("CAXEN_ENABLE_SQLITE_HOTPATH_READS") == "1" and sqlite_path.exists():
            # Keep compatibility mode explicit via env flag.
            from graph.query import load_graph_sqlite

            graph = load_graph_sqlite(sqlite_path)
            return {
                "payload": graph["payload"],
                "node_by_id": graph["node_by_id"],
                "outgoing": graph["outgoing"],
                "incoming": graph["incoming"],
            }
        return None

    def _resolve_seed_nodes(self, graph: Dict[str, object], seed: object, *, limit: int) -> List[Dict[str, object]]:
        if seed is None:
            return []

        node_by_id = graph["node_by_id"]
        nodes = list(node_by_id.values())

        if isinstance(seed, dict):
            if seed.get("node_id"):
                node = node_by_id.get(str(seed["node_id"]))
                return [node] if node else []
            if seed.get("symbol_id"):
                node = node_by_id.get(str(seed["symbol_id"]))
                return [node] if node else []
            key = str(seed.get("qualified_name") or seed.get("name") or seed.get("path") or "").strip()
            if not key:
                return []
            seed = key

        if not isinstance(seed, str):
            return []

        query = seed.strip()
        if not query:
            return []

        if query in node_by_id:
            return [node_by_id[query]]

        exact = [
            node
            for node in nodes
            if str(node.get("qualified_name") or "") == query
            or str(node.get("name") or "") == query
            or str(node.get("path") or "") == query
        ]
        if exact:
            return exact[:limit]

        lowered = query.lower()
        fuzzy = [
            node
            for node in nodes
            if lowered in str(node.get("qualified_name") or "").lower()
            or lowered in str(node.get("name") or "").lower()
            or lowered in str(node.get("path") or "").lower()
        ]
        return fuzzy[:limit]

    def _neighbors(
        self,
        graph: Dict[str, object],
        seeds: Sequence[Dict[str, object]],
        *,
        direction: str,
        edge_types: Sequence[str],
        node_kinds: Sequence[str],
        depth: int,
        limit: int,
    ) -> List[Dict[str, object]]:
        node_by_id = graph["node_by_id"]
        outgoing = graph["outgoing"]
        incoming = graph["incoming"]

        allowed_edges = set(edge_types)
        allowed_kinds = set(node_kinds)
        results: List[Dict[str, object]] = []
        seen = set()
        frontier = [(seed["node_id"], 0) for seed in seeds]

        while frontier and len(results) < limit:
            node_id, steps = frontier.pop(0)
            if steps >= max(depth, 1):
                continue

            edges: List[tuple[str, Dict[str, object], str]] = []
            if direction in {"outgoing", "both"}:
                edges.extend((edge["to"], edge, "outgoing") for edge in outgoing.get(node_id, []))
            if direction in {"incoming", "both"}:
                edges.extend((edge["from"], edge, "incoming") for edge in incoming.get(node_id, []))

            for neighbor_id, edge, edge_direction in edges:
                edge_type = str(edge.get("type") or "")
                if allowed_edges and edge_type not in allowed_edges:
                    continue
                neighbor = node_by_id.get(neighbor_id)
                if not neighbor:
                    continue
                if allowed_kinds and str(neighbor.get("kind") or "") not in allowed_kinds:
                    continue
                key = (node_id, neighbor_id, edge_type, edge_direction)
                if key in seen:
                    continue
                seen.add(key)
                edge_payload = {
                    "edge_id": edge.get("edge_id"),
                    "type": edge_type,
                    "from": edge.get("from"),
                    "to": edge.get("to"),
                    "metadata": {**dict(edge.get("metadata") or {}), "direction": edge_direction},
                }
                results.append({**neighbor, "edge": edge_payload})
                frontier.append((neighbor_id, steps + 1))
                if len(results) >= limit:
                    break

        return results

    @staticmethod
    def _symbol_summaries(graph: Dict[str, object], seeds: Sequence[Dict[str, object]], *, limit: int) -> List[Dict[str, object]]:
        node_by_id = graph["node_by_id"]
        summaries = []
        for seed in seeds:
            node = node_by_id.get(seed["node_id"])
            if not node:
                continue
            summaries.append(
                {
                    "node_id": seed["node_id"],
                    "incoming_counts": {},
                    "outgoing_counts": {},
                    "direct_calls": [],
                    "reads": [],
                    "writes": [],
                    "refs": [],
                    "statements": [],
                    "name": node.get("name"),
                    "qualified_name": node.get("qualified_name"),
                }
            )
            if len(summaries) >= limit:
                break
        return summaries
