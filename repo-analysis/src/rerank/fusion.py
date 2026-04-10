from __future__ import annotations

from typing import Dict, Iterable, List


KIND_PRIORITY = {
    "symbol": 5,
    "function": 5,
    "method": 5,
    "struct": 5,
    "enum": 5,
    "trait": 5,
    "impl": 4,
    "file": 3,
    "directory": 2,
    "repo": 1,
    "module_ref": 0,
    "symbol_ref": 0,
    "type_ref": 0,
}


def rerank_candidates(candidates: Iterable[Dict[str, object]], query_tokens: List[str]) -> List[Dict[str, object]]:
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
        if any(token == name for token in query_tokens):
            exact_bonus += 0.75
        final_name = qualified_name.split("::")[-1] if qualified_name else ""
        if any(token == final_name for token in query_tokens):
            exact_bonus += 0.5

        kind = str(candidate.get("kind") or "")
        priority_bonus = KIND_PRIORITY.get(kind, 0) * 0.05
        path_penalty = -1.0 if not candidate.get("path") else 0.0
        unresolved_penalty = -0.75 if kind in {"module_ref", "symbol_ref", "type_ref"} else 0.0
        reasons = set(candidate.get("reasons", []))
        lexical_reason_bonus = 0.5 if "lexical" in reasons else 0.0
        localization_bonus = 0.25 if "symbol-localization" in reasons else 0.0
        score = (
            float(candidate.get("score") or 0.0)
            + lexical_bonus
            + exact_bonus
            + priority_bonus
            + path_penalty
            + unresolved_penalty
            + lexical_reason_bonus
            + localization_bonus
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
