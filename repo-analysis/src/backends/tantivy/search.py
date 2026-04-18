from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Optional, Sequence

from search.indexer import lookup_symbol_documents, search_documents, search_documents_scoped


class TantivySearchBackend:
    """Search adapter that prefers Tantivy/BM25 via `search_documents`."""

    def __init__(self, search_root: Path, repo_name: str) -> None:
        self.search_root = search_root
        self.repo_name = repo_name

    def search(
        self,
        query: str,
        *,
        limit: int,
        kinds: Sequence[str] = (),
        path_prefix: Optional[str] = None,
    ) -> List[Dict[str, object]]:
        if path_prefix:
            return search_documents_scoped(
                self.search_root,
                self.repo_name,
                query,
                limit=limit,
                kinds=kinds,
                path_prefix=path_prefix,
            )
        return search_documents(
            self.search_root,
            self.repo_name,
            query,
            limit=limit,
            kinds=kinds,
        )

    def find_file(self, path_pattern: str, *, limit: int) -> List[Dict[str, object]]:
        docs = self.search(
            path_pattern,
            limit=max(limit * 8, 40),
            kinds=("directory", "file"),
        )
        normalized_pattern = path_pattern.lower().replace("*", "")
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

    def lookup_symbol_docs(self, symbol_id: str, *, kinds: Sequence[str] = (), limit: int = 20) -> List[Dict[str, object]]:
        docs = self.search(
            symbol_id,
            limit=max(limit * 8, 40),
            kinds=kinds,
        )
        exact = [item for item in docs if str(item.get("symbol_id") or "") == symbol_id]
        if exact:
            return exact[:limit]
        fallback = lookup_symbol_documents(
            self.search_root,
            self.repo_name,
            symbol_id,
            kinds=kinds,
            limit=limit,
        )
        return fallback if fallback else docs[:limit]

    def compare_repo_candidates(self, query: str, *, limit: int) -> List[Dict[str, object]]:
        return self.search(
            query,
            limit=max(limit * 4, 20),
            kinds=("symbol", "function_body", "type_body", "doc", "file", "directory", "package"),
        )[:limit]
