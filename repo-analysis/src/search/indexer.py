from __future__ import annotations

import json
import os
import sqlite3
import time
from collections import Counter, defaultdict
from pathlib import Path, PurePosixPath
from typing import Callable, Dict, Iterable, List, Optional, Sequence

from common.native_tool import build_bm25_index, native_worker_available, query_bm25_index
from common.query_manifest import update_query_manifest
from common.telemetry import trace_operation
from symbols.indexer import stable_id, timestamp_now
from symbols.persistence import load_symbol_index


SCHEMA_VERSION = "0.3.0"
AGENT_CACHE_SCHEMA_VERSION = "0.1.0"
TEXT_EXTENSIONS = {
    ".c",
    ".cc",
    ".cpp",
    ".css",
    ".go",
    ".h",
    ".html",
    ".java",
    ".js",
    ".json",
    ".jsx",
    ".proto",
    ".py",
    ".rs",
    ".sh",
    ".sql",
    ".toml",
    ".ts",
    ".tsx",
    ".txt",
    ".yaml",
    ".yml",
}
MAX_INDEXED_FILE_BYTES = 256_000


def build_search_index(
    repo_name: str,
    repo_root: Path,
    raw_root: Path,
    parsed_root: Path,
    output_root: Path,
    *,
    emit_json: bool = False,
    emit_sqlite: bool = False,
    progress_callback: Callable[[Dict[str, object]], None] | None = None,
) -> Dict[str, object]:
    started = time.perf_counter()

    def emit(event: str, **extra: object) -> None:
        if progress_callback is None:
            return
        progress_callback(
            {
                "event": event,
                "repo": repo_name,
                "elapsed_ms": round((time.perf_counter() - started) * 1000, 3),
                **extra,
            }
        )

    emit("build_started")
    manifest = load_json(raw_root / repo_name / "manifest.json")
    emit("loaded_manifest")
    repo_map = load_json(raw_root / repo_name / "repo_map.json")
    emit(
        "loaded_repo_map",
        files=len(repo_map.get("files", [])),
        directories=len(repo_map.get("directories", [])),
    )
    symbols = load_symbol_index(parsed_root, repo_name)
    emit(
        "loaded_symbols",
        parsed_files=len(symbols.get("files", [])),
        symbols=len(symbols.get("symbols", [])),
        statements=len(symbols.get("statements", [])),
    )

    emit("building_documents")
    documents = list(build_documents(repo_name, repo_root, manifest, repo_map, symbols))
    repo_output = output_root / repo_name
    repo_output.mkdir(parents=True, exist_ok=True)
    emit("documents_built", documents=len(documents))

    agent_cache = build_agent_cache(repo_name, documents)
    sqlite_path = repo_output / "search.sqlite3"
    if emit_sqlite:
        if sqlite_path.exists():
            sqlite_path.unlink()
        emit("writing_sqlite")
        write_search_database(sqlite_path, documents, agent_cache)
    else:
        remove_file_if_exists(sqlite_path)

    documents_path = repo_output / "documents.jsonl"
    emit("writing_documents_jsonl")
    write_documents_jsonl(documents_path, documents)
    if emit_json:
        emit("writing_agent_cache", entries=agent_cache["summary"]["entries"])
        write_json(repo_output / "agent_cache.json", agent_cache)
    else:
        remove_file_if_exists(repo_output / "agent_cache.json")

    bm25_artifact = {
        "available": False,
        "built": False,
    }
    tantivy_dir = repo_output / "tantivy"
    if native_worker_available():
        emit("building_bm25")
        try:
            bm25_artifact = build_bm25_index(documents_path, tantivy_dir)
            bm25_artifact["available"] = True
            bm25_artifact["built"] = True
            emit("bm25_built", built=True)
        except Exception as exc:  # pragma: no cover - defensive fallback
            bm25_artifact = {
                "available": True,
                "built": False,
                "reason": str(exc),
            }
            emit("bm25_built", built=False, reason=str(exc))
    else:
        emit("bm25_skipped", reason="native_worker_unavailable")

    counts = Counter(document["kind"] for document in documents)
    payload = {
        "schema_version": SCHEMA_VERSION,
        "repo": repo_name,
        "generated_at": timestamp_now(),
        "artifacts": {
            "sqlite": "search.sqlite3" if emit_sqlite else None,
            "documents_jsonl": "documents.jsonl",
            "agent_cache": "agent_cache.json" if emit_json else None,
            "tantivy": "tantivy" if bm25_artifact.get("built") else None,
        },
        "bm25": bm25_artifact,
        "summary": {
            "documents": len(documents),
            "document_kind_counts": [
                {
                    "kind": kind,
                    "count": count,
                }
                for kind, count in sorted(counts.items())
            ],
        },
    }
    with (repo_output / "search_manifest.json").open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, sort_keys=False)
        handle.write("\n")
    emit("writing_query_manifest")
    update_query_manifest(
        parsed_root,
        repo_name,
        artifacts={
            "search_sqlite": "data/search/{repo}/search.sqlite3".format(repo=repo_name) if emit_sqlite else None,
            "search_documents_jsonl": "data/search/{repo}/documents.jsonl".format(repo=repo_name),
            "search_agent_cache": "data/search/{repo}/agent_cache.json".format(repo=repo_name) if emit_json else None,
            "search_tantivy": "data/search/{repo}/tantivy".format(repo=repo_name) if bm25_artifact.get("built") else None,
        },
        features={
            "bm25_default": bool(bm25_artifact.get("built")),
            "agent_cache_sqlite": True,
        },
        build={
            "bm25": bm25_artifact,
            "search_json_exports": emit_json,
            "search_sqlite_compat": emit_sqlite,
        },
    )
    emit("build_completed", documents=len(documents), bm25_built=bool(bm25_artifact.get("built")))
    return payload


