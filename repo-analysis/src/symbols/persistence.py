from __future__ import annotations

import json
import sqlite3
from functools import lru_cache
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence

from common.telemetry import increment_counter, trace_operation


def write_symbol_database(output_root: Path, repo_name: str, payload: Dict[str, object]) -> None:
    repo_output = output_root / repo_name
    repo_output.mkdir(parents=True, exist_ok=True)
    target = repo_output / "symbols.sqlite3"

    if target.exists():
        target.unlink()

    connection = sqlite3.connect(target)
    try:
        cursor = connection.cursor()
        cursor.executescript(
            """
            CREATE TABLE metadata (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );

            CREATE TABLE files (
                path TEXT PRIMARY KEY,
                crate TEXT NOT NULL,
                package_name TEXT NOT NULL,
                module_path TEXT NOT NULL,
                language TEXT NOT NULL,
                symbols INTEGER NOT NULL,
                imports INTEGER NOT NULL,
                primary_parser_backend TEXT NOT NULL,
                content_hash TEXT
            );

            CREATE TABLE symbols (
                symbol_id TEXT PRIMARY KEY,
                repo TEXT NOT NULL,
                path TEXT NOT NULL,
                crate TEXT NOT NULL,
                package_name TEXT NOT NULL,
                module_path TEXT NOT NULL,
                language TEXT NOT NULL,
                kind TEXT NOT NULL,
                name TEXT NOT NULL,
                qualified_name TEXT NOT NULL,
                start_line INTEGER NOT NULL,
                start_column INTEGER NOT NULL,
                end_line INTEGER NOT NULL,
                end_column INTEGER NOT NULL,
                signature TEXT NOT NULL,
                docstring TEXT,
                visibility TEXT NOT NULL,
                container_symbol_id TEXT,
                container_qualified_name TEXT,
                statement_id TEXT,
                scope_symbol_id TEXT,
                reference_target_symbol_id TEXT,
                attributes_json TEXT NOT NULL,
                is_test INTEGER NOT NULL,
                impl_target TEXT,
                impl_trait TEXT,
                super_traits_json TEXT NOT NULL,
                resolved_impl_target_symbol_id TEXT,
                resolved_impl_target_qualified_name TEXT,
                resolved_impl_trait_symbol_id TEXT,
                resolved_impl_trait_qualified_name TEXT,
                resolved_super_traits_json TEXT NOT NULL,
                summary_id TEXT,
                normalized_body_hash TEXT,
                semantic_summary_json TEXT NOT NULL
            );

            CREATE TABLE imports (
                import_id TEXT PRIMARY KEY,
                repo TEXT NOT NULL,
                path TEXT NOT NULL,
                crate TEXT NOT NULL,
                module_path TEXT NOT NULL,
                language TEXT NOT NULL,
                visibility TEXT NOT NULL,
                signature TEXT NOT NULL,
                raw_target TEXT NOT NULL,
                target TEXT NOT NULL,
                normalized_target TEXT NOT NULL,
                alias TEXT,
                start_line INTEGER NOT NULL,
                start_column INTEGER NOT NULL,
                end_line INTEGER NOT NULL,
                end_column INTEGER NOT NULL,
                container_symbol_id TEXT,
                container_qualified_name TEXT,
                target_symbol_id TEXT,
                target_qualified_name TEXT,
                target_kind TEXT
            );

            CREATE TABLE symbol_references (
                reference_id TEXT PRIMARY KEY,
                repo TEXT NOT NULL,
                path TEXT NOT NULL,
                crate TEXT NOT NULL,
                module_path TEXT NOT NULL,
                language TEXT NOT NULL,
                kind TEXT NOT NULL,
                name TEXT NOT NULL,
                qualified_name_hint TEXT NOT NULL,
                start_line INTEGER NOT NULL,
                start_column INTEGER NOT NULL,
                end_line INTEGER NOT NULL,
                end_column INTEGER NOT NULL,
                container_symbol_id TEXT NOT NULL,
                container_qualified_name TEXT NOT NULL,
                scope_symbol_id TEXT,
                target_symbol_id TEXT,
                target_qualified_name TEXT NOT NULL,
                target_kind TEXT
            );

            CREATE TABLE statements (
                statement_id TEXT PRIMARY KEY,
                repo TEXT NOT NULL,
                path TEXT NOT NULL,
                crate TEXT NOT NULL,
                module_path TEXT NOT NULL,
                language TEXT NOT NULL,
                kind TEXT NOT NULL,
                text TEXT NOT NULL,
                start_line INTEGER NOT NULL,
                start_column INTEGER NOT NULL,
                end_line INTEGER NOT NULL,
                end_column INTEGER NOT NULL,
                container_symbol_id TEXT NOT NULL,
                container_qualified_name TEXT NOT NULL,
                parent_statement_id TEXT,
                previous_statement_id TEXT,
                nesting_depth INTEGER NOT NULL,
                defines_json TEXT NOT NULL,
                reads_json TEXT NOT NULL,
                writes_json TEXT NOT NULL,
                calls_json TEXT NOT NULL
            );

            CREATE TABLE tests (
                test_id TEXT PRIMARY KEY,
                symbol_id TEXT NOT NULL,
                repo TEXT NOT NULL,
                path TEXT NOT NULL,
                qualified_name TEXT NOT NULL,
                kind TEXT NOT NULL
            );

            CREATE TABLE summaries (
                summary_id TEXT PRIMARY KEY,
                repo TEXT NOT NULL,
                scope TEXT NOT NULL,
                path TEXT,
                symbol_id TEXT,
                title TEXT NOT NULL,
                summary TEXT NOT NULL,
                payload_json TEXT NOT NULL
            );

            CREATE TABLE index_runs (
                run_id TEXT PRIMARY KEY,
                repo TEXT NOT NULL,
                generated_at TEXT NOT NULL,
                parser TEXT NOT NULL,
                schema_version TEXT NOT NULL,
                summary_json TEXT NOT NULL,
                build_metrics_json TEXT NOT NULL
            );

            CREATE INDEX idx_symbols_kind ON symbols(kind);
            CREATE INDEX idx_symbols_qname ON symbols(qualified_name);
            CREATE INDEX idx_symbols_container ON symbols(container_symbol_id);
            CREATE INDEX idx_symbols_summary_id ON symbols(summary_id);
            CREATE INDEX idx_imports_target ON imports(target_qualified_name);
            CREATE INDEX idx_references_kind ON symbol_references(kind);
            CREATE INDEX idx_references_target ON symbol_references(target_qualified_name);
            CREATE INDEX idx_statements_container ON statements(container_symbol_id);
            CREATE INDEX idx_statements_kind ON statements(kind);
            CREATE INDEX idx_summaries_scope ON summaries(scope);
            CREATE INDEX idx_summaries_path ON summaries(path);
            CREATE INDEX idx_summaries_symbol_id ON summaries(symbol_id);
            """
        )

        metadata_rows = [
            ("schema_version", str(payload["schema_version"])),
            ("repo", str(payload["repo"])),
            ("generated_at", str(payload["generated_at"])),
            ("parser", str(payload["parser"])),
            ("primary_parser_backends_json", json.dumps(payload.get("primary_parser_backends", []))),
            ("parser_backends_json", json.dumps(payload.get("parser_backends", {}))),
            ("source_roots_json", json.dumps(payload["source_roots"])),
            ("path_prefixes_json", json.dumps(payload["path_prefixes"])),
            ("summary_json", json.dumps(payload["summary"])),
        ]
        cursor.executemany("INSERT INTO metadata(key, value) VALUES (?, ?)", metadata_rows)

        cursor.executemany(
            """
            INSERT INTO files(path, crate, package_name, module_path, language, symbols, imports, primary_parser_backend, content_hash)
            VALUES (:path, :crate, :package_name, :module_path, :language, :symbols, :imports, :primary_parser_backend, :content_hash)
            """,
            payload["files"],
        )

        cursor.executemany(
            """
            INSERT INTO symbols(
                symbol_id, repo, path, crate, package_name, module_path, language, kind, name, qualified_name,
                start_line, start_column, end_line, end_column, signature, docstring, visibility,
                container_symbol_id, container_qualified_name, statement_id, scope_symbol_id,
                reference_target_symbol_id, attributes_json, is_test, impl_target, impl_trait,
                super_traits_json,
                resolved_impl_target_symbol_id, resolved_impl_target_qualified_name,
                resolved_impl_trait_symbol_id, resolved_impl_trait_qualified_name,
                resolved_super_traits_json, summary_id, normalized_body_hash, semantic_summary_json
            )
            VALUES (
                :symbol_id, :repo, :path, :crate, :package_name, :module_path, :language, :kind, :name, :qualified_name,
                :start_line, :start_column, :end_line, :end_column, :signature, :docstring, :visibility,
                :container_symbol_id, :container_qualified_name, :statement_id, :scope_symbol_id,
                :reference_target_symbol_id, :attributes_json, :is_test, :impl_target, :impl_trait,
                :super_traits_json,
                :resolved_impl_target_symbol_id, :resolved_impl_target_qualified_name,
                :resolved_impl_trait_symbol_id, :resolved_impl_trait_qualified_name,
                :resolved_super_traits_json, :summary_id, :normalized_body_hash, :semantic_summary_json
            )
            """,
            [flatten_symbol_row(row) for row in payload["symbols"]],
        )

        cursor.executemany(
            """
            INSERT INTO imports(
                import_id, repo, path, crate, module_path, language, visibility, signature,
                raw_target, target, normalized_target, alias, start_line, start_column,
                end_line, end_column, container_symbol_id, container_qualified_name,
                target_symbol_id, target_qualified_name, target_kind
            )
            VALUES (
                :import_id, :repo, :path, :crate, :module_path, :language, :visibility, :signature,
                :raw_target, :target, :normalized_target, :alias, :start_line, :start_column,
                :end_line, :end_column, :container_symbol_id, :container_qualified_name,
                :target_symbol_id, :target_qualified_name, :target_kind
            )
            """,
            [flatten_import_row(row) for row in payload["imports"]],
        )

        cursor.executemany(
            """
            INSERT INTO symbol_references(
                reference_id, repo, path, crate, module_path, language, kind, name,
                qualified_name_hint, start_line, start_column, end_line, end_column,
                container_symbol_id, container_qualified_name, scope_symbol_id,
                target_symbol_id, target_qualified_name, target_kind
            )
            VALUES (
                :reference_id, :repo, :path, :crate, :module_path, :language, :kind, :name,
                :qualified_name_hint, :start_line, :start_column, :end_line, :end_column,
                :container_symbol_id, :container_qualified_name, :scope_symbol_id,
                :target_symbol_id, :target_qualified_name, :target_kind
            )
            """,
            [flatten_reference_row(row) for row in payload["references"]],
        )

        cursor.executemany(
            """
            INSERT INTO statements(
                statement_id, repo, path, crate, module_path, language, kind, text,
                start_line, start_column, end_line, end_column, container_symbol_id,
                container_qualified_name, parent_statement_id, previous_statement_id,
                nesting_depth, defines_json, reads_json, writes_json, calls_json
            )
            VALUES (
                :statement_id, :repo, :path, :crate, :module_path, :language, :kind, :text,
                :start_line, :start_column, :end_line, :end_column, :container_symbol_id,
                :container_qualified_name, :parent_statement_id, :previous_statement_id,
                :nesting_depth, :defines_json, :reads_json, :writes_json, :calls_json
            )
            """,
            [flatten_statement_row(row) for row in payload.get("statements", [])],
        )

        cursor.executemany(
            """
            INSERT INTO tests(test_id, symbol_id, repo, path, qualified_name, kind)
            VALUES (:test_id, :symbol_id, :repo, :path, :qualified_name, :kind)
            """,
            [
                {
                    "test_id": f"test:{row['symbol_id']}",
                    "symbol_id": row["symbol_id"],
                    "repo": row["repo"],
                    "path": row["path"],
                    "qualified_name": row["qualified_name"],
                    "kind": row["kind"],
                }
                for row in payload["symbols"]
                if row.get("is_test")
            ],
        )

        cursor.execute(
            """
            INSERT INTO index_runs(run_id, repo, generated_at, parser, schema_version, summary_json, build_metrics_json)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            [
                f"run:{payload['repo']}:{payload['generated_at']}",
                payload["repo"],
                payload["generated_at"],
                payload["parser"],
                str(payload["schema_version"]),
                json.dumps(payload.get("summary", {})),
                json.dumps(payload.get("build_metrics", {})),
            ],
        )

        connection.commit()
    finally:
        connection.close()
    _load_symbol_index_cached.cache_clear()


def write_symbol_parquet_bundle(output_root: Path, repo_name: str, payload: Dict[str, object]) -> None:
    repo_output = output_root / repo_name
    repo_output.mkdir(parents=True, exist_ok=True)
    status_path = repo_output / "parquet_status.json"

    try:
        import pyarrow as pa
        import pyarrow.parquet as pq
    except ImportError:
        write_json(
            status_path,
            {
                "available": False,
                "reason": "pyarrow is not installed in the active Python environment",
                "artifacts": [],
            },
        )
        return

    parquet_artifacts = []
    datasets = {
        "files.parquet": payload["files"],
        "symbols.parquet": [flatten_symbol_row(row) for row in payload["symbols"]],
        "imports.parquet": [flatten_import_row(row) for row in payload["imports"]],
        "references.parquet": [flatten_reference_row(row) for row in payload["references"]],
        "statements.parquet": [flatten_statement_row(row) for row in payload.get("statements", [])],
    }

    for filename, rows in datasets.items():
        target = repo_output / filename
        table = pa.Table.from_pylist(list(rows)) if rows else pa.table({})
        pq.write_table(table, target)
        parquet_artifacts.append(filename)

    write_json(
        status_path,
        {
            "available": True,
            "reason": None,
            "artifacts": parquet_artifacts,
        },
    )


def flatten_import_row(row: Dict[str, object]) -> Dict[str, object]:
    span = row["span"]
    return {
        "import_id": row["import_id"],
        "repo": row["repo"],
        "path": row["path"],
        "crate": row["crate"],
        "module_path": row["module_path"],
        "language": row["language"],
        "visibility": row["visibility"],
        "signature": row["signature"],
        "raw_target": row["raw_target"],
        "target": row["target"],
        "normalized_target": row["normalized_target"],
        "alias": row["alias"],
        "start_line": span["start_line"],
        "start_column": span["start_column"],
        "end_line": span["end_line"],
        "end_column": span["end_column"],
        "container_symbol_id": row["container_symbol_id"],
        "container_qualified_name": row["container_qualified_name"],
        "target_symbol_id": row["target_symbol_id"],
        "target_qualified_name": row["target_qualified_name"],
        "target_kind": row["target_kind"],
    }


def flatten_reference_row(row: Dict[str, object]) -> Dict[str, object]:
    span = row["span"]
    return {
        "reference_id": row["reference_id"],
        "repo": row["repo"],
        "path": row["path"],
        "crate": row["crate"],
        "module_path": row["module_path"],
        "language": row["language"],
        "kind": row["kind"],
        "name": row["name"],
        "qualified_name_hint": row["qualified_name_hint"],
        "start_line": span["start_line"],
        "start_column": span["start_column"],
        "end_line": span["end_line"],
        "end_column": span["end_column"],
        "container_symbol_id": row["container_symbol_id"],
        "container_qualified_name": row["container_qualified_name"],
        "scope_symbol_id": row["scope_symbol_id"],
        "target_symbol_id": row["target_symbol_id"],
        "target_qualified_name": row["target_qualified_name"],
        "target_kind": row["target_kind"],
    }


def flatten_statement_row(row: Dict[str, object]) -> Dict[str, object]:
    span = row["span"]
    return {
        "statement_id": row["statement_id"],
        "repo": row["repo"],
        "path": row["path"],
        "crate": row["crate"],
        "module_path": row["module_path"],
        "language": row["language"],
        "kind": row["kind"],
        "text": row["text"],
        "start_line": span["start_line"],
        "start_column": span["start_column"],
        "end_line": span["end_line"],
        "end_column": span["end_column"],
        "container_symbol_id": row["container_symbol_id"],
        "container_qualified_name": row["container_qualified_name"],
        "parent_statement_id": row["parent_statement_id"],
        "previous_statement_id": row["previous_statement_id"],
        "nesting_depth": row["nesting_depth"],
        "defines_json": json.dumps(row["defines"]),
        "reads_json": json.dumps(row["reads"]),
        "writes_json": json.dumps(row["writes"]),
        "calls_json": json.dumps(row["calls"]),
    }


def flatten_symbol_row(row: Dict[str, object]) -> Dict[str, object]:
    span = row["span"]
    return {
        "symbol_id": row["symbol_id"],
        "repo": row["repo"],
        "path": row["path"],
        "crate": row["crate"],
        "package_name": row["package_name"],
        "module_path": row["module_path"],
        "language": row["language"],
        "kind": row["kind"],
        "name": row["name"],
        "qualified_name": row["qualified_name"],
        "start_line": span["start_line"],
        "start_column": span["start_column"],
        "end_line": span["end_line"],
        "end_column": span["end_column"],
        "signature": row["signature"],
        "docstring": row["docstring"],
        "visibility": row["visibility"],
        "container_symbol_id": row["container_symbol_id"],
        "container_qualified_name": row["container_qualified_name"],
        "statement_id": row["statement_id"],
        "scope_symbol_id": row["scope_symbol_id"],
        "reference_target_symbol_id": row["reference_target_symbol_id"],
        "attributes_json": json.dumps(row["attributes"]),
        "is_test": int(bool(row["is_test"])),
        "impl_target": row["impl_target"],
        "impl_trait": row["impl_trait"],
        "super_traits_json": json.dumps(row.get("super_traits", [])),
        "resolved_impl_target_symbol_id": row["resolved_impl_target_symbol_id"],
        "resolved_impl_target_qualified_name": row["resolved_impl_target_qualified_name"],
        "resolved_impl_trait_symbol_id": row["resolved_impl_trait_symbol_id"],
        "resolved_impl_trait_qualified_name": row["resolved_impl_trait_qualified_name"],
        "resolved_super_traits_json": json.dumps(row.get("resolved_super_traits", [])),
        "summary_id": row.get("summary_id"),
        "normalized_body_hash": row.get("normalized_body_hash"),
        "semantic_summary_json": json.dumps(row.get("semantic_summary", {})),
    }


def write_summary_database(output_root: Path, repo_name: str, payload: Dict[str, object]) -> None:
    target = output_root / repo_name / "symbols.sqlite3"
    if not target.exists():
        return

    summary_rows = build_summary_rows(repo_name, payload)
    with sqlite3.connect(target) as connection:
        cursor = connection.cursor()
        cursor.execute("DELETE FROM summaries")
        cursor.executemany(
            """
            INSERT INTO summaries(summary_id, repo, scope, path, symbol_id, title, summary, payload_json)
            VALUES (:summary_id, :repo, :scope, :path, :symbol_id, :title, :summary, :payload_json)
            """,
            summary_rows,
        )
        connection.commit()


def write_summary_bundle_database(output_root: Path, repo_name: str, payload: Dict[str, object]) -> None:
    repo_output = output_root / repo_name
    repo_output.mkdir(parents=True, exist_ok=True)
    target = repo_output / "summary.sqlite3"
    if target.exists():
        target.unlink()

    summary_rows = build_summary_rows(repo_name, payload)
    with sqlite3.connect(target) as connection:
        cursor = connection.cursor()
        cursor.executescript(
            """
            CREATE TABLE metadata (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );

            CREATE TABLE summaries (
                summary_id TEXT PRIMARY KEY,
                repo TEXT NOT NULL,
                scope TEXT NOT NULL,
                path TEXT,
                symbol_id TEXT,
                title TEXT NOT NULL,
                summary TEXT NOT NULL,
                payload_json TEXT NOT NULL
            );

            CREATE INDEX idx_summaries_scope ON summaries(scope);
            CREATE INDEX idx_summaries_path ON summaries(path);
            CREATE INDEX idx_summaries_symbol_id ON summaries(symbol_id);
            """
        )
        cursor.executemany(
            "INSERT INTO metadata(key, value) VALUES (?, ?)",
            [
                ("schema_version", str(payload["schema_version"])),
                ("repo", str(payload["repo"])),
                ("generated_at", str(payload["generated_at"])),
                ("summary_json", json.dumps(payload.get("summary", {}))),
            ],
        )
        cursor.executemany(
            """
            INSERT INTO summaries(summary_id, repo, scope, path, symbol_id, title, summary, payload_json)
            VALUES (:summary_id, :repo, :scope, :path, :symbol_id, :title, :summary, :payload_json)
            """,
            summary_rows,
        )
        connection.commit()


def load_summary_bundle_database(summary_root: Path, repo_name: str) -> Dict[str, object]:
    sqlite_path = summary_root / repo_name / "summary.sqlite3"
    with sqlite3.connect(sqlite_path) as connection:
        connection.row_factory = sqlite3.Row
        metadata_rows = dict(connection.execute("SELECT key, value FROM metadata").fetchall())
        rows = connection.execute(
            """
            SELECT summary_id, repo, scope, path, symbol_id, title, summary, payload_json
            FROM summaries
            ORDER BY scope, COALESCE(path, ''), COALESCE(symbol_id, ''), title
            """
        ).fetchall()

    payload = {
        "project": {},
        "packages": [],
        "directories": [],
        "files": [],
        "symbols": [],
        "manifest": {
            "schema_version": metadata_rows.get("schema_version"),
            "repo": metadata_rows.get("repo") or repo_name,
            "generated_at": metadata_rows.get("generated_at"),
            "summary": json.loads(metadata_rows.get("summary_json") or "{}"),
        },
    }

    scope_map = {
        "package": "packages",
        "directory": "directories",
        "file": "files",
        "symbol": "symbols",
    }
    for row in rows:
        record = json.loads(row["payload_json"] or "{}")
        scope = str(row["scope"])
        if scope == "project":
            payload["project"] = record
            continue
        collection = scope_map.get(scope)
        if collection:
            payload[collection].append(record)
    return payload


def build_summary_rows(repo_name: str, payload: Dict[str, object]) -> List[Dict[str, object]]:
    rows: List[Dict[str, object]] = []

    project = payload.get("project") or {}
    if project:
        rows.append(
            {
                "summary_id": str(project.get("summary_id") or f"sum:{repo_name}:project"),
                "repo": repo_name,
                "scope": "project",
                "path": None,
                "symbol_id": None,
                "title": project.get("repo") or repo_name,
                "summary": project.get("summary") or "",
                "payload_json": json.dumps(project),
            }
        )

    for scope, items in (
        ("package", payload.get("packages", [])),
        ("directory", payload.get("directories", [])),
        ("file", payload.get("files", [])),
        ("symbol", payload.get("symbols", [])),
    ):
        for item in items:
            rows.append(
                {
                    "summary_id": str(item.get("summary_id") or ""),
                    "repo": repo_name,
                    "scope": scope,
                    "path": item.get("path"),
                    "symbol_id": item.get("symbol_id"),
                    "title": item.get("qualified_name") or item.get("path") or item.get("name") or repo_name,
                    "summary": item.get("summary") or "",
                    "payload_json": json.dumps(item),
                }
            )
    return rows


def write_json(path: Path, payload: Dict[str, object]) -> None:
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, sort_keys=False)
        handle.write("\n")


def load_symbol_index(parsed_root: Path, repo_name: str) -> Dict[str, object]:
    increment_counter("full_symbol_payload_loads")
    with trace_operation("load_symbol_index"):
        return _load_symbol_index_cached(str(parsed_root.resolve()), repo_name)


@lru_cache(maxsize=8)
def _load_symbol_index_cached(parsed_root: str, repo_name: str) -> Dict[str, object]:
    sqlite_path = Path(parsed_root) / repo_name / "symbols.sqlite3"
    with sqlite3.connect(sqlite_path) as connection:
        connection.row_factory = sqlite3.Row
        metadata_rows = dict(connection.execute("SELECT key, value FROM metadata").fetchall())
        files = [
            {
                "path": row["path"],
                "crate": row["crate"],
                "package_name": row["package_name"],
                "module_path": row["module_path"],
                "language": row["language"],
                "symbols": int(row["symbols"]),
                "imports": int(row["imports"]),
                "primary_parser_backend": row["primary_parser_backend"],
                "content_hash": row["content_hash"],
            }
            for row in connection.execute(
                """
                SELECT path, crate, package_name, module_path, language, symbols, imports, primary_parser_backend, content_hash
                FROM files
                ORDER BY path
                """
            )
        ]
        symbols = [
            unflatten_symbol_row(row)
            for row in connection.execute(
                """
                SELECT symbol_id, repo, path, crate, package_name, module_path, language, kind, name, qualified_name,
                       start_line, start_column, end_line, end_column, signature, docstring, visibility,
                       container_symbol_id, container_qualified_name, statement_id, scope_symbol_id,
                       reference_target_symbol_id, attributes_json, is_test, impl_target, impl_trait,
                       super_traits_json, resolved_impl_target_symbol_id, resolved_impl_target_qualified_name,
                       resolved_impl_trait_symbol_id, resolved_impl_trait_qualified_name,
                       resolved_super_traits_json, summary_id, normalized_body_hash, semantic_summary_json
                FROM symbols
                ORDER BY path, start_line, start_column, qualified_name, symbol_id
                """
            )
        ]
        imports = [
            unflatten_import_row(row)
            for row in connection.execute(
                """
                SELECT import_id, repo, path, crate, module_path, language, visibility, signature,
                       raw_target, target, normalized_target, alias, start_line, start_column,
                       end_line, end_column, container_symbol_id, container_qualified_name,
                       target_symbol_id, target_qualified_name, target_kind
                FROM imports
                ORDER BY path, start_line, start_column, import_id
                """
            )
        ]
        references = [
            unflatten_reference_row(row)
            for row in connection.execute(
                """
                SELECT reference_id, repo, path, crate, module_path, language, kind, name,
                       qualified_name_hint, start_line, start_column, end_line, end_column,
                       container_symbol_id, container_qualified_name, scope_symbol_id,
                       target_symbol_id, target_qualified_name, target_kind
                FROM symbol_references
                ORDER BY path, start_line, start_column, reference_id
                """
            )
        ]
        statements = [
            unflatten_statement_row(row)
            for row in connection.execute(
                """
                SELECT statement_id, repo, path, crate, module_path, language, kind, text,
                       start_line, start_column, end_line, end_column, container_symbol_id,
                       container_qualified_name, parent_statement_id, previous_statement_id,
                       nesting_depth, defines_json, reads_json, writes_json, calls_json
                FROM statements
                ORDER BY path, start_line, start_column, statement_id
                """
            )
        ]

    return {
        "schema_version": metadata_rows.get("schema_version"),
        "repo": metadata_rows.get("repo") or repo_name,
        "generated_at": metadata_rows.get("generated_at"),
        "parser": metadata_rows.get("parser"),
        "primary_parser_backends": json.loads(metadata_rows.get("primary_parser_backends_json") or "[]"),
        "parser_backends": json.loads(metadata_rows.get("parser_backends_json") or "{}"),
        "source_roots": json.loads(metadata_rows.get("source_roots_json") or "[]"),
        "path_prefixes": json.loads(metadata_rows.get("path_prefixes_json") or "[]"),
        "summary": json.loads(metadata_rows.get("summary_json") or "{}"),
        "files": files,
        "symbols": symbols,
        "imports": imports,
        "references": references,
        "statements": statements,
    }


def load_symbol_by_id(parsed_root: Path, repo_name: str, symbol_id: str) -> Optional[Dict[str, object]]:
    sqlite_path = parsed_root / repo_name / "symbols.sqlite3"
    with sqlite3.connect(sqlite_path) as connection:
        connection.row_factory = sqlite3.Row
        row = connection.execute(
            """
            SELECT symbol_id, repo, path, crate, package_name, module_path, language, kind, name, qualified_name,
                   start_line, start_column, end_line, end_column, signature, docstring, visibility,
                   container_symbol_id, container_qualified_name, statement_id, scope_symbol_id,
                   reference_target_symbol_id, attributes_json, is_test, impl_target, impl_trait,
                   super_traits_json, resolved_impl_target_symbol_id, resolved_impl_target_qualified_name,
                   resolved_impl_trait_symbol_id, resolved_impl_trait_qualified_name,
                   resolved_super_traits_json, summary_id, normalized_body_hash, semantic_summary_json
            FROM symbols
            WHERE symbol_id = ?
            """,
            [symbol_id],
        ).fetchone()
    return unflatten_symbol_row(row) if row else None


def load_symbols_by_ids(parsed_root: Path, repo_name: str, symbol_ids: Sequence[str]) -> Dict[str, Dict[str, object]]:
    symbol_ids = [symbol_id for symbol_id in symbol_ids if symbol_id]
    if not symbol_ids:
        return {}
    sqlite_path = parsed_root / repo_name / "symbols.sqlite3"
    placeholders = ",".join("?" for _ in symbol_ids)
    with sqlite3.connect(sqlite_path) as connection:
        connection.row_factory = sqlite3.Row
        rows = connection.execute(
            f"""
            SELECT symbol_id, repo, path, crate, package_name, module_path, language, kind, name, qualified_name,
                   start_line, start_column, end_line, end_column, signature, docstring, visibility,
                   container_symbol_id, container_qualified_name, statement_id, scope_symbol_id,
                   reference_target_symbol_id, attributes_json, is_test, impl_target, impl_trait,
                   super_traits_json, resolved_impl_target_symbol_id, resolved_impl_target_qualified_name,
                   resolved_impl_trait_symbol_id, resolved_impl_trait_qualified_name,
                   resolved_super_traits_json, summary_id, normalized_body_hash, semantic_summary_json
            FROM symbols
            WHERE symbol_id IN ({placeholders})
            """,
            symbol_ids,
        ).fetchall()
    return {str(row["symbol_id"]): unflatten_symbol_row(row) for row in rows}


def unflatten_symbol_row(row: sqlite3.Row) -> Dict[str, object]:
    return {
        "symbol_id": row["symbol_id"],
        "repo": row["repo"],
        "path": row["path"],
        "crate": row["crate"],
        "package_name": row["package_name"],
        "module_path": row["module_path"],
        "language": row["language"],
        "kind": row["kind"],
        "name": row["name"],
        "qualified_name": row["qualified_name"],
        "span": {
            "start_line": int(row["start_line"]),
            "start_column": int(row["start_column"]),
            "end_line": int(row["end_line"]),
            "end_column": int(row["end_column"]),
        },
        "signature": row["signature"],
        "docstring": row["docstring"],
        "visibility": row["visibility"],
        "container_symbol_id": row["container_symbol_id"],
        "container_qualified_name": row["container_qualified_name"],
        "statement_id": row["statement_id"],
        "scope_symbol_id": row["scope_symbol_id"],
        "reference_target_symbol_id": row["reference_target_symbol_id"],
        "attributes": json.loads(row["attributes_json"] or "[]"),
        "is_test": bool(row["is_test"]),
        "impl_target": row["impl_target"],
        "impl_trait": row["impl_trait"],
        "super_traits": json.loads(row["super_traits_json"] or "[]"),
        "resolved_impl_target_symbol_id": row["resolved_impl_target_symbol_id"],
        "resolved_impl_target_qualified_name": row["resolved_impl_target_qualified_name"],
        "resolved_impl_trait_symbol_id": row["resolved_impl_trait_symbol_id"],
        "resolved_impl_trait_qualified_name": row["resolved_impl_trait_qualified_name"],
        "resolved_super_traits": json.loads(row["resolved_super_traits_json"] or "[]"),
        "summary_id": row["summary_id"],
        "normalized_body_hash": row["normalized_body_hash"],
        "semantic_summary": json.loads(row["semantic_summary_json"] or "{}"),
    }


def unflatten_import_row(row: sqlite3.Row) -> Dict[str, object]:
    return {
        "import_id": row["import_id"],
        "repo": row["repo"],
        "path": row["path"],
        "crate": row["crate"],
        "module_path": row["module_path"],
        "language": row["language"],
        "visibility": row["visibility"],
        "signature": row["signature"],
        "raw_target": row["raw_target"],
        "target": row["target"],
        "normalized_target": row["normalized_target"],
        "alias": row["alias"],
        "span": {
            "start_line": int(row["start_line"]),
            "start_column": int(row["start_column"]),
            "end_line": int(row["end_line"]),
            "end_column": int(row["end_column"]),
        },
        "container_symbol_id": row["container_symbol_id"],
        "container_qualified_name": row["container_qualified_name"],
        "target_symbol_id": row["target_symbol_id"],
        "target_qualified_name": row["target_qualified_name"],
        "target_kind": row["target_kind"],
    }


def unflatten_reference_row(row: sqlite3.Row) -> Dict[str, object]:
    return {
        "reference_id": row["reference_id"],
        "repo": row["repo"],
        "path": row["path"],
        "crate": row["crate"],
        "module_path": row["module_path"],
        "language": row["language"],
        "kind": row["kind"],
        "name": row["name"],
        "qualified_name_hint": row["qualified_name_hint"],
        "span": {
            "start_line": int(row["start_line"]),
            "start_column": int(row["start_column"]),
            "end_line": int(row["end_line"]),
            "end_column": int(row["end_column"]),
        },
        "container_symbol_id": row["container_symbol_id"],
        "container_qualified_name": row["container_qualified_name"],
        "scope_symbol_id": row["scope_symbol_id"],
        "target_symbol_id": row["target_symbol_id"],
        "target_qualified_name": row["target_qualified_name"],
        "target_kind": row["target_kind"],
    }


def unflatten_statement_row(row: sqlite3.Row) -> Dict[str, object]:
    return {
        "statement_id": row["statement_id"],
        "repo": row["repo"],
        "path": row["path"],
        "crate": row["crate"],
        "module_path": row["module_path"],
        "language": row["language"],
        "kind": row["kind"],
        "text": row["text"],
        "span": {
            "start_line": int(row["start_line"]),
            "start_column": int(row["start_column"]),
            "end_line": int(row["end_line"]),
            "end_column": int(row["end_column"]),
        },
        "container_symbol_id": row["container_symbol_id"],
        "container_qualified_name": row["container_qualified_name"],
        "parent_statement_id": row["parent_statement_id"],
        "previous_statement_id": row["previous_statement_id"],
        "nesting_depth": int(row["nesting_depth"]),
        "defines": json.loads(row["defines_json"] or "[]"),
        "reads": json.loads(row["reads_json"] or "[]"),
        "writes": json.loads(row["writes_json"] or "[]"),
        "calls": json.loads(row["calls_json"] or "[]"),
    }
