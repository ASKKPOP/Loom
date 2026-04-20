#!/usr/bin/env bash
# session-verify.sh — Run the verification suite (step 3 baseline + step 6 test).
# Exits 0 if everything passes, non-zero on any failure.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

fail=0

run() {
  local label="$1"; shift
  printf "→ %s\n" "$label"
  if "$@"; then
    printf "  ✓ pass\n"
  else
    printf "  ✗ FAIL\n"
    fail=1
  fi
}

# tasks.json must parse
if [ -f tasks/tasks.json ]; then
  run "tasks.json parses" python3 -c "import json; json.load(open('tasks/tasks.json'))"
fi

# Python packages (only run if they have code + tests)
if [ -f vmlx/pyproject.toml ]; then
  run "ruff vmlx/"    python3 -m ruff check vmlx/
  run "mypy vmlx/"    python3 -m mypy vmlx/
  if ls vmlx/tests/test_*.py >/dev/null 2>&1; then
    run "pytest vmlx/" python3 -m pytest vmlx/tests/ -q
  fi
fi

if [ -f loom/pyproject.toml ] || [ -d loom/gateway ] && ls loom/gateway/*.py >/dev/null 2>&1; then
  if [ -f loom/pyproject.toml ]; then
    run "ruff loom/"     python3 -m ruff check loom/
    run "mypy loom/"     python3 -m mypy loom/
  fi
  if ls loom/**/tests/test_*.py >/dev/null 2>&1; then
    run "pytest loom/" python3 -m pytest loom/ -q
  fi
fi

# Web
if [ -f loom/web/package.json ]; then
  run "tsc loom/web"  bash -c "cd loom/web && pnpm tsc --noEmit"
  run "test loom/web" bash -c "cd loom/web && pnpm test --run"
fi

if [ "$fail" -ne 0 ]; then
  echo
  echo "✗ Verification failed"
  exit 1
fi

echo
echo "✓ All verification checks passed"
