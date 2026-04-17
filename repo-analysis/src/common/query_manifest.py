from __future__ import annotations

import json
from pathlib import Path
from typing import Dict

from symbols.indexer import timestamp_now


SCHEMA_VERSION = "0.1.0"


def load_query_manifest(parsed_root: Path, repo_name: str) -> Dict[str, object]:
    path = manifest_path(parsed_root, repo_name)
    if not path.exists():
        return {
            "schema_version": SCHEMA_VERSION,
            "repo": repo_name,
            "generated_at": timestamp_now(),
            "artifacts": {},
            "features": {},
            "build": {},
        }
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def update_query_manifest(
    parsed_root: Path,
    repo_name: str,
    *,
    artifacts: Dict[str, object] | None = None,
    features: Dict[str, object] | None = None,
    build: Dict[str, object] | None = None,
) -> Dict[str, object]:
    payload = load_query_manifest(parsed_root, repo_name)
    payload["schema_version"] = SCHEMA_VERSION
    payload["repo"] = repo_name
    payload["generated_at"] = timestamp_now()
    merge_section(payload.setdefault("artifacts", {}), artifacts or {})
    merge_section(payload.setdefault("features", {}), features or {})
    merge_section(payload.setdefault("build", {}), build or {})
    write_query_manifest(parsed_root, repo_name, payload)
    return payload


def write_query_manifest(parsed_root: Path, repo_name: str, payload: Dict[str, object]) -> None:
    target = manifest_path(parsed_root, repo_name)
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, sort_keys=False)
        handle.write("\n")


def manifest_path(parsed_root: Path, repo_name: str) -> Path:
    return parsed_root / repo_name / "query_manifest.json"


def merge_section(target: Dict[str, object], updates: Dict[str, object]) -> None:
    for key, value in updates.items():
        if value is None:
            target.pop(key, None)
            continue
        target[key] = value
