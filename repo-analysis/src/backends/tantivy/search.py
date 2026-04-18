from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Dict, List, Optional, Sequence

from backends.metadata_store import get_metadata_store
from common.native_tool import query_bm25_index
from common.text import tokenize
from search.indexer import list_documents


class TantivySearchBackend:
    """Tantivy-native search adapter for the interactive hot path."""

    def __init__(self, search_root: Path, repo_name: str) -> None:
        self.search_root = search_root
        self.repo_name = repo_name

    def _metadata_store(self):
        parsed_root = self.search_root.parent / "parsed"
        return get_metadata_store(str(parsed_root.resolve()), self.repo_name)

    def search(
        self,
        query: str,
        *,
        limit: int,
        kinds: Sequence[str] = (),
        path_prefix: Optional[str] = None,
    ) -> List[Dict[str, object]]:
        normalized_query = " ".join(tokenize(query))
        tantivy_dir = self.search_root / self.repo_name / "tantivy"
        if tantivy_dir.exists():
            results = query_bm25_index(
                tantivy_dir,
                normalized_query,
                limit=max(limit * 3, limit),
                kinds=kinds,
                path_prefix=path_prefix,
            )
            return results[:limit]
        return []

    def find_file(self, path_pattern: str, *, limit: int) -> List[Dict[str, object]]:
        normalized_pattern = path_pattern.strip()
        if not normalized_pattern:
            return self.list_documents(limit=limit, kinds=("directory", "file"))
        metadata_store = self._metadata_store()
        exact = metadata_store.get_file(normalized_pattern)
        if exact is not None:
            return [file_record_to_result(self.repo_name, exact)]
        prefix = normalized_pattern.rstrip("*").rstrip("/")
        if prefix:
            prefixed = metadata_store.find_files_by_prefix(prefix, limit=limit)
            if prefixed:
                return [file_record_to_result(self.repo_name, item) for item in prefixed[:limit]]
        docs = self.search(
            path_pattern,
            limit=max(limit * 8, 40),
            kinds=("directory", "file"),
        )
        normalized_pattern = normalized_pattern.lower().replace("*", "")
        if not normalized_pattern:
            return docs[:limit]
        ranked = []
        for item in docs:
            path = str(item.get("path") or "")
            if not path:
                continue
            haystack = path.lower()
            score = float(item.get("score") or 0.0)
            if normalized_pattern in haystack:
                score += 2.0
            ranked.append((score, item))
        ranked.sort(key=lambda pair: (-pair[0], str(pair[1].get("path") or "")))
        return [item for _, item in ranked[:limit]]

    def list_documents(
        self,
        *,
        limit: int,
        kinds: Sequence[str] = (),
        path_prefix: Optional[str] = None,
    ) -> List[Dict[str, object]]:
        return list_documents(
            self.search_root,
            self.repo_name,
            limit=limit,
            kinds=kinds,
            path_prefix=path_prefix,
        )

    def lookup_symbol_docs(self, symbol_id: str, *, kinds: Sequence[str] = (), limit: int = 20) -> List[Dict[str, object]]:
        metadata_store = self._metadata_store()
        symbol = metadata_store.get_symbol(symbol_id)
        body = metadata_store.get_symbol_body(symbol_id)
        if symbol is not None and body is not None:
            result = body_payload_to_result(symbol, body)
            if not kinds or str(result.get("kind") or "") in kinds:
                return [result]
        tantivy_dir = self.search_root / self.repo_name / "tantivy"
        if tantivy_dir.exists():
            docs = query_bm25_index(
                tantivy_dir,
                "",
                limit=max(limit * 4, 20),
                kinds=kinds,
                symbol_id=symbol_id,
            )
            exact = [item for item in docs if str(item.get("symbol_id") or "") == symbol_id]
            if exact:
                return exact[:limit]
        return []

    def compare_repo_candidates(self, query: str, *, limit: int) -> List[Dict[str, object]]:
        return self.search(
            query,
            limit=max(limit * 4, 20),
            kinds=("symbol", "function_body", "type_body", "doc", "file", "directory", "package"),
        )[:limit]

    def artifact_fingerprint(self) -> str:
        tracked_paths = [
            self.search_root / self.repo_name / "tantivy",
        ]
        snapshot = []
        for path in tracked_paths:
            if path.exists():
                snapshot.extend(snapshot_artifact(path))
        return hashlib.sha1(json.dumps(snapshot, sort_keys=True).encode("utf-8")).hexdigest()


def snapshot_artifact(path: Path) -> List[Dict[str, object]]:
    if path.is_dir():
        rows: List[Dict[str, object]] = []
        for child in sorted(path.rglob("*")):
            if not child.is_file():
                continue
            stat = child.stat()
            rows.append(
                {
                    "path": str(child),
                    "size": stat.st_size,
                    "mtime_ns": stat.st_mtime_ns,
                }
            )
        return rows
    stat = path.stat()
    return [
        {
            "path": str(path),
            "size": stat.st_size,
            "mtime_ns": stat.st_mtime_ns,
        }
    ]


def body_payload_to_result(symbol: Dict[str, object], body: Dict[str, object]) -> Dict[str, object]:
    symbol_kind = str(symbol.get("kind") or "")
    body_kind = "type_body" if symbol_kind in {"trait", "struct", "enum", "type", "impl"} else "function_body"
    statements = body.get("statements") or []
    preview = " ".join(str(item.get("text") or "") for item in statements[:4]).strip()
    if not preview:
        preview = str(symbol.get("signature") or symbol.get("qualified_name") or "")
    return {
        "doc_id": f"body:{symbol.get('symbol_id')}",
        "kind": body_kind,
        "repo": symbol.get("repo"),
        "path": symbol.get("path"),
        "name": symbol.get("name"),
        "qualified_name": symbol.get("qualified_name"),
        "symbol_id": symbol.get("symbol_id"),
        "title": f"{symbol.get('qualified_name') or symbol.get('name')} body",
        "preview": preview,
        "score": 1.0,
        "metadata": {
            "kind": symbol_kind,
            "body_kind": body_kind,
        },
    }


def file_record_to_result(repo_name: str, file_record: Dict[str, object]) -> Dict[str, object]:
    path = str(file_record.get("path") or "")
    return {
        "doc_id": f"file:{path}",
        "kind": "file",
        "repo": repo_name,
        "path": path,
        "name": Path(path).name if path else None,
        "qualified_name": None,
        "symbol_id": None,
        "title": path,
        "preview": f"{file_record.get('language') or 'file'} in {file_record.get('crate') or file_record.get('package_name') or 'repo'}",
        "score": 1.0,
        "metadata": {
            "language": file_record.get("language"),
            "crate": file_record.get("crate"),
            "package_name": file_record.get("package_name"),
            "module_path": file_record.get("module_path"),
        },
    }
