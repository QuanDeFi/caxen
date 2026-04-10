from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

from rerank.fusion import rerank_candidates
from search.indexer import search_documents, tokenize
from symbols.indexer import stable_id


EDGE_BONUS = {
    "CALLS": 1.4,
    "USES": 1.2,
    "IMPLEMENTS": 1.1,
    "IMPORTS": 0.9,
    "DEFINES": 0.8,
    "CONTAINS": 0.6,
    "REFERENCES": 0.7,
}


def retrieve_context(
    search_root: Path,
    graph_root: Path,
    parsed_root: Path,
    repo_name: str,
    query: str,
    *,
    limit: int = 8,
    depth: int = 1,
    kinds: Sequence[str] = (),
) -> Dict[str, object]:
    tokens = tokenize(query)
    lexical_results = search_documents(search_root, repo_name, query, limit=max(limit * 2, 10), kinds=kinds)
    graph = load_json(graph_root / repo_name / "graph.json")
    symbols = load_json(parsed_root / repo_name / "symbols.json")
    symbol_by_id = {item["symbol_id"]: item for item in symbols.get("symbols", [])}
    symbols_by_path = defaultdict(list)
    for symbol in symbols.get("symbols", []):
        symbols_by_path[symbol["path"]].append(symbol)

    node_by_id, outgoing, incoming = graph_indexes(graph)
    candidates: Dict[Tuple[str, str], Dict[str, object]] = {}

    for result in lexical_results:
        add_candidate(
            candidates,
            {
                **result,
                "reasons": ["lexical"],
            },
        )
        if result["kind"] == "file" and result.get("path"):
            for localized in localize_file_symbols(tokens, symbols_by_path[result["path"]], base_score=float(result["score"]) * 0.5):
                add_candidate(candidates, localized)

    seed_nodes = []
    for result in lexical_results[:limit]:
        node_id = result_to_node_id(repo_name, result)
        if node_id:
            seed_nodes.append((node_id, float(result["score"])))

    expanded = expand_graph_candidates(repo_name, node_by_id, outgoing, incoming, seed_nodes, depth)
    for candidate in expanded:
        symbol = symbol_by_id.get(candidate.get("symbol_id"))
        if symbol:
            candidate.setdefault("preview", symbol.get("signature") or symbol["qualified_name"])
        add_candidate(candidates, candidate)

    ranked = rerank_candidates(candidates.values(), tokens)[:limit]
    return {
        "repo": repo_name,
        "query": query,
        "lexical_results": lexical_results[:limit],
        "selected_context": ranked,
        "summary": {
            "lexical_results": len(lexical_results),
            "expanded_candidates": len(expanded),
            "selected": len(ranked),
        },
    }


def graph_indexes(graph: Dict[str, object]) -> Tuple[Dict[str, Dict[str, object]], Dict[str, List[Dict[str, object]]], Dict[str, List[Dict[str, object]]]]:
    node_by_id = {node["node_id"]: node for node in graph.get("nodes", [])}
    outgoing: Dict[str, List[Dict[str, object]]] = defaultdict(list)
    incoming: Dict[str, List[Dict[str, object]]] = defaultdict(list)
    for edge in graph.get("edges", []):
        outgoing[edge["from"]].append(edge)
        incoming[edge["to"]].append(edge)
    return node_by_id, outgoing, incoming


def result_to_node_id(repo_name: str, result: Dict[str, object]) -> Optional[str]:
    if result.get("symbol_id"):
        return result["symbol_id"]
    if result.get("kind") == "file" and result.get("path"):
        return stable_id("file", repo_name, result["path"])
    return None


