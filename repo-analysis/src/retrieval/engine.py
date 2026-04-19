from __future__ import annotations

from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

from backends.graph_backend import get_graph_backend
from backends.metadata_store import get_metadata_store
from backends.search_backend import get_search_backend
from common.text import tokenize
from common.telemetry import trace_operation
from embeddings.indexer import query_embedding_index
from rerank.fusion import rerank_candidates
from symbols.indexer import stable_id


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
TYPE_HINTS = {"trait", "struct", "enum", "type", "class", "interface"}
MEMBER_HINTS = {"field", "property", "member", "local", "variable", "param", "parameter", "method"}


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
    use_graph: bool = True,
    use_embeddings: bool = True,
    use_rerank: bool = True,
    use_summaries: bool = False,
    selective_retrieval: bool = True,
    max_graph_fanout: int = 32,
) -> Dict[str, object]:
    with trace_operation("retrieve_context"):
        search_backend = get_search_backend(str(search_root.resolve()), repo_name)
        graph_backend = get_graph_backend(str(graph_root.resolve()), repo_name)
        metadata_store = get_metadata_store(
            str(parsed_root.resolve()),
            repo_name,
        )
        tokens = tokenize(query)
        query_profile = classify_query(tokens, query)
        effective_kinds = tuple(kinds) if kinds else default_query_kinds(query_profile)
        with trace_operation("retrieve_context.lexical_search"):
            lexical_results = search_backend.search(query, limit=max(limit * 2, 10), kinds=effective_kinds)
        gate = retrieval_gate(tokens, lexical_results, selective_retrieval)
        effective_use_graph = use_graph and gate["use_graph"]
        effective_use_embeddings = use_embeddings and gate["use_embeddings"]
        with trace_operation("retrieve_context.embedding_search"):
            embedding_results = (
                query_embedding_index(search_root, repo_name, query, limit=max(limit, 5))
                if effective_use_embeddings
                else []
            )
        candidates: Dict[Tuple[str, str], Dict[str, object]] = {}

        for result in lexical_results:
            add_candidate(
                candidates,
                {
                    **result,
                    "reasons": ["lexical"],
                },
            )

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

        with trace_operation("retrieve_context.graph_expansion"):
            expanded = (
                expand_graph_candidates(
                    graph_backend,
                    repo_name,
                    seed_nodes,
                    depth,
                    max_fanout=max_graph_fanout,
                )
                if effective_use_graph
                else []
            )
        with trace_operation("retrieve_context.metadata_hydration"):
            for candidate in expanded:
                symbol = metadata_store.get_symbol(str(candidate.get("symbol_id") or ""))
                if symbol:
                    candidate.setdefault("preview", symbol.get("signature") or symbol["qualified_name"])
                    candidate["name"] = symbol.get("name")
                    candidate["qualified_name"] = symbol.get("qualified_name")
                    candidate["path"] = symbol.get("path")
                add_candidate(candidates, candidate)

        if use_summaries:
            with trace_operation("retrieve_context.summary_bonus"):
                apply_summary_bonus(candidates, metadata_store, tokens)

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
                "summaries_enabled": bool(use_summaries),
                "retrieval_gate": gate,
                "query_profile": query_profile,
            },
        }


def result_to_node_id(repo_name: str, result: Dict[str, object]) -> Optional[str]:
    if result.get("symbol_id"):
        return result["symbol_id"]
    if result.get("kind") == "file" and result.get("path"):
        return stable_id("file", repo_name, result["path"])
    return None


def graph_indexes(graph: Dict[str, object]) -> Tuple[Dict[str, Dict[str, object]], Dict[str, List[Dict[str, object]]], Dict[str, List[Dict[str, object]]]]:
    node_by_id = {node["node_id"]: node for node in graph.get("nodes", [])}
    outgoing: Dict[str, List[Dict[str, object]]] = defaultdict(list)
    incoming: Dict[str, List[Dict[str, object]]] = defaultdict(list)
    for edge in graph.get("edges", []):
        outgoing[edge["from"]].append(edge)
        incoming[edge["to"]].append(edge)
    return node_by_id, outgoing, incoming


def expand_graph_candidates(
    graph_backend: object,
    repo_name: str,
    seed_nodes: Sequence[Tuple[str, float]],
    depth: int,
    *,
    max_fanout: int,
) -> List[Dict[str, object]]:
    expanded = []
    for node_id, base_score in seed_nodes:
        response = graph_backend.execute(
            {
                "operation": "neighbors",
                "seed": {"node_id": node_id},
                "edge_types": tuple(EDGE_BONUS.keys()),
                "direction": "both",
                "depth": max(depth, 1),
                "limit": max(max_fanout, 1),
            }
        )
        for item in (response or {}).get("results", []):
            edge = dict(item.get("edge") or {})
            edge_type = str(edge.get("type") or "NEIGHBOR")
            direction = str(edge.get("metadata", {}).get("direction") or "both")
            score = round(base_score + EDGE_BONUS.get(edge_type, 0.5), 6)
            expanded.append(node_to_candidate(repo_name, item, score, edge, direction))
    return expanded


def node_to_candidate(
    repo_name: str,
    node: Dict[str, object],
    score: float,
    edge: Dict[str, object],
    direction: str,
) -> Dict[str, object]:
    edge_id = str(edge.get("edge_id") or stable_id("edge", repo_name, node.get("node_id") or "unknown"))
    edge_type = str(edge.get("type") or "NEIGHBOR")
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
        "doc_id": stable_id("cand", repo_name, node["node_id"], edge_id, direction),
        "kind": kind,
        "repo": repo_name,
        "path": node.get("path"),
        "name": node.get("name"),
        "qualified_name": node.get("qualified_name"),
        "symbol_id": node["node_id"] if kind == "symbol" and node["node_id"].startswith("sym:") else None,
        "title": node.get("qualified_name") or node.get("path") or node.get("name"),
        "preview": f"{edge_type} via {direction}",
        "score": score,
        "metadata": {
            "node_kind": node["kind"],
            "edge_type": edge_type,
            "direction": direction,
        },
        "reasons": [f"graph:{edge_type}:{direction}"],
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
    type_intent = bool(token_set.intersection(TYPE_HINTS))
    member_intent = bool(token_set.intersection(MEMBER_HINTS))
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
        "requested_symbol_kinds": sorted(token for token in token_set if token in TYPE_HINTS.union(MEMBER_HINTS)),
        "prefer_docs": doc_intent,
        "prefer_symbols": intent == "symbol",
        "type_intent": type_intent,
        "member_intent": member_intent,
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
    metadata_store: object,
    tokens: Sequence[str],
) -> None:
    for candidate in candidates.values():
        searchable = []
        if candidate.get("path"):
            summaries = metadata_store.get_summary_by_path(str(candidate["path"]))
            searchable.extend(str(item.get("summary") or "") for item in summaries)
        if candidate.get("symbol_id"):
            summaries = metadata_store.get_summary_by_symbol(str(candidate["symbol_id"]))
            searchable.extend(str(item.get("summary") or "") for item in summaries)
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
