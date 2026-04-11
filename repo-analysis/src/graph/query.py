from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence

from retrieval.engine import graph_indexes
from search.indexer import search_documents


def where_defined(
    search_root: Path,
    parsed_root: Path,
    repo_name: str,
    symbol_query: str,
    *,
    limit: int = 10,
) -> Dict[str, object]:
    matches = resolve_symbol_matches(search_root, parsed_root, repo_name, symbol_query, limit=limit)
    return {
        "repo": repo_name,
        "query": symbol_query,
        "matches": [
            {
                "symbol_id": symbol["symbol_id"],
                "kind": symbol["kind"],
                "name": symbol["name"],
                "qualified_name": symbol["qualified_name"],
                "path": symbol["path"],
                "span": symbol["span"],
                "container_qualified_name": symbol["container_qualified_name"],
            }
            for symbol in matches
        ],
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
    return neighbors_for_symbol(
        search_root,
        parsed_root,
        graph_root,
        repo_name,
        symbol_query,
        edge_types=("IMPORTS",),
        direction="incoming",
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
    return neighbors_for_symbol(
        search_root,
        parsed_root,
        graph_root,
        repo_name,
        symbol_query,
        edge_types=edge_types,
        direction=direction,
        limit=limit,
    )


def neighbors_for_symbol(
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
    graph = load_json(graph_root / repo_name / "graph.json")
    node_by_id, outgoing, incoming = graph_indexes(graph)
    matches = resolve_symbol_matches(search_root, parsed_root, repo_name, symbol_query, limit=10)
    if not matches:
        return {"repo": repo_name, "query": symbol_query, "matches": [], "neighbors": []}

    allowed_edges = set(edge_types)
    neighbors: List[Dict[str, object]] = []
    seen = set()

    for symbol in matches:
        if direction in {"outgoing", "both"}:
            neighbors.extend(
                collect_neighbors(
                    node_by_id,
                    outgoing.get(symbol["symbol_id"], []),
                    allowed_edges,
                    seen,
                    from_symbol=symbol,
                    outgoing_edges=True,
                )
            )
        if direction in {"incoming", "both"}:
            neighbors.extend(
                collect_neighbors(
                    node_by_id,
                    incoming.get(symbol["symbol_id"], []),
                    allowed_edges,
                    seen,
                    from_symbol=symbol,
                    outgoing_edges=False,
                )
            )

    neighbors = sorted(
        neighbors,
        key=lambda item: (
            item["edge_type"],
            str(item.get("path") or ""),
            str(item.get("qualified_name") or item.get("name") or ""),
        ),
    )[:limit]

    return {
        "repo": repo_name,
        "query": symbol_query,
        "matches": [
            {
                "symbol_id": symbol["symbol_id"],
                "kind": symbol["kind"],
                "qualified_name": symbol["qualified_name"],
                "path": symbol["path"],
                "span": symbol["span"],
            }
            for symbol in matches
        ],
        "neighbors": neighbors,
    }


def resolve_symbol_matches(
    search_root: Path,
    parsed_root: Path,
    repo_name: str,
    symbol_query: str,
    *,
    limit: int = 10,
) -> List[Dict[str, object]]:
    payload = load_json(parsed_root / repo_name / "symbols.json")
    normalized = symbol_query.lower()
    direct_matches = direct_symbol_matches(payload.get("symbols", []), normalized)
    if direct_matches:
        return direct_matches[:limit]

    symbol_by_id = {symbol["symbol_id"]: symbol for symbol in payload.get("symbols", [])}
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

    matches.sort(
        key=lambda item: (
            -int(item["_match_score"]),
            str(item["path"]),
            str(item["qualified_name"]),
        )
    )
    direct_matches = [
        match
        for match in matches
        if normalized
        in {
            str(match.get("name") or "").lower(),
            str(match.get("qualified_name") or "").lower(),
            str(match.get("qualified_name") or "").lower().split("::")[-1],
        }
    ]
    if direct_matches:
        matches = direct_matches
    for match in matches:
        match.pop("_match_score", None)
    return matches[:limit]


def collect_neighbors(
    node_by_id: Dict[str, Dict[str, object]],
    edges: Iterable[Dict[str, object]],
    allowed_edges: set[str],
    seen: set[tuple[str, str, str]],
    *,
    from_symbol: Dict[str, object],
    outgoing_edges: bool,
) -> List[Dict[str, object]]:
    neighbors = []
    for edge in edges:
        if allowed_edges and edge["type"] not in allowed_edges:
            continue
        node_id = edge["to"] if outgoing_edges else edge["from"]
        node = node_by_id.get(node_id)
        if not node or node["kind"] in {"repository", "file"}:
            continue
        key = (from_symbol["symbol_id"], node_id, edge["type"])
        if key in seen:
            continue
        seen.add(key)
        neighbors.append(
            {
                "direction": "outgoing" if outgoing_edges else "incoming",
                "edge_type": edge["type"],
                "symbol_id": node_id if str(node_id).startswith("sym:") else None,
                "kind": node["kind"],
                "name": node.get("name"),
                "qualified_name": node.get("qualified_name"),
                "path": node.get("path"),
                "metadata": edge.get("metadata", {}),
            }
        )
    return neighbors


def load_json(path: Path) -> Dict[str, object]:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def direct_symbol_matches(symbols: Sequence[Dict[str, object]], normalized_query: str) -> List[Dict[str, object]]:
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
            str(item["path"]),
            str(item["qualified_name"]),
        ),
    )
