from __future__ import annotations

import json
import os
import sqlite3
from collections import Counter, defaultdict, deque
from functools import lru_cache
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

from backends.graph_backend import get_graph_backend
from common.telemetry import increment_counter, trace_operation
from search.indexer import search_documents
from symbols.indexer import stable_id
from symbols.persistence import load_symbol_index


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


def execute_graph_query(
    search_root: Path,
    parsed_root: Path,
    graph_root: Path,
    repo_name: str,
    request: Dict[str, object],
) -> Dict[str, object]:
    operation = str(request.get("operation") or "neighbors")
    graph_backend = get_graph_backend(str(graph_root.resolve()), repo_name)
    backend_response = graph_backend.execute(request)
    if backend_response is not None:
        return backend_response
    cached_response = execute_cached_graph_query(search_root, parsed_root, graph_root, repo_name, request)
    if cached_response is not None:
        return cached_response
    limit = max(int(request.get("limit") or 20), 1)
    depth = max(int(request.get("depth") or 1), 0)
    direction = str(request.get("direction") or EDGE_DIRECTIONS.get(operation, "both"))
    edge_types = tuple(request.get("edge_types") or EDGE_DEFAULTS.get(operation, ()))
    node_kinds = tuple(request.get("node_kinds") or ())
    graph = load_graph_view(graph_root, repo_name)
    symbols_payload = load_symbols_payload(parsed_root, repo_name)
    symbol_by_id = {item["symbol_id"]: item for item in symbols_payload.get("symbols", [])}
    seeds = resolve_seed_matches(
        search_root,
        parsed_root,
        graph,
        symbols_payload,
        repo_name,
        request.get("seed") or request.get("query"),
        limit=max(limit, 10),
    )

    payload = {
        "repo": repo_name,
        "operation": operation,
        "graph_backend": graph["backend"],
        "request": {
            "direction": direction,
            "edge_types": list(edge_types),
            "depth": depth,
            "limit": limit,
            "node_kinds": list(node_kinds),
            "seed": request.get("seed") or request.get("query"),
        },
        "seeds": [describe_node(seed, symbol_by_id) for seed in seeds],
    }

    if operation == "where_defined":
        payload["results"] = payload["seeds"][:limit]
        return payload

    if operation == "statement_slice":
        payload["results"] = collect_statement_slice(
            graph,
            symbol_by_id,
            seeds,
            limit=limit,
            window=max(int(request.get("window") or 8), 1),
        )
        return payload

    if operation == "path_between":
        targets = resolve_seed_matches(
            search_root,
            parsed_root,
            graph,
            symbols_payload,
            repo_name,
            request.get("target"),
            limit=max(limit, 10),
        )
        payload["targets"] = [describe_node(target, symbol_by_id) for target in targets]
        payload["results"] = shortest_paths(
            graph,
            symbol_by_id,
            seeds,
            targets,
            edge_types=edge_types,
            direction=direction,
            node_kinds=node_kinds,
            limit=limit,
        )
        return payload

    if operation == "symbol_summary":
        payload["results"] = build_symbol_summaries(graph, symbol_by_id, seeds, limit=limit)
        return payload

    payload["results"] = collect_neighbors(
        graph,
        symbol_by_id,
        seeds,
        edge_types=edge_types,
        direction=direction,
        depth=depth,
        node_kinds=node_kinds,
        limit=limit,
    )
    return payload


