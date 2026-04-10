from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence

from retrieval.engine import graph_indexes, retrieve_context
from search.indexer import list_documents, search_documents
from summaries.builder import load_summary_artifacts


DEFAULT_REPOS = ("carbon", "yellowstone-vixen")


def repo_overview(summary_root: Path, repo_name: str) -> Dict[str, object]:
    summaries = load_summary_artifacts(summary_root, repo_name)
    return {
        "repo": repo_name,
        "project": summaries["project"],
        "summary_counts": summaries["manifest"]["summary"],
    }


def find_symbol(search_root: Path, repo_name: str, query: str, *, limit: int = 10) -> Dict[str, object]:
    return {
        "repo": repo_name,
        "query": query,
        "results": search_documents(search_root, repo_name, query, limit=limit, kinds=("symbol",)),
    }


def trace_calls(
    search_root: Path,
    graph_root: Path,
    parsed_root: Path,
    repo_name: str,
    symbol_query: str,
    *,
    limit: int = 10,
) -> Dict[str, object]:
    resolved = resolve_symbol(search_root, parsed_root, repo_name, symbol_query)
    if not resolved:
        return {
            "repo": repo_name,
            "query": symbol_query,
            "error": "symbol not found",
        }

    graph = load_json(graph_root / repo_name / "graph.json")
    node_by_id, outgoing, incoming = graph_indexes(graph)

    callers = []
    callees = []
    for edge in incoming.get(resolved["symbol_id"], []):
        if edge["type"] != "CALLS":
            continue
        caller = node_by_id.get(edge["from"])
        if caller:
            callers.append(describe_node(caller, edge))

    for edge in outgoing.get(resolved["symbol_id"], []):
        if edge["type"] != "CALLS":
            continue
        callee = node_by_id.get(edge["to"])
        if callee:
            callees.append(describe_node(callee, edge))

    return {
        "repo": repo_name,
        "query": symbol_query,
        "resolved_symbol": resolved,
        "callers": callers[:limit],
        "callees": callees[:limit],
    }


def compare_repos(
    search_root: Path,
    summary_root: Path,
    graph_root: Path,
    parsed_root: Path,
    query: str,
    *,
    repos: Sequence[str] = DEFAULT_REPOS,
    limit: int = 5,
) -> Dict[str, object]:
    comparisons = []
    for repo_name in repos:
        overview = repo_overview(summary_root, repo_name)
        context = retrieve_context(search_root, graph_root, parsed_root, repo_name, query, limit=limit)
        comparisons.append(
            {
                "repo": repo_name,
                "focus": overview["project"]["focus"],
                "top_context": context["selected_context"],
            }
        )

    return {
        "query": query,
        "comparisons": comparisons,
    }


def find_parsers(search_root: Path, repo_name: str, *, limit: int = 10) -> Dict[str, object]:
    return {
        "repo": repo_name,
        "results": themed_results(search_root, repo_name, "parser parse instruction", ("parser", "parsers"), limit),
    }


def find_datasources(search_root: Path, repo_name: str, *, limit: int = 10) -> Dict[str, object]:
    return {
        "repo": repo_name,
        "results": themed_results(search_root, repo_name, "datasource source stream", ("datasource", "datasources"), limit),
    }


def find_decoders(search_root: Path, repo_name: str, *, limit: int = 10) -> Dict[str, object]:
    return {
        "repo": repo_name,
        "results": themed_results(search_root, repo_name, "decoder decode instruction account", ("decoder", "decoders"), limit),
    }


def find_runtime_handlers(search_root: Path, repo_name: str, *, limit: int = 10) -> Dict[str, object]:
    return {
        "repo": repo_name,
        "results": themed_results(search_root, repo_name, "runtime handler source", ("runtime", "handler", "handlers"), limit),
    }


