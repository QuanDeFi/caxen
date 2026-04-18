from __future__ import annotations

import hashlib
import json
import math
from collections import Counter
from pathlib import Path
from typing import Dict, Iterable, List, Sequence

from embeddings.providers import (
    DEFAULT_HASHING_MODEL,
    embed_with_openai,
    openai_embeddings_available,
    resolve_embedding_provider,
)
from search.indexer import tokenize
from symbols.indexer import timestamp_now


SCHEMA_VERSION = "0.2.0"
DIMENSIONS = 256
BATCH_SIZE = 32
KIND_PRIORITY = {
    "symbol": 0.2,
    "statement": 0.15,
    "file": 0.1,
    "repo": 0.05,
    "directory": 0.0,
}


def build_embedding_index(
    search_root: Path,
    repo_name: str,
    *,
    provider: str | None = None,
    model: str | None = None,
) -> Dict[str, object]:
    repo_search_root = search_root / repo_name
    documents_path = repo_search_root / "documents.jsonl"
    documents = load_search_documents(documents_path)
    if not documents:
        raise FileNotFoundError(f"Missing search documents for {repo_name}: {documents_path}")
    provider_config = resolve_embedding_provider(provider, model)
    provider_name = str(provider_config["provider"])
    model_name = str(provider_config["model"])

    if provider_name == "openai":
        payload = build_openai_embedding_payload(repo_name, documents, model_name)
    else:
        payload = build_hashing_embedding_payload(repo_name, documents, model_name)

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
                "provider": payload["provider"],
                "model": payload["model"],
                "model_backed": payload["model_backed"],
                "dimensions": payload["dimensions"],
                "vector_format": payload["vector_format"],
                "summary": payload["summary"],
            },
            handle,
            indent=2,
            sort_keys=False,
        )
        handle.write("\n")
    return payload


def build_hashing_embedding_payload(
    repo_name: str,
    documents: Sequence[Dict[str, object]],
    model_name: str,
) -> Dict[str, object]:
    document_tokens = [tokenize(document["content"]) for document in documents]
    document_frequency = compute_document_frequency(document_tokens)

    embedded_documents = []
    for document, tokens in zip(documents, document_tokens):
        raw_vector = embed_tokens(tokens, document_frequency, len(documents))
        norm = vector_norm(raw_vector)
        vector = normalize_sparse_vector(raw_vector, norm)
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
                "norm": 1.0 if vector else 0.0,
                "vector": {str(index): round(value, 8) for index, value in sorted(vector.items()) if value},
            }
        )

    return {
        "schema_version": SCHEMA_VERSION,
        "repo": repo_name,
        "generated_at": timestamp_now(),
        "provider": "hashing",
        "model": model_name or DEFAULT_HASHING_MODEL,
        "model_backed": False,
        "dimensions": DIMENSIONS,
        "vector_format": "sparse",
        "documents": embedded_documents,
        "summary": {
            "documents": len(embedded_documents),
            "nonzero_dimensions": sum(len(document["vector"]) for document in embedded_documents),
        },
    }


def build_openai_embedding_payload(
    repo_name: str,
    documents: Sequence[Dict[str, object]],
    model_name: str,
) -> Dict[str, object]:
    if not openai_embeddings_available():
        raise RuntimeError("OpenAI embedding provider requested but OPENAI_API_KEY is not set")

    embedded_documents = []
    for batch in batched(documents, BATCH_SIZE):
        vectors = embed_with_openai([str(document["content"] or "") for document in batch], model_name)
        for document, vector in zip(batch, vectors):
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
                    "norm": 1.0 if vector else 0.0,
                    "vector": [round(float(value), 8) for value in vector],
                }
            )

    dimensions = len(embedded_documents[0]["vector"]) if embedded_documents else 0
    return {
        "schema_version": SCHEMA_VERSION,
        "repo": repo_name,
        "generated_at": timestamp_now(),
        "provider": "openai",
        "model": model_name,
        "model_backed": True,
        "dimensions": dimensions,
        "vector_format": "dense",
        "documents": embedded_documents,
        "summary": {
            "documents": len(embedded_documents),
            "nonzero_dimensions": dimensions * len(embedded_documents),
        },
    }