def execute_cached_graph_query(
    search_root: Path,
    parsed_root: Path,
    graph_root: Path,
    repo_name: str,
    request: Dict[str, object],
) -> Optional[Dict[str, object]]:
    operation = str(request.get("operation") or "neighbors")
    sqlite_path = graph_root / repo_name / "graph.sqlite3"
    if not sqlite_path.exists():
        return None

    limit = max(int(request.get("limit") or 20), 1)
    depth = max(int(request.get("depth") or 1), 0)
    direction = str(request.get("direction") or EDGE_DIRECTIONS.get(operation, "both"))
    edge_types = tuple(request.get("edge_types") or EDGE_DEFAULTS.get(operation, ()))
    node_kinds = tuple(request.get("node_kinds") or ())
    seeds = resolve_cached_seed_matches(search_root, repo_name, request.get("seed") or request.get("query"), limit=max(limit, 10))
    if not seeds:
        return {
            "repo": repo_name,
            "operation": operation,
            "graph_backend": "sqlite",
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

    with sqlite3.connect(sqlite_path) as connection:
        connection.row_factory = sqlite3.Row
        if operation == "symbol_summary":
            if not has_symbol_summary_cache(connection):
                return None
        elif operation in {"callers_of", "callees_of"}:
            if not has_neighbor_cache(connection):
                return None
        elif operation == "neighbors":
            if not can_use_cached_neighbors(request, depth=depth, edge_types=edge_types):
                return None
            if not has_neighbor_cache(connection):
                return None
        elif operation in {"statement_slice", "path_between"}:
            pass
        else:
            return None
        seed_rows = load_nodes_by_id(connection, [seed["node_id"] for seed in seeds])
        described_seeds = [describe_sqlite_node(seed_rows[seed["node_id"]]) for seed in seeds if seed["node_id"] in seed_rows]

        payload = {
            "repo": repo_name,
            "operation": operation,
            "graph_backend": "sqlite",
            "request": {
                "direction": direction,
                "edge_types": list(edge_types),
                "depth": depth,
                "limit": limit,
                "node_kinds": list(node_kinds),
                "seed": request.get("seed") or request.get("query"),
            },
            "seeds": described_seeds,
        }

        if operation == "symbol_summary":
            payload["results"] = build_cached_symbol_summaries(connection, seeds, limit=limit)
        elif operation == "statement_slice":
            payload["results"] = build_cached_statement_slice(
                connection,
                seeds,
                limit=limit,
                window=max(int(request.get("window") or 8), 1),
            )
        elif operation == "path_between":
            targets = resolve_cached_seed_matches(search_root, repo_name, request.get("target"), limit=max(limit, 10))
            target_rows = load_nodes_by_id(connection, [target["node_id"] for target in targets])
            payload["targets"] = [
                describe_sqlite_node(target_rows[target["node_id"]])
                for target in targets
                if target["node_id"] in target_rows
            ]
            payload["results"] = build_cached_shortest_paths(
                connection,
                seeds,
                targets,
                edge_types=edge_types,
                direction=direction,
                node_kinds=node_kinds,
                limit=limit,
            )
        else:
            payload["results"] = build_cached_neighbors(
                connection,
                seeds,
                direction=direction,
                edge_types=edge_types,
                node_kinds=node_kinds,
                limit=limit,
            )
        return payload


def where_defined(
    search_root: Path,
    parsed_root: Path,
    repo_name: str,
    symbol_query: str,
    *,
    limit: int = 10,
) -> Dict[str, object]:
    with trace_operation("where_defined"):
        symbols = load_symbols_payload(parsed_root, repo_name)
        matches = resolve_symbol_matches(search_root, symbols, repo_name, symbol_query, limit=limit)
        return {
            "repo": repo_name,
            "query": symbol_query,
            "matches": [describe_symbol(symbol) for symbol in matches],
        }


def who_imports(
    search_root: Path,
    parsed_root: Path,
    graph_root: Path,
    repo_name: str,
    symbol_query: str,
    *,
    limit: int = 20,
) -> Dict[str, object]:
    return _neighbors_wrapper(
        search_root,
        parsed_root,
        graph_root,
        repo_name,
        symbol_query,
        operation="who_imports",
        limit=limit,
    )


def adjacent_symbols(
    search_root: Path,
    parsed_root: Path,
    graph_root: Path,
    repo_name: str,
    symbol_query: str,
    *,
    edge_types: Sequence[str] = (),
    direction: str = "both",
    limit: int = 20,
) -> Dict[str, object]:
    response = execute_graph_query(
        search_root,
        parsed_root,
        graph_root,
        repo_name,
        {
            "operation": "neighbors",
            "seed": symbol_query,
            "edge_types": list(edge_types),
            "direction": direction,
            "depth": 1,
            "limit": limit,
        },
    )
    return {
        "repo": repo_name,
        "query": symbol_query,
        "matches": response["seeds"],
        "neighbors": response["results"],
    }


def callers_of(
    search_root: Path,
    parsed_root: Path,
    graph_root: Path,
    repo_name: str,
    symbol_query: str,
    *,
    limit: int = 20,
) -> Dict[str, object]:
    with trace_operation("callers_of"):
        return _neighbors_wrapper(
            search_root,
            parsed_root,
            graph_root,
            repo_name,
            symbol_query,
            operation="callers_of",
            limit=limit,
        )


def callees_of(
    search_root: Path,
    parsed_root: Path,
    graph_root: Path,
    repo_name: str,
    symbol_query: str,
    *,
    limit: int = 20,
) -> Dict[str, object]:
    with trace_operation("callees_of"):
        return _neighbors_wrapper(
            search_root,
            parsed_root,
            graph_root,
            repo_name,
            symbol_query,
            operation="callees_of",
            limit=limit,
        )


def reads_of(
    search_root: Path,
    parsed_root: Path,
    graph_root: Path,
    repo_name: str,
    symbol_query: str,
    *,
    limit: int = 20,
) -> Dict[str, object]:
    return _neighbors_wrapper(
        search_root,
        parsed_root,
        graph_root,
        repo_name,
        symbol_query,
        operation="reads_of",
        limit=limit,
    )


def writes_of(
    search_root: Path,
    parsed_root: Path,
    graph_root: Path,
    repo_name: str,
    symbol_query: str,
    *,
    limit: int = 20,
) -> Dict[str, object]:
    return _neighbors_wrapper(
        search_root,
        parsed_root,
        graph_root,
        repo_name,
        symbol_query,
        operation="writes_of",
        limit=limit,
    )


def refs_of(
    search_root: Path,
    parsed_root: Path,
    graph_root: Path,
    repo_name: str,
    symbol_query: str,
    *,
    limit: int = 20,
) -> Dict[str, object]:
    return _neighbors_wrapper(
        search_root,
        parsed_root,
        graph_root,
        repo_name,
        symbol_query,
        operation="refs_of",
        limit=limit,
    )


def implements_of(
    search_root: Path,
    parsed_root: Path,
    graph_root: Path,
    repo_name: str,
    symbol_query: str,
    *,
    limit: int = 20,
) -> Dict[str, object]:
    return _neighbors_wrapper(
        search_root,
        parsed_root,
        graph_root,
        repo_name,
        symbol_query,
        operation="implements_of",
        limit=limit,
    )


def inherits_of(
    search_root: Path,
    parsed_root: Path,
    graph_root: Path,
    repo_name: str,
    symbol_query: str,
    *,
    limit: int = 20,
) -> Dict[str, object]:
    return _neighbors_wrapper(
        search_root,
        parsed_root,
        graph_root,
        repo_name,
        symbol_query,
        operation="inherits_of",
        limit=limit,
    )


def statement_slice(
    search_root: Path,
    parsed_root: Path,
    graph_root: Path,
    repo_name: str,
    symbol_query: str,
    *,
    limit: int = 20,
    window: int = 8,
) -> Dict[str, object]:
    with trace_operation("statement_slice"):
        response = execute_graph_query(
            search_root,
            parsed_root,
            graph_root,
            repo_name,
            {
                "operation": "statement_slice",
                "seed": symbol_query,
                "limit": limit,
                "window": window,
            },
        )
        return {
            "repo": repo_name,
            "query": symbol_query,
            "matches": response["seeds"],
            "statements": response["results"],
        }


def path_between(
    search_root: Path,
    parsed_root: Path,
    graph_root: Path,
    repo_name: str,
    source_query: str,
    target_query: str,
    *,
    limit: int = 5,
    edge_types: Sequence[str] = (),
    direction: str = "both",
) -> Dict[str, object]:
    with trace_operation("path_between"):
        response = execute_graph_query(
            search_root,
            parsed_root,
            graph_root,
            repo_name,
            {
                "operation": "path_between",
                "seed": source_query,
                "target": target_query,
                "limit": limit,
                "edge_types": list(edge_types),
                "direction": direction,
            },
        )
        return {
            "repo": repo_name,
            "source_query": source_query,
            "target_query": target_query,
            "matches": response["seeds"],
            "targets": response.get("targets", []),
            "paths": response["results"],
        }


def symbol_summary(
    search_root: Path,
    parsed_root: Path,
    graph_root: Path,
    repo_name: str,
    symbol_query: str,
    *,
    limit: int = 5,
) -> Dict[str, object]:
    response = execute_graph_query(
        search_root,
        parsed_root,
        graph_root,
        repo_name,
        {
            "operation": "symbol_summary",
            "seed": symbol_query,
            "limit": limit,
        },
    )
    return {
        "repo": repo_name,
        "query": symbol_query,
        "matches": response["seeds"],
        "summaries": response["results"],
    }


def load_graph_view(graph_root: Path, repo_name: str) -> Dict[str, object]:
    return _load_graph_view_cached(str(graph_root.resolve()), repo_name)


@lru_cache(maxsize=8)
def _load_graph_view_cached(graph_root: str, repo_name: str) -> Dict[str, object]:
    root = Path(graph_root)
    ryugraph_path = root / repo_name / "ryugraph.json"
    if ryugraph_path.exists():
        return graph_indexes(load_json(ryugraph_path), backend="ryugraph")
    graph_json_path = root / repo_name / "graph.json"
    if graph_json_path.exists():
        return load_graph_json(graph_json_path)
    if os.environ.get("CAXEN_ENABLE_SQLITE_HOTPATH_READS") != "1":
        raise FileNotFoundError(f"Missing ryugraph/json graph artifact for repo '{repo_name}' under {root / repo_name}")
    sqlite_path = root / repo_name / "graph.sqlite3"
    if sqlite_path.exists():
        return load_graph_sqlite(sqlite_path)
    return load_graph_json(graph_json_path)


def load_graph_view_uncached(graph_root: Path, repo_name: str) -> Dict[str, object]:
    increment_counter("full_graph_payload_loads")
    with trace_operation("load_graph_view_uncached"):
        ryugraph_path = graph_root / repo_name / "ryugraph.json"
        if ryugraph_path.exists():
            return graph_indexes(load_json(ryugraph_path), backend="ryugraph")
        graph_json_path = graph_root / repo_name / "graph.json"
        if graph_json_path.exists():
            return load_graph_json(graph_json_path)
        if os.environ.get("CAXEN_ENABLE_SQLITE_HOTPATH_READS") != "1":
            raise FileNotFoundError(
                f"Missing ryugraph/json graph artifact for repo '{repo_name}' under {graph_root / repo_name}"
            )
        sqlite_path = graph_root / repo_name / "graph.sqlite3"
        if sqlite_path.exists():
            return load_graph_sqlite(sqlite_path)
        return load_graph_json(graph_json_path)


def has_symbol_summary_cache(connection: sqlite3.Connection) -> bool:
    row = connection.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='symbol_summary_cache'"
    ).fetchone()
    return row is not None