def summarize_path(summary_root: Path, repo_name: str, path: str) -> Dict[str, object]:
    summaries = load_summary_artifacts(summary_root, repo_name)
    for file_summary in summaries["files"]:
        if file_summary["path"] == path:
            return {"repo": repo_name, "path": path, "kind": "file", "summary": file_summary}

    for directory_summary in summaries["directories"]:
        if directory_summary["path"] == path:
            return {"repo": repo_name, "path": path, "kind": "directory", "summary": directory_summary}

    matching_prefix = None
    for directory_summary in summaries["directories"]:
        if path.startswith(f"{directory_summary['path']}/") or path == directory_summary["path"]:
            if matching_prefix is None or len(directory_summary["path"]) > len(matching_prefix["path"]):
                matching_prefix = directory_summary

    return {
        "repo": repo_name,
        "path": path,
        "kind": "directory" if matching_prefix else "unknown",
        "summary": matching_prefix,
    }


def prepare_context(
    search_root: Path,
    summary_root: Path,
    graph_root: Path,
    parsed_root: Path,
    task: str,
    *,
    repo_name: Optional[str] = None,
    limit: int = 8,
) -> Dict[str, object]:
    repos = (repo_name,) if repo_name else DEFAULT_REPOS
    contexts = []
    for current_repo in repos:
        context = retrieve_context(search_root, graph_root, parsed_root, current_repo, task, limit=limit)
        overview = repo_overview(summary_root, current_repo)
        contexts.append(
            {
                "repo": current_repo,
                "focus": overview["project"]["focus"],
                "project_summary": overview["project"]["summary"],
                "selected_context": context["selected_context"],
            }
        )
    return {
        "task": task,
        "contexts": contexts,
    }


def themed_results(
    search_root: Path,
    repo_name: str,
    query: str,
    path_keywords: Sequence[str],
    limit: int,
) -> List[Dict[str, object]]:
    results = search_documents(search_root, repo_name, query, limit=max(limit * 3, 20), kinds=("directory", "file", "symbol"))
    filtered = []
    for result in results:
        haystack = " ".join(
            str(item or "").lower()
            for item in (
                result.get("path"),
                result.get("name"),
                result.get("qualified_name"),
                " ".join(result.get("metadata", {}).get("tags", [])),
            )
        )
        if any(keyword in haystack for keyword in path_keywords):
            filtered.append(result)
    if filtered:
        return filtered[:limit]
    return list_documents(search_root, repo_name, limit=limit, kinds=("directory", "file"))


def resolve_symbol(
    search_root: Path,
    parsed_root: Path,
    repo_name: str,
    symbol_query: str,
) -> Optional[Dict[str, object]]:
    exact_results = search_documents(search_root, repo_name, symbol_query, limit=10, kinds=("symbol",))
    if exact_results:
        normalized_query = symbol_query.lower()
        for result in exact_results:
            if str(result.get("qualified_name") or "").lower() == normalized_query:
                return load_symbol(parsed_root, repo_name, result["symbol_id"])
        for result in exact_results:
            if str(result.get("name") or "").lower() == normalized_query:
                return load_symbol(parsed_root, repo_name, result["symbol_id"])
        return load_symbol(parsed_root, repo_name, exact_results[0]["symbol_id"])
    return None


def load_symbol(parsed_root: Path, repo_name: str, symbol_id: str) -> Optional[Dict[str, object]]:
    payload = load_json(parsed_root / repo_name / "symbols.json")
    for symbol in payload.get("symbols", []):
        if symbol["symbol_id"] == symbol_id:
            return symbol
    return None


def describe_node(node: Dict[str, object], edge: Dict[str, object]) -> Dict[str, object]:
    return {
        "kind": node["kind"],
        "name": node.get("name"),
        "qualified_name": node.get("qualified_name"),
        "path": node.get("path"),
        "edge": edge["type"],
        "metadata": edge.get("metadata", {}),
    }


def load_json(path: Path) -> Dict[str, object]:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)
