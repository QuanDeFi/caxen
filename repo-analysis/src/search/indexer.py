from __future__ import annotations

import json
import sqlite3
from collections import Counter, defaultdict
from pathlib import Path, PurePosixPath
from typing import Dict, Iterable, List, Optional, Sequence

from common.native_tool import build_bm25_index, native_worker_available, query_bm25_index
from common.query_manifest import update_query_manifest
from symbols.indexer import stable_id, timestamp_now


SCHEMA_VERSION = "0.2.0"
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
    ".md",
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
) -> Dict[str, object]:
    manifest = load_json(raw_root / repo_name / "manifest.json")
    repo_map = load_json(raw_root / repo_name / "repo_map.json")
    symbols = load_json(parsed_root / repo_name / "symbols.json")

    documents = list(build_documents(repo_name, repo_root, manifest, repo_map, symbols))
    repo_output = output_root / repo_name
    repo_output.mkdir(parents=True, exist_ok=True)

    sqlite_path = repo_output / "search.sqlite3"
    if sqlite_path.exists():
        sqlite_path.unlink()
    write_search_database(sqlite_path, documents)

    documents_path = repo_output / "documents.jsonl"
    write_documents_jsonl(documents_path, documents)

    bm25_artifact = {
        "available": False,
        "built": False,
    }
    tantivy_dir = repo_output / "tantivy"
    if native_worker_available():
        try:
            bm25_artifact = build_bm25_index(documents_path, tantivy_dir)
            bm25_artifact["available"] = True
            bm25_artifact["built"] = True
        except Exception as exc:  # pragma: no cover - defensive fallback
            bm25_artifact = {
                "available": True,
                "built": False,
                "reason": str(exc),
            }

    counts = Counter(document["kind"] for document in documents)
    payload = {
        "schema_version": SCHEMA_VERSION,
        "repo": repo_name,
        "generated_at": timestamp_now(),
        "artifacts": {
            "sqlite": "search.sqlite3",
            "documents_jsonl": "documents.jsonl",
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
    update_query_manifest(
        parsed_root,
        repo_name,
        artifacts={
            "search_sqlite": "data/search/{repo}/search.sqlite3".format(repo=repo_name),
            "search_documents_jsonl": "data/search/{repo}/documents.jsonl".format(repo=repo_name),
            "search_tantivy": "data/search/{repo}/tantivy".format(repo=repo_name) if bm25_artifact.get("built") else None,
        },
        features={
            "bm25_default": bool(bm25_artifact.get("built")),
        },
        build={
            "bm25": bm25_artifact,
        },
    )
    return payload


def search_documents(
    search_root: Path,
    repo_name: str,
    query: str,
    *,
    limit: int = 10,
    kinds: Sequence[str] = (),
) -> List[Dict[str, object]]:
    sqlite_path = search_root / repo_name / "search.sqlite3"
    tantivy_dir = search_root / repo_name / "tantivy"
    tokens = tokenize(query)
    if not tokens or (not sqlite_path.exists() and not tantivy_dir.exists()):
        return []

    if tantivy_dir.exists():
        try:
            results = query_bm25_index(tantivy_dir, query, limit=limit, kinds=kinds)
            if results:
                return results
        except Exception:
            pass

    with sqlite3.connect(sqlite_path) as connection:
        connection.row_factory = sqlite3.Row
        results = query_documents(connection, build_and_query(tokens), limit, kinds)
        if not results and len(tokens) > 1:
            results = query_documents(connection, build_or_query(tokens), limit, kinds)
        return results


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


def load_search_manifest(search_root: Path, repo_name: str) -> Dict[str, object]:
    return load_json(search_root / repo_name / "search_manifest.json")


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
                "symbols": symbol_counts_by_path.get(path, 0),
                "crate": parsed_file.get("crate"),
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
                "semantic_summary": symbol.get("semantic_summary", {}),
                "tags": symbol_tags,
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


def write_search_database(sqlite_path: Path, documents: Sequence[Dict[str, object]]) -> None:
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

        connection.executemany(
            "INSERT INTO metadata(key, value) VALUES(?, ?)",
            [
                ("schema_version", SCHEMA_VERSION),
                ("generated_at", timestamp_now()),
                ("documents", str(len(documents))),
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
        connection.commit()


def load_json(path: Path) -> Dict[str, object]:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)
