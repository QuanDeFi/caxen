from __future__ import annotations

import json
import re
import time
from pathlib import Path
from typing import Dict, List, Optional, Sequence

from embeddings.indexer import query_embedding_index
from retrieval.engine import retrieve_context
from retrieval.planner import prepare_answer_bundle
from search.indexer import search_documents
from symbols.indexer import timestamp_now


SCHEMA_VERSION = "0.4.0"
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
    progress_callback=None,
) -> Dict[str, object]:
    started = time.perf_counter()
    benchmark_cases = list(benchmarks or DEFAULT_BENCHMARKS)
    selected_repos = set(repos or [item["repo"] for item in benchmark_cases])
    cases = [item for item in benchmark_cases if item["repo"] in selected_repos]
    selected_modes = tuple(modes or DEFAULT_MODES)
    total_runs = len(cases) * len(selected_modes)

    def emit(event: str, **extra: object) -> None:
        if progress_callback is None:
            return
        progress_callback(
            {
                "event": event,
                "elapsed_ms": round((time.perf_counter() - started) * 1000, 3),
                "cases": len(cases),
                "modes": len(selected_modes),
                "total_runs": total_runs,
                **extra,
            }
        )

    emit("run_started", repos=sorted(selected_repos))

    runs = []
    completed_runs = 0
    for case in cases:
        for mode in selected_modes:
            emit("case_started", repo=case["repo"], case_name=case["name"], mode=mode, completed_runs=completed_runs)
            runs.append(run_case(case, mode, search_root, graph_root, parsed_root, summary_root, limit))
            completed_runs += 1
            latest = runs[-1]
            emit(
                "case_completed",
                repo=case["repo"],
                case_name=case["name"],
                mode=mode,
                completed_runs=completed_runs,
                exact_hit=latest["exact_hit"],
                path_hit=latest["path_hit"],
                latency_ms=latest["latency_ms"],
            )

    payload = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": timestamp_now(),
        "summary": summarize_runs(runs),
        "runs": runs,
    }

    eval_root.mkdir(parents=True, exist_ok=True)
    write_json(eval_root / "benchmarks.json", payload)
    emit("run_completed", completed_runs=completed_runs)
    return payload


def export_benchmark_prompts(
    search_root: Path,
    graph_root: Path,
    parsed_root: Path,
    summary_root: Path,
    eval_root: Path,
    *,
    repos: Sequence[str] = (),
    limit: int = 8,
    benchmarks: Optional[Sequence[Dict[str, object]]] = None,
) -> Dict[str, object]:
    benchmark_cases = list(benchmarks or DEFAULT_BENCHMARKS)
    selected_repos = set(repos or [item["repo"] for item in benchmark_cases])
    cases = [item for item in benchmark_cases if item["repo"] in selected_repos]
    export_root = eval_root / "prompt_exports"
    export_root.mkdir(parents=True, exist_ok=True)

    prompt_exports = []
    for case in cases:
        bundle = prepare_answer_bundle(
            search_root,
            summary_root,
            graph_root,
            parsed_root,
            case["query"],
            repo_name=case["repo"],
            limit=limit,
        )
        prompt_payload = {
            "name": case["name"],
            "repo": case["repo"],
            "task_type": case["task_type"],
            "query": case["query"],
            "expected_path": case["expected_path"],
            "expected_name": case["expected_name"],
            "expected_terms": case.get("expected_terms", []),
            "prompt": build_prompt_text(case, bundle),
            "answer_bundle": bundle,
            "provenance_requirements": {
                "must_cite_path": case["expected_path"],
                "should_cite_symbol": case["expected_name"],
            },
        }
        write_json(export_root / f"{case['name']}.json", prompt_payload)
        prompt_exports.append(
            {
                "name": case["name"],
                "repo": case["repo"],
                "path": f"data/eval/prompt_exports/{case['name']}.json",
            }
        )

    manifest = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": timestamp_now(),
        "summary": {
            "exports": len(prompt_exports),
            "repos": sorted(selected_repos),
        },
        "exports": prompt_exports,
    }
    write_json(export_root / "manifest.json", manifest)
    return manifest