def search_documents(
    search_root: Path,
    repo_name: str,
    query: str,
    *,
    limit: int = 10,
    kinds: Sequence[str] = (),
) -> List[Dict[str, object]]:
    with trace_operation("search_documents"):
        sqlite_path = search_root / repo_name / "search.sqlite3"
        tantivy_dir = search_root / repo_name / "tantivy"
        tokens = tokenize(query)
        if not tokens or (not sqlite_path.exists() and not tantivy_dir.exists()):
            return []

        if tantivy_dir.exists():
            try:
                results = query_bm25_index(tantivy_dir, " ".join(tokens), limit=limit, kinds=kinds)
                if results:
                    return results
            except Exception:
                pass

        if os.environ.get("CAXEN_ENABLE_SQLITE_HOTPATH_READS") != "1":
            return []

        with sqlite3.connect(sqlite_path) as connection:
            connection.row_factory = sqlite3.Row
            results = query_documents(connection, build_and_query(tokens), limit, kinds)
            if not results and len(tokens) > 1:
                results = query_documents(connection, build_or_query(tokens), limit, kinds)
            return results


def search_documents_scoped(
    search_root: Path,
    repo_name: str,
    query: str,
    *,
    limit: int = 10,
    kinds: Sequence[str] = (),
    path_prefix: Optional[str] = None,
) -> List[Dict[str, object]]:
    results = search_documents(search_root, repo_name, query, limit=max(limit * 3, limit), kinds=kinds)
    if path_prefix:
        normalized_prefix = path_prefix.rstrip("/")
        results = [item for item in results if str(item.get("path") or "").startswith(normalized_prefix)]
    return results[:limit]


def list_documents(
    search_root: Path,
    repo_name: str,
    *,
    limit: int = 20,
    kinds: Sequence[str] = (),
    path_prefix: Optional[str] = None,
) -> List[Dict[str, object]]:
    sqlite_path = search_root / repo_name / "search.sqlite3"
    if not sqlite_path.exists():
        return []

    clauses = []
    params: List[object] = []
    if kinds:
        clauses.append(f"kind IN ({','.join('?' for _ in kinds)})")
        params.extend(kinds)
    if path_prefix:
        clauses.append("path LIKE ?")
        params.append(f"{path_prefix}%")

    where_clause = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    sql = (
        "SELECT doc_id, kind, repo, path, name, qualified_name, symbol_id, title, preview, metadata_json "
        "FROM documents "
        f"{where_clause} "
        "ORDER BY kind, COALESCE(path, ''), COALESCE(qualified_name, ''), COALESCE(name, '') "
        "LIMIT ?"
    )
    params.append(limit)

    with sqlite3.connect(sqlite_path) as connection:
        connection.row_factory = sqlite3.Row
        rows = connection.execute(sql, params).fetchall()
        return [row_to_result(row, score=0.0) for row in rows]


def find_files(
    search_root: Path,
    repo_name: str,
    path_pattern: str,
    *,
    limit: int = 20,
) -> List[Dict[str, object]]:
    sqlite_path = search_root / repo_name / "search.sqlite3"
    if not sqlite_path.exists():
        return []

    like_pattern = path_pattern.replace("*", "%")
    if "%" not in like_pattern:
        like_pattern = f"%{like_pattern}%"

    with sqlite3.connect(sqlite_path) as connection:
        connection.row_factory = sqlite3.Row
        rows = connection.execute(
            """
            SELECT doc_id, kind, repo, path, name, qualified_name, symbol_id, title, preview, metadata_json
            FROM documents
            WHERE kind IN ('directory', 'file')
              AND path LIKE ?
            ORDER BY kind, LENGTH(COALESCE(path, '')), COALESCE(path, '')
            LIMIT ?
            """,
            [like_pattern, limit],
        ).fetchall()
    return [row_to_result(row, score=0.0) for row in rows]


def lookup_symbol_documents(
    search_root: Path,
    repo_name: str,
    symbol_id: str,
    *,
    kinds: Sequence[str] = (),
    limit: int = 20,
) -> List[Dict[str, object]]:
    sqlite_path = search_root / repo_name / "search.sqlite3"
    if not sqlite_path.exists():
        return []

    clauses = ["symbol_id = ?"]
    params: List[object] = [symbol_id]
    if kinds:
        clauses.append(f"kind IN ({','.join('?' for _ in kinds)})")
        params.extend(kinds)
    params.append(limit)

    with sqlite3.connect(sqlite_path) as connection:
        connection.row_factory = sqlite3.Row
        rows = connection.execute(
            (
                "SELECT doc_id, kind, repo, path, name, qualified_name, symbol_id, title, preview, metadata_json "
                "FROM documents "
                f"WHERE {' AND '.join(clauses)} "
                "ORDER BY kind, COALESCE(path, ''), COALESCE(name, ''), COALESCE(qualified_name, '') "
                "LIMIT ?"
            ),
            params,
        ).fetchall()
    return [row_to_result(row, score=0.0) for row in rows]


def load_search_manifest(search_root: Path, repo_name: str) -> Dict[str, object]:
    return load_json(search_root / repo_name / "search_manifest.json")


def load_agent_cache(search_root: Path, repo_name: str) -> Dict[str, object]:
    sqlite_path = search_root / repo_name / "search.sqlite3"
    with sqlite3.connect(sqlite_path) as connection:
        connection.row_factory = sqlite3.Row
        metadata_rows = dict(connection.execute("SELECT key, value FROM metadata").fetchall())
        rows = connection.execute(
            """
            SELECT doc_id, kind, path, name, qualified_name, symbol_id, title, preview, metadata_json, search_text
            FROM agent_cache_entries
            ORDER BY kind, COALESCE(path, ''), COALESCE(qualified_name, ''), COALESCE(name, '')
            """
        ).fetchall()
    entries = [
        {
            "doc_id": row["doc_id"],
            "kind": row["kind"],
            "path": row["path"],
            "name": row["name"],
            "qualified_name": row["qualified_name"],
            "symbol_id": row["symbol_id"],
            "title": row["title"],
            "preview": row["preview"],
            "metadata": json.loads(row["metadata_json"] or "{}"),
            "search_text": row["search_text"],
        }
        for row in rows
    ]
    return {
        "schema_version": AGENT_CACHE_SCHEMA_VERSION,
        "repo": repo_name,
        "generated_at": metadata_rows.get("generated_at"),
        "summary": {
            "entries": len(entries),
            "kinds": dict(sorted(Counter(entry["kind"] for entry in entries).items())),
        },
        "entries": entries,
    }


def build_documents(
    repo_name: str,
    repo_root: Path,
    manifest: Dict[str, object],
    repo_map: Dict[str, object],
    symbols: Dict[str, object],
) -> Iterable[Dict[str, object]]:
    files_by_path = {item["path"]: item for item in repo_map.get("files", [])}
    parsed_files_by_path = {item["path"]: item for item in symbols.get("files", [])}
    symbol_counts_by_path = Counter(item["path"] for item in symbols.get("symbols", []))
    package_rollups = build_package_rollups(symbols)
    directory_rollups = build_directory_rollups(repo_map, symbols)

    yield {
        "doc_id": stable_id("doc", repo_name, "repo"),
        "kind": "repo",
        "repo": repo_name,
        "path": None,
        "name": repo_name,
        "qualified_name": None,
        "symbol_id": None,
        "title": repo_name,
        "preview": f"Repository overview for {repo_name}",
        "content": " ".join(
            [
                repo_name,
                " ".join(str(item) for item in manifest.get("notes", [])),
                " ".join(str(item) for item in manifest.get("build_commands", [])),
                " ".join(str(item) for item in manifest.get("test_commands", [])),
                " ".join(str(item) for item in manifest.get("parser_relevant_source_roots", [])),
                " ".join(str(item["language"]) for item in manifest.get("language_mix", [])),
            ]
        ).strip(),
        "metadata": {
            "analysis_surfaces": list(manifest.get("module_graph_seeds", {}).get("analysis_surfaces", [])),
            "parser_relevant_source_roots": list(manifest.get("parser_relevant_source_roots", [])),
        },
    }

    for directory in repo_map.get("directories", []):
        path = directory["path"]
        rollup = directory_rollups.get(path, {})
        child_files = rollup.get("sample_files", [])
        yield {
            "doc_id": stable_id("doc", repo_name, "directory", path),
            "kind": "directory",
            "repo": repo_name,
            "path": path,
            "name": PurePosixPath(path).name if path != "." else repo_name,
            "qualified_name": None,
            "symbol_id": None,
            "title": path,
            "preview": summarize_preview(
                f"Directory {path} with {rollup.get('files', 0)} files and {rollup.get('symbols', 0)} symbols."
            ),
            "content": " ".join(
                [
                    path,
                    " ".join(path_tags(path)),
                    " ".join(child_files),
                ]
            ).strip(),
            "metadata": {
                "depth": directory["depth"],
                "files": rollup.get("files", 0),
                "symbols": rollup.get("symbols", 0),
                "tags": path_tags(path),
            },
        }

    for package_name, rollup in sorted(package_rollups.items()):
        yield {
            "doc_id": stable_id("doc", repo_name, "package", package_name),
            "kind": "package",
            "repo": repo_name,
            "path": None,
            "name": package_name,
            "qualified_name": package_name,
            "symbol_id": None,
            "title": package_name,
            "preview": f"Package overview for {package_name}",
            "content": " ".join(
                item
                for item in [
                    package_name,
                    " ".join(rollup.get("module_paths", [])),
                    " ".join(rollup.get("top_symbol_kinds", [])),
                    " ".join(rollup.get("sample_files", [])),
                ]
                if item
            ),
            "metadata": {
                "files": rollup.get("files", 0),
                "symbols": rollup.get("symbols", 0),
                "module_paths": rollup.get("module_paths", []),
                "top_symbol_kinds": rollup.get("top_symbol_kinds", []),
            },
        }

    for path, file_record in sorted(files_by_path.items()):
        parsed_file = parsed_files_by_path.get(path, {})
        source_text = read_indexable_file(repo_root / path, file_record)
        yield {
            "doc_id": stable_id("doc", repo_name, "file", path),
            "kind": "file",
            "repo": repo_name,
            "path": path,
            "name": PurePosixPath(path).name,
            "qualified_name": None,
            "symbol_id": None,
            "title": path,
            "preview": summarize_preview(source_text or path),
            "content": " ".join(
                item
                for item in [
                    path,
                    file_record.get("language"),
                    parsed_file.get("crate"),
                    parsed_file.get("module_path"),
                    parsed_file.get("primary_parser_backend"),
                    " ".join(path_tags(path)),
                    source_text,
                ]
                if item
            ),
            "metadata": {
                "language": file_record.get("language"),
                "generated": bool(file_record.get("generated")),
                "content_hash": file_record.get("content_hash"),
                "symbols": symbol_counts_by_path.get(path, 0),
                "crate": parsed_file.get("crate"),
                "package_name": parsed_file.get("package_name"),
                "module_path": parsed_file.get("module_path"),
                "primary_parser_backend": parsed_file.get("primary_parser_backend"),
                "tags": path_tags(path),
            },
        }

    for symbol in symbols.get("symbols", []):
        symbol_tags = build_symbol_tags(symbol)
        yield {
            "doc_id": stable_id("doc", repo_name, "symbol", symbol["symbol_id"]),
            "kind": "symbol",
            "repo": repo_name,
            "path": symbol["path"],
            "name": symbol["name"],
            "qualified_name": symbol["qualified_name"],
            "symbol_id": symbol["symbol_id"],
            "title": symbol["qualified_name"],
            "preview": summarize_preview(symbol["signature"] or symbol["qualified_name"]),
            "content": " ".join(
                item
                for item in [
                    symbol["kind"],
                    symbol["name"],
                    symbol["qualified_name"],
                    symbol.get("signature"),
                    symbol.get("docstring"),
                    symbol.get("container_qualified_name"),
                    symbol.get("impl_target"),
                    symbol.get("impl_trait"),
                    " ".join(symbol.get("super_traits", [])),
                    " ".join(item.get("target_qualified_name", "") for item in symbol.get("resolved_super_traits", [])),
                    " ".join(item.get("target_qualified_name", "") for item in symbol.get("semantic_summary", {}).get("direct_calls", [])),
                    " ".join(item.get("target_qualified_name", "") for item in symbol.get("semantic_summary", {}).get("transitive_calls", [])),
                    " ".join(item.get("target_qualified_name", "") for item in symbol.get("semantic_summary", {}).get("reads", [])),
                    " ".join(item.get("target_qualified_name", "") for item in symbol.get("semantic_summary", {}).get("writes", [])),
                    " ".join(item.get("target_qualified_name", "") for item in symbol.get("semantic_summary", {}).get("interprocedural_reads", [])),
                    " ".join(item.get("target_qualified_name", "") for item in symbol.get("semantic_summary", {}).get("interprocedural_writes", [])),
                    " ".join(item.get("target_qualified_name", "") for item in symbol.get("semantic_summary", {}).get("interprocedural_references", [])),
                    " ".join(symbol.get("attributes", [])),
                    " ".join(symbol_tags),
                ]
                if item
            ),
            "metadata": {
                "kind": symbol["kind"],
                "path": symbol["path"],
                "module_path": symbol["module_path"],
                "crate": symbol["crate"],
                "visibility": symbol["visibility"],
                "container_symbol_id": symbol["container_symbol_id"],
                "container_qualified_name": symbol["container_qualified_name"],
                "is_test": symbol["is_test"],
                "summary_id": symbol.get("summary_id"),
                "normalized_body_hash": symbol.get("normalized_body_hash"),
                "semantic_summary": symbol.get("semantic_summary", {}),
                "tags": symbol_tags,
            },
        }

        body_kind = symbol_body_kind(symbol)
        body_text = extract_symbol_chunk(repo_root, symbol)
        if body_kind and body_text:
            yield {
                "doc_id": stable_id("doc", repo_name, body_kind, symbol["symbol_id"]),
                "kind": body_kind,
                "repo": repo_name,
                "path": symbol["path"],
                "name": symbol["name"],
                "qualified_name": symbol["qualified_name"],
                "symbol_id": symbol["symbol_id"],
                "title": f"{symbol['qualified_name']} body",
                "preview": summarize_preview(body_text),
                "content": " ".join(
                    item
                    for item in [
                        symbol["kind"],
                        symbol["name"],
                        symbol["qualified_name"],
                        body_text,
                        symbol.get("docstring"),
                    ]
                    if item
                ),
                "metadata": {
                    "kind": symbol["kind"],
                    "path": symbol["path"],
                    "module_path": symbol["module_path"],
                    "crate": symbol["crate"],
                    "body_kind": body_kind,
                    "summary_id": symbol.get("summary_id"),
                    "normalized_body_hash": symbol.get("normalized_body_hash"),
                    "tags": symbol_tags,
                },
            }

        if symbol.get("docstring"):
            yield {
                "doc_id": stable_id("doc", repo_name, "doc", symbol["symbol_id"]),
                "kind": "doc",
                "repo": repo_name,
                "path": symbol["path"],
                "name": symbol["name"],
                "qualified_name": symbol["qualified_name"],
                "symbol_id": symbol["symbol_id"],
                "title": f"{symbol['qualified_name']} docs",
                "preview": summarize_preview(symbol["docstring"]),
                "content": " ".join(
                    item
                    for item in [
                        symbol["kind"],
                        symbol["name"],
                        symbol["qualified_name"],
                        symbol["docstring"],
                    ]
                    if item
                ),
                "metadata": {
                    "kind": symbol["kind"],
                    "path": symbol["path"],
                    "module_path": symbol["module_path"],
                    "crate": symbol["crate"],
                    "summary_id": symbol.get("summary_id"),
                    "tags": symbol_tags + ["doc"],
                },
            }

    for statement in symbols.get("statements", []):
        yield {
            "doc_id": stable_id("doc", repo_name, "statement", statement["statement_id"]),
            "kind": "statement",
            "repo": repo_name,
            "path": statement["path"],
            "name": f"{statement['kind']}@L{statement['span']['start_line']}",
            "qualified_name": statement["container_qualified_name"],
            "symbol_id": statement["container_symbol_id"],
            "title": f"{statement['path']}:{statement['span']['start_line']}",
            "preview": summarize_preview(statement["text"]),
            "content": " ".join(
                item
                for item in [
                    statement["kind"],
                    statement["text"],
                    statement["container_qualified_name"],
                    " ".join(path_tags(statement["path"])),
                    " ".join(target["target_qualified_name"] for target in statement.get("calls", [])),
                    " ".join(target["target_qualified_name"] for target in statement.get("reads", [])),
                    " ".join(target["target_qualified_name"] for target in statement.get("writes", [])),
                ]
                if item
            ),
            "metadata": {
                "kind": statement["kind"],
                "path": statement["path"],
                "container_symbol_id": statement["container_symbol_id"],
                "container_qualified_name": statement["container_qualified_name"],
                "line": statement["span"]["start_line"],
                "tags": path_tags(statement["path"]),
            },
        }


