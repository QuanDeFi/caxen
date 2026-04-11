from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Dict, List, Sequence

from embeddings.indexer import query_embedding_index
from retrieval.engine import retrieve_context
from search.indexer import search_documents
from symbols.indexer import timestamp_now


SCHEMA_VERSION = "0.2.0"
DEFAULT_MODES = (
    "lexical_only",
    "lexical_graph",
    "lexical_graph_rerank",
    "lexical_graph_rerank_summaries",
    "lexical_graph_vector_rerank",
    "lexical_graph_vector_rerank_summaries",
    "selective_on",
    "selective_off",
)
DEFAULT_BENCHMARKS = [
    {
        "name": "yellowstone_vixen_attr_macro",
        "repo": "yellowstone-vixen",
        "task_type": "symbol_lookup",
        "query": "vixen proc macro attribute",
        "expected_path": "crates/proc-macro/src/lib.rs",
        "expected_name": "vixen",
    },
    {
        "name": "yellowstone_include_parser_macro",
        "repo": "yellowstone-vixen",
        "task_type": "extension_point",
        "query": "include vixen parser macro",
        "expected_path": "crates/proc-macro/src/lib.rs",
        "expected_name": "include_vixen_parser",
    },
    {
        "name": "yellowstone_runtime_handler_trait",
        "repo": "yellowstone-vixen",
        "task_type": "architecture",
        "query": "runtime handler trait",
        "expected_path": "crates/runtime/src/handler.rs",
        "expected_name": "Handler",
    },
    {
        "name": "yellowstone_runtime_source_trait",
        "repo": "yellowstone-vixen",
        "task_type": "extension_point",
        "query": "runtime source trait",
        "expected_path": "crates/runtime/src/sources.rs",
        "expected_name": "SourceTrait",
    },
    {
        "name": "carbon_deduplication_filter",
        "repo": "carbon",
        "task_type": "symbol_lookup",
        "query": "deduplication filter",
        "expected_path": "crates/core/src/filter.rs",
        "expected_name": "DeduplicationFilter",
    },
    {
        "name": "carbon_datasource_filter",
        "repo": "carbon",
        "task_type": "extension_point",
        "query": "datasource filter",
        "expected_path": "crates/core/src/filter.rs",
        "expected_name": "DatasourceFilter",
    },
    {
        "name": "carbon_instruction_decoder_trait",
        "repo": "carbon",
        "task_type": "architecture",
        "query": "instruction decoder trait",
        "expected_path": "crates/core/src/instruction.rs",
        "expected_name": "InstructionDecoder",
    },
    {
        "name": "carbon_account_decoder_trait",
        "repo": "carbon",
        "task_type": "architecture",
        "query": "account decoder trait",
        "expected_path": "crates/core/src/account.rs",
        "expected_name": "AccountDecoder",
    },
]


def run_benchmarks(
    search_root: Path,
    graph_root: Path,
    parsed_root: Path,
    eval_root: Path,
    *,
    summary_root: Path | None = None,
    repos: Sequence[str] = (),
    limit: int = 5,
    modes: Sequence[str] = DEFAULT_MODES,
) -> Dict[str, object]:
    selected_repos = set(repos or [item["repo"] for item in DEFAULT_BENCHMARKS])
    cases = [item for item in DEFAULT_BENCHMARKS if item["repo"] in selected_repos]
    selected_modes = tuple(modes or DEFAULT_MODES)

    runs = []
    for case in cases:
        for mode in selected_modes:
            runs.append(run_case(case, mode, search_root, graph_root, parsed_root, summary_root, limit))

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
    summary_root: Path | None,
    limit: int,
) -> Dict[str, object]:
    started = time.perf_counter()
    if mode == "lexical_only":
        selected = search_documents(search_root, case["repo"], case["query"], limit=limit, kinds=("symbol", "file"))
        context_summary = {"mode": "lexical_only"}
    elif mode == "embedding_only":
        selected = query_embedding_index(search_root, case["repo"], case["query"], limit=limit)
        context_summary = {"mode": "embedding_only"}
    else:
        context = retrieve_context(
            search_root,
            graph_root,
            parsed_root,
            case["repo"],
            case["query"],
            summary_root=summary_root,
            limit=limit,
            use_graph=mode != "lexical_only",
            use_embeddings=mode in {"lexical_graph_vector_rerank", "lexical_graph_vector_rerank_summaries", "selective_on", "selective_off"},
            use_rerank=mode not in {"lexical_graph", "lexical_only"},
            use_summaries=mode in {"lexical_graph_rerank_summaries", "lexical_graph_vector_rerank_summaries", "selective_on", "selective_off"},
            selective_retrieval=mode == "selective_on",
        )
        selected = context["selected_context"]
        context_summary = context["summary"]
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
        "task_type": case["task_type"],
        "query": case["query"],
        "mode": mode,
        "expected_path": case["expected_path"],
        "expected_name": case["expected_name"],
        "latency_ms": elapsed_ms,
        "exact_hit": exact_hit,
        "path_hit": path_hit,
        "files_opened": count_unique_paths(selected),
        "prepared_tokens": estimate_prepared_tokens(selected),
        "selected_count": len(selected),
        "context_summary": context_summary,
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
                "avg_latency_ms": average(run["latency_ms"] for run in mode_runs),
                "avg_files_opened": average(run["files_opened"] for run in mode_runs),
                "avg_prepared_tokens": average(run["prepared_tokens"] for run in mode_runs),
            }
        )

    return {
        "runs": len(runs),
        "modes": mode_summaries,
    }


def count_unique_paths(selected: Sequence[Dict[str, object]]) -> int:
    return len({str(item.get("path")) for item in selected if item.get("path")})


def estimate_prepared_tokens(selected: Sequence[Dict[str, object]]) -> int:
    total = 0
    for item in selected:
        text = " ".join(
            str(part or "")
            for part in (item.get("title"), item.get("preview"), item.get("qualified_name"), item.get("path"))
        )
        total += len(text.split())
    return total


def average(values: Sequence[float] | Sequence[int]) -> float:
    values = list(values)
    if not values:
        return 0.0
    return round(sum(float(value) for value in values) / len(values), 3)
