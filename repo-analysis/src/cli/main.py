from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import List, Optional


SRC_ROOT = Path(__file__).resolve().parents[1]
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from agents.toolkit import (
    compare_repos,
    find_datasources,
    find_decoders,
    find_parsers,
    find_runtime_handlers,
    find_symbol,
    prepare_context,
    repo_overview,
    summarize_path,
    trace_calls,
)
from adapters.carbon.adapter import inventory as inventory_carbon
from adapters.yellowstone_vixen.adapter import inventory as inventory_yellowstone_vixen
from common.inventory import write_inventory
from evaluation.harness import run_benchmarks
from graph.builder import build_graph_artifact, write_graph_artifact
from search.indexer import build_search_index
from summaries.builder import build_summary_artifacts, write_summary_artifacts
from symbols.indexer import build_symbol_index, write_symbol_index
from symbols.persistence import write_symbol_database, write_symbol_parquet_bundle


ADAPTERS = {
    "carbon": inventory_carbon,
    "yellowstone-vixen": inventory_yellowstone_vixen,
}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="repo-analysis operator CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    parse_repos = subparsers.add_parser(
        "parse-repos",
        help="Collect normalized raw repo inventory for the upstream repos.",
    )
    parse_repos.add_argument(
        "--workspace-root",
        required=True,
        help="Absolute path to the umbrella workspace root.",
    )
    parse_repos.add_argument(
        "--output-root",
        required=True,
        help="Directory where raw inventory JSON files should be written.",
    )
    parse_repos.add_argument(
        "--repo",
        action="append",
        choices=sorted(ADAPTERS),
        help="Restrict inventory generation to one or more named repos.",
    )

    build_index = subparsers.add_parser(
        "build-index",
        help="Parse Rust source roots into symbol and graph artifacts.",
    )
    build_index.add_argument(
        "--workspace-root",
        required=True,
        help="Absolute path to the umbrella workspace root.",
    )
    build_index.add_argument(
        "--raw-root",
        required=True,
        help="Directory containing raw inventory JSON files.",
    )
    build_index.add_argument(
        "--parsed-root",
        required=True,
        help="Directory where parsed symbol artifacts should be written.",
    )
    build_index.add_argument(
        "--graph-root",
        required=True,
        help="Directory where graph artifacts should be written.",
    )
    build_index.add_argument(
        "--repo",
        action="append",
        choices=sorted(ADAPTERS),
        help="Restrict indexing to one or more named repos.",
    )
    build_index.add_argument(
        "--path-prefix",
        action="append",
        help="Optional repo-relative file or directory prefix to narrow indexing scope.",
    )

    build_search = subparsers.add_parser(
        "build-search",
        help="Build lexical search artifacts over raw and parsed outputs.",
    )
    build_search.add_argument("--workspace-root", required=True)
    build_search.add_argument("--raw-root", required=True)
    build_search.add_argument("--parsed-root", required=True)
    build_search.add_argument("--search-root", required=True)
    build_search.add_argument("--repo", action="append", choices=sorted(ADAPTERS))

    build_summaries = subparsers.add_parser(
        "build-summaries",
        help="Build deterministic project/directory/file/symbol summaries.",
    )
    build_summaries.add_argument("--raw-root", required=True)
    build_summaries.add_argument("--parsed-root", required=True)
    build_summaries.add_argument("--graph-root", required=True)
    build_summaries.add_argument("--summary-root", required=True)
    build_summaries.add_argument("--repo", action="append", choices=sorted(ADAPTERS))

    run_eval = subparsers.add_parser(
        "run-benchmarks",
        help="Run the lightweight retrieval benchmark slice.",
    )
    run_eval.add_argument("--search-root", required=True)
    run_eval.add_argument("--graph-root", required=True)
    run_eval.add_argument("--parsed-root", required=True)
    run_eval.add_argument("--eval-root", required=True)
    run_eval.add_argument("--repo", action="append", choices=sorted(ADAPTERS))
    run_eval.add_argument("--limit", type=int, default=5)

    repo_overview_cmd = subparsers.add_parser("repo-overview", help="Show the repo-level summary.")
    repo_overview_cmd.add_argument("--summary-root", required=True)
    repo_overview_cmd.add_argument("--repo", required=True, choices=sorted(ADAPTERS))

    find_symbol_cmd = subparsers.add_parser("find-symbol", help="Search indexed symbols.")
    find_symbol_cmd.add_argument("--search-root", required=True)
    find_symbol_cmd.add_argument("--repo", required=True, choices=sorted(ADAPTERS))
    find_symbol_cmd.add_argument("query")
    find_symbol_cmd.add_argument("--limit", type=int, default=10)

    trace_calls_cmd = subparsers.add_parser("trace-calls", help="Trace callers and callees for a symbol.")
    trace_calls_cmd.add_argument("--search-root", required=True)
    trace_calls_cmd.add_argument("--graph-root", required=True)
    trace_calls_cmd.add_argument("--parsed-root", required=True)
    trace_calls_cmd.add_argument("--repo", required=True, choices=sorted(ADAPTERS))
    trace_calls_cmd.add_argument("symbol")
    trace_calls_cmd.add_argument("--limit", type=int, default=10)

    compare_repos_cmd = subparsers.add_parser("compare-repos", help="Compare retrieval context across repos.")
    compare_repos_cmd.add_argument("--search-root", required=True)
    compare_repos_cmd.add_argument("--summary-root", required=True)
    compare_repos_cmd.add_argument("--graph-root", required=True)
    compare_repos_cmd.add_argument("--parsed-root", required=True)
    compare_repos_cmd.add_argument("--repo", action="append", choices=sorted(ADAPTERS))
    compare_repos_cmd.add_argument("query")
    compare_repos_cmd.add_argument("--limit", type=int, default=5)

    find_parsers_cmd = subparsers.add_parser("find-parsers", help="Find parser-related paths and symbols.")
    find_parsers_cmd.add_argument("--search-root", required=True)
    find_parsers_cmd.add_argument("--repo", required=True, choices=sorted(ADAPTERS))
    find_parsers_cmd.add_argument("--limit", type=int, default=10)

    find_datasources_cmd = subparsers.add_parser("find-datasources", help="Find datasource-related paths and symbols.")
    find_datasources_cmd.add_argument("--search-root", required=True)
    find_datasources_cmd.add_argument("--repo", required=True, choices=sorted(ADAPTERS))
    find_datasources_cmd.add_argument("--limit", type=int, default=10)

    find_decoders_cmd = subparsers.add_parser("find-decoders", help="Find decoder-related paths and symbols.")
    find_decoders_cmd.add_argument("--search-root", required=True)
    find_decoders_cmd.add_argument("--repo", required=True, choices=sorted(ADAPTERS))
    find_decoders_cmd.add_argument("--limit", type=int, default=10)

    find_runtime_handlers_cmd = subparsers.add_parser("find-runtime-handlers", help="Find runtime and handler surfaces.")
    find_runtime_handlers_cmd.add_argument("--search-root", required=True)
    find_runtime_handlers_cmd.add_argument("--repo", required=True, choices=sorted(ADAPTERS))
    find_runtime_handlers_cmd.add_argument("--limit", type=int, default=10)

    summarize_path_cmd = subparsers.add_parser("summarize-path", help="Summarize a file or directory path.")
    summarize_path_cmd.add_argument("--summary-root", required=True)
    summarize_path_cmd.add_argument("--repo", required=True, choices=sorted(ADAPTERS))
    summarize_path_cmd.add_argument("path")

    prepare_context_cmd = subparsers.add_parser("prepare-context", help="Prepare a compact retrieval context for a task.")
    prepare_context_cmd.add_argument("--search-root", required=True)
    prepare_context_cmd.add_argument("--summary-root", required=True)
    prepare_context_cmd.add_argument("--graph-root", required=True)
    prepare_context_cmd.add_argument("--parsed-root", required=True)
    prepare_context_cmd.add_argument("--repo", choices=sorted(ADAPTERS))
    prepare_context_cmd.add_argument("task")
    prepare_context_cmd.add_argument("--limit", type=int, default=8)
    return parser