def has_neighbor_cache(connection: sqlite3.Connection) -> bool:
    row = connection.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='neighbor_cache'"
    ).fetchone()
    return row is not None


def can_use_cached_neighbors(
    request: Dict[str, object],
    *,
    depth: int,
    edge_types: Sequence[str],
) -> bool:
    if depth > 1:
        return False
    requested_edge_types = set(edge_types)
    if not requested_edge_types:
        return False
    return requested_edge_types.issubset(CACHEABLE_NEIGHBOR_EDGE_TYPES)


def load_graph_json(path: Path) -> Dict[str, object]:
    payload = load_json(path)
    return graph_indexes(payload, backend="json")


def load_graph_sqlite(path: Path) -> Dict[str, object]:
    with sqlite3.connect(path) as connection:
        connection.row_factory = sqlite3.Row
        nodes = []
        for row in connection.execute(
            "SELECT node_id, kind, repo, path, name, qualified_name, metadata_json FROM nodes"
        ):
            metadata = json.loads(row["metadata_json"] or "{}")
            nodes.append(
                {
                    "node_id": row["node_id"],
                    "kind": row["kind"],
                    "repo": row["repo"],
                    "path": row["path"],
                    "name": row["name"],
                    "qualified_name": row["qualified_name"],
                    **metadata,
                }
            )
        edges = []
        for row in connection.execute(
            "SELECT edge_id, type, source_node_id, target_node_id, path, metadata_json FROM edges"
        ):
            metadata = json.loads(row["metadata_json"] or "{}")
            edges.append(
                {
                    "edge_id": row["edge_id"],
                    "type": row["type"],
                    "from": row["source_node_id"],
                    "to": row["target_node_id"],
                    "metadata": metadata,
                }
            )
        metadata_rows = dict(connection.execute("SELECT key, value FROM metadata").fetchall())

    payload = {
        "repo": metadata_rows.get("repo"),
        "generated_at": metadata_rows.get("generated_at"),
        "schema_version": metadata_rows.get("schema_version"),
        "summary": json.loads(metadata_rows.get("summary_json") or "{}"),
        "nodes": nodes,
        "edges": edges,
    }
    return graph_indexes(payload, backend="sqlite")


def graph_indexes(payload: Dict[str, object], *, backend: str) -> Dict[str, object]:
    node_by_id = {node["node_id"]: node for node in payload.get("nodes", [])}
    outgoing: Dict[str, List[Dict[str, object]]] = defaultdict(list)
    incoming: Dict[str, List[Dict[str, object]]] = defaultdict(list)
    for edge in payload.get("edges", []):
        outgoing[edge["from"]].append(edge)
        incoming[edge["to"]].append(edge)
    for node_id in outgoing:
        outgoing[node_id].sort(key=edge_sort_key)
    for node_id in incoming:
        incoming[node_id].sort(key=edge_sort_key)
    return {
        "backend": backend,
        "payload": payload,
        "node_by_id": node_by_id,
        "outgoing": outgoing,
        "incoming": incoming,
    }


def edge_sort_key(edge: Dict[str, object]) -> Tuple[str, str, str]:
    metadata = edge.get("metadata", {})
    return (
        str(edge["type"]),
        str(metadata.get("path") or ""),
        str(metadata.get("line") or 0),
    )


def load_symbols_payload(parsed_root: Path, repo_name: str) -> Dict[str, object]:
    return load_symbol_index(parsed_root, repo_name)


def resolve_seed_matches(
    search_root: Path,
    parsed_root: Path,
    graph: Dict[str, object],
    symbols_payload: Dict[str, object],
    repo_name: str,
    seed: object,
    *,
    limit: int,
) -> List[Dict[str, object]]:
    if seed is None:
        return []

    symbol_by_id = {item["symbol_id"]: item for item in symbols_payload.get("symbols", [])}
    node_by_id = graph["node_by_id"]

    if isinstance(seed, dict):
        if seed.get("symbol_id"):
            symbol = symbol_by_id.get(str(seed["symbol_id"]))
            if symbol:
                node = node_by_id.get(symbol["symbol_id"])
                return [node] if node else []
        if seed.get("node_id"):
            node = node_by_id.get(str(seed["node_id"]))
            return [node] if node else []
        if seed.get("qualified_name"):
            raw_query = str(seed["qualified_name"])
            matches = direct_symbol_matches(symbols_payload.get("symbols", []), raw_query, raw_query.lower())
            return [node_by_id[item["symbol_id"]] for item in matches if item["symbol_id"] in node_by_id][:limit]
        if seed.get("name"):
            raw_query = str(seed["name"])
            matches = direct_symbol_matches(symbols_payload.get("symbols", []), raw_query, raw_query.lower())
            return [node_by_id[item["symbol_id"]] for item in matches if item["symbol_id"] in node_by_id][:limit]
        if seed.get("path"):
            return resolve_path_nodes(node_by_id, str(seed["path"]), limit=limit)

    if not isinstance(seed, str):
        return []

    query = seed.strip()
    if not query:
        return []

    if query in node_by_id:
        return [node_by_id[query]]

    symbol_matches = resolve_symbol_matches(search_root, symbols_payload, repo_name, query, limit=limit)
    if symbol_matches:
        nodes = [node_by_id[item["symbol_id"]] for item in symbol_matches if item["symbol_id"] in node_by_id]
        if nodes:
            return nodes[:limit]

    path_matches = resolve_path_nodes(node_by_id, query, limit=limit)
    if path_matches:
        return path_matches

    search_results = search_documents(search_root, repo_name, query, limit=max(limit * 4, 20))
    matches: List[Dict[str, object]] = []
    seen = set()
    for result in search_results:
        node = search_result_to_node(node_by_id, result, repo_name)
        if not node or node["node_id"] in seen:
            continue
        seen.add(node["node_id"])
        matches.append(node)
    return matches[:limit]


def resolve_cached_seed_matches(
    search_root: Path,
    repo_name: str,
    seed: object,
    *,
    limit: int,
) -> List[Dict[str, object]]:
    if seed is None:
        return []
    if isinstance(seed, dict):
        if seed.get("symbol_id"):
            return [{"node_id": str(seed["symbol_id"])}]
        if seed.get("node_id"):
            return [{"node_id": str(seed["node_id"])}]
        if seed.get("qualified_name"):
            return resolve_cached_search_matches(search_root, repo_name, str(seed["qualified_name"]), limit=limit)
        if seed.get("name"):
            return resolve_cached_search_matches(search_root, repo_name, str(seed["name"]), limit=limit)
        if seed.get("path"):
            return resolve_cached_path_matches(search_root, repo_name, str(seed["path"]), limit=limit)
        return []
    if not isinstance(seed, str):
        return []
    query = seed.strip()
    if not query:
        return []
    if query.startswith("sym:"):
        return [{"node_id": query}]
    return resolve_cached_search_matches(search_root, repo_name, query, limit=limit)


