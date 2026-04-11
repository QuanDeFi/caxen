from __future__ import annotations

import json
from collections import Counter, defaultdict
from pathlib import Path, PurePosixPath
from typing import Dict, Iterable, List, Tuple

from symbols.indexer import timestamp_now


SCHEMA_VERSION = "0.1.0"


def build_summary_artifacts(
    repo_name: str,
    raw_root: Path,
    parsed_root: Path,
    graph_root: Path,
) -> Dict[str, object]:
    manifest = load_json(raw_root / repo_name / "manifest.json")
    repo_map = load_json(raw_root / repo_name / "repo_map.json")
    symbols = load_json(parsed_root / repo_name / "symbols.json")
    graph = load_json(graph_root / repo_name / "graph.json")

    symbol_records = list(symbols.get("symbols", []))
    symbols_by_path: Dict[str, List[Dict[str, object]]] = defaultdict(list)
    for symbol in symbol_records:
        symbols_by_path[symbol["path"]].append(symbol)

    incoming_counts, outgoing_counts = edge_counts(graph)
    project_summary = build_project_summary(repo_name, manifest, symbols, graph)
    directory_summaries = build_directory_summaries(repo_map, symbols)
    file_summaries = build_file_summaries(symbols, symbols_by_path)
    symbol_summaries = build_symbol_summaries(symbol_records, incoming_counts, outgoing_counts)

    return {
        "schema_version": SCHEMA_VERSION,
        "repo": repo_name,
        "generated_at": timestamp_now(),
        "project": project_summary,
        "directories": directory_summaries,
        "files": file_summaries,
        "symbols": symbol_summaries,
        "summary": {
            "directories": len(directory_summaries),
            "files": len(file_summaries),
            "symbols": len(symbol_summaries),
        },
    }


def write_summary_artifacts(output_root: Path, repo_name: str, payload: Dict[str, object]) -> None:
    repo_output = output_root / repo_name
    repo_output.mkdir(parents=True, exist_ok=True)

    for filename, value in (
        ("project.json", payload["project"]),
        ("directories.json", payload["directories"]),
        ("files.json", payload["files"]),
        ("symbols.json", payload["symbols"]),
        ("summary_manifest.json", {
            "schema_version": payload["schema_version"],
            "repo": payload["repo"],
            "generated_at": payload["generated_at"],
            "summary": payload["summary"],
        }),
    ):
        with (repo_output / filename).open("w", encoding="utf-8") as handle:
            json.dump(value, handle, indent=2, sort_keys=False)
            handle.write("\n")


def load_summary_artifacts(summary_root: Path, repo_name: str) -> Dict[str, object]:
    repo_root = summary_root / repo_name
    return {
        "project": load_json(repo_root / "project.json"),
        "directories": load_json(repo_root / "directories.json"),
        "files": load_json(repo_root / "files.json"),
        "symbols": load_json(repo_root / "symbols.json"),
        "manifest": load_json(repo_root / "summary_manifest.json"),
    }


def build_project_summary(
    repo_name: str,
    manifest: Dict[str, object],
    symbols: Dict[str, object],
    graph: Dict[str, object],
) -> Dict[str, object]:
    focus = infer_repo_focus(repo_name)
    source_roots = list(manifest.get("parser_relevant_source_roots", []))
    language_mix = [f"{item['language']}:{item['files']}" for item in manifest.get("language_mix", [])[:5]]
    kind_counts = symbols.get("summary", {}).get("kind_counts", [])
    top_kinds = [f"{item['kind']}:{item['count']}" for item in kind_counts[:6]]
    summary = (
        f"{repo_name} is indexed as {focus}. "
        f"The current analysis slice covers {symbols['summary']['rust_files']} Rust files, "
        f"{symbols['summary']['symbols']} symbols, {symbols['summary']['imports']} imports, "
        f"{symbols['summary'].get('statements', 0)} statements, "
        f"and {graph['summary']['edges']} graph edges. "
        f"Parser-relevant source roots: {', '.join(source_roots) or 'none detected'}."
    )
    return {
        "repo": repo_name,
        "focus": focus,
        "analysis_surfaces": list(manifest.get("module_graph_seeds", {}).get("analysis_surfaces", [])),
        "parser_relevant_source_roots": source_roots,
        "build_commands": list(manifest.get("build_commands", [])),
        "test_commands": list(manifest.get("test_commands", [])),
        "language_mix": language_mix,
        "top_symbol_kinds": top_kinds,
        "summary": summary,
    }