def localize_file_symbols(tokens: Sequence[str], symbols: Sequence[Dict[str, object]], *, base_score: float) -> List[Dict[str, object]]:
    localized = []
    for symbol in symbols:
        searchable = " ".join(
            str(item or "").lower()
            for item in (
                symbol["name"],
                symbol["qualified_name"],
                symbol["kind"],
                symbol.get("signature"),
            )
        )
        overlap = sum(1 for token in tokens if token in searchable)
        if overlap == 0:
            continue
        localized.append(
            {
                "doc_id": stable_id("cand", symbol["repo"], symbol["symbol_id"], "localized"),
                "kind": "symbol",
                "repo": symbol["repo"],
                "path": symbol["path"],
                "name": symbol["name"],
                "qualified_name": symbol["qualified_name"],
                "symbol_id": symbol["symbol_id"],
                "title": symbol["qualified_name"],
                "preview": symbol.get("signature") or symbol["qualified_name"],
                "score": round(base_score + overlap * 0.4, 6),
                "metadata": {
                    "kind": symbol["kind"],
                    "crate": symbol["crate"],
                    "module_path": symbol["module_path"],
                },
                "reasons": ["symbol-localization"],
            }
        )
    return localized


def expand_graph_candidates(
    repo_name: str,
    node_by_id: Dict[str, Dict[str, object]],
    outgoing: Dict[str, List[Dict[str, object]]],
    incoming: Dict[str, List[Dict[str, object]]],
    seed_nodes: Sequence[Tuple[str, float]],
    depth: int,
) -> List[Dict[str, object]]:
    expanded = []
    seen = set()
    frontier = list(seed_nodes)

    for _ in range(max(depth, 0)):
        next_frontier = []
        for node_id, base_score in frontier:
            for direction, edges in (("outgoing", outgoing.get(node_id, [])), ("incoming", incoming.get(node_id, []))):
                for edge in edges:
                    neighbor_id = edge["to"] if direction == "outgoing" else edge["from"]
                    if neighbor_id == node_id or (node_id, neighbor_id, edge["type"]) in seen:
                        continue
                    seen.add((node_id, neighbor_id, edge["type"]))
                    neighbor = node_by_id.get(neighbor_id)
                    if not neighbor or neighbor["kind"] == "repository":
                        continue
                    score = round(base_score + EDGE_BONUS.get(edge["type"], 0.5), 6)
                    expanded.append(node_to_candidate(repo_name, neighbor, score, edge, direction))
                    next_frontier.append((neighbor_id, score * 0.5))
        frontier = next_frontier
    return expanded


def node_to_candidate(
    repo_name: str,
    node: Dict[str, object],
    score: float,
    edge: Dict[str, object],
    direction: str,
) -> Dict[str, object]:
    kind = "symbol" if node["kind"] not in {"file", "directory", "repository"} and "path" in node else node["kind"]
    return {
        "doc_id": stable_id("cand", repo_name, node["node_id"], edge["edge_id"], direction),
        "kind": kind,
        "repo": repo_name,
        "path": node.get("path"),
        "name": node.get("name"),
        "qualified_name": node.get("qualified_name"),
        "symbol_id": node["node_id"] if kind == "symbol" and node["node_id"].startswith("sym:") else None,
        "title": node.get("qualified_name") or node.get("path") or node.get("name"),
        "preview": f"{edge['type']} via {direction}",
        "score": score,
        "metadata": {
            "node_kind": node["kind"],
            "edge_type": edge["type"],
            "direction": direction,
        },
        "reasons": [f"graph:{edge['type']}:{direction}"],
    }


def add_candidate(candidates: Dict[Tuple[str, str], Dict[str, object]], candidate: Dict[str, object]) -> None:
    key = (candidate.get("kind") or "unknown", candidate.get("symbol_id") or candidate.get("path") or candidate["doc_id"])
    existing = candidates.get(key)
    if not existing:
        candidates[key] = candidate
        return

    existing["score"] = max(float(existing.get("score") or 0.0), float(candidate.get("score") or 0.0))
    existing_reasons = list(existing.get("reasons", []))
    for reason in candidate.get("reasons", []):
        if reason not in existing_reasons:
            existing_reasons.append(reason)
    existing["reasons"] = existing_reasons
    existing_metadata = dict(existing.get("metadata", {}))
    existing_metadata.update(candidate.get("metadata", {}))
    existing["metadata"] = existing_metadata
    if not existing.get("preview") and candidate.get("preview"):
        existing["preview"] = candidate["preview"]


def load_json(path: Path) -> Dict[str, object]:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)
