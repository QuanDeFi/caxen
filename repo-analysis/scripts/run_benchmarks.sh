#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

"$SCRIPT_DIR/parse_repos.sh"
"$SCRIPT_DIR/build_index.sh"
"$SCRIPT_DIR/build_search.sh"
"$SCRIPT_DIR/build_embeddings.sh"
"$SCRIPT_DIR/export_summaries.sh"

PYTHON_BIN="${PYTHON_BIN:-python3}"

exec "$PYTHON_BIN" "$SCRIPT_DIR/../src/cli/main.py" run-benchmarks \
  --search-root "$SCRIPT_DIR/../data/search" \
  --graph-root "$SCRIPT_DIR/../data/graph" \
  --parsed-root "$SCRIPT_DIR/../data/parsed" \
  --eval-root "$SCRIPT_DIR/../data/eval" \
  "$@"
