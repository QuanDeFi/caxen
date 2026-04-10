from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import List, Optional


SRC_ROOT = Path(__file__).resolve().parents[1]
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from adapters.carbon.adapter import inventory as inventory_carbon
from adapters.yellowstone_vixen.adapter import inventory as inventory_yellowstone_vixen
from common.inventory import write_inventory
from graph.builder import build_graph_artifact, write_graph_artifact
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


def main(argv: Optional[List[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "parse-repos":
        return handle_parse_repos(args)
    if args.command == "build-index":
        return handle_build_index(args)

    parser.error(f"Unsupported command: {args.command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