def build_directory_summaries(repo_map: Dict[str, object], symbols: Dict[str, object]) -> List[Dict[str, object]]:
    rollups: Dict[str, Dict[str, object]] = defaultdict(
        lambda: {
            "files": 0,
            "rust_files": 0,
            "symbols": 0,
            "statements": 0,
            "public_symbols": 0,
            "top_symbol_kinds": Counter(),
        }
    )
    for file_record in repo_map.get("files", []):
        for prefix in directory_prefixes(file_record["path"]):
            rollups[prefix]["files"] += 1
            if file_record.get("language") == "Rust":
                rollups[prefix]["rust_files"] += 1

    for symbol in symbols.get("symbols", []):
        for prefix in directory_prefixes(symbol["path"]):
            rollups[prefix]["symbols"] += 1
            if str(symbol.get("visibility") or "").startswith("pub"):
                rollups[prefix]["public_symbols"] += 1
            rollups[prefix]["top_symbol_kinds"][symbol["kind"]] += 1

    for statement in symbols.get("statements", []):
        for prefix in directory_prefixes(statement["path"]):
            rollups[prefix]["statements"] += 1

    summaries = []
    for directory in repo_map.get("directories", []):
        path = directory["path"]
        rollup = rollups.get(path, {})
        top_kinds = [kind for kind, _count in rollup.get("top_symbol_kinds", Counter()).most_common(4)]
        tags = path_tags(path)
        summaries.append(
            {
                "path": path,
                "depth": directory["depth"],
                "files": rollup.get("files", 0),
                "rust_files": rollup.get("rust_files", 0),
                "symbols": rollup.get("symbols", 0),
                "statements": rollup.get("statements", 0),
                "public_symbols": rollup.get("public_symbols", 0),
                "top_symbol_kinds": top_kinds,
                "tags": tags,
                "summary": (
                    f"{path} contains {rollup.get('files', 0)} files, "
                    f"{rollup.get('rust_files', 0)} Rust files, {rollup.get('symbols', 0)} indexed symbols, "
                    f"and {rollup.get('statements', 0)} statements."
                ),
            }
        )
    return summaries


def build_file_summaries(
    symbols: Dict[str, object],
    symbols_by_path: Dict[str, List[Dict[str, object]]],
) -> List[Dict[str, object]]:
    files = []
    file_records = {item["path"]: item for item in symbols.get("files", [])}
    statement_counts = Counter(statement["path"] for statement in symbols.get("statements", []))
    for path, file_record in sorted(file_records.items()):
        file_symbols = symbols_by_path.get(path, [])
        public_symbols = [symbol["qualified_name"] for symbol in file_symbols if str(symbol.get("visibility") or "").startswith("pub")]
        top_symbols = [symbol["qualified_name"] for symbol in file_symbols[:6]]
        tags = path_tags(path)
        files.append(
            {
                "path": path,
                "crate": file_record.get("crate"),
                "module_path": file_record.get("module_path"),
                "language": file_record.get("language"),
                "symbols": len(file_symbols),
                "imports": file_record.get("imports", 0),
                "statements": statement_counts.get(path, 0),
                "public_symbols": public_symbols[:8],
                "top_symbols": top_symbols,
                "tags": tags,
                "summary": (
                    f"{path} defines {len(file_symbols)} symbols and {statement_counts.get(path, 0)} statements "
                    f"in crate {file_record.get('crate')}. "
                    f"Top symbols: {', '.join(top_symbols[:3]) or 'none'}."
                ),
            }
        )
    return files


def build_symbol_summaries(
    symbol_records: Iterable[Dict[str, object]],
    incoming_counts: Dict[str, Counter],
    outgoing_counts: Dict[str, Counter],
) -> List[Dict[str, object]]:
    summaries = []
    for symbol in symbol_records:
        incoming = incoming_counts.get(symbol["symbol_id"], Counter())
        outgoing = outgoing_counts.get(symbol["symbol_id"], Counter())
        summaries.append(
            {
                "symbol_id": symbol["symbol_id"],
                "path": symbol["path"],
                "kind": symbol["kind"],
                "name": symbol["name"],
                "qualified_name": symbol["qualified_name"],
                "visibility": symbol["visibility"],
                "container_qualified_name": symbol["container_qualified_name"],
                "incoming_edges": dict(sorted(incoming.items())),
                "outgoing_edges": dict(sorted(outgoing.items())),
                "summary": (
                    f"{symbol['kind']} {symbol['qualified_name']} is defined in {symbol['path']}. "
                    f"Incoming edges: {format_edge_counts(incoming)}. "
                    f"Outgoing edges: {format_edge_counts(outgoing)}."
                ),
            }
        )
    return summaries


def edge_counts(graph: Dict[str, object]) -> Tuple[Dict[str, Counter], Dict[str, Counter]]:
    incoming: Dict[str, Counter] = defaultdict(Counter)
    outgoing: Dict[str, Counter] = defaultdict(Counter)
    for edge in graph.get("edges", []):
        incoming[edge["to"]][edge["type"]] += 1
        outgoing[edge["from"]][edge["type"]] += 1
    return incoming, outgoing


def format_edge_counts(counts: Counter) -> str:
    if not counts:
        return "none"
    return ", ".join(f"{edge_type}:{count}" for edge_type, count in sorted(counts.items()))


def directory_prefixes(path: str) -> List[str]:
    parts = PurePosixPath(path).parts[:-1]
    prefixes = ["."]
    current: List[str] = []
    for part in parts:
        current.append(part)
        prefixes.append("/".join(current))
    return prefixes


def path_tags(path: str) -> List[str]:
    tags = []
    parts = [part.lower() for part in PurePosixPath(path).parts]
    for keyword in ("parser", "parsers", "datasource", "datasources", "decoder", "decoders", "runtime", "handler", "handlers", "source", "sources", "example", "examples", "test", "tests"):
        if keyword in parts:
            tags.append(keyword)
    return sorted(dict.fromkeys(tags))


def infer_repo_focus(repo_name: str) -> str:
    if repo_name == "carbon":
        return "a Rust-first Solana indexing workspace centered on datasources, decoders, and processing pipelines"
    if repo_name == "yellowstone-vixen":
        return "a Rust-first Solana parsing/runtime workspace centered on runtime handlers, parsers, and sources"
    return "a parser-first repository analysis target"


def load_json(path: Path) -> Dict[str, object]:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)
