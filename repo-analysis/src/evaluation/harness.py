from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Dict, List, Sequence

from retrieval.engine import retrieve_context
from search.indexer import search_documents
from embeddings.indexer import query_embedding_index
from symbols.indexer import timestamp_now


SCHEMA_VERSION = "0.1.0"
DEFAULT_BENCHMARKS = [
    {
        "name": "yellowstone_vixen_attr_macro",
        "repo": "yellowstone-vixen",
        "query": "vixen proc macro attribute",
        "expected_path": "crates/proc-macro/src/lib.rs",
        "expected_name": "vixen",
    },
    {
        "name": "yellowstone_include_parser_macro",
        "repo": "yellowstone-vixen",
        "query": "include vixen parser macro",
        "expected_path": "crates/proc-macro/src/lib.rs",
        "expected_name": "include_vixen_parser",
    },
    {
        "name": "carbon_deduplication_filter",
        "repo": "carbon",
        "query": "deduplication filter",
        "expected_path": "crates/core/src/filter.rs",
        "expected_name": "DeduplicationFilter",
    },
    {
        "name": "carbon_datasource_filter",
        "repo": "carbon",
        "query": "datasource filter",
        "expected_path": "crates/core/src/filter.rs",
        "expected_name": "DatasourceFilter",
    },
]


def run_benchmarks(
    search_root: Path,
    graph_root: Path,
    parsed_root: Path,
    eval_root: Path,
    *,
    repos: Sequence[str] = (),
    limit: int = 5,
) -> Dict[str, object]:
    selected_repos = set(repos or [item["repo"] for item in DEFAULT_BENCHMARKS])
    cases = [item for item in DEFAULT_BENCHMARKS if item["repo"] in selected_repos]

    runs = []
    for case in cases:
        runs.append(run_case(case, "lexical", search_root, graph_root, parsed_root, limit))
        runs.append(run_case(case, "lexical_graph", search_root, graph_root, parsed_root, limit))
        runs.append(run_case(case, "embedding", search_root, graph_root, parsed_root, limit))

    payload = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": timestamp_now(),
        "summary": summarize_runs(runs),
        "runs": runs,
    }

    eval_root.mkdir(parents=True, exist_ok=True)
    target = eval_root / "benchmarks.json"
    with target.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, sort_keys=False)
        handle.write("\n")
    return payload


def run_case(
    case: Dict[str, object],
    mode: str,
    search_root: Path,
    graph_root: Path,
    parsed_root: Path,
    limit: int,
) -> Dict[str, object]:
    started = time.perf_counter()
    if mode == "lexical":
        results = search_documents(search_root, case["repo"], case["query"], limit=limit, kinds=("symbol", "file"))
        selected = results
    elif mode == "embedding":
        selected = query_embedding_index(search_root, case["repo"], case["query"], limit=limit)
    else:
        context = retrieve_context(
            search_root,
            graph_root,
            parsed_root,
            case["repo"],
            case["query"],
            limit=limit,
            use_embeddings=False,
        )
        selected = context["selected_context"]
    elapsed_ms = round((time.perf_counter() - started) * 1000, 3)

    exact_hit = False
    path_hit = False
    for item in selected:
        if item.get("path") == case["expected_path"]:
            path_hit = True
        if item.get("path") == case["expected_path"] and item.get("name") == case["expected_name"]:
            exact_hit = True

    return {
        "name": case["name"],
        "repo": case["repo"],
        "query": case["query"],
        "mode": mode,
        "expected_path": case["expected_path"],
        "expected_name": case["expected_name"],
        "latency_ms": elapsed_ms,
        "exact_hit": exact_hit,
        "path_hit": path_hit,
        "selected": selected,
    }


def summarize_runs(runs: Sequence[Dict[str, object]]) -> Dict[str, object]:
    by_mode: Dict[str, List[Dict[str, object]]] = {}
    for run in runs:
        by_mode.setdefault(run["mode"], []).append(run)

    mode_summaries = []
    for mode, mode_runs in sorted(by_mode.items()):
        mode_summaries.append(
            {
                "mode": mode,
                "runs": len(mode_runs),
                "exact_hits": sum(1 for run in mode_runs if run["exact_hit"]),
                "path_hits": sum(1 for run in mode_runs if run["path_hit"]),
                "avg_latency_ms": round(sum(run["latency_ms"] for run in mode_runs) / max(len(mode_runs), 1), 3),
            }
        )

    return {
        "runs": len(runs),
        "modes": mode_summaries,
    }