def score_answer_bundles(
    search_root: Path,
    graph_root: Path,
    parsed_root: Path,
    summary_root: Path,
    eval_root: Path,
    *,
    repos: Sequence[str] = (),
    limit: int = 8,
    benchmarks: Optional[Sequence[Dict[str, object]]] = None,
) -> Dict[str, object]:
    benchmark_cases = list(benchmarks or DEFAULT_BENCHMARKS)
    selected_repos = set(repos or [item["repo"] for item in benchmark_cases])
    cases = [item for item in benchmark_cases if item["repo"] in selected_repos]
    scores = []
    for case in cases:
        bundle = prepare_answer_bundle(
            search_root,
            summary_root,
            graph_root,
            parsed_root,
            case["query"],
            repo_name=case["repo"],
            limit=limit,
        )
        scores.append(score_bundle(case, bundle))
    payload = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": timestamp_now(),
        "summary": summarize_bundle_scores(scores),
        "scores": scores,
    }
    eval_root.mkdir(parents=True, exist_ok=True)
    write_json(eval_root / "bundle_scores.json", payload)
    return payload


def score_external_answers(
    eval_root: Path,
    answers_path: Path,
    *,
    benchmarks: Optional[Sequence[Dict[str, object]]] = None,
) -> Dict[str, object]:
    benchmark_cases = {item["name"]: item for item in list(benchmarks or DEFAULT_BENCHMARKS)}
    answers_payload = load_json(answers_path)
    raw_answers = answers_payload.get("answers", answers_payload)
    if isinstance(raw_answers, list):
        answers_by_name = {item["name"]: item for item in raw_answers}
    else:
        answers_by_name = raw_answers

    results = []
    for case_name, case in sorted(benchmark_cases.items()):
        answer = answers_by_name.get(case_name, {})
        results.append(score_external_answer(case, answer))

    payload = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": timestamp_now(),
        "summary": summarize_external_answer_scores(results),
        "scores": results,
    }
    eval_root.mkdir(parents=True, exist_ok=True)
    write_json(eval_root / "external_answer_scores.json", payload)
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
    bundle_quality = None
    if summary_root is not None:
        bundle = prepare_answer_bundle(
            search_root,
            summary_root,
            graph_root,
            parsed_root,
            case["query"],
            repo_name=case["repo"],
            limit=limit,
        )
        bundle_quality = score_bundle(case, bundle)

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
        "bundle_quality": bundle_quality,
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
                "avg_bundle_score": average(
                    run["bundle_quality"]["score"] for run in mode_runs if run.get("bundle_quality") is not None
                ),
            }
        )

    retrieval_metrics = {
        "runs": len(runs),
        "exact_hits": sum(1 for run in runs if run["exact_hit"]),
        "path_hits": sum(1 for run in runs if run["path_hit"]),
        "avg_latency_ms": average(run["latency_ms"] for run in runs),
    }
    consumer_metrics = {
        "avg_answer_score": average(run["answer_quality"]["score"] for run in runs),
        "avg_bundle_score": average(
            run["bundle_quality"]["score"] for run in runs if run.get("bundle_quality") is not None
        ),
        "runs_with_bundle_scores": sum(1 for run in runs if run.get("bundle_quality") is not None),
    }

    return {
        "runs": len(runs),
        "modes": mode_summaries,
        "task_types": summarize_task_types(runs),
        "retrieval_metrics": retrieval_metrics,
        "consumer_readiness": consumer_metrics,
    }


