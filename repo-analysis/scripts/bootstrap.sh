#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR/.."

echo "Bootstrapping repo-analysis workspace..."
mkdir -p data/{raw,parsed,graph,search,summaries,eval}
for d in raw parsed graph search summaries eval; do
  touch "data/$d/.gitkeep"
done

if command -v python3 >/dev/null 2>&1; then
  echo "python3: $(python3 --version 2>&1)"
else
  echo "WARNING: python3 not found; inventory tooling will not run." >&2
fi

if command -v cargo >/dev/null 2>&1; then
  echo "cargo: $(cargo --version 2>&1)"
else
  echo "WARNING: cargo not found; upstream Rust builds cannot be verified locally." >&2
fi

if command -v node >/dev/null 2>&1; then
  echo "node: $(node --version 2>&1)"
else
  echo "WARNING: node not found; Carbon package workspace tooling is unavailable locally." >&2
fi

echo "Done."
