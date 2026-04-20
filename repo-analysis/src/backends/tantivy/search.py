from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

from backends.metadata_store import get_metadata_store
from common.native_tool import query_bm25_index
from common.text import tokenize
from search.indexer import list_documents


QUERY_EXPANSIONS = {
    "deduplication": ("dedup", "dedupe", "duplicate", "duplicates"),
    "dedup": ("dedupe", "duplicate", "duplicates"),
    "dedupe": ("dedup", "duplicate", "duplicates"),
    "duplicate": ("dedup", "dedupe", "duplicates"),
    "duplicates": ("duplicate", "dedup", "dedupe"),
    "datasource": ("datasources", "source", "stream"),
    "datasources": ("datasource", "source", "stream"),
    "routing": ("route", "dispatch", "process", "run"),
    "route": ("routing", "dispatch", "process", "run"),
    "pipeline": ("process", "run", "dispatch"),
}


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
        if not normalized_query:
            return []

        tantivy_dir = self.search_root / self.repo_name / "tantivy"
        if not tantivy_dir.exists():
            return []

        fanout = max(limit * 8, 40)
        merged: Dict[str, Dict[str, object]] = {}

        for query_variant in build_query_variants(query):
            variant = " ".join(tokenize(query_variant))
            if not variant:
                continue

            results = query_bm25_index(
                tantivy_dir,
                variant,
                limit=fanout,
                kinds=kinds,
                path_prefix=path_prefix,
            )
            for item in results:
                doc_id = str(item.get("doc_id") or "")
                if not doc_id:
                    doc_id = f"{item.get('kind')}::{item.get('path')}::{item.get('qualified_name') or item.get('name') or ''}"

                native_score = float(item.get("score") or 0.0)
                existing = merged.get(doc_id)
                if existing is None:
                    candidate = dict(item)
                    candidate["_best_native_score"] = native_score
                    candidate["_variant_hits"] = 1
                    merged[doc_id] = candidate
                    continue

                existing["_variant_hits"] = int(existing.get("_variant_hits") or 1) + 1
                existing["_best_native_score"] = max(float(existing.get("_best_native_score") or 0.0), native_score)
                if native_score > float(existing.get("score") or 0.0):
                    for key, value in item.items():
                        existing[key] = value

        return rerank_search_results(query, list(merged.values()), limit=limit)

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


def build_query_variants(query: str) -> List[str]:
    base_tokens = [token for token in tokenize(query) if token]
    if not base_tokens:
        return []

    variants: List[str] = [" ".join(base_tokens)]
    for index, token in enumerate(base_tokens):
        for expanded in QUERY_EXPANSIONS.get(token, ()):
            alternate = list(base_tokens)
            alternate[index] = expanded
            variants.append(" ".join(alternate))

    deduped: List[str] = []
    seen = set()
    for variant in variants:
        normalized = " ".join(tokenize(variant))
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        deduped.append(normalized)
    return deduped


def rerank_search_results(
    query: str,
    results: Sequence[Dict[str, object]],
    *,
    limit: int,
) -> List[Dict[str, object]]:
    query_tokens = normalize_query_tokens(query)
    expanded_tokens = expand_query_tokens(query_tokens)

    scored: List[Tuple[float, Dict[str, object]]] = []
    for item in results:
        reranked = dict(item)
        score = score_search_result(query, query_tokens, expanded_tokens, reranked)
        reranked["score"] = round(float(score), 6)
        reranked.pop("_best_native_score", None)
        reranked.pop("_variant_hits", None)
        scored.append((float(reranked["score"]), reranked))

    scored.sort(
        key=lambda pair: (
            -pair[0],
            kind_rank(str(pair[1].get("kind") or "")),
            str(pair[1].get("path") or ""),
            str(pair[1].get("qualified_name") or pair[1].get("name") or ""),
        )
    )
    return [item for _score, item in scored[:limit]]


def score_search_result(
    query: str,
    query_tokens: Sequence[str],
    expanded_tokens: Sequence[str],
    item: Dict[str, object],
) -> float:
    lowered_query = str(query or "").strip().lower()
    name = str(item.get("name") or "").lower()
    qualified_name = str(item.get("qualified_name") or "").lower()
    title = str(item.get("title") or "").lower()
    preview = str(item.get("preview") or "").lower()
    searchable = str(item.get("searchable") or "").lower()
    path = str(item.get("path") or "").lower()
    metadata = item.get("metadata", {}) or {}
    tags = " ".join(str(tag).lower() for tag in metadata.get("tags", []) or ())
    kind = str(item.get("kind") or "")

    haystack = " ".join(part for part in (name, qualified_name, title, preview, searchable, path, tags) if part)
    score = float(item.get("_best_native_score") or item.get("score") or 0.0)

    if lowered_query == qualified_name:
        score += 180.0
    if lowered_query == name:
        score += 150.0
    if lowered_query and qualified_name.endswith(f"::{lowered_query}"):
        score += 140.0
    if lowered_query and lowered_query in title:
        score += 40.0
    if lowered_query and lowered_query in preview:
        score += 24.0
    if lowered_query and lowered_query in path:
        score += 18.0

    exact_token_hits = 0
    for token in query_tokens:
        token_hit = False
        if token and token in qualified_name:
            score += 18.0
            token_hit = True
        elif token and token in name:
            score += 16.0
            token_hit = True
        elif token and token in title:
            score += 12.0
            token_hit = True
        elif token and token in preview:
            score += 10.0
            token_hit = True
        elif token and token in path:
            score += 8.0
            token_hit = True
        elif token and token in haystack:
            score += 6.0
            token_hit = True

        if token_hit:
            exact_token_hits += 1

    if query_tokens and exact_token_hits == len(query_tokens):
        score += 35.0
    elif query_tokens:
        score -= (len(query_tokens) - exact_token_hits) * 10.0

    expansion_hits = 0
    for token in expanded_tokens:
        if token and token in haystack:
            expansion_hits += 1
    score += min(expansion_hits, 4) * 4.0

    variant_hits = int(item.get("_variant_hits") or 1)
    if variant_hits > 1:
        score += min(variant_hits - 1, 3) * 5.0

    if kind == "symbol":
        score += 4.0
    elif kind in {"function_body", "type_body"}:
        score += 2.0

    if query_tokens and exact_token_hits == 0 and expansion_hits == 0:
        score -= 25.0
    if len(query_tokens) >= 2 and exact_token_hits < max(1, len(query_tokens) // 2):
        score -= 10.0

    return score


def normalize_query_tokens(query: str) -> List[str]:
    return [token.lower() for token in tokenize(query) if token]


def expand_query_tokens(query_tokens: Sequence[str]) -> List[str]:
    expanded: List[str] = []
    seen = set(query_tokens)
    for token in query_tokens:
        for expanded_token in QUERY_EXPANSIONS.get(token, ()):
            normalized = str(expanded_token).strip().lower()
            if not normalized or normalized in seen:
                continue
            seen.add(normalized)
            expanded.append(normalized)
    return expanded


def kind_rank(kind: str) -> int:
    ranking = {
        "symbol": 0,
        "function_body": 1,
        "type_body": 2,
        "file": 3,
        "directory": 4,
        "package": 5,
        "doc": 6,
    }
    return ranking.get(kind, 99)


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