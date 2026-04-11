from __future__ import annotations

import hashlib
import json
import math
import sqlite3
from collections import Counter
from pathlib import Path
from typing import Dict, Iterable, List, Sequence

from search.indexer import tokenize
from symbols.indexer import timestamp_now


SCHEMA_VERSION = "0.1.0"
MODEL_NAME = "hashing-tfidf-v1"
DIMENSIONS = 256
KIND_PRIORITY = {
    "symbol": 0.2,
    "statement": 0.15,
    "file": 0.1,
    "repo": 0.05,
    "directory": 0.0,
}


def build_embedding_index(search_root: Path, repo_name: str) -> Dict[str, object]:
    sqlite_path = search_root / repo_name / "search.sqlite3"
    if not sqlite_path.exists():
        raise FileNotFoundError(f"Missing search index for {repo_name}: {sqlite_path}")

    documents = load_search_documents(sqlite_path)
    document_tokens = [tokenize(document["content"]) for document in documents]
    document_frequency = compute_document_frequency(document_tokens)

    embedded_documents = []
    for document, tokens in zip(documents, document_tokens):
        vector = embed_tokens(tokens, document_frequency, len(documents))
        embedded_documents.append(
            {
                "doc_id": document["doc_id"],
                "kind": document["kind"],
                "path": document["path"],
                "name": document["name"],
                "qualified_name": document["qualified_name"],
                "symbol_id": document["symbol_id"],
                "title": document["title"],
                "preview": document["preview"],
                "norm": round(vector_norm(vector), 8),
                "vector": {str(index): round(value, 8) for index, value in sorted(vector.items()) if value},
            }
        )

    payload = {
        "schema_version": SCHEMA_VERSION,
        "repo": repo_name,
        "generated_at": timestamp_now(),
        "model": MODEL_NAME,
        "dimensions": DIMENSIONS,
        "documents": embedded_documents,
        "summary": {
            "documents": len(embedded_documents),
            "nonzero_dimensions": sum(len(document["vector"]) for document in embedded_documents),
        },
    }
    repo_root = search_root / repo_name
    repo_root.mkdir(parents=True, exist_ok=True)
    with (repo_root / "embedding_index.json").open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, sort_keys=False)
        handle.write("\n")
    with (repo_root / "embedding_manifest.json").open("w", encoding="utf-8") as handle:
        json.dump(
            {
                "schema_version": SCHEMA_VERSION,
                "repo": repo_name,
                "generated_at": payload["generated_at"],
                "model": MODEL_NAME,
                "dimensions": DIMENSIONS,
                "summary": payload["summary"],
            },
            handle,
            indent=2,
            sort_keys=False,
        )
        handle.write("\n")
    return payload


def query_embedding_index(search_root: Path, repo_name: str, query: str, *, limit: int = 10) -> List[Dict[str, object]]:
    index_path = search_root / repo_name / "embedding_index.json"
    if not index_path.exists():
        return []

    with index_path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)

    documents = payload.get("documents", [])
    document_frequency = Counter()
    for document in documents:
        for index in document.get("vector", {}):
            document_frequency[index] += 1

    query_tokens = tokenize(query)
    if not query_tokens:
        return []

    vector = embed_tokens(query_tokens, None, max(len(documents), 1))
    query_norm = vector_norm(vector)
    if query_norm == 0:
        return []

    results = []
    for document in documents:
        doc_vector = {int(index): float(value) for index, value in document["vector"].items()}
        denominator = query_norm * float(document.get("norm") or 0.0)
        if denominator == 0:
            continue
        similarity = dot_product(vector, doc_vector) / denominator
        if similarity <= 0:
            continue
        searchable = " ".join(
            str(item or "").lower()
            for item in (
                document.get("name"),
                document.get("qualified_name"),
                document.get("path"),
                document.get("title"),
                document.get("preview"),
            )
        )
        overlap_bonus = 0.03 * sum(1 for token in query_tokens if token in searchable)
        kind_bonus = KIND_PRIORITY.get(str(document.get("kind") or ""), 0.0)
        path_value = str(document.get("path") or "").lower()
        path_penalty = 0.0
        if any(marker in path_value for marker in ("/tests/", "/test/", ".snap")) and not any(token in {"test", "tests", "snap", "schema"} for token in query_tokens):
            path_penalty -= 0.12
        score = similarity + overlap_bonus + kind_bonus + path_penalty
        if score <= 0:
            continue
        results.append(
            {
                "doc_id": document["doc_id"],
                "kind": document["kind"],
                "repo": repo_name,
                "path": document.get("path"),
                "name": document.get("name"),
                "qualified_name": document.get("qualified_name"),
                "symbol_id": document.get("symbol_id"),
                "title": document.get("title"),
                "preview": document.get("preview"),
                "score": round(score, 6),
                "metadata": {
                    "model": payload["model"],
                    "dimensions": payload["dimensions"],
                },
            }
        )

    return sorted(results, key=lambda item: (-item["score"], str(item.get("path") or ""), str(item.get("qualified_name") or item.get("title") or "")))[:limit]


def load_search_documents(sqlite_path: Path) -> List[Dict[str, object]]:
    with sqlite3.connect(sqlite_path) as connection:
        connection.row_factory = sqlite3.Row
        rows = connection.execute(
            """
            SELECT d.doc_id, d.kind, d.path, d.name, d.qualified_name, d.symbol_id, d.title, d.preview,
                   f.content
            FROM documents d
            JOIN lexical_documents f ON d.doc_id = f.doc_id
            ORDER BY d.kind, COALESCE(d.path, ''), COALESCE(d.qualified_name, ''), COALESCE(d.name, '')
            """
        ).fetchall()
    return [
        {
            "doc_id": row["doc_id"],
            "kind": row["kind"],
            "path": row["path"],
            "name": row["name"],
            "qualified_name": row["qualified_name"],
            "symbol_id": row["symbol_id"],
            "title": row["title"],
            "preview": row["preview"],
            "content": row["content"] or "",
        }
        for row in rows
    ]


def compute_document_frequency(document_tokens: Sequence[Sequence[str]]) -> Counter[str]:
    frequency: Counter[str] = Counter()
    for tokens in document_tokens:
        for token in set(tokens):
            frequency[token] += 1
    return frequency


def embed_tokens(tokens: Sequence[str], document_frequency: Counter[str] | None, document_count: int) -> Dict[int, float]:
    term_frequency = Counter(tokens)
    vector: Dict[int, float] = {}
    for token, tf in term_frequency.items():
        index, sign = hashed_dimension(token)
        if document_frequency is None:
            idf = 1.0
        else:
            idf = math.log((document_count + 1) / (document_frequency[token] + 1)) + 1.0
        vector[index] = vector.get(index, 0.0) + sign * tf * idf
    return vector


def hashed_dimension(token: str) -> tuple[int, float]:
    digest = hashlib.sha1(token.encode("utf-8")).digest()
    index = int.from_bytes(digest[:4], "big") % DIMENSIONS
    return index, 1.0


def vector_norm(vector: Dict[int, float]) -> float:
    return math.sqrt(sum(value * value for value in vector.values()))


def dot_product(left: Dict[int, float], right: Dict[int, float]) -> float:
    if len(left) > len(right):
        left, right = right, left
    return sum(value * right.get(index, 0.0) for index, value in left.items())