def resolve_cached_search_matches(
    search_root: Path,
    repo_name: str,
    query: str,
    *,
    limit: int,
) -> List[Dict[str, object]]:
    normalized = query.lower()
    results = search_documents(search_root, repo_name, query, limit=max(limit * 4, 40), kinds=("symbol",))
    scored = []
    direct_only = []
    seen = set()
    for result in results:
        symbol_id = str(result.get("symbol_id") or "")
        if not symbol_id or symbol_id in seen:
            continue
        seen.add(symbol_id)
        qualified_name = str(result.get("qualified_name") or "")
        name = str(result.get("name") or "")
        terminal = qualified_name.split("::")[-1] if qualified_name else ""
        score = 0
        if qualified_name == query:
            score += 120
        if name == query:
            score += 100
        if terminal == query:
            score += 90
        if qualified_name.lower() == normalized:
            score += 80
        if name.lower() == normalized:
            score += 70
        if terminal.lower() == normalized:
            score += 60
        score += int(float(result.get("score") or 0.0) * 10)
        if normalized in {qualified_name.lower(), name.lower(), terminal.lower()}:
            direct_only.append((score, symbol_id, qualified_name, name))
        scored.append((score, symbol_id, qualified_name, name))
    final = direct_only or scored
    final.sort(key=lambda item: (-item[0], item[2], item[3]))
    return [{"node_id": item[1]} for item in final[:limit]]


def resolve_cached_path_matches(
    search_root: Path,
    repo_name: str,
    path_query: str,
    *,
    limit: int,
) -> List[Dict[str, object]]:
    results = search_documents(search_root, repo_name, path_query, limit=max(limit * 4, 40), kinds=("symbol", "file"))
    scored = []
    seen = set()
    for result in results:
        node_id = str(result.get("symbol_id") or "")
        if not node_id and str(result.get("kind") or "") == "file" and result.get("path"):
            node_id = stable_file_id(repo_name, str(result["path"]))
        if not node_id or node_id in seen:
            continue
        seen.add(node_id)
        path = str(result.get("path") or "")
        score = 0
        if path == path_query:
            score += 120
        elif path.startswith(f"{path_query}/"):
            score += 80
        score += int(float(result.get("score") or 0.0) * 10)
        scored.append((score, node_id, path))
    scored.sort(key=lambda item: (-item[0], item[2]))
    return [{"node_id": item[1]} for item in scored[:limit]]


def resolve_symbol_matches(
    search_root: Path,
    symbols_payload: Dict[str, object],
    repo_name: str,
    symbol_query: str,
    *,
    limit: int = 10,
) -> List[Dict[str, object]]:
    normalized = symbol_query.lower()
    symbol_by_id = {symbol["symbol_id"]: symbol for symbol in symbols_payload.get("symbols", [])}
    direct_symbol_id_match = symbol_by_id.get(symbol_query)
    if direct_symbol_id_match:
        return [direct_symbol_id_match]

    direct_matches = direct_symbol_matches(symbols_payload.get("symbols", []), symbol_query, normalized)
    if direct_matches:
        return direct_matches[:limit]

    search_results = search_documents(search_root, repo_name, symbol_query, limit=max(limit * 4, 40), kinds=("symbol",))
    matches = []
    seen = set()
    for result in search_results:
        symbol_id = result.get("symbol_id")
        symbol = symbol_by_id.get(symbol_id)
        if not symbol or symbol_id in seen:
            continue
        seen.add(symbol_id)
        score = 0
        if str(symbol.get("qualified_name") or "").lower() == normalized:
            score += 100
        if str(symbol.get("name") or "").lower() == normalized:
            score += 50
        score += int(float(result.get("score") or 0.0) * 10)
        match = dict(symbol)
        match["_match_score"] = score
        matches.append(match)
    matches.sort(key=lambda item: (-int(item["_match_score"]), str(item["path"]), str(item["qualified_name"])))
    direct_only = [
        match
        for match in matches
        if normalized
        in {
            str(match.get("name") or "").lower(),
            str(match.get("qualified_name") or "").lower(),
            str(match.get("qualified_name") or "").lower().split("::")[-1],
        }
    ]
    if direct_only:
        matches = direct_only
    for match in matches:
        match.pop("_match_score", None)
    return matches[:limit]


def direct_symbol_matches(
    symbols: Sequence[Dict[str, object]],
    raw_query: str,
    normalized_query: str,
) -> List[Dict[str, object]]:
    matches = []
    for symbol in symbols:
        candidates = {
            str(symbol.get("name") or "").lower(),
            str(symbol.get("qualified_name") or "").lower(),
            str(symbol.get("qualified_name") or "").lower().split("::")[-1],
        }
        if normalized_query not in candidates:
            continue
        matches.append(symbol)
    return sorted(
        matches,
        key=lambda item: (
            exact_symbol_match_rank(item, raw_query, normalized_query),
            visibility_rank(str(item.get("visibility") or "")),
            kind_rank(str(item.get("kind") or "")),
            str(item.get("path") or ""),
            str(item.get("qualified_name") or ""),
        ),
    )


def exact_symbol_match_rank(symbol: Dict[str, object], raw_query: str, normalized_query: str) -> int:
    qualified_name_raw = str(symbol.get("qualified_name") or "")
    name_raw = str(symbol.get("name") or "")
    terminal_raw = qualified_name_raw.split("::")[-1] if qualified_name_raw else ""
    qualified_name = qualified_name_raw.lower()
    name = name_raw.lower()
    terminal = terminal_raw.lower()
    if qualified_name_raw == raw_query:
        return 0
    if name_raw == raw_query:
        return 1
    if terminal_raw == raw_query:
        return 2
    if qualified_name == normalized_query:
        return 3
    if name == normalized_query:
        return 4
    if terminal == normalized_query:
        return 5
    return 6


def visibility_rank(visibility: str) -> int:
    if visibility.startswith("pub"):
        return 0
    if visibility == "public":
        return 0
    return 1


def resolve_path_nodes(node_by_id: Dict[str, Dict[str, object]], path_query: str, *, limit: int) -> List[Dict[str, object]]:
    matches = [
        node
        for node in node_by_id.values()
        if str(node.get("path") or "") == path_query
        or str(node.get("path") or "").startswith(f"{path_query}/")
    ]
    matches.sort(
        key=lambda item: (
            0 if str(item.get("path") or "") == path_query else 1,
            kind_rank(item["kind"]),
            str(item.get("qualified_name") or item.get("name") or ""),
        )
    )
    return matches[:limit]


def search_result_to_node(
    node_by_id: Dict[str, Dict[str, object]],
    result: Dict[str, object],
    repo_name: str,
) -> Optional[Dict[str, object]]:
    symbol_id = result.get("symbol_id")
    if symbol_id and symbol_id in node_by_id:
        return node_by_id[symbol_id]
    if result.get("kind") == "file" and result.get("path"):
        node_id = stable_file_id(repo_name, str(result["path"]))
        return node_by_id.get(node_id)
    return None


def collect_neighbors(
    graph: Dict[str, object],
    symbol_by_id: Dict[str, Dict[str, object]],
    seeds: Sequence[Dict[str, object]],
    *,
    edge_types: Sequence[str],
    direction: str,
    depth: int,
    node_kinds: Sequence[str],
    limit: int,
) -> List[Dict[str, object]]:
    allowed_edge_types = set(edge_types)
    allowed_node_kinds = set(node_kinds)
    node_by_id = graph["node_by_id"]
    outgoing = graph["outgoing"]
    incoming = graph["incoming"]
    queue = deque((seed["node_id"], 0, "seed") for seed in seeds)
    seen_nodes = {seed["node_id"] for seed in seeds}
    seen_results = set()
    results: List[Dict[str, object]] = []

    while queue and len(results) < limit:
        node_id, current_depth, arrived_via = queue.popleft()
        if current_depth >= max(depth, 1):
            continue
        edge_sets = []
        if direction in {"outgoing", "both"}:
            edge_sets.append(("outgoing", outgoing.get(node_id, [])))
        if direction in {"incoming", "both"}:
            edge_sets.append(("incoming", incoming.get(node_id, [])))
        for edge_direction, edges in edge_sets:
            for edge in edges:
                if allowed_edge_types and edge["type"] not in allowed_edge_types:
                    continue
                neighbor_id = edge["to"] if edge_direction == "outgoing" else edge["from"]
                neighbor = node_by_id.get(neighbor_id)
                if not neighbor:
                    continue
                if allowed_node_kinds and neighbor["kind"] not in allowed_node_kinds:
                    continue
                key = (neighbor_id, edge["type"], edge_direction, current_depth + 1)
                if key in seen_results:
                    continue
                seen_results.add(key)
                results.append(
                    {
                        "depth": current_depth + 1,
                        "direction": edge_direction,
                        "edge_type": edge["type"],
                        "arrived_via": arrived_via,
                        **describe_node(neighbor, symbol_by_id),
                        "edge_metadata": edge.get("metadata", {}),
                    }
                )
                if neighbor_id not in seen_nodes:
                    seen_nodes.add(neighbor_id)
                    queue.append((neighbor_id, current_depth + 1, edge["type"]))
                if len(results) >= limit:
                    break
            if len(results) >= limit:
                break

    results.sort(
        key=lambda item: (
            int(item["depth"]),
            str(item["edge_type"]),
            str(item.get("path") or ""),
            str(item.get("qualified_name") or item.get("name") or ""),
        )
    )
    return results[:limit]


def collect_statement_slice(
    graph: Dict[str, object],
    symbol_by_id: Dict[str, Dict[str, object]],
    seeds: Sequence[Dict[str, object]],
    *,
    limit: int,
    window: int,
) -> List[Dict[str, object]]:
    node_by_id = graph["node_by_id"]
    outgoing = graph["outgoing"]
    incoming = graph["incoming"]
    statements: List[Dict[str, object]] = []
    seen = set()

    for seed in seeds:
        if seed["kind"] == "statement":
            statement_ids = {seed["node_id"]}
            for edge in outgoing.get(seed["node_id"], []):
                if edge["type"] == "CONTROL_FLOW" and len(statement_ids) < window:
                    statement_ids.add(edge["to"])
            for edge in incoming.get(seed["node_id"], []):
                if edge["type"] == "CONTROL_FLOW" and len(statement_ids) < window:
                    statement_ids.add(edge["from"])
        else:
            statement_ids = {
                edge["to"]
                for edge in outgoing.get(seed["node_id"], [])
                if edge["type"] == "CONTAINS" and node_by_id.get(edge["to"], {}).get("kind") == "statement"
            }
        for statement_id in statement_ids:
            if statement_id in seen:
                continue
            seen.add(statement_id)
            statement = node_by_id.get(statement_id)
            if not statement:
                continue
            statements.append(describe_statement(graph, symbol_by_id, statement))

    statements.sort(
        key=lambda item: (
            str(item.get("path") or ""),
            int(item.get("line") or 0),
            str(item["statement_id"]),
        )
    )
    return statements[:limit]


