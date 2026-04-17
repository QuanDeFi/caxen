from __future__ import annotations

import re
from pathlib import PurePosixPath
from typing import Dict, Iterable, List


KIND_PRIORITY = {
    "symbol": 5,
    "function": 5,
    "method": 5,
    "struct": 5,
    "enum": 5,
    "trait": 5,
    "impl": 4,
    "statement": 4,
    "file": 3,
    "directory": 2,
    "repo": 1,
    "module_ref": 0,
    "symbol_ref": 0,
    "type_ref": 0,
}


def identifier_terms(value: str) -> List[str]:
    if not value:
        return []
    spaced = re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", value)
    tokens = re.split(r"[^A-Za-z0-9]+", spaced.lower())
    return [token for token in tokens if token]


def rerank_candidates(
    candidates: Iterable[Dict[str, object]],
    query_tokens: List[str],
    *,
    query_profile: Dict[str, object] | None = None,
) -> List[Dict[str, object]]:
    query_profile = query_profile or {}
    prefer_tags = set(query_profile.get("prefer_tags", []))
    prefer_symbol_kinds = set(query_profile.get("prefer_symbol_kinds", []))
    requested_symbol_kinds = set(query_profile.get("requested_symbol_kinds", []))
    prefer_symbols = bool(query_profile.get("prefer_symbols"))
    prefer_docs = bool(query_profile.get("prefer_docs"))
    type_intent = bool(query_profile.get("type_intent"))
    member_intent = bool(query_profile.get("member_intent"))
    intent = str(query_profile.get("intent") or "")
    ranked = []
    for candidate in candidates:
        searchable = " ".join(
            str(item or "").lower()
            for item in (
                candidate.get("name"),
                candidate.get("qualified_name"),
                candidate.get("path"),
                candidate.get("title"),
                candidate.get("preview"),
            )
        )
        lexical_bonus = sum(0.25 for token in query_tokens if token in searchable)
        exact_bonus = 0.0
        name = str(candidate.get("name") or "").lower()
        qualified_name = str(candidate.get("qualified_name") or "").lower()
        metadata = candidate.get("metadata", {}) or {}
        tags = {str(tag).lower() for tag in metadata.get("tags", [])}
        symbol_kind = str(
            metadata.get("kind")
            or metadata.get("symbol_kind")
            or metadata.get("node_kind")
            or candidate.get("kind")
            or ""
        ).lower()
        identifier_overlap_terms = set(identifier_terms(str(candidate.get("name") or "")))
        if qualified_name:
            identifier_overlap_terms.update(identifier_terms(qualified_name.split("::")[-1]))
        identifier_bonus = sum(0.3 for token in query_tokens if token in identifier_overlap_terms)
        if any(token == name for token in query_tokens):
            exact_bonus += 0.75
        final_name = qualified_name.split("::")[-1] if qualified_name else ""
        if any(token == final_name for token in query_tokens):
            exact_bonus += 0.5
        if "trait" in query_tokens and symbol_kind == "trait":
            exact_bonus += 0.9
        if "struct" in query_tokens and symbol_kind == "struct":
            exact_bonus += 0.75
        if "enum" in query_tokens and symbol_kind == "enum":
            exact_bonus += 0.75
        if "type" in query_tokens and symbol_kind == "type":
            exact_bonus += 0.75

        kind = str(candidate.get("kind") or "")
        priority_bonus = KIND_PRIORITY.get(kind, 0) * 0.05
        path_penalty = -1.0 if not candidate.get("path") else 0.0
        unresolved_penalty = -0.75 if kind in {"module_ref", "symbol_ref", "type_ref"} else 0.0
        reasons = set(candidate.get("reasons", []))
        lexical_reason_bonus = 0.5 if "lexical" in reasons else 0.0
        localization_bonus = 0.25 if "symbol-localization" in reasons else 0.0
        embedding_bonus = 0.15 if "embedding" in reasons else 0.0
        tag_bonus = 0.3 * sum(1 for tag in prefer_tags if tag in tags)
        symbol_kind_bonus = 0.25 * sum(1 for tag in prefer_symbol_kinds if tag == kind or tag in tags)
        kind_intent_bonus = 0.0
        if prefer_symbols and kind in {"symbol", "statement"}:
            kind_intent_bonus += 0.35
        if intent == "architecture" and kind in {"symbol", "file"}:
            kind_intent_bonus += 0.2
        if prefer_docs and kind in {"repo", "directory", "file"}:
            kind_intent_bonus += 0.35
        if type_intent:
            if symbol_kind in {"trait", "struct", "enum", "type", "impl"}:
                kind_intent_bonus += 0.85
            if symbol_kind in {"field", "local", "parameter", "variable"}:
                kind_intent_bonus -= 0.85
        if member_intent and symbol_kind in {"field", "local", "parameter", "variable", "method"}:
            kind_intent_bonus += 0.45
        requested_type_kinds = requested_symbol_kinds.intersection({"trait", "struct", "enum", "type", "class", "interface"})
        if requested_type_kinds:
            if symbol_kind in requested_type_kinds or ("class" in requested_type_kinds and symbol_kind == "struct"):
                kind_intent_bonus += 1.1
            elif symbol_kind in {"trait", "struct", "enum", "type", "impl"}:
                kind_intent_bonus -= 0.9
        requested_member_kinds = requested_symbol_kinds.intersection({"field", "property", "member", "local", "variable", "param", "parameter", "method"})
        if requested_member_kinds:
            if symbol_kind in {"field", "local", "parameter", "variable", "method"}:
                kind_intent_bonus += 0.75
            elif symbol_kind in {"trait", "struct", "enum", "type", "impl"}:
                kind_intent_bonus -= 0.4
        path = str(candidate.get("path") or "")
        suffix = PurePosixPath(path).suffix.lower() if path else ""
        path_name = PurePosixPath(path).stem.lower() if path else ""
        path_bonus = 0.0
        if path_name:
            path_terms = set(identifier_terms(path_name))
            path_bonus += sum(0.15 for token in query_tokens if token in path_terms)
            if type_intent and "source" in query_tokens and path_name in {"source", "sources"}:
                path_bonus += 0.5
        markdown_penalty = -0.6 if suffix == ".md" and not prefer_docs else 0.0
        score = (
            float(candidate.get("score") or 0.0)
            + lexical_bonus
            + exact_bonus
            + identifier_bonus
            + priority_bonus
            + path_penalty
            + unresolved_penalty
            + lexical_reason_bonus
            + localization_bonus
            + embedding_bonus
            + tag_bonus
            + symbol_kind_bonus
            + kind_intent_bonus
            + path_bonus
            + markdown_penalty
        )

        updated = dict(candidate)
        updated["score"] = round(score, 6)
        ranked.append(updated)

    return sorted(
        ranked,
        key=lambda item: (
            -float(item["score"]),
            -KIND_PRIORITY.get(str(item.get("kind") or ""), 0),
            str(item.get("path") or ""),
            str(item.get("qualified_name") or item.get("title") or ""),
        ),
    )
