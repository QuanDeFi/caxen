from __future__ import annotations

from pathlib import Path
from typing import Dict

from backends.ryugraph.loader import load_ryugraph_database


def write_graph_database(
    output_root: Path,
    repo_name: str,
    payload: Dict[str, object],
) -> Path:
    return load_ryugraph_database(output_root, repo_name, payload)
