from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Dict, Iterable, List


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
                module_path TEXT NOT NULL,
                language TEXT NOT NULL,
                symbols INTEGER NOT NULL,
                imports INTEGER NOT NULL
            );

            CREATE TABLE symbols (
                symbol_id TEXT PRIMARY KEY,
                repo TEXT NOT NULL,
                path TEXT NOT NULL,
                crate TEXT NOT NULL,
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
                resolved_impl_target_symbol_id TEXT,
                resolved_impl_target_qualified_name TEXT,
                resolved_impl_trait_symbol_id TEXT,
                resolved_impl_trait_qualified_name TEXT
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

            CREATE INDEX idx_symbols_kind ON symbols(kind);
            CREATE INDEX idx_symbols_qname ON symbols(qualified_name);
            CREATE INDEX idx_symbols_container ON symbols(container_symbol_id);
            CREATE INDEX idx_imports_target ON imports(target_qualified_name);
            CREATE INDEX idx_references_kind ON symbol_references(kind);
            CREATE INDEX idx_references_target ON symbol_references(target_qualified_name);
            """
        )

        metadata_rows = [
            ("schema_version", str(payload["schema_version"])),
            ("repo", str(payload["repo"])),
            ("generated_at", str(payload["generated_at"])),
            ("parser", str(payload["parser"])),
            ("source_roots_json", json.dumps(payload["source_roots"])),
            ("path_prefixes_json", json.dumps(payload["path_prefixes"])),
            ("summary_json", json.dumps(payload["summary"])),
        ]
        cursor.executemany("INSERT INTO metadata(key, value) VALUES (?, ?)", metadata_rows)

        cursor.executemany(
            """
            INSERT INTO files(path, crate, module_path, language, symbols, imports)
            VALUES (:path, :crate, :module_path, :language, :symbols, :imports)
            """,
            payload["files"],
        )

        cursor.executemany(
            """
            INSERT INTO symbols(
                symbol_id, repo, path, crate, module_path, language, kind, name, qualified_name,
                start_line, start_column, end_line, end_column, signature, docstring, visibility,
                container_symbol_id, container_qualified_name, statement_id, scope_symbol_id,
                reference_target_symbol_id, attributes_json, is_test, impl_target, impl_trait,
                resolved_impl_target_symbol_id, resolved_impl_target_qualified_name,
                resolved_impl_trait_symbol_id, resolved_impl_trait_qualified_name
            )
            VALUES (
                :symbol_id, :repo, :path, :crate, :module_path, :language, :kind, :name, :qualified_name,
                :start_line, :start_column, :end_line, :end_column, :signature, :docstring, :visibility,
                :container_symbol_id, :container_qualified_name, :statement_id, :scope_symbol_id,
                :reference_target_symbol_id, :attributes_json, :is_test, :impl_target, :impl_trait,
                :resolved_impl_target_symbol_id, :resolved_impl_target_qualified_name,
                :resolved_impl_trait_symbol_id, :resolved_impl_trait_qualified_name
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

        connection.commit()
    finally:
        connection.close()


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


def flatten_symbol_row(row: Dict[str, object]) -> Dict[str, object]:
    span = row["span"]
    return {
        "symbol_id": row["symbol_id"],
        "repo": row["repo"],
        "path": row["path"],
        "crate": row["crate"],
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
        "resolved_impl_target_symbol_id": row["resolved_impl_target_symbol_id"],
        "resolved_impl_target_qualified_name": row["resolved_impl_target_qualified_name"],
        "resolved_impl_trait_symbol_id": row["resolved_impl_trait_symbol_id"],
        "resolved_impl_trait_qualified_name": row["resolved_impl_trait_qualified_name"],
    }


def write_json(path: Path, payload: Dict[str, object]) -> None:
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, sort_keys=False)
        handle.write("\n")
