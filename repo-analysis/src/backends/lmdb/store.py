from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Dict, List, Optional, Sequence

import lmdb


@dataclass(frozen=True)
class LmdbMetadataStore:
    parsed_root: Path
    repo_name: str
    summary_root: Optional[Path] = None
    eval_root: Optional[Path] = None

    @property
    def metadata_path(self) -> Path:
        return self.parsed_root / self.repo_name / "metadata.lmdb"

    @property
    def eval_path(self) -> Optional[Path]:
        if self.eval_root is None:
            return None
        return self.eval_root / "eval.lmdb"

    def get_symbol(self, symbol_id: str) -> Optional[Dict[str, object]]:
        return self._get_json("symbol_by_id", symbol_id)

    def get_symbols(self, symbol_ids: Sequence[str]) -> Dict[str, Dict[str, object]]:
        env = self._metadata_env()
        db = env.open_db(b"symbol_by_id")
        results: Dict[str, Dict[str, object]] = {}
        with env.begin(db=db, write=False) as txn:
            for symbol_id in symbol_ids:
                if not symbol_id:
                    continue
                value = decode_json(txn.get(encode_key(symbol_id)))
                if isinstance(value, dict):
                    results[symbol_id] = value
        return results

    def resolve_qname(self, qname: str) -> List[str]:
        value = self._get_json("symbol_ids_by_qname", qname)
        return [str(item) for item in value] if isinstance(value, list) else []

    def resolve_name(self, name: str, *, repo: str | None = None) -> List[str]:
        value = self._get_json("symbol_ids_by_name", name)
        return [str(item) for item in value] if isinstance(value, list) else []

    def get_symbol_body(self, symbol_id: str) -> Optional[Dict[str, object]]:
        value = self._get_json("body_by_symbol_id", symbol_id)
        return value if isinstance(value, dict) else None

    def get_summary_by_id(self, summary_id: str) -> Optional[Dict[str, object]]:
        value = self._get_json("summary_by_id", summary_id)
        return value if isinstance(value, dict) else None

    def get_summary_by_path(self, path: str) -> List[Dict[str, object]]:
        value = self._get_json("summary_by_path", path)
        return [item for item in value if isinstance(item, dict)] if isinstance(value, list) else []

    def get_summary_by_symbol(self, symbol_id: str) -> List[Dict[str, object]]:
        value = self._get_json("summary_by_symbol_id", symbol_id)
        return [item for item in value if isinstance(item, dict)] if isinstance(value, list) else []

    def get_eval_case(self, case_name: str, fingerprint: str) -> Optional[Dict[str, object]]:
        env = self._eval_env()
        if env is None:
            return None
        db = env.open_db(b"eval_case_cache")
        with env.begin(db=db, write=False) as txn:
            payload = decode_json(txn.get(encode_key(f"case:{case_name}:{fingerprint}")))
            if payload is None:
                payload = decode_json(txn.get(encode_key(f"latest:{case_name}")))
        return payload if isinstance(payload, dict) else None

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
        env = self._ensure_eval_env()
        db = env.open_db(b"eval_case_cache")
        payload = {
            "repo": repo,
            "task_type": task_type,
            "query": query,
            "limit_value": int(limit_value),
            "artifact_fingerprint": artifact_fingerprint,
            "cache_fingerprint": cache_fingerprint,
            "bundle": bundle,
            "prompt_payload": prompt_payload,
            "bundle_score": bundle_score,
        }
        with env.begin(db=db, write=True) as txn:
            txn.put(encode_key(f"case:{case_name}:{cache_fingerprint}"), encode_value(payload))
            txn.put(encode_key(f"latest:{case_name}"), encode_value(payload))

    def _get_json(self, db_name: str, key: str) -> object | None:
        if not key:
            return None
        env = self._metadata_env()
        db = env.open_db(db_name.encode("utf-8"))
        with env.begin(db=db, write=False) as txn:
            return decode_json(txn.get(encode_key(key)))

    def _metadata_env(self) -> lmdb.Environment:
        return open_lmdb_env(str(self.metadata_path), readonly=True)

    def _eval_env(self) -> lmdb.Environment | None:
        if self.eval_path is None or not self.eval_path.exists():
            return None
        return open_lmdb_env(str(self.eval_path), readonly=False)

    def _ensure_eval_env(self) -> lmdb.Environment:
        if self.eval_path is None:
            raise FileNotFoundError("eval_root is not configured for LMDB eval cache")
        self.eval_path.mkdir(parents=True, exist_ok=True)
        return open_lmdb_env(str(self.eval_path), readonly=False)


@lru_cache(maxsize=32)
def open_lmdb_env(path: str, *, readonly: bool) -> lmdb.Environment:
    return lmdb.open(
        path,
        subdir=True,
        readonly=readonly,
        lock=not readonly,
        create=not readonly,
        max_dbs=16,
        readahead=readonly,
        map_size=1 << 30,
    )


def encode_key(value: str) -> bytes:
    return value.encode("utf-8")


def encode_value(value: object) -> bytes:
    return json.dumps(value, sort_keys=True).encode("utf-8")


def decode_json(raw: bytes | None) -> object | None:
    if raw is None:
        return None
    return json.loads(raw.decode("utf-8"))