def query_embedding_index(search_root: Path, repo_name: str, query: str, *, limit: int = 10) -> List[Dict[str, object]]:
    index_path = search_root / repo_name / "embedding_index.json"
    if not index_path.exists():
        return []

    with index_path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)

    documents = payload.get("documents", [])
    query_tokens = tokenize(query)
    if not query_tokens:
        return []

    provider = str(payload.get("provider") or "hashing")
    vector_format = str(payload.get("vector_format") or "sparse")
    if provider == "openai":
        if not openai_embeddings_available():
            return []
        query_vector = embed_with_openai([query], str(payload["model"]))[0]
        query_norm = 1.0 if query_vector else 0.0
    else:
        raw_query_vector = embed_tokens(query_tokens, None, max(len(documents), 1))
        query_norm = vector_norm(raw_query_vector)
        query_vector = normalize_sparse_vector(raw_query_vector, query_norm)

    if query_norm == 0:
        return []

    results = []
    for document in documents:
        if vector_format == "dense":
            similarity = dense_dot_product(query_vector, [float(value) for value in document.get("vector", [])])
        else:
            doc_vector = {int(index): float(value) for index, value in document["vector"].items()}
            similarity = dot_product(query_vector, doc_vector)
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
        if any(marker in path_value for marker in ("/tests/", "/test/", ".snap")) and not any(
            token in {"test", "tests", "snap", "schema"} for token in query_tokens
        ):
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
                    "provider": payload["provider"],
                    "model": payload["model"],
                    "dimensions": payload["dimensions"],
                    "model_backed": bool(payload.get("model_backed")),
                },
            }
        )

    return sorted(
        results,
        key=lambda item: (
            -item["score"],
            str(item.get("path") or ""),
            str(item.get("qualified_name") or item.get("title") or ""),
        ),
    )[:limit]


def load_search_documents(documents_path: Path) -> List[Dict[str, object]]:
    if documents_path.exists():
        documents: List[Dict[str, object]] = []
        with documents_path.open("r", encoding="utf-8") as handle:
            for line in handle:
                raw = line.strip()
                if not raw:
                    continue
                payload = json.loads(raw)
                documents.append(
                    {
                        "doc_id": payload["doc_id"],
                        "kind": payload["kind"],
                        "path": payload.get("path"),
                        "name": payload.get("name"),
                        "qualified_name": payload.get("qualified_name"),
                        "symbol_id": payload.get("symbol_id"),
                        "title": payload.get("title"),
                        "preview": payload.get("preview"),
                        "content": payload.get("content") or "",
                    }
                )
        return documents
    return []


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


def normalize_sparse_vector(vector: Dict[int, float], norm: float | None = None) -> Dict[int, float]:
    actual_norm = vector_norm(vector) if norm is None else norm
    if actual_norm == 0:
        return {}
    return {index: value / actual_norm for index, value in vector.items()}


def vector_norm(vector: Dict[int, float]) -> float:
    return math.sqrt(sum(value * value for value in vector.values()))


def dot_product(left: Dict[int, float], right: Dict[int, float]) -> float:
    if len(left) > len(right):
        left, right = right, left
    return sum(value * right.get(index, 0.0) for index, value in left.items())


def dense_dot_product(left: Sequence[float], right: Sequence[float]) -> float:
    return sum(float(a) * float(b) for a, b in zip(left, right))


def batched(values: Sequence[Dict[str, object]], size: int) -> Iterable[Sequence[Dict[str, object]]]:
    for index in range(0, len(values), size):
        yield values[index : index + size]