def score_bundle(case: Dict[str, object], bundle: Dict[str, object]) -> Dict[str, object]:
    repo_bundle = bundle["bundles"][0]
    selected = repo_bundle["selected_context"]
    evidence = repo_bundle["evidence"]
    graph_neighborhoods = repo_bundle["graph_neighborhoods"]
    statement_slices = repo_bundle["statement_slices"]
    all_text = normalize_answer_text(
        " ".join(
            str(part or "")
            for item in [*selected, *evidence]
            for part in (
                item.get("path"),
                item.get("name"),
                item.get("qualified_name"),
                item.get("title"),
                item.get("preview"),
                item.get("why_included"),
            )
        )
    )

    expected_terms = [str(term) for term in case.get("expected_terms", [])]
    expected_name = str(case.get("expected_name") or "")
    expected_path = str(case.get("expected_path") or "")
    path_credit = 1.0 if any(str(item.get("path") or "") == expected_path for item in selected) else 0.0
    name_credit = 1.0 if expected_name and expected_name.lower() in all_text else 0.0
    term_hits = sum(1 for term in expected_terms if normalize_answer_text(term) in all_text)
    term_coverage = round(term_hits / len(expected_terms), 3) if expected_terms else 0.0
    provenance_credit = 1.0 if all(item.get("provenance", {}).get("path") for item in evidence[:3]) else 0.0
    graph_credit = 1.0 if graph_neighborhoods else 0.0
    statement_credit = 1.0 if statement_slices else 0.0
    score = round(
        path_credit * 0.3
        + name_credit * 0.2
        + term_coverage * 0.2
        + provenance_credit * 0.1
        + graph_credit * 0.1
        + statement_credit * 0.1,
        3,
    )
    return {
        "score": score,
        "path_credit": path_credit,
        "name_credit": name_credit,
        "term_coverage": term_coverage,
        "provenance_credit": provenance_credit,
        "graph_credit": graph_credit,
        "statement_credit": statement_credit,
        "selected_context": len(selected),
        "evidence_items": len(evidence),
    }


def score_external_answer(case: Dict[str, object], answer: Dict[str, object]) -> Dict[str, object]:
    answer_text = normalize_answer_text(str(answer.get("answer") or ""))
    cited_paths = {str(item) for item in answer.get("cited_paths", [])}
    cited_symbols = {str(item) for item in answer.get("cited_symbols", [])}
    expected_terms = [str(term) for term in case.get("expected_terms", [])]
    expected_name = str(case.get("expected_name") or "")
    expected_path = str(case.get("expected_path") or "")
    name_credit = 1.0 if expected_name.lower() in answer_text else 0.0
    path_credit = 1.0 if expected_path in cited_paths or expected_path in answer_text else 0.0
    symbol_credit = 1.0 if expected_name in cited_symbols else 0.0
    term_hits = sum(1 for term in expected_terms if normalize_answer_text(term) in answer_text)
    term_coverage = round(term_hits / len(expected_terms), 3) if expected_terms else 0.0
    score = round(path_credit * 0.35 + name_credit * 0.25 + symbol_credit * 0.2 + term_coverage * 0.2, 3)
    return {
        "name": case["name"],
        "repo": case["repo"],
        "score": score,
        "path_credit": path_credit,
        "name_credit": name_credit,
        "symbol_credit": symbol_credit,
        "term_coverage": term_coverage,
    }


def summarize_bundle_scores(scores: Sequence[Dict[str, object]]) -> Dict[str, object]:
    return {
        "cases": len(scores),
        "avg_bundle_score": average(item["score"] for item in scores),
        "full_path_hits": sum(1 for item in scores if item["path_credit"] >= 1.0),
    }


def summarize_external_answer_scores(scores: Sequence[Dict[str, object]]) -> Dict[str, object]:
    return {
        "cases": len(scores),
        "avg_score": average(item["score"] for item in scores),
        "path_hits": sum(1 for item in scores if item["path_credit"] >= 1.0),
        "name_hits": sum(1 for item in scores if item["name_credit"] >= 1.0),
    }


def build_prompt_text(case: Dict[str, object], bundle: Dict[str, object]) -> str:
    repo_bundle = bundle["bundles"][0]
    return (
        "Answer the repository question using only the provided bundle.\n"
        f"Question: {case['query']}\n"
        f"Expected task type: {case['task_type']}\n"
        "Cite file paths and symbol names used as evidence.\n"
        f"Project summary: {repo_bundle['project_summary']}\n"
        f"Evidence items: {json.dumps(repo_bundle['evidence'][:5], sort_keys=False)}\n"
    )


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
            "avg_bundle_score": average(
                run["bundle_quality"]["score"] for run in task_runs if run.get("bundle_quality") is not None
            ),
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


def load_json(path: Path) -> Dict[str, object]:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def write_json(path: Path, payload: Dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, sort_keys=False)
        handle.write("\n")
