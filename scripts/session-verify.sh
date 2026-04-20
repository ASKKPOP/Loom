#!/usr/bin/env bash
# session-verify.sh — Run the verification suite (step 3 baseline + step 6 test).
# Exits 0 if everything passes, non-zero on any failure.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

# Prefer the project venv; fall back to system python3 for tasks.json-only checks.
if [ -x "$ROOT/.venv/bin/python" ]; then
  PY="$ROOT/.venv/bin/python"
else
  PY="python3"
fi

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

# vMLX package (only run if installed in the venv)
if [ -f vmlx/pyproject.toml ] && "$PY" -c "import vmlx" >/dev/null 2>&1; then
  run "ruff vmlx/"    "$PY" -m ruff check vmlx/
  run "mypy vmlx/src/" "$PY" -m mypy vmlx/src/
  run "pytest vmlx/" bash -c "cd vmlx && '$PY' -m pytest -q"
fi

# Loom gateway (only run when it actually has code)
if [ -f loom/pyproject.toml ] && "$PY" -c "import loom" >/dev/null 2>&1; then
  run "ruff loom/"  "$PY" -m ruff check loom/
  run "mypy loom/"  "$PY" -m mypy loom/
  run "pytest loom/" "$PY" -m pytest loom/ -q
fi

# Loom web
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
