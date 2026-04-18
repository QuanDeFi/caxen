from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence

from common.telemetry import snapshot_telemetry, trace_operation
from graph.query import (
    adjacent_symbols as graph_adjacent_symbols,
    callers_of as graph_callers_of,
    callees_of as graph_callees_of,
    execute_graph_query as execute_graph_request,
    implements_of as graph_implements_of,
    inherits_of as graph_inherits_of,
    path_between as graph_path_between,
    reads_of as graph_reads_of,
    refs_of as graph_refs_of,
    statement_slice as graph_statement_slice,
    symbol_summary as graph_symbol_summary,
    where_defined as graph_where_defined,
    who_imports as graph_who_imports,
    writes_of as graph_writes_of,
)
from retrieval.engine import retrieve_context
from retrieval.planner import (
    plan_query as build_query_plan,
    prepare_answer_bundle as build_answer_bundle,
    retrieve_iterative as build_iterative_bundle,
)
from search.indexer import (
    find_files,
    list_documents,
    load_agent_cache,
    lookup_symbol_documents,
    search_documents,
    search_documents_scoped,
)
from summaries.builder import load_summary_artifacts
from symbols.persistence import load_symbol_by_id, load_symbols_by_ids


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


def find_file(search_root: Path, repo_name: str, path_pattern: str, *, limit: int = 20) -> Dict[str, object]:
    return {
        "repo": repo_name,
        "path_pattern": path_pattern,
        "results": find_files(search_root, repo_name, path_pattern, limit=limit),
    }