def build_directory_rollups(repo_map: Dict[str, object], symbols: Dict[str, object]) -> Dict[str, Dict[str, object]]:
    rollups: Dict[str, Dict[str, object]] = defaultdict(lambda: {"files": 0, "symbols": 0, "sample_files": []})
    for file_record in repo_map.get("files", []):
        for prefix in path_prefixes(file_record["path"]):
            bucket = rollups[prefix]
            bucket["files"] += 1
            if len(bucket["sample_files"]) < 12:
                bucket["sample_files"].append(PurePosixPath(file_record["path"]).name)

    for symbol in symbols.get("symbols", []):
        for prefix in path_prefixes(symbol["path"]):
            rollups[prefix]["symbols"] += 1

    return rollups


def build_package_rollups(symbols: Dict[str, object]) -> Dict[str, Dict[str, object]]:
    rollups: Dict[str, Dict[str, object]] = defaultdict(
        lambda: {
            "files": 0,
            "symbols": 0,
            "sample_files": [],
            "module_paths": [],
            "top_symbol_kinds": [],
        }
    )
    top_symbol_kinds: Dict[str, Counter] = defaultdict(Counter)
    for file_record in symbols.get("files", []):
        package_name = str(file_record.get("package_name") or file_record.get("crate") or "")
        if not package_name:
            continue
        bucket = rollups[package_name]
        bucket["files"] += 1
        if len(bucket["sample_files"]) < 8:
            bucket["sample_files"].append(file_record["path"])
        module_path = str(file_record.get("module_path") or "")
        if module_path and module_path not in bucket["module_paths"]:
            bucket["module_paths"].append(module_path)

    for symbol in symbols.get("symbols", []):
        package_name = str(symbol.get("package_name") or symbol.get("crate") or "")
        if not package_name:
            continue
        rollups[package_name]["symbols"] += 1
        top_symbol_kinds[package_name][symbol["kind"]] += 1

    for package_name, counts in top_symbol_kinds.items():
        rollups[package_name]["top_symbol_kinds"] = [kind for kind, _count in counts.most_common(5)]

    return rollups


