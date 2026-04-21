from __future__ import annotations

import copy
import json
from functools import lru_cache
from pathlib import Path
from typing import Dict, Iterable, Mapping, MutableMapping, Sequence, Set, Tuple


REPO_ANALYSIS_ROOT = Path(__file__).resolve().parents[2]
RETRIEVAL_PROFILES_PATH = REPO_ANALYSIS_ROOT / "configs" / "retrieval_profiles.json"

DEFAULT_RETRIEVAL_PROFILES: Dict[str, object] = {
    "query_expansions": {},
    "concept_families": {},
    "discovery_profiles": {},
}


def _normalize_terms(values: Sequence[object] | object | None) -> Tuple[str, ...]:
    if values is None:
        return ()
    if isinstance(values, (str, bytes)):
        values = [values]
    normalized = []
    seen = set()
    for value in values:
        term = str(value or "").strip().lower()
        if not term or term in seen:
            continue
        seen.add(term)
        normalized.append(term)
    return tuple(normalized)


def _deep_merge(base: MutableMapping[str, object], override: Mapping[str, object]) -> MutableMapping[str, object]:
    for key, value in override.items():
        existing = base.get(key)
        if isinstance(existing, dict) and isinstance(value, Mapping):
            _deep_merge(existing, value)
        else:
            base[key] = value
    return base


@lru_cache(maxsize=1)
def load_retrieval_profiles() -> Dict[str, object]:
    payload = copy.deepcopy(DEFAULT_RETRIEVAL_PROFILES)
    if RETRIEVAL_PROFILES_PATH.exists():
        with RETRIEVAL_PROFILES_PATH.open("r", encoding="utf-8") as handle:
            loaded = json.load(handle)
        if isinstance(loaded, Mapping):
            _deep_merge(payload, loaded)
    return payload


def get_query_expansions() -> Dict[str, Tuple[str, ...]]:
    raw = load_retrieval_profiles().get("query_expansions", {})
    if not isinstance(raw, Mapping):
        return {}
    expansions: Dict[str, Tuple[str, ...]] = {}
    for key, values in raw.items():
        normalized_key = str(key or "").strip().lower()
        if not normalized_key:
            continue
        expansions[normalized_key] = _normalize_terms(values)
    return expansions


def get_concept_family(name: str) -> Set[str]:
    raw = load_retrieval_profiles().get("concept_families", {})
    if not isinstance(raw, Mapping):
        return set()
    values = raw.get(str(name or "").strip().lower())
    return set(_normalize_terms(values))


def get_discovery_profile(name: str) -> Dict[str, object]:
    raw_profiles = load_retrieval_profiles().get("discovery_profiles", {})
    if not isinstance(raw_profiles, Mapping):
        return {}
    raw = raw_profiles.get(str(name or "").strip().lower(), {})
    if not isinstance(raw, Mapping):
        return {}
    profile = {
        "query": str(raw.get("query") or "").strip(),
        "path_keywords": _normalize_terms(raw.get("path_keywords")),
        "anchor_queries": _normalize_terms(raw.get("anchor_queries")),
        "surface_keywords": _normalize_terms(raw.get("surface_keywords")),
        "focus_keywords": _normalize_terms(raw.get("focus_keywords")),
        "callable_keywords": _normalize_terms(raw.get("callable_keywords")),
        "deprioritize_keywords": _normalize_terms(raw.get("deprioritize_keywords")),
        "prefer_symbol_kinds": _normalize_terms(raw.get("prefer_symbol_kinds")),
        "implementation_path_keywords": _normalize_terms(raw.get("implementation_path_keywords")),
    }
    return profile


def clear_retrieval_profile_cache() -> None:
    load_retrieval_profiles.cache_clear()