def search_lexical(
    search_root: Path,
    repo_name: str,
    query: str,
    *,
    limit: int = 10,
    kinds: Sequence[str] = (),
    path_prefix: Optional[str] = None,
) -> Dict[str, object]:
    return {
        "repo": repo_name,
        "query": query,
        "scope": {
            "kinds": list(kinds),
            "path_prefix": path_prefix,
        },
        "results": search_documents_scoped(
            search_root,
            repo_name,
            query,
            limit=limit,
            kinds=kinds,
            path_prefix=path_prefix,
        ),
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
    resolved = where_defined(search_root, parsed_root, repo_name, symbol_query, limit=1)
    if not resolved["matches"]:
        return {
            "repo": repo_name,
            "query": symbol_query,
            "error": "symbol not found",
        }
    callers = callers_of(search_root, parsed_root, graph_root, repo_name, symbol_query, limit=limit)
    callees = callees_of(search_root, parsed_root, graph_root, repo_name, symbol_query, limit=limit)
    return {
        "repo": repo_name,
        "query": symbol_query,
        "resolved_symbol": resolved["matches"][0],
        "callers": callers["neighbors"],
        "callees": callees["neighbors"],
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
        summaries = load_summary_artifacts(summary_root, repo_name)
        cached = compare_repo_from_agent_cache(search_root, repo_name, query, summaries, limit=limit)
        if cached is not None:
            comparisons.append(cached)
            continue

        bundle = prepare_answer_bundle(
            search_root,
            summary_root,
            graph_root,
            parsed_root,
            query,
            repo_name=repo_name,
            limit=limit,
        )
        repo_bundle = bundle["bundles"][0]
        comparisons.append(
            {
                "repo": repo_name,
                "focus": repo_bundle["focus"],
                "top_context": repo_bundle["selected_context"],
                "bundle_summary": {
                    **repo_bundle["bundle_summary"],
                    "source": "answer_bundle_fallback",
                },
            }
        )
    return {"query": query, "comparisons": comparisons}


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


def get_summary(
    search_root: Path,
    summary_root: Path,
    graph_root: Path,
    parsed_root: Path,
    repo_name: str,
    node_id: str,
) -> Dict[str, object]:
    summaries = load_summary_artifacts(summary_root, repo_name)
    if node_id == stable_repo_id(repo_name):
        return {"repo": repo_name, "node_id": node_id, "summary": summaries["project"]}
    for collection_name in ("packages", "directories", "files", "symbols"):
        for item in summaries.get(collection_name, []):
            if item.get("summary_id") == node_id:
                return {"repo": repo_name, "node_id": node_id, "summary": item}

    graph_response = execute_graph_request(
        search_root,
        parsed_root,
        graph_root,
        repo_name,
        {"operation": "symbol_summary", "seed": {"node_id": node_id}, "limit": 1},
    )
    if graph_response.get("results"):
        return {"repo": repo_name, "node_id": node_id, "summary": graph_response["results"][0]}

    for file_summary in summaries["files"]:
        if stable_file_id(repo_name, file_summary["path"]) == node_id:
            return {"repo": repo_name, "node_id": node_id, "summary": file_summary}
    for directory_summary in summaries["directories"]:
        if stable_directory_id(repo_name, directory_summary["path"]) == node_id:
            return {"repo": repo_name, "node_id": node_id, "summary": directory_summary}
    for package_summary in summaries.get("packages", []):
        if stable_package_id(repo_name, str(package_summary.get("package_name") or "")) == node_id:
            return {"repo": repo_name, "node_id": node_id, "summary": package_summary}
    return {"repo": repo_name, "node_id": node_id, "summary": None}


def get_symbol_signature(
    search_root: Path,
    parsed_root: Path,
    repo_name: str,
    symbol_query: str,
) -> Dict[str, object]:
    with trace_operation("get_symbol_signature"):
        symbol = resolve_symbol_query(search_root, parsed_root, repo_name, symbol_query)
        return {
            "repo": repo_name,
            "query": symbol_query,
            "symbol": symbol,
            "signature": symbol.get("signature") if symbol else None,
        }


def get_symbol_body(
    search_root: Path,
    parsed_root: Path,
    repo_name: str,
    symbol_query: str,
) -> Dict[str, object]:
    with trace_operation("get_symbol_body"):
        symbol = resolve_symbol_query(search_root, parsed_root, repo_name, symbol_query)
        if not symbol:
            return {"repo": repo_name, "query": symbol_query, "symbol": None, "body": None}

        documents = lookup_symbol_documents(
            search_root,
            repo_name,
            symbol["symbol_id"],
            kinds=("function_body", "type_body"),
            limit=4,
        )
        return {
            "repo": repo_name,
            "query": symbol_query,
            "symbol": describe_symbol_row(symbol),
            "body": documents[0] if documents else None,
        }


def telemetry_snapshot() -> Dict[str, object]:
    return snapshot_telemetry()


def get_enclosing_context(
    search_root: Path,
    summary_root: Path,
    graph_root: Path,
    parsed_root: Path,
    repo_name: str,
    symbol_query: str,
) -> Dict[str, object]:
    symbol = resolve_symbol_query(search_root, parsed_root, repo_name, symbol_query)
    if not symbol:
        return {"repo": repo_name, "query": symbol_query, "context": None}

    container = load_symbol_by_id(parsed_root, repo_name, str(symbol.get("container_symbol_id") or ""))
    return {
        "repo": repo_name,
        "query": symbol_query,
        "context": {
            "symbol": describe_symbol_row(symbol),
            "container": describe_symbol_row(container) if container else None,
            "path_summary": summarize_path(summary_root, repo_name, symbol["path"]),
            "statement_slice": graph_statement_slice(
                search_root,
                parsed_root,
                graph_root,
                repo_name,
                symbol_query,
                limit=8,
                window=8,
            ),
        },
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
    bundle = prepare_answer_bundle(
        search_root,
        summary_root,
        graph_root,
        parsed_root,
        task,
        repo_name=repo_name,
        limit=limit,
    )
    contexts = []
    for repo_bundle in bundle["bundles"]:
        contexts.append(
            {
                "repo": repo_bundle["repo"],
                "focus": repo_bundle["focus"],
                "project_summary": repo_bundle["project_summary"],
                "selected_context": repo_bundle["selected_context"],
            }
        )
    return {
        "task": task,
        "contexts": contexts,
    }


def where_defined(
    search_root: Path,
    parsed_root: Path,
    repo_name: str,
    symbol_query: str,
    *,
    limit: int = 10,
) -> Dict[str, object]:
    return graph_where_defined(search_root, parsed_root, repo_name, symbol_query, limit=limit)


def who_imports(
    search_root: Path,
    parsed_root: Path,
    graph_root: Path,
    repo_name: str,
    symbol_query: str,
    *,
    limit: int = 20,
) -> Dict[str, object]:
    return graph_who_imports(search_root, parsed_root, graph_root, repo_name, symbol_query, limit=limit)


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
    return graph_adjacent_symbols(
        search_root,
        parsed_root,
        graph_root,
        repo_name,
        symbol_query,
        edge_types=edge_types,
        direction=direction,
        limit=limit,
    )


def callers_of(
    search_root: Path,
    parsed_root: Path,
    graph_root: Path,
    repo_name: str,
    symbol_query: str,
    *,
    limit: int = 20,
) -> Dict[str, object]:
    return graph_callers_of(search_root, parsed_root, graph_root, repo_name, symbol_query, limit=limit)


def callees_of(
    search_root: Path,
    parsed_root: Path,
    graph_root: Path,
    repo_name: str,
    symbol_query: str,
    *,
    limit: int = 20,
) -> Dict[str, object]:
    return graph_callees_of(search_root, parsed_root, graph_root, repo_name, symbol_query, limit=limit)


def reads_of(
    search_root: Path,
    parsed_root: Path,
    graph_root: Path,
    repo_name: str,
    symbol_query: str,
    *,
    limit: int = 20,
) -> Dict[str, object]:
    return graph_reads_of(search_root, parsed_root, graph_root, repo_name, symbol_query, limit=limit)


def writes_of(
    search_root: Path,
    parsed_root: Path,
    graph_root: Path,
    repo_name: str,
    symbol_query: str,
    *,
    limit: int = 20,
) -> Dict[str, object]:
    return graph_writes_of(search_root, parsed_root, graph_root, repo_name, symbol_query, limit=limit)


def refs_of(
    search_root: Path,
    parsed_root: Path,
    graph_root: Path,
    repo_name: str,
    symbol_query: str,
    *,
    limit: int = 20,
) -> Dict[str, object]:
    return graph_refs_of(search_root, parsed_root, graph_root, repo_name, symbol_query, limit=limit)


def implements_of(
    search_root: Path,
    parsed_root: Path,
    graph_root: Path,
    repo_name: str,
    symbol_query: str,
    *,
    limit: int = 20,
) -> Dict[str, object]:
    return graph_implements_of(search_root, parsed_root, graph_root, repo_name, symbol_query, limit=limit)


def inherits_of(
    search_root: Path,
    parsed_root: Path,
    graph_root: Path,
    repo_name: str,
    symbol_query: str,
    *,
    limit: int = 20,
) -> Dict[str, object]:
    return graph_inherits_of(search_root, parsed_root, graph_root, repo_name, symbol_query, limit=limit)


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
    return graph_statement_slice(search_root, parsed_root, graph_root, repo_name, symbol_query, limit=limit, window=window)


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
    return graph_path_between(
        search_root,
        parsed_root,
        graph_root,
        repo_name,
        source_query,
        target_query,
        limit=limit,
        edge_types=edge_types,
        direction=direction,
    )


def execute_graph_query(
    search_root: Path,
    parsed_root: Path,
    graph_root: Path,
    repo_name: str,
    request: Dict[str, object],
) -> Dict[str, object]:
    return execute_graph_request(search_root, parsed_root, graph_root, repo_name, request)


def expand_subgraph(
    search_root: Path,
    parsed_root: Path,
    graph_root: Path,
    repo_name: str,
    seed: object,
    *,
    edge_types: Sequence[str] = (),
    direction: str = "both",
    depth: int = 1,
    node_kinds: Sequence[str] = (),
    budget: int = 20,
) -> Dict[str, object]:
    return execute_graph_request(
        search_root,
        parsed_root,
        graph_root,
        repo_name,
        {
            "operation": "neighbors",
            "seed": seed,
            "edge_types": list(edge_types),
            "direction": direction,
            "depth": depth,
            "node_kinds": list(node_kinds),
            "limit": budget,
        },
    )


def symbol_summary(
    search_root: Path,
    parsed_root: Path,
    graph_root: Path,
    repo_name: str,
    symbol_query: str,
    *,
    limit: int = 5,
) -> Dict[str, object]:
    return graph_symbol_summary(search_root, parsed_root, graph_root, repo_name, symbol_query, limit=limit)


def plan_query(
    search_root: Path,
    graph_root: Path,
    parsed_root: Path,
    task: str,
    *,
    repo_name: Optional[str] = None,
    summary_root: Optional[Path] = None,
    limit: int = 8,
) -> Dict[str, object]:
    return build_query_plan(
        search_root,
        graph_root,
        parsed_root,
        task,
        repo_name=repo_name,
        summary_root=summary_root,
        limit=limit,
    )


def prepare_answer_bundle(
    search_root: Path,
    summary_root: Path,
    graph_root: Path,
    parsed_root: Path,
    task: str,
    *,
    repo_name: Optional[str] = None,
    limit: int = 8,
    refinement_hints: Sequence[str] = (),
) -> Dict[str, object]:
    return build_answer_bundle(
        search_root,
        summary_root,
        graph_root,
        parsed_root,
        task,
        repo_name=repo_name,
        limit=limit,
        refinement_hints=refinement_hints,
    )


def retrieve_iterative(
    search_root: Path,
    summary_root: Path,
    graph_root: Path,
    parsed_root: Path,
    task: str,
    *,
    repo_name: Optional[str] = None,
    limit: int = 8,
    prior_bundle: Optional[Dict[str, object]] = None,
    refinement_hints: Sequence[str] = (),
) -> Dict[str, object]:
    return build_iterative_bundle(
        search_root,
        summary_root,
        graph_root,
        parsed_root,
        task,
        repo_name=repo_name,
        limit=limit,
        prior_bundle=prior_bundle,
        refinement_hints=refinement_hints,
    )


def score_external_answers(
    eval_root: Path,
    answers_path: Path,
) -> Dict[str, object]:
    from evaluation.harness import score_external_answers as score_external_answers_payload

    return score_external_answers_payload(eval_root, answers_path)


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


def compare_repo_from_agent_cache(
    search_root: Path,
    repo_name: str,
    query: str,
    summaries: Dict[str, object],
    *,
    limit: int,
) -> Optional[Dict[str, object]]:
    try:
        cache = load_agent_cache(search_root, repo_name)
    except FileNotFoundError:
        return None

    entries = list(cache.get("entries", []))
    if not entries:
        return None

    top_context = query_agent_cache(entries, query, limit=limit)
    return {
        "repo": repo_name,
        "focus": str(summaries.get("project", {}).get("focus") or ""),
        "top_context": top_context,
        "bundle_summary": {
            "selected_context": len(top_context),
            "graph_neighborhoods": 0,
            "statement_slices": 0,
            "evidence_items": len(top_context),
            "source": "agent_cache",
            "cache_entries": int(cache.get("summary", {}).get("entries") or 0),
        },
    }


def query_agent_cache(entries: Sequence[Dict[str, object]], query: str, *, limit: int) -> List[Dict[str, object]]:
    query_tokens = normalize_query_tokens(query)
    scored = []
    for entry in entries:
        score = score_agent_cache_entry(entry, query, query_tokens)
        if score <= 0:
            continue
        scored.append((score, entry))

    scored.sort(
        key=lambda item: (
            -item[0],
            kind_compare_rank(str(item[1].get("kind") or "")),
            str(item[1].get("path") or ""),
            str(item[1].get("qualified_name") or item[1].get("name") or ""),
        )
    )

    results = []
    seen = set()
    for score, entry in scored:
        dedupe_key = (
            str(entry.get("symbol_id") or ""),
            str(entry.get("path") or ""),
            str(entry.get("qualified_name") or entry.get("name") or ""),
            str(entry.get("kind") or ""),
        )
        if dedupe_key in seen:
            continue
        seen.add(dedupe_key)
        result = dict(entry)
        result["score"] = round(float(score), 3)
        result.pop("search_text", None)
        results.append(result)
        if len(results) >= limit:
            break
    return results


def score_agent_cache_entry(entry: Dict[str, object], raw_query: str, query_tokens: Sequence[str]) -> float:
    search_text = str(entry.get("search_text") or "")
    name = str(entry.get("name") or "")
    qualified_name = str(entry.get("qualified_name") or "")
    path = str(entry.get("path") or "")
    tags = [str(item) for item in entry.get("metadata", {}).get("tags", []) or ()]

    score = 0.0
    if raw_query == qualified_name:
        score += 120.0
    if raw_query == name:
        score += 100.0
    lowered_query = raw_query.lower()
    if lowered_query == qualified_name.lower():
        score += 90.0
    if lowered_query == name.lower():
        score += 75.0
    if lowered_query and lowered_query in path.lower():
        score += 30.0

    token_hits = 0
    for token in query_tokens:
        if token in search_text:
            score += 8.0
            token_hits += 1
        if token in (name.lower(), qualified_name.lower()):
            score += 12.0
        if token in path.lower():
            score += 6.0
        if token in tags:
            score += 6.0

    if token_hits == len(query_tokens) and query_tokens:
        score += 20.0

    visibility = str(entry.get("metadata", {}).get("visibility") or "")
    if visibility.startswith("pub") or visibility == "public":
        score += 5.0
    return score


def normalize_query_tokens(query: str) -> List[str]:
    tokens = []
    for raw_token in query.replace("::", " ").replace("/", " ").replace("-", " ").replace(".", " ").split():
        normalized = "".join(char for char in raw_token.lower() if char.isalnum() or char == "_")
        if normalized:
            tokens.append(normalized)
    return tokens


def kind_compare_rank(kind: str) -> int:
    ranking = {
        "repo": 0,
        "package": 1,
        "directory": 2,
        "file": 3,
        "symbol": 4,
        "type_body": 5,
        "function_body": 6,
        "doc": 7,
    }
    return ranking.get(kind, 99)


def resolve_symbol_query(search_root: Path, parsed_root: Path, repo_name: str, symbol_query: str) -> Optional[Dict[str, object]]:
    if symbol_query.startswith("sym:"):
        return load_symbol_by_id(parsed_root, repo_name, symbol_query)

    matches = graph_where_defined(search_root, parsed_root, repo_name, symbol_query, limit=1)["matches"]
    if not matches:
        return None
    symbol_id = matches[0]["symbol_id"]
    if not symbol_id:
        return None
    return load_symbol_by_id(parsed_root, repo_name, symbol_id)


def describe_symbol_row(symbol: Optional[Dict[str, object]]) -> Optional[Dict[str, object]]:
    if symbol is None:
        return None
    return {
        "symbol_id": symbol["symbol_id"],
        "name": symbol["name"],
        "qualified_name": symbol["qualified_name"],
        "kind": symbol["kind"],
        "path": symbol["path"],
        "signature": symbol.get("signature"),
        "summary_id": symbol.get("summary_id"),
        "normalized_body_hash": symbol.get("normalized_body_hash"),
        "container_symbol_id": symbol.get("container_symbol_id"),
        "container_qualified_name": symbol.get("container_qualified_name"),
    }


def stable_repo_id(repo_name: str) -> str:
    from symbols.indexer import stable_id

    return stable_id("repo", repo_name)


def stable_file_id(repo_name: str, path: str) -> str:
    from symbols.indexer import stable_id

    return stable_id("file", repo_name, path)


def stable_directory_id(repo_name: str, path: str) -> str:
    from symbols.indexer import stable_id

    return stable_id("dir", repo_name, path)


def stable_package_id(repo_name: str, package_name: str) -> str:
    from symbols.indexer import stable_id

    return stable_id("pkg", repo_name, package_name)
