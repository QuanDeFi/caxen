from __future__ import annotations

import json
from pathlib import Path
from typing import Dict


def write_ryugraph_payload(output_root: Path, repo_name: str, payload: Dict[str, object]) -> Path:
    """Compatibility sink for the PR-3 graph backend cutover.

    We keep the canonical graph artifact in SQLite for now and also persist a
    backend-oriented JSON payload that can be consumed by future native graph
    loaders without requiring SQLite schema knowledge.
    """

    repo_output = output_root / repo_name
    repo_output.mkdir(parents=True, exist_ok=True)
    target = repo_output / "ryugraph.json"
    target.write_text(json.dumps(payload, separators=(",", ":")), encoding="utf-8")
    return target