def path_prefixes(path: str) -> List[str]:
    parts = PurePosixPath(path).parts
    prefixes = ["."]
    current: List[str] = []
    for part in parts[:-1]:
        current.append(part)
        prefixes.append("/".join(current))
    return prefixes


def build_symbol_tags(symbol: Dict[str, object]) -> List[str]:
    tags = path_tags(symbol["path"])
    tags.append(symbol["kind"])
    if symbol.get("is_test"):
        tags.append("test")
    semantic_summary = symbol.get("semantic_summary", {})
    if semantic_summary.get("direct_calls"):
        tags.append("calls")
    if semantic_summary.get("reads"):
        tags.append("reads")
    if semantic_summary.get("writes"):
        tags.append("writes")
    if symbol.get("impl_trait"):
        tags.append("impl")
    if symbol.get("super_traits"):
        tags.append("trait")
    return list(dict.fromkeys(tag for tag in tags if tag))


def symbol_body_kind(symbol: Dict[str, object]) -> str | None:
    kind = str(symbol.get("kind") or "")
    if kind in {"fn", "function", "method"}:
        return "function_body"
    if kind in {"struct", "enum", "trait", "impl", "type"}:
        return "type_body"
    return None


def extract_symbol_chunk(repo_root: Path, symbol: Dict[str, object]) -> str:
    path = repo_root / str(symbol["path"])
    try:
        lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()
    except OSError:
        return ""
    span = symbol.get("span") or {}
    start_line = max(int(span.get("start_line") or 1), 1)
    end_line = max(int(span.get("end_line") or start_line), start_line)
    if start_line > len(lines):
        return ""
    selected = lines[start_line - 1 : min(end_line, len(lines))]
    return "\n".join(selected).strip()


def path_tags(path: str) -> List[str]:
    parts = [part.lower() for part in PurePosixPath(path).parts]
    tags = []
    for keyword in ("parser", "parsers", "datasource", "datasources", "decoder", "decoders", "runtime", "handler", "handlers", "source", "sources", "metric", "metrics", "example", "examples", "test", "tests"):
        if keyword in parts:
            tags.append(keyword)
    return sorted(dict.fromkeys(tags))


def read_indexable_file(path: Path, file_record: Dict[str, object]) -> str:
    if file_record.get("generated"):
        return ""
    if path.suffix.lower() not in TEXT_EXTENSIONS:
        return ""
    try:
        size = path.stat().st_size
    except OSError:
        return ""
    if size > MAX_INDEXED_FILE_BYTES:
        return ""
    try:
        return path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return ""