def shortest_paths(
    graph: Dict[str, object],
    symbol_by_id: Dict[str, Dict[str, object]],
    seeds: Sequence[Dict[str, object]],
    targets: Sequence[Dict[str, object]],
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
    target_ids = {target["node_id"] for target in targets}
    node_by_id = graph["node_by_id"]
    outgoing = graph["outgoing"]
    incoming = graph["incoming"]
    paths: List[Dict[str, object]] = []

    for seed in seeds:
        queue = deque([seed["node_id"]])
        parents: Dict[str, Tuple[Optional[str], Optional[Dict[str, object]]]] = {
            seed["node_id"]: (None, None)
        }
        found_target_id: Optional[str] = None
        while queue and found_target_id is None:
            current = queue.popleft()
            edge_sets = []
            if direction in {"outgoing", "both"}:
                edge_sets.append(("outgoing", outgoing.get(current, [])))
            if direction in {"incoming", "both"}:
                edge_sets.append(("incoming", incoming.get(current, [])))
            for edge_direction, edges in edge_sets:
                for edge in edges:
                    if allowed_edge_types and edge["type"] not in allowed_edge_types:
                        continue
                    neighbor_id = edge["to"] if edge_direction == "outgoing" else edge["from"]
                    neighbor = node_by_id.get(neighbor_id)
                    if not neighbor:
                        continue
                    if allowed_node_kinds and neighbor["kind"] not in allowed_node_kinds and neighbor_id not in target_ids:
                        continue
                    if neighbor_id in parents:
                        continue
                    parents[neighbor_id] = (
                        current,
                        {
                            "type": edge["type"],
                            "direction": edge_direction,
                            "metadata": edge.get("metadata", {}),
                        },
                    )
                    if neighbor_id in target_ids:
                        found_target_id = neighbor_id
                        break
                    queue.append(neighbor_id)
                if found_target_id is not None:
                    break
        if found_target_id is None:
            continue
        path_nodes = []
        path_edges = []
        cursor = found_target_id
        while cursor is not None:
            parent_id, parent_edge = parents[cursor]
            path_nodes.append(describe_node(node_by_id[cursor], symbol_by_id))
            if parent_edge is not None:
                path_edges.append(parent_edge)
            cursor = parent_id
        path_nodes.reverse()
        path_edges.reverse()
        paths.append(
            {
                "source": describe_node(seed, symbol_by_id),
                "target": describe_node(node_by_id[found_target_id], symbol_by_id),
                "hop_count": len(path_edges),
                "nodes": path_nodes,
                "edges": path_edges,
            }
        )
        if len(paths) >= limit:
            break

    paths.sort(
        key=lambda item: (
            int(item["hop_count"]),
            str(item["target"].get("path") or ""),
            str(item["target"].get("qualified_name") or item["target"].get("name") or ""),
        )
    )
    return paths[:limit]


def build_symbol_summaries(
    graph: Dict[str, object],
    symbol_by_id: Dict[str, Dict[str, object]],
    seeds: Sequence[Dict[str, object]],
    *,
    limit: int,
) -> List[Dict[str, object]]:
    node_by_id = graph["node_by_id"]
    outgoing = graph["outgoing"]
    incoming = graph["incoming"]
    summaries = []
    for seed in seeds[:limit]:
        if seed["kind"] in NON_SYMBOL_NODE_KINDS:
            continue
        direct_calls = count_edge_targets(outgoing.get(seed["node_id"], []), node_by_id, "CALLS")
        reads = count_edge_targets(outgoing.get(seed["node_id"], []), node_by_id, "READS")
        writes = count_edge_targets(outgoing.get(seed["node_id"], []), node_by_id, "WRITES")
        refs = count_edge_targets(outgoing.get(seed["node_id"], []), node_by_id, "REFS", "REFERENCES")
        statements = collect_statement_slice(graph, symbol_by_id, [seed], limit=6, window=6)
        summaries.append(
            {
                **describe_node(seed, symbol_by_id),
                "incoming_edge_counts": edge_counter(incoming.get(seed["node_id"], [])),
                "outgoing_edge_counts": edge_counter(outgoing.get(seed["node_id"], [])),
                "direct_calls": direct_calls,
                "reads": reads,
                "writes": writes,
                "references": refs,
                "defining_statements": statements,
                "summary": summarize_symbol(seed, direct_calls, reads, writes, refs, statements),
            }
        )
    return summaries


def describe_statement(
    graph: Dict[str, object],
    symbol_by_id: Dict[str, Dict[str, object]],
    statement: Dict[str, object],
) -> Dict[str, object]:
    outgoing = graph["outgoing"].get(statement["node_id"], [])
    incoming = graph["incoming"].get(statement["node_id"], [])
    edge_targets = defaultdict(list)
    for edge in outgoing:
        target = graph["node_by_id"].get(edge["to"])
        if target:
            edge_targets[edge["type"]].append(describe_node(target, symbol_by_id))
    control_predecessors = [
        describe_node(graph["node_by_id"][edge["from"]], symbol_by_id)
        for edge in incoming
        if edge["type"] == "CONTROL_FLOW" and edge["from"] in graph["node_by_id"]
    ]
    control_successors = [
        describe_node(graph["node_by_id"][edge["to"]], symbol_by_id)
        for edge in outgoing
        if edge["type"] == "CONTROL_FLOW" and edge["to"] in graph["node_by_id"]
    ]
    return {
        **describe_node(statement, symbol_by_id),
        "statement_id": statement["node_id"],
        "text": statement.get("text"),
        "container_symbol_id": statement.get("container_symbol_id"),
        "container_qualified_name": statement.get("container_qualified_name"),
        "line": int(str(statement.get("name") or "0").split("@L")[-1]) if "@L" in str(statement.get("name") or "") else 0,
        "defines": edge_targets.get("DEFINES", []),
        "reads": edge_targets.get("READS", []),
        "writes": edge_targets.get("WRITES", []),
        "refs": edge_targets.get("REFS", []) + edge_targets.get("REFERENCES", []),
        "calls": edge_targets.get("CALLS", []),
        "control_predecessors": control_predecessors,
        "control_successors": control_successors,
    }


def describe_node(node: Dict[str, object], symbol_by_id: Dict[str, Dict[str, object]]) -> Dict[str, object]:
    if not node:
        return {}
    payload = {
        "node_id": node["node_id"],
        "kind": node["kind"],
        "path": node.get("path"),
        "name": node.get("name"),
        "qualified_name": node.get("qualified_name"),
    }
    symbol = symbol_by_id.get(node["node_id"])
    if symbol:
        payload.update(
            {
                "symbol_id": symbol["symbol_id"],
                "span": symbol.get("span"),
                "container_qualified_name": symbol.get("container_qualified_name"),
                "signature": symbol.get("signature"),
                "visibility": symbol.get("visibility"),
            }
        )
    elif node["kind"] == "statement":
        payload["symbol_id"] = None
    elif str(node["node_id"]).startswith("sym:"):
        payload["symbol_id"] = node["node_id"]
    else:
        payload["symbol_id"] = None
    return payload


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


def describe_symbol(symbol: Dict[str, object]) -> Dict[str, object]:
    return {
        "symbol_id": symbol["symbol_id"],
        "kind": symbol["kind"],
        "name": symbol["name"],
        "qualified_name": symbol["qualified_name"],
        "path": symbol["path"],
        "span": symbol["span"],
        "container_qualified_name": symbol.get("container_qualified_name"),
        "signature": symbol.get("signature"),
    }


def load_nodes_by_id(connection: sqlite3.Connection, node_ids: Sequence[str]) -> Dict[str, sqlite3.Row]:
    if not node_ids:
        return {}
    rows = connection.execute(
        f"SELECT node_id, kind, repo, path, name, qualified_name, metadata_json FROM nodes WHERE node_id IN ({','.join('?' for _ in node_ids)})",
        list(node_ids),
    ).fetchall()
    return {str(row["node_id"]): row for row in rows}


def build_cached_symbol_summaries(
    connection: sqlite3.Connection,
    seeds: Sequence[Dict[str, object]],
    *,
    limit: int,
) -> List[Dict[str, object]]:
    seed_ids = [seed["node_id"] for seed in seeds[:limit]]
    cache_rows = connection.execute(
        f"""
        SELECT node_id, incoming_counts_json, outgoing_counts_json, direct_calls_json, reads_json, writes_json, refs_json, statements_json
        FROM symbol_summary_cache
        WHERE node_id IN ({','.join('?' for _ in seed_ids)})
        """,
        seed_ids,
    ).fetchall()
    cache_by_id = {str(row["node_id"]): row for row in cache_rows}
    referenced_ids: set[str] = set()
    for row in cache_rows:
        for column in ("direct_calls_json", "reads_json", "writes_json", "refs_json", "statements_json"):
            referenced_ids.update(json.loads(row[column] or "[]"))
    node_rows = load_nodes_by_id(connection, list(set(seed_ids) | referenced_ids))

    results = []
    for seed in seeds[:limit]:
        row = cache_by_id.get(seed["node_id"])
        seed_row = node_rows.get(seed["node_id"])
        if not row or not seed_row:
            continue
        described_seed = describe_sqlite_node(seed_row)
        direct_calls = hydrate_cached_node_list(node_rows, json.loads(row["direct_calls_json"] or "[]"))
        reads = hydrate_cached_node_list(node_rows, json.loads(row["reads_json"] or "[]"))
        writes = hydrate_cached_node_list(node_rows, json.loads(row["writes_json"] or "[]"))
        refs = hydrate_cached_node_list(node_rows, json.loads(row["refs_json"] or "[]"))
        statements = hydrate_cached_statements(node_rows, json.loads(row["statements_json"] or "[]"))
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
    results.sort(
        key=lambda item: (
            kind_rank(str(item.get("kind") or "")),
            str(item.get("path") or ""),
            str(item.get("qualified_name") or item.get("name") or ""),
        )
    )
    return results


def build_cached_neighbors(
    connection: sqlite3.Connection,
    seeds: Sequence[Dict[str, object]],
    *,
    direction: str,
    edge_types: Sequence[str],
    node_kinds: Sequence[str],
    limit: int,
) -> List[Dict[str, object]]:
    seed_ids = [seed["node_id"] for seed in seeds]
    if not seed_ids:
        return []
    cache_rows = connection.execute(
        f"""
        SELECT node_id, outgoing_edges_json, incoming_edges_json
        FROM neighbor_cache
        WHERE node_id IN ({','.join('?' for _ in seed_ids)})
        """,
        seed_ids,
    ).fetchall()
    cache_by_id = {str(row["node_id"]): row for row in cache_rows}
    requested_edge_types = set(edge_types)
    requested_node_kinds = set(node_kinds)
    raw_entries: list[dict[str, object]] = []
    referenced_ids: set[str] = set()

    for seed in seeds:
        row = cache_by_id.get(seed["node_id"])
        if not row:
            continue
        if direction in {"outgoing", "both"}:
            for entry in json.loads(row["outgoing_edges_json"] or "[]"):
                if requested_edge_types and str(entry.get("edge_type") or "") not in requested_edge_types:
                    continue
                raw_entries.append(
                    {
                        "direction": "outgoing",
                        "arrived_via": "seed",
                        "depth": 1,
                        "edge_type": str(entry.get("edge_type") or ""),
                        "neighbor_id": str(entry.get("neighbor_id") or ""),
                        "edge_metadata": dict(entry.get("edge_metadata") or {}),
                    }
                )
                referenced_ids.add(str(entry.get("neighbor_id") or ""))
        if direction in {"incoming", "both"}:
            for entry in json.loads(row["incoming_edges_json"] or "[]"):
                if requested_edge_types and str(entry.get("edge_type") or "") not in requested_edge_types:
                    continue
                raw_entries.append(
                    {
                        "direction": "incoming",
                        "arrived_via": "seed",
                        "depth": 1,
                        "edge_type": str(entry.get("edge_type") or ""),
                        "neighbor_id": str(entry.get("neighbor_id") or ""),
                        "edge_metadata": dict(entry.get("edge_metadata") or {}),
                    }
                )
                referenced_ids.add(str(entry.get("neighbor_id") or ""))

    node_rows = load_nodes_by_id(connection, list(referenced_ids))
    results: list[Dict[str, object]] = []
    seen = set()
    for entry in raw_entries:
        neighbor_id = str(entry["neighbor_id"])
        if not neighbor_id:
            continue
        row = node_rows.get(neighbor_id)
        if not row:
            continue
        if requested_node_kinds and str(row["kind"]) not in requested_node_kinds:
            continue
        dedupe_key = (neighbor_id, str(entry["edge_type"]), str(entry["direction"]), 1)
        if dedupe_key in seen:
            continue
        seen.add(dedupe_key)
        results.append(
            {
                "depth": 1,
                "direction": str(entry["direction"]),
                "edge_type": str(entry["edge_type"]),
                "arrived_via": "seed",
                **describe_sqlite_node(row),
                "edge_metadata": dict(entry["edge_metadata"]),
            }
        )

    results.sort(
        key=lambda item: (
            int(item["depth"]),
            str(item["edge_type"]),
            str(item.get("path") or ""),
            str(item.get("qualified_name") or item.get("name") or ""),
        )
    )
    return results[:limit]


def hydrate_cached_node_list(
    node_rows: Dict[str, sqlite3.Row],
    node_ids: Sequence[str],
) -> List[Dict[str, object]]:
    results = []
    for node_id in node_ids:
        row = node_rows.get(node_id)
        if not row:
            continue
        results.append(describe_sqlite_node(row))
    return results


def hydrate_cached_statements(
    node_rows: Dict[str, sqlite3.Row],
    statement_ids: Sequence[str],
) -> List[Dict[str, object]]:
    results = []
    for node_id in statement_ids:
        row = node_rows.get(node_id)
        if not row:
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


def build_cached_statement_slice(
    connection: sqlite3.Connection,
    seeds: Sequence[Dict[str, object]],
    *,
    limit: int,
    window: int,
) -> List[Dict[str, object]]:
    if not seeds:
        return []
    seed_ids = [seed["node_id"] for seed in seeds]
    seed_rows = load_nodes_by_id(connection, seed_ids)
    statement_ids: list[str] = []
    seen_statement_ids: set[str] = set()

    for seed in seeds:
        seed_row = seed_rows.get(seed["node_id"])
        if seed_row is None:
            continue
        if str(seed_row["kind"]) == "statement":
            candidate_ids = [seed["node_id"]]
            outgoing_rows = connection.execute(
                """
                SELECT target_node_id
                FROM edges
                WHERE source_node_id = ? AND type = 'CONTROL_FLOW'
                ORDER BY edge_id
                LIMIT ?
                """,
                [seed["node_id"], window],
            ).fetchall()
            incoming_rows = connection.execute(
                """
                SELECT source_node_id
                FROM edges
                WHERE target_node_id = ? AND type = 'CONTROL_FLOW'
                ORDER BY edge_id
                LIMIT ?
                """,
                [seed["node_id"], window],
            ).fetchall()
            candidate_ids.extend(str(row[0]) for row in outgoing_rows)
            candidate_ids.extend(str(row[0]) for row in incoming_rows)
        else:
            contain_rows = connection.execute(
                """
                SELECT target_node_id
                FROM edges
                WHERE source_node_id = ? AND type = 'CONTAINS'
                ORDER BY edge_id
                LIMIT ?
                """,
                [seed["node_id"], window * 4],
            ).fetchall()
            candidate_ids = [str(row[0]) for row in contain_rows]

        if candidate_ids:
            node_rows = load_nodes_by_id(connection, candidate_ids)
            ordered = sorted(
                (
                    row for row in node_rows.values()
                    if str(row["kind"]) == "statement"
                ),
                key=lambda row: statement_row_sort_key(row),
            )
            for row in ordered[:window]:
                statement_id = str(row["node_id"])
                if statement_id in seen_statement_ids:
                    continue
                seen_statement_ids.add(statement_id)
                statement_ids.append(statement_id)
                if len(statement_ids) >= limit:
                    break
        if len(statement_ids) >= limit:
            break

    statement_rows = load_nodes_by_id(connection, statement_ids)
    return [
        hydrate_cached_statement(connection, statement_rows[statement_id])
        for statement_id in statement_ids
        if statement_id in statement_rows
    ][:limit]


def hydrate_cached_statement(connection: sqlite3.Connection, row: sqlite3.Row) -> Dict[str, object]:
    metadata = json.loads(row["metadata_json"] or "{}")
    statement_id = str(row["node_id"])
    outgoing_rows = connection.execute(
        """
        SELECT type, target_node_id
        FROM edges
        WHERE source_node_id = ?
        ORDER BY edge_id
        """,
        [statement_id],
    ).fetchall()
    incoming_rows = connection.execute(
        """
        SELECT type, source_node_id
        FROM edges
        WHERE target_node_id = ?
        ORDER BY edge_id
        """,
        [statement_id],
    ).fetchall()
    referenced_ids = {
        str(item[1])
        for item in outgoing_rows
        if item[1]
    } | {
        str(item[1])
        for item in incoming_rows
        if item[1]
    }
    node_rows = load_nodes_by_id(connection, list(referenced_ids))
    described = describe_sqlite_node(row)
    described["statement_id"] = statement_id
    described["text"] = metadata.get("text")
    described["container_symbol_id"] = metadata.get("container_symbol_id")
    described["container_qualified_name"] = metadata.get("container_qualified_name")
    described["line"] = int(str(described.get("name") or "0").split("@L")[-1]) if "@L" in str(described.get("name") or "") else 0
    described["defines"] = hydrate_cached_node_list(node_rows, [str(item[1]) for item in outgoing_rows if str(item[0]) == "DEFINES"])
    described["reads"] = hydrate_cached_node_list(node_rows, [str(item[1]) for item in outgoing_rows if str(item[0]) == "READS"])
    described["writes"] = hydrate_cached_node_list(node_rows, [str(item[1]) for item in outgoing_rows if str(item[0]) == "WRITES"])
    described["refs"] = hydrate_cached_node_list(
        node_rows,
        [str(item[1]) for item in outgoing_rows if str(item[0]) in {"REFS", "REFERENCES"}],
    )
    described["calls"] = hydrate_cached_node_list(node_rows, [str(item[1]) for item in outgoing_rows if str(item[0]) == "CALLS"])
    described["control_predecessors"] = hydrate_cached_node_list(
        node_rows,
        [str(item[1]) for item in incoming_rows if str(item[0]) == "CONTROL_FLOW"],
    )
    described["control_successors"] = hydrate_cached_node_list(
        node_rows,
        [str(item[1]) for item in outgoing_rows if str(item[0]) == "CONTROL_FLOW"],
    )
    return described


def build_cached_shortest_paths(
    connection: sqlite3.Connection,
    seeds: Sequence[Dict[str, object]],
    targets: Sequence[Dict[str, object]],
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
    target_ids = {target["node_id"] for target in targets}
    results: list[Dict[str, object]] = []

    for seed in seeds:
        queue = deque([seed["node_id"]])
        parents: Dict[str, Tuple[Optional[str], Optional[Dict[str, object]]]] = {
            seed["node_id"]: (None, None)
        }
        found_target_id: Optional[str] = None
        while queue and found_target_id is None:
            current = queue.popleft()
            for neighbor_id, edge_payload in query_cached_adjacency(
                connection,
                current,
                direction=direction,
                edge_types=allowed_edge_types,
            ):
                neighbor_row = load_nodes_by_id(connection, [neighbor_id]).get(neighbor_id)
                if neighbor_row is None:
                    continue
                neighbor_kind = str(neighbor_row["kind"] or "")
                if allowed_node_kinds and neighbor_kind not in allowed_node_kinds and neighbor_id not in target_ids:
                    continue
                if neighbor_id in parents:
                    continue
                parents[neighbor_id] = (current, edge_payload)
                if neighbor_id in target_ids:
                    found_target_id = neighbor_id
                    break
                queue.append(neighbor_id)

        if found_target_id is None:
            continue

        ordered_node_ids: list[str] = []
        ordered_edges: list[Dict[str, object]] = []
        cursor = found_target_id
        while cursor is not None:
            parent_id, parent_edge = parents[cursor]
            ordered_node_ids.append(cursor)
            if parent_edge is not None:
                ordered_edges.append(parent_edge)
            cursor = parent_id
        ordered_node_ids.reverse()
        ordered_edges.reverse()
        node_rows = load_nodes_by_id(connection, ordered_node_ids)
        results.append(
            {
                "source": describe_sqlite_node(node_rows[seed["node_id"]]),
                "target": describe_sqlite_node(node_rows[found_target_id]),
                "hop_count": len(ordered_edges),
                "nodes": [describe_sqlite_node(node_rows[node_id]) for node_id in ordered_node_ids if node_id in node_rows],
                "edges": ordered_edges,
            }
        )
        if len(results) >= limit:
            break

    results.sort(
        key=lambda item: (
            int(item["hop_count"]),
            str(item["target"].get("path") or ""),
            str(item["target"].get("qualified_name") or item["target"].get("name") or ""),
        )
    )
    return results[:limit]


def query_cached_adjacency(
    connection: sqlite3.Connection,
    node_id: str,
    *,
    direction: str,
    edge_types: set[str],
) -> List[Tuple[str, Dict[str, object]]]:
    entries: list[Tuple[str, Dict[str, object]]] = []
    if direction in {"outgoing", "both"}:
        rows = connection.execute(
            """
            SELECT edge_id, type, target_node_id, metadata_json
            FROM edges
            WHERE source_node_id = ?
            ORDER BY edge_id
            """,
            [node_id],
        ).fetchall()
        for row in rows:
            edge_type = str(row["type"])
            if edge_types and edge_type not in edge_types:
                continue
            entries.append(
                (
                    str(row["target_node_id"]),
                    {
                        "type": edge_type,
                        "direction": "outgoing",
                        "metadata": json.loads(row["metadata_json"] or "{}"),
                    },
                )
            )
    if direction in {"incoming", "both"}:
        rows = connection.execute(
            """
            SELECT edge_id, type, source_node_id, metadata_json
            FROM edges
            WHERE target_node_id = ?
            ORDER BY edge_id
            """,
            [node_id],
        ).fetchall()
        for row in rows:
            edge_type = str(row["type"])
            if edge_types and edge_type not in edge_types:
                continue
            entries.append(
                (
                    str(row["source_node_id"]),
                    {
                        "type": edge_type,
                        "direction": "incoming",
                        "metadata": json.loads(row["metadata_json"] or "{}"),
                    },
                )
            )
    return entries


def statement_row_sort_key(row: sqlite3.Row) -> Tuple[str, int, str]:
    metadata = json.loads(row["metadata_json"] or "{}")
    span = metadata.get("span") or {}
    return (
        str(row["path"] or ""),
        int(span.get("start_line") or 0),
        str(row["node_id"]),
    )


def count_edge_targets(
    edges: Iterable[Dict[str, object]],
    node_by_id: Dict[str, Dict[str, object]],
    *edge_types: str,
) -> List[Dict[str, object]]:
    seen = set()
    results = []
    for edge in edges:
        if edge["type"] not in edge_types:
            continue
        node = node_by_id.get(edge["to"])
        if not node:
            continue
        key = node["node_id"]
        if key in seen:
            continue
        seen.add(key)
        results.append(
            {
                "node_id": node["node_id"],
                "kind": node["kind"],
                "path": node.get("path"),
                "name": node.get("name"),
                "qualified_name": node.get("qualified_name"),
            }
        )
    results.sort(key=lambda item: (str(item.get("path") or ""), str(item.get("qualified_name") or item.get("name") or "")))
    return results[:10]


def edge_counter(edges: Iterable[Dict[str, object]]) -> Dict[str, int]:
    counts = Counter(edge["type"] for edge in edges)
    return {edge_type: counts[edge_type] for edge_type in sorted(counts)}


def summarize_symbol(
    seed: Dict[str, object],
    direct_calls: Sequence[Dict[str, object]],
    reads: Sequence[Dict[str, object]],
    writes: Sequence[Dict[str, object]],
    refs: Sequence[Dict[str, object]],
    statements: Sequence[Dict[str, object]],
) -> str:
    fragments = [f"{seed['kind']} {seed.get('qualified_name') or seed.get('name')}"]
    if seed.get("path"):
        fragments.append(f"is defined in {seed['path']}")
    if direct_calls:
        fragments.append(f"direct calls: {', '.join(item.get('name') or item.get('qualified_name') or '' for item in direct_calls[:3])}")
    if reads:
        fragments.append(f"reads: {', '.join(item.get('name') or item.get('qualified_name') or '' for item in reads[:3])}")
    if writes:
        fragments.append(f"writes: {', '.join(item.get('name') or item.get('qualified_name') or '' for item in writes[:3])}")
    if refs:
        fragments.append(f"references: {', '.join(item.get('name') or item.get('qualified_name') or '' for item in refs[:3])}")
    if statements:
        fragments.append(f"statement slice lines: {', '.join(str(item.get('line') or 0) for item in statements[:4])}")
    return ". ".join(fragment for fragment in fragments if fragment) + "."


def kind_rank(kind: str) -> int:
    ranking = {
        "file": 0,
        "module": 1,
        "struct": 2,
        "enum": 3,
        "trait": 4,
        "function": 5,
        "method": 6,
        "statement": 7,
    }
    return ranking.get(kind, 99)


def stable_file_id(repo_name: str, path: str) -> str:
    return stable_id("file", repo_name, path)


def _neighbors_wrapper(
    search_root: Path,
    parsed_root: Path,
    graph_root: Path,
    repo_name: str,
    symbol_query: str,
    *,
    operation: str,
    limit: int,
) -> Dict[str, object]:
    response = execute_graph_query(
        search_root,
        parsed_root,
        graph_root,
        repo_name,
        {
            "operation": operation,
            "seed": symbol_query,
            "limit": limit,
        },
    )
    return {
        "repo": repo_name,
        "query": symbol_query,
        "matches": response["seeds"],
        "neighbors": response["results"],
    }


def load_json(path: Path) -> Dict[str, object]:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)