def handle_parse_repos(args: argparse.Namespace) -> int:
    workspace_root = Path(args.workspace_root).resolve()
    output_root = Path(args.output_root).resolve()
    repo_names = args.repo or sorted(ADAPTERS)

    output_root.mkdir(parents=True, exist_ok=True)

    for repo_name in repo_names:
        repo_root = workspace_root / repo_name
        if not repo_root.exists():
            raise FileNotFoundError(f"Missing repo root: {repo_root}")
        inventory = ADAPTERS[repo_name](repo_root)
        write_inventory(output_root, repo_name, inventory)
        print(f"Wrote raw inventory for {repo_name} to {output_root / repo_name}")

    return 0


def handle_build_index(args: argparse.Namespace) -> int:
    workspace_root = Path(args.workspace_root).resolve()
    raw_root = Path(args.raw_root).resolve()
    parsed_root = Path(args.parsed_root).resolve()
    graph_root = Path(args.graph_root).resolve()
    repo_names = args.repo or sorted(ADAPTERS)
    path_prefixes = tuple(args.path_prefix or [])

    parsed_root.mkdir(parents=True, exist_ok=True)
    graph_root.mkdir(parents=True, exist_ok=True)

    for repo_name in repo_names:
        repo_root = workspace_root / repo_name
        if not repo_root.exists():
            raise FileNotFoundError(f"Missing repo root: {repo_root}")

        symbol_index = build_symbol_index(
            repo_name,
            repo_root,
            raw_root,
            path_prefixes=path_prefixes,
        )
        graph_artifact = build_graph_artifact(symbol_index)

        write_symbol_index(parsed_root, repo_name, symbol_index)
        write_symbol_database(parsed_root, repo_name, symbol_index)
        write_symbol_parquet_bundle(parsed_root, repo_name, symbol_index)
        write_graph_artifact(graph_root, repo_name, graph_artifact)

        print(f"Wrote parsed symbols for {repo_name} to {parsed_root / repo_name}")
        print(f"Wrote graph artifact for {repo_name} to {graph_root / repo_name}")

    return 0