def summarize_preview(value: str, limit: int = 180) -> str:
    collapsed = " ".join(value.split())
    if len(collapsed) <= limit:
        return collapsed
    return collapsed[: limit - 3].rstrip() + "..."


def write_json(path: Path, payload: Dict[str, object]) -> None:
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, sort_keys=False)
        handle.write("\n")


def remove_file_if_exists(path: Path) -> None:
    try:
        path.unlink()
    except FileNotFoundError:
        return


def build_agent_cache(repo_name: str, documents: Sequence[Dict[str, object]]) -> Dict[str, object]:
    entries = []
    for document in documents:
        kind = str(document.get("kind") or "")
        metadata = dict(document.get("metadata") or {})
        if kind not in {"repo", "package", "directory", "file", "symbol", "function_body", "type_body", "doc"}:
            continue
        if kind in {"symbol", "function_body", "type_body", "doc"} and not include_agent_symbol(document):
            continue
        entries.append(build_agent_cache_entry(document, metadata))

    return {
        "schema_version": AGENT_CACHE_SCHEMA_VERSION,
        "repo": repo_name,
        "generated_at": timestamp_now(),
        "summary": {
            "entries": len(entries),
            "kinds": dict(sorted(Counter(entry["kind"] for entry in entries).items())),
        },
        "entries": entries,
    }


def include_agent_symbol(document: Dict[str, object]) -> bool:
    metadata = dict(document.get("metadata") or {})
    symbol_kind = str(metadata.get("kind") or document.get("kind") or "")
    visibility = str(metadata.get("visibility") or "")
    if symbol_kind in {"local", "field", "variant"}:
        return False
    if symbol_kind == "method" and not visibility.startswith("pub") and visibility != "public":
        return False
    return True


def build_agent_cache_entry(document: Dict[str, object], metadata: Dict[str, object]) -> Dict[str, object]:
    text_parts = [
        str(document.get("kind") or ""),
        str(document.get("path") or ""),
        str(document.get("name") or ""),
        str(document.get("qualified_name") or ""),
        str(document.get("title") or ""),
        str(document.get("preview") or ""),
        str(metadata.get("module_path") or ""),
        str(metadata.get("package_name") or ""),
        str(metadata.get("crate") or ""),
        " ".join(str(item) for item in metadata.get("tags", []) or ()),
    ]
    return {
        "doc_id": document.get("doc_id"),
        "kind": document.get("kind"),
        "path": document.get("path"),
        "name": document.get("name"),
        "qualified_name": document.get("qualified_name"),
        "symbol_id": document.get("symbol_id"),
        "title": document.get("title"),
        "preview": document.get("preview"),
        "metadata": {
            "kind": metadata.get("kind"),
            "crate": metadata.get("crate"),
            "package_name": metadata.get("package_name"),
            "module_path": metadata.get("module_path"),
            "tags": list(metadata.get("tags", []) or ()),
            "visibility": metadata.get("visibility"),
        },
        "search_text": " ".join(part for part in text_parts if part).lower(),
    }


def write_documents_jsonl(path: Path, documents: Sequence[Dict[str, object]]) -> None:
    with path.open("w", encoding="utf-8") as handle:
        for document in documents:
            json.dump(document, handle, sort_keys=False)
            handle.write("\n")


def tokenize(query: str) -> List[str]:
    tokens = []
    for raw_token in query.replace("::", " ").replace("/", " ").replace("-", " ").replace(".", " ").split():
        normalized = "".join(char for char in raw_token.lower() if char.isalnum() or char == "_")
        if normalized:
            tokens.append(normalized)
    return tokens


def build_and_query(tokens: Sequence[str]) -> str:
    return " ".join(f"{token}*" for token in tokens)


def build_or_query(tokens: Sequence[str]) -> str:
    return " OR ".join(f"{token}*" for token in tokens)


def query_documents(
    connection: sqlite3.Connection,
    fts_query: str,
    limit: int,
    kinds: Sequence[str],
) -> List[Dict[str, object]]:
    where_clauses = ["lexical_documents MATCH ?"]
    params: List[object] = [fts_query]
    if kinds:
        where_clauses.append(f"documents.kind IN ({','.join('?' for _ in kinds)})")
        params.extend(kinds)

    sql = (
        "SELECT documents.doc_id, documents.kind, documents.repo, documents.path, documents.name, "
        "documents.qualified_name, documents.symbol_id, documents.title, documents.preview, "
        "documents.metadata_json, -bm25(lexical_documents) AS score "
        "FROM lexical_documents "
        "JOIN documents ON documents.doc_id = lexical_documents.doc_id "
        f"WHERE {' AND '.join(where_clauses)} "
        "ORDER BY score DESC, documents.kind, COALESCE(documents.path, ''), COALESCE(documents.qualified_name, '') "
        "LIMIT ?"
    )
    params.append(limit)
    rows = connection.execute(sql, params).fetchall()
    return [row_to_result(row, score=row["score"]) for row in rows]


