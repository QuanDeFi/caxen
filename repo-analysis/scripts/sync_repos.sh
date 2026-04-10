#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT_DIR"

assert_gitlink() {
  local path="$1"
  local mode
  mode="$(git ls-files --stage -- "$path" | awk '{print $1}' | head -n1)"
  if [[ "$mode" != "160000" ]]; then
    echo "ERROR: $path is not recorded as a gitlink/submodule in the superproject index." >&2
    echo "       Current mode: ${mode:-<missing>}" >&2
    exit 1
  fi
}

assert_initialized_submodule() {
  local path="$1"
  local top
  top="$(git -C "$path" rev-parse --show-toplevel 2>/dev/null || true)"
  if [[ "$top" != "$ROOT_DIR/$path" ]]; then
    echo "ERROR: $path is not initialized as a standalone submodule checkout." >&2
    echo "       Run: git submodule update --init --recursive" >&2
    exit 1
  fi
}

assert_expected_head() {
  local path="$1"
  local expected
  local current
  expected="$(git ls-files --stage -- "$path" | awk '{print $2}' | head -n1)"
  current="$(git -C "$path" rev-parse HEAD)"
  if [[ "$expected" != "$current" ]]; then
    echo "ERROR: $path HEAD does not match the gitlink recorded in the superproject." >&2
    echo "       expected: $expected" >&2
    echo "       current:  $current" >&2
    exit 1
  fi
}

if [[ "${1:-}" == "--verify" ]]; then
  echo "Verifying upstream repositories are recorded and initialized as submodules..."
  [[ -f .gitmodules ]] || { echo "ERROR: .gitmodules not found" >&2; exit 1; }

  assert_gitlink "carbon"
  assert_gitlink "yellowstone-vixen"
  assert_initialized_submodule "carbon"
  assert_initialized_submodule "yellowstone-vixen"
  assert_expected_head "carbon"
  assert_expected_head "yellowstone-vixen"

  echo "carbon gitlink: OK"
  echo "yellowstone-vixen gitlink: OK"
  echo "carbon ref: $(git -C carbon rev-parse HEAD)"
  if git -C carbon show-ref --verify --quiet refs/remotes/origin/v1.0-rc; then
    echo "carbon origin/v1.0-rc: $(git -C carbon rev-parse origin/v1.0-rc)"
  fi
  echo "carbon branch: $(git -C carbon branch --show-current || true)"
  echo "yellowstone-vixen ref: $(git -C yellowstone-vixen rev-parse HEAD)"
  exit 0
fi

git submodule sync --recursive
git submodule update --init --recursive
