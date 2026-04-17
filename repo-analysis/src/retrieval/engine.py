from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

from embeddings.indexer import query_embedding_index
from rerank.fusion import rerank_candidates
from search.indexer import search_documents, tokenize
from symbols.indexer import stable_id
from summaries.builder import load_summary_artifacts


EDGE_BONUS = {
    "CALLS": 1.4,
    "USES": 1.2,
    "IMPLEMENTS": 1.1,
    "INHERITS": 1.1,
    "IMPORTS": 0.9,
    "DEFINES": 0.8,
    "CONTAINS": 0.6,
    "REFERENCES": 0.7,
    "TESTS": 0.8,
    "READS": 0.75,
    "WRITES": 0.75,
    "REFS": 0.7,
    "DATA_FLOW": 0.65,
    "CONTROL_FLOW": 0.55,
    "DEPENDENCE": 0.55,
}
ARCHITECTURE_HINTS = {"architecture", "datasource", "decoder", "extension", "handler", "macro", "parser", "runtime", "source", "trait"}
DOC_HINTS = {"doc", "docs", "documentation", "overview", "readme", "summary"}
SYMBOL_KIND_HINTS = {"enum", "function", "handler", "macro", "method", "module", "parser", "source", "struct", "trait", "type"}


def retrieve_context(
    search_root: Path,
    graph_root: Path,
    parsed_root: Path,
    repo_name: str,
    query: str,
    *,
    summary_root: Path | None = None,
    limit: int = 8,
    depth: int = 1,
    kinds: Sequence[str] = (),
    use_graph: bool = True,
    use_embeddings: bool = True,
    use_rerank: bool = True,
    use_summaries: bool = False,
    selective_retrieval: bool = True,
    max_graph_fanout: int = 32,
) -> Dict[str, object]:
    tokens = tokenize(query)
    query_profile = classify_query(tokens, query)
    effective_kinds = tuple(kinds) if kinds else default_query_kinds(query_profile)
    lexical_results = search_documents(search_root, repo_name, query, limit=max(limit * 2, 10), kinds=effective_kinds)
    gate = retrieval_gate(tokens, lexical_results, selective_retrieval)
    effective_use_graph = use_graph and gate["use_graph"]
    effective_use_embeddings = use_embeddings and gate["use_embeddings"]
    embedding_results = (
        query_embedding_index(search_root, repo_name, query, limit=max(limit, 5)) if effective_use_embeddings else []
    )
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

    for result in embedding_results:
        add_candidate(
            candidates,
            {
                **result,
                "reasons": ["embedding"],
            },
        )

    seed_nodes = []
    for result in lexical_results[:limit]:
        node_id = result_to_node_id(repo_name, result)
        if node_id:
            seed_nodes.append((node_id, float(result["score"])))

    expanded = (
        expand_graph_candidates(repo_name, node_by_id, outgoing, incoming, seed_nodes, depth, max_fanout=max_graph_fanout)
        if effective_use_graph
        else []
    )
    for candidate in expanded:
        symbol = symbol_by_id.get(candidate.get("symbol_id"))
        if symbol:
            candidate.setdefault("preview", symbol.get("signature") or symbol["qualified_name"])
        add_candidate(candidates, candidate)

    if use_summaries and summary_root is not None:
        apply_summary_bonus(candidates, summary_root, repo_name, tokens)

    ranked_candidates = list(candidates.values())
    ranked = (
        rerank_candidates(ranked_candidates, tokens, query_profile=query_profile)[:limit]
        if use_rerank
        else sort_candidates(ranked_candidates)[:limit]
    )
    return {
        "repo": repo_name,
        "query": query,
        "lexical_results": lexical_results[:limit],
        "embedding_results": embedding_results[:limit],
        "selected_context": ranked,
        "summary": {
            "lexical_results": len(lexical_results),
            "embedding_results": len(embedding_results),
            "expanded_candidates": len(expanded),
            "selected": len(ranked),
            "graph_enabled": effective_use_graph,
            "embeddings_enabled": effective_use_embeddings,
            "rerank_enabled": use_rerank,
            "summaries_enabled": bool(use_summaries and summary_root is not None),
            "retrieval_gate": gate,
            "query_profile": query_profile,
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
    *,
    max_fanout: int,
) -> List[Dict[str, object]]:
    expanded = []
    seen = set()
    frontier = list(seed_nodes)

    for _ in range(max(depth, 0)):
        next_frontier = []
        for node_id, base_score in frontier:
            for direction, edges in (("outgoing", outgoing.get(node_id, [])), ("incoming", incoming.get(node_id, []))):
                for edge in edges[:max(max_fanout, 1)]:
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
    if node["kind"] in {
        "statement",
        "file",
        "directory",
        "repository",
        "package",
        "dependency",
        "test",
        "project_summary",
        "package_summary",
        "directory_summary",
        "file_summary",
        "symbol_summary",
        "module_ref",
        "symbol_ref",
        "type_ref",
        "trait_ref",
    }:
        kind = node["kind"]
    elif "path" in node:
        kind = "symbol"
    else:
        kind = node["kind"]
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


def retrieval_gate(
    tokens: Sequence[str],
    lexical_results: Sequence[Dict[str, object]],
    selective_retrieval: bool,
) -> Dict[str, object]:
    if not selective_retrieval:
        return {
            "enabled": False,
            "reason": "disabled",
            "use_graph": True,
            "use_embeddings": True,
        }

    if not tokens or not lexical_results:
        return {
            "enabled": True,
            "reason": "no-exact-lexical-hit",
            "use_graph": True,
            "use_embeddings": True,
        }

    top = lexical_results[0]
    normalized_tokens = set(token.lower() for token in tokens)
    exact_name = str(top.get("name") or "").lower()
    exact_qname = str(top.get("qualified_name") or "").lower()
    if len(tokens) <= 2 and top.get("kind") == "symbol" and normalized_tokens.intersection(
        {exact_name, exact_qname, exact_qname.split("::")[-1]}
    ):
        return {
            "enabled": True,
            "reason": "exact-symbol-lexical-hit",
            "use_graph": False,
            "use_embeddings": False,
        }

    return {
        "enabled": True,
        "reason": "broad-query",
        "use_graph": True,
        "use_embeddings": True,
    }


def classify_query(tokens: Sequence[str], query: str) -> Dict[str, object]:
    token_set = {token.lower() for token in tokens}
    doc_intent = bool(token_set.intersection(DOC_HINTS))
    architecture_intent = bool(token_set.intersection(ARCHITECTURE_HINTS))
    symbolish = "::" in query or (len(token_set) <= 2 and not doc_intent and not architecture_intent)

    if doc_intent:
        intent = "docs"
    elif symbolish:
        intent = "symbol"
    elif architecture_intent:
        intent = "architecture"
    else:
        intent = "exploration"

    return {
        "intent": intent,
        "prefer_tags": sorted(token for token in token_set if token in ARCHITECTURE_HINTS),
        "prefer_symbol_kinds": sorted(token for token in token_set if token in SYMBOL_KIND_HINTS),
        "prefer_docs": doc_intent,
        "prefer_symbols": intent == "symbol",
    }


def default_query_kinds(query_profile: Dict[str, object]) -> Tuple[str, ...]:
    intent = query_profile.get("intent")
    if intent == "docs":
        return ("repo", "package", "directory", "file", "doc", "symbol")
    if intent == "symbol":
        return ("symbol", "function_body", "type_body", "statement", "file")
    return ("symbol", "function_body", "type_body", "file", "statement", "directory", "package")


def apply_summary_bonus(
    candidates: Dict[Tuple[str, str], Dict[str, object]],
    summary_root: Path,
    repo_name: str,
    tokens: Sequence[str],
) -> None:
    summaries = load_summary_artifacts(summary_root, repo_name)
    file_summaries = {item["path"]: item for item in summaries.get("files", [])}
    symbol_summaries = {item["symbol_id"]: item for item in summaries.get("symbols", [])}

    for candidate in candidates.values():
        searchable = []
        if candidate.get("path") and candidate["path"] in file_summaries:
            searchable.append(file_summaries[candidate["path"]]["summary"])
        if candidate.get("symbol_id") and candidate["symbol_id"] in symbol_summaries:
            searchable.append(symbol_summaries[candidate["symbol_id"]]["summary"])
        if not searchable:
            continue
        haystack = " ".join(searchable).lower()
        overlap = sum(1 for token in tokens if token in haystack)
        if overlap <= 0:
            continue
        candidate["score"] = round(float(candidate.get("score") or 0.0) + overlap * 0.2, 6)
        reasons = list(candidate.get("reasons", []))
        if "summary" not in reasons:
            reasons.append("summary")
        candidate["reasons"] = reasons


def sort_candidates(candidates: Sequence[Dict[str, object]]) -> List[Dict[str, object]]:
    return sorted(
        candidates,
        key=lambda item: (
            -float(item.get("score") or 0.0),
            str(item.get("path") or ""),
            str(item.get("qualified_name") or item.get("title") or ""),
        ),
    )


def load_json(path: Path) -> Dict[str, object]:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)