def row_to_result(row: sqlite3.Row, *, score: float) -> Dict[str, object]:
    return {
        "doc_id": row["doc_id"],
        "kind": row["kind"],
        "repo": row["repo"],
        "path": row["path"],
        "name": row["name"],
        "qualified_name": row["qualified_name"],
        "symbol_id": row["symbol_id"],
        "title": row["title"],
        "preview": row["preview"],
        "score": round(float(score), 6),
        "metadata": json.loads(row["metadata_json"]),
    }


def write_search_database(
    sqlite_path: Path,
    documents: Sequence[Dict[str, object]],
    agent_cache: Dict[str, object],
) -> None:
    with sqlite3.connect(sqlite_path) as connection:
        connection.execute("PRAGMA journal_mode = WAL")
        connection.execute("CREATE TABLE metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL)")
        connection.execute(
            """
            CREATE TABLE documents (
                doc_id TEXT PRIMARY KEY,
                kind TEXT NOT NULL,
                repo TEXT NOT NULL,
                path TEXT,
                name TEXT,
                qualified_name TEXT,
                symbol_id TEXT,
                title TEXT NOT NULL,
                preview TEXT NOT NULL,
                metadata_json TEXT NOT NULL
            )
            """
        )
        connection.execute(
            """
            CREATE VIRTUAL TABLE lexical_documents USING fts5(
                doc_id UNINDEXED,
                title,
                content,
                kind,
                path,
                name,
                qualified_name,
                tokenize = 'unicode61'
            )
            """
        )
        connection.execute("CREATE INDEX idx_documents_kind ON documents(kind)")
        connection.execute("CREATE INDEX idx_documents_path ON documents(path)")
        connection.execute("CREATE INDEX idx_documents_symbol_id ON documents(symbol_id)")
        connection.execute(
            """
            CREATE TABLE agent_cache_entries (
                doc_id TEXT PRIMARY KEY,
                kind TEXT NOT NULL,
                path TEXT,
                name TEXT,
                qualified_name TEXT,
                symbol_id TEXT,
                title TEXT,
                preview TEXT,
                metadata_json TEXT NOT NULL,
                search_text TEXT NOT NULL
            )
            """
        )
        connection.execute("CREATE INDEX idx_agent_cache_kind ON agent_cache_entries(kind)")
        connection.execute("CREATE INDEX idx_agent_cache_path ON agent_cache_entries(path)")
        connection.execute("CREATE INDEX idx_agent_cache_symbol_id ON agent_cache_entries(symbol_id)")

        connection.executemany(
            "INSERT INTO metadata(key, value) VALUES(?, ?)",
            [
                ("schema_version", SCHEMA_VERSION),
                ("generated_at", timestamp_now()),
                ("documents", str(len(documents))),
                ("agent_cache_entries", str(int(agent_cache.get("summary", {}).get("entries") or 0))),
            ],
        )
        connection.executemany(
            """
            INSERT INTO documents(doc_id, kind, repo, path, name, qualified_name, symbol_id, title, preview, metadata_json)
            VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    document["doc_id"],
                    document["kind"],
                    document["repo"],
                    document["path"],
                    document["name"],
                    document["qualified_name"],
                    document["symbol_id"],
                    document["title"],
                    document["preview"],
                    json.dumps(document["metadata"], sort_keys=True),
                )
                for document in documents
            ],
        )
        connection.executemany(
            """
            INSERT INTO lexical_documents(doc_id, title, content, kind, path, name, qualified_name)
            VALUES(?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    document["doc_id"],
                    document["title"],
                    document["content"],
                    document["kind"],
                    document["path"],
                    document["name"],
                    document["qualified_name"],
                )
                for document in documents
            ],
        )
        connection.executemany(
            """
            INSERT INTO agent_cache_entries(
                doc_id, kind, path, name, qualified_name, symbol_id, title, preview, metadata_json, search_text
            )
            VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    entry["doc_id"],
                    entry["kind"],
                    entry["path"],
                    entry["name"],
                    entry["qualified_name"],
                    entry["symbol_id"],
                    entry["title"],
                    entry["preview"],
                    json.dumps(entry["metadata"], sort_keys=True),
                    entry["search_text"],
                )
                for entry in agent_cache.get("entries", [])
            ],
        )
        connection.commit()


def load_json(path: Path) -> Dict[str, object]:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)