def handle_build_search(args: argparse.Namespace) -> int:
    workspace_root = Path(args.workspace_root).resolve()
    raw_root = Path(args.raw_root).resolve()
    parsed_root = Path(args.parsed_root).resolve()
    search_root = Path(args.search_root).resolve()
    repo_names = args.repo or sorted(ADAPTERS)

    search_root.mkdir(parents=True, exist_ok=True)
    for repo_name in repo_names:
        repo_root = workspace_root / repo_name
        payload = build_search_index(repo_name, repo_root, raw_root, parsed_root, search_root)
        print(f"Wrote search artifacts for {repo_name} to {search_root / repo_name} ({payload['summary']['documents']} documents)")
    return 0


def handle_build_summaries(args: argparse.Namespace) -> int:
    raw_root = Path(args.raw_root).resolve()
    parsed_root = Path(args.parsed_root).resolve()
    graph_root = Path(args.graph_root).resolve()
    summary_root = Path(args.summary_root).resolve()
    repo_names = args.repo or sorted(ADAPTERS)

    summary_root.mkdir(parents=True, exist_ok=True)
    for repo_name in repo_names:
        payload = build_summary_artifacts(repo_name, raw_root, parsed_root, graph_root)
        write_summary_artifacts(summary_root, repo_name, payload)
        print(f"Wrote summaries for {repo_name} to {summary_root / repo_name}")
    return 0


def handle_run_benchmarks(args: argparse.Namespace) -> int:
    payload = run_benchmarks(
        Path(args.search_root).resolve(),
        Path(args.graph_root).resolve(),
        Path(args.parsed_root).resolve(),
        Path(args.eval_root).resolve(),
        repos=tuple(args.repo or ()),
        limit=args.limit,
    )
    print_json(payload)
    return 0


def print_json(payload: object) -> int:
    print(json.dumps(payload, indent=2, sort_keys=False))
    return 0


def main(argv: Optional[List[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "parse-repos":
        return handle_parse_repos(args)
    if args.command == "build-index":
        return handle_build_index(args)
    if args.command == "build-search":
        return handle_build_search(args)
    if args.command == "build-summaries":
        return handle_build_summaries(args)
    if args.command == "run-benchmarks":
        return handle_run_benchmarks(args)
    if args.command == "repo-overview":
        return print_json(repo_overview(Path(args.summary_root).resolve(), args.repo))
    if args.command == "find-symbol":
        return print_json(find_symbol(Path(args.search_root).resolve(), args.repo, args.query, limit=args.limit))
    if args.command == "trace-calls":
        return print_json(
            trace_calls(
                Path(args.search_root).resolve(),
                Path(args.graph_root).resolve(),
                Path(args.parsed_root).resolve(),
                args.repo,
                args.symbol,
                limit=args.limit,
            )
        )
    if args.command == "compare-repos":
        return print_json(
            compare_repos(
                Path(args.search_root).resolve(),
                Path(args.summary_root).resolve(),
                Path(args.graph_root).resolve(),
                Path(args.parsed_root).resolve(),
                args.query,
                repos=tuple(args.repo or ("carbon", "yellowstone-vixen")),
                limit=args.limit,
            )
        )
    if args.command == "find-parsers":
        return print_json(find_parsers(Path(args.search_root).resolve(), args.repo, limit=args.limit))
    if args.command == "find-datasources":
        return print_json(find_datasources(Path(args.search_root).resolve(), args.repo, limit=args.limit))
    if args.command == "find-decoders":
        return print_json(find_decoders(Path(args.search_root).resolve(), args.repo, limit=args.limit))
    if args.command == "find-runtime-handlers":
        return print_json(find_runtime_handlers(Path(args.search_root).resolve(), args.repo, limit=args.limit))
    if args.command == "summarize-path":
        return print_json(summarize_path(Path(args.summary_root).resolve(), args.repo, args.path))
    if args.command == "prepare-context":
        return print_json(
            prepare_context(
                Path(args.search_root).resolve(),
                Path(args.summary_root).resolve(),
                Path(args.graph_root).resolve(),
                Path(args.parsed_root).resolve(),
                args.task,
                repo_name=args.repo,
                limit=args.limit,
            )
        )

    parser.error(f"Unsupported command: {args.command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
