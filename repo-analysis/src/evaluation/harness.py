from __future__ import annotations

import json
import re
import time
from pathlib import Path
from typing import Dict, List, Optional, Sequence

from embeddings.indexer import query_embedding_index
from retrieval.engine import retrieve_context
from search.indexer import search_documents
from symbols.indexer import timestamp_now


SCHEMA_VERSION = "0.3.0"
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
        "expected_terms": ["vixen", "proc-macro"],
    },
    {
        "name": "yellowstone_include_parser_macro",
        "repo": "yellowstone-vixen",
        "task_type": "extension_point",
        "query": "include vixen parser macro",
        "expected_path": "crates/proc-macro/src/lib.rs",
        "expected_name": "include_vixen_parser",
        "expected_terms": ["include_vixen_parser", "parser", "proc-macro"],
    },
    {
        "name": "yellowstone_runtime_handler_trait",
        "repo": "yellowstone-vixen",
        "task_type": "architecture",
        "query": "runtime handler trait",
        "expected_path": "crates/runtime/src/handler.rs",
        "expected_name": "Handler",
        "expected_terms": ["handler", "runtime", "trait"],
    },
    {
        "name": "yellowstone_runtime_source_trait",
        "repo": "yellowstone-vixen",
        "task_type": "extension_point",
        "query": "runtime source trait",
        "expected_path": "crates/runtime/src/sources.rs",
        "expected_name": "SourceTrait",
        "expected_terms": ["source", "runtime", "trait"],
    },
    {
        "name": "carbon_deduplication_filter",
        "repo": "carbon",
        "task_type": "symbol_lookup",
        "query": "deduplication filter",
        "expected_path": "crates/core/src/filter.rs",
        "expected_name": "DeduplicationFilter",
        "expected_terms": ["deduplication", "filter"],
    },
    {
        "name": "carbon_datasource_filter",
        "repo": "carbon",
        "task_type": "extension_point",
        "query": "datasource filter",
        "expected_path": "crates/core/src/filter.rs",
        "expected_name": "DatasourceFilter",
        "expected_terms": ["datasource", "filter"],
    },
    {
        "name": "carbon_instruction_decoder_trait",
        "repo": "carbon",
        "task_type": "architecture",
        "query": "instruction decoder trait",
        "expected_path": "crates/core/src/instruction.rs",
        "expected_name": "InstructionDecoder",
        "expected_terms": ["instruction", "decoder", "trait"],
    },
    {
        "name": "carbon_account_decoder_trait",
        "repo": "carbon",
        "task_type": "architecture",
        "query": "account decoder trait",
        "expected_path": "crates/core/src/account.rs",
        "expected_name": "AccountDecoder",
        "expected_terms": ["account", "decoder", "trait"],
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
    benchmarks: Optional[Sequence[Dict[str, object]]] = None,
) -> Dict[str, object]:
    benchmark_cases = list(benchmarks or DEFAULT_BENCHMARKS)
    selected_repos = set(repos or [item["repo"] for item in benchmark_cases])
    cases = [item for item in benchmark_cases if item["repo"] in selected_repos]
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
    answer_quality = grade_answer_quality(case, selected)

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
        "answer_quality": answer_quality,
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
                "avg_answer_score": average(run["answer_quality"]["score"] for run in mode_runs),
            }
        )

    return {
        "runs": len(runs),
        "modes": mode_summaries,
        "task_types": summarize_task_types(runs),
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


def summarize_task_types(runs: Sequence[Dict[str, object]]) -> List[Dict[str, object]]:
    grouped: Dict[str, List[Dict[str, object]]] = {}
    for run in runs:
        grouped.setdefault(str(run["task_type"]), []).append(run)

    return [
        {
            "task_type": task_type,
            "runs": len(task_runs),
            "exact_hits": sum(1 for run in task_runs if run["exact_hit"]),
            "path_hits": sum(1 for run in task_runs if run["path_hit"]),
            "avg_answer_score": average(run["answer_quality"]["score"] for run in task_runs),
        }
        for task_type, task_runs in sorted(grouped.items())
    ]


def grade_answer_quality(case: Dict[str, object], selected: Sequence[Dict[str, object]]) -> Dict[str, object]:
    synthesized_answer = synthesize_answer(selected)
    haystack = normalize_answer_text(synthesized_answer)
    expected_terms = [str(term) for term in case.get("expected_terms", [])]
    expected_name = str(case.get("expected_name") or "")
    expected_path = str(case.get("expected_path") or "")

    path_credit = 1.0 if any(str(item.get("path") or "") == expected_path for item in selected) else 0.0
    name_credit = 1.0 if expected_name and expected_name.lower() in haystack else 0.0
    term_hits = sum(1 for term in expected_terms if normalize_answer_text(term) in haystack)
    term_coverage = round(term_hits / len(expected_terms), 3) if expected_terms else 0.0
    top_hit = bool(
        selected
        and str(selected[0].get("path") or "") == expected_path
        and str(selected[0].get("name") or "") == expected_name
    )
    score = round(path_credit * 0.35 + name_credit * 0.35 + term_coverage * 0.2 + (0.1 if top_hit else 0.0), 3)

    return {
        "score": score,
        "path_credit": path_credit,
        "name_credit": name_credit,
        "term_coverage": term_coverage,
        "top_hit": top_hit,
        "expected_terms": expected_terms,
        "synthesized_answer": synthesized_answer,
    }


def synthesize_answer(selected: Sequence[Dict[str, object]]) -> str:
    parts: List[str] = []
    for item in selected[:3]:
        part_bits = []
        if item.get("qualified_name"):
            part_bits.append(str(item["qualified_name"]))
        elif item.get("name"):
            part_bits.append(str(item["name"]))
        elif item.get("title"):
            part_bits.append(str(item["title"]))
        if item.get("path"):
            part_bits.append(f"in {item['path']}")
        if item.get("preview"):
            part_bits.append(str(item["preview"]))
        if part_bits:
            parts.append(" ".join(part_bits))
    return " | ".join(parts)


def normalize_answer_text(value: str) -> str:
    return re.sub(r"[^a-z0-9_:/.-]+", " ", value.lower()).strip()
