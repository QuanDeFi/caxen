from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Sequence

from symbols.persistence import unflatten_symbol_row


@dataclass(frozen=True)
class LmdbMetadataStore:
    """
    Metadata store interface for PR-2 cutover.

    NOTE: this implementation is a compatibility bridge that serves the PR-2
    interface from keyed SQLite queries. It removes hot-path whole-dataset
    hydration while keeping artifact compatibility until full LMDB migration.
    """

    parsed_root: Path
    repo_name: str
    summary_root: Optional[Path] = None
    eval_root: Optional[Path] = None

    @property
    def symbols_path(self) -> Path:
        return self.parsed_root / self.repo_name / "symbols.sqlite3"

    @property
    def summary_path(self) -> Optional[Path]:
        if self.summary_root is None:
            return None
        path = self.summary_root / self.repo_name / "summary.sqlite3"
        return path if path.exists() else None

    @property
    def eval_path(self) -> Optional[Path]:
        if self.eval_root is None:
            return None
        path = self.eval_root / "eval.sqlite3"
        return path if path.exists() else None

    def get_symbol(self, symbol_id: str) -> Optional[Dict[str, object]]:
        if not symbol_id:
            return None
        with sqlite3.connect(self.symbols_path) as connection:
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

    def get_symbols(self, symbol_ids: Sequence[str]) -> Dict[str, Dict[str, object]]:
        normalized = [symbol_id for symbol_id in symbol_ids if symbol_id]
        if not normalized:
            return {}
        placeholders = ",".join("?" for _ in normalized)
        with sqlite3.connect(self.symbols_path) as connection:
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
                normalized,
            ).fetchall()
        return {row["symbol_id"]: unflatten_symbol_row(row) for row in rows}

    def resolve_qname(self, qname: str) -> List[str]:
        if not qname:
            return []
        with sqlite3.connect(self.symbols_path) as connection:
            rows = connection.execute(
                """
                SELECT symbol_id
                FROM symbols
                WHERE qualified_name = ?
                ORDER BY path, start_line, start_column, symbol_id
                LIMIT 64
                """,
                [qname],
            ).fetchall()
        return [str(row[0]) for row in rows]

    def resolve_name(self, name: str, *, repo: str | None = None) -> List[str]:
        if not name:
            return []
        query = (
            "SELECT symbol_id FROM symbols WHERE name = ? "
            + ("AND repo = ? " if repo else "")
            + "ORDER BY path, start_line, start_column, symbol_id LIMIT 64"
        )
        params: List[object] = [name]
        if repo:
            params.append(repo)
        with sqlite3.connect(self.symbols_path) as connection:
            rows = connection.execute(query, params).fetchall()
        return [str(row[0]) for row in rows]

    def get_symbol_body(self, symbol_id: str) -> Optional[Dict[str, object]]:
        symbol = self.get_symbol(symbol_id)
        if symbol is None:
            return None
        with sqlite3.connect(self.symbols_path) as connection:
            connection.row_factory = sqlite3.Row
            statements = [
                {
                    "statement_id": row["statement_id"],
                    "text": row["text"],
                    "line": int(row["start_line"]),
                }
                for row in connection.execute(
                    """
                    SELECT statement_id, text, start_line
                    FROM statements
                    WHERE container_symbol_id = ?
                    ORDER BY start_line, start_column
                    LIMIT 256
                    """,
                    [symbol_id],
                )
            ]
        return {
            "symbol_id": symbol_id,
            "path": symbol.get("path"),
            "qualified_name": symbol.get("qualified_name"),
            "signature": symbol.get("signature"),
            "statements": statements,
        }

    def get_summary_by_id(self, summary_id: str) -> Optional[Dict[str, object]]:
        if not summary_id:
            return None
        row = self._query_summary_row("summary_id = ?", [summary_id])
        if row is None:
            return None
        return self._summary_payload(row)

    def get_summary_by_path(self, path: str) -> List[Dict[str, object]]:
        if not path:
            return []
        rows = self._query_summary_rows("path = ?", [path], limit=32)
        return [self._summary_payload(row) for row in rows]

    def get_summary_by_symbol(self, symbol_id: str) -> List[Dict[str, object]]:
        if not symbol_id:
            return []
        rows = self._query_summary_rows("symbol_id = ?", [symbol_id], limit=32)
        return [self._summary_payload(row) for row in rows]

    def get_eval_case(self, case_name: str, fingerprint: str) -> Optional[Dict[str, object]]:
        if self.eval_path is None:
            return None
        with sqlite3.connect(self.eval_path) as connection:
            connection.row_factory = sqlite3.Row
            row = connection.execute(
                """
                SELECT bundle_json, prompt_payload_json, bundle_score_json
                FROM benchmark_case_cache
                WHERE case_name = ? AND cache_fingerprint = ?
                """,
                [case_name, fingerprint],
            ).fetchone()
            if row is None:
                row = connection.execute(
                    """
                    SELECT bundle_json, prompt_payload_json, bundle_score_json
                    FROM benchmark_case_cache
                    WHERE case_name = ?
                    """,
                    [case_name],
                ).fetchone()
        if row is None:
            return None
        return {
            "bundle": json.loads(row["bundle_json"]),
            "prompt_payload": json.loads(row["prompt_payload_json"]),
            "bundle_score": json.loads(row["bundle_score_json"]),
        }

    def put_eval_case(
        self,
        case_name: str,
        *,
        repo: str,
        task_type: str,
        query: str,
        limit_value: int,
        artifact_fingerprint: str,
        cache_fingerprint: str,
        bundle: Dict[str, object],
        prompt_payload: Dict[str, object],
        bundle_score: Dict[str, object],
    ) -> None:
        if self.eval_path is None:
            return
        with sqlite3.connect(self.eval_path) as connection:
            connection.execute(
                """
                INSERT INTO benchmark_case_cache(
                    case_name,
                    repo,
                    task_type,
                    query,
                    limit_value,
                    artifact_fingerprint,
                    cache_fingerprint,
                    bundle_json,
                    prompt_payload_json,
                    bundle_score_json,
                    updated_at
                )
                VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))
                ON CONFLICT(case_name) DO UPDATE SET
                    repo=excluded.repo,
                    task_type=excluded.task_type,
                    query=excluded.query,
                    limit_value=excluded.limit_value,
                    artifact_fingerprint=excluded.artifact_fingerprint,
                    cache_fingerprint=excluded.cache_fingerprint,
                    bundle_json=excluded.bundle_json,
                    prompt_payload_json=excluded.prompt_payload_json,
                    bundle_score_json=excluded.bundle_score_json,
                    updated_at=excluded.updated_at
                """,
                [
                    case_name,
                    repo,
                    task_type,
                    query,
                    int(limit_value),
                    artifact_fingerprint,
                    cache_fingerprint,
                    json.dumps(bundle),
                    json.dumps(prompt_payload),
                    json.dumps(bundle_score),
                ],
            )

    def _query_summary_row(self, where_clause: str, params: Sequence[object]) -> Optional[sqlite3.Row]:
        rows = self._query_summary_rows(where_clause, params, limit=1)
        return rows[0] if rows else None

    def _query_summary_rows(self, where_clause: str, params: Sequence[object], *, limit: int) -> List[sqlite3.Row]:
        # Prefer symbols.sqlite3 summaries table for keyed reads.
        with sqlite3.connect(self.symbols_path) as connection:
            connection.row_factory = sqlite3.Row
            rows = connection.execute(
                f"""
                SELECT summary_id, repo, scope, path, symbol_id, title, summary, payload_json
                FROM summaries
                WHERE {where_clause}
                ORDER BY scope, COALESCE(path, ''), COALESCE(symbol_id, '')
                LIMIT ?
                """,
                [*params, int(limit)],
            ).fetchall()
            if rows:
                return rows

        if self.summary_path is None:
            return []

        with sqlite3.connect(self.summary_path) as connection:
            connection.row_factory = sqlite3.Row
            return connection.execute(
                f"""
                SELECT summary_id, repo, scope, path, symbol_id, title, summary, payload_json
                FROM summaries
                WHERE {where_clause}
                ORDER BY scope, COALESCE(path, ''), COALESCE(symbol_id, '')
                LIMIT ?
                """,
                [*params, int(limit)],
            ).fetchall()

    @staticmethod
    def _summary_payload(row: sqlite3.Row) -> Dict[str, object]:
        payload_json = row["payload_json"]
        if payload_json:
            return json.loads(payload_json)
        return {
            "summary_id": row["summary_id"],
            "repo": row["repo"],
            "scope": row["scope"],
            "path": row["path"],
            "symbol_id": row["symbol_id"],
            "title": row["title"],
            "summary": row["summary"],
        }
