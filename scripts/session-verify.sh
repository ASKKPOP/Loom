#!/usr/bin/env bash
# session-verify.sh — Run the verification suite.
# Exits 0 only if every applicable check passed. No silent passes:
# if a package's pyproject.toml exists but the package isn't importable
# we fail loudly rather than skip.
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
ran=0

run() {
  local label="$1"; shift
  printf "→ %s\n" "$label"
  ran=$((ran + 1))
  if "$@"; then
    printf "  ✓ pass\n"
  else
    printf "  ✗ FAIL\n"
    fail=1
  fi
}

# A package with a pyproject.toml MUST be importable under $PY.
# If it is not, the developer's venv is broken or packages aren't installed.
# That's a setup error, not a skip.
require_importable() {
  local pyproject="$1" import_name="$2" pkg_dir
  pkg_dir="$(dirname "$pyproject")"
  if [ ! -f "$pyproject" ]; then
    return 1  # package doesn't exist at all → caller skips
  fi
  if "$PY" -c "import $import_name" >/dev/null 2>&1; then
    return 0
  fi
  printf "→ %s\n" "import $import_name"
  printf "  ✗ FAIL — '%s' exists but '%s' is not importable.\n" "$pyproject" "$import_name"
  printf "         Fix: %s -m pip install -e '%s[dev]'\n" "$PY" "$pkg_dir"
  fail=1
  ran=$((ran + 1))
  return 1
}

# tasks.json must parse
if [ -f tasks/tasks.json ]; then
  run "tasks.json parses" python3 -c "import json; json.load(open('tasks/tasks.json'))"
fi

# vMLX package.
# Metal-tagged tests are skipped here (slow, require model weights on GPU).
# Run them explicitly with:  cd vmlx && ../.venv/bin/python -m pytest -m metal
if [ -f vmlx/pyproject.toml ]; then
  if require_importable vmlx/pyproject.toml vmlx; then
    run "ruff vmlx/"              "$PY" -m ruff check vmlx/
    run "mypy vmlx/src/"           "$PY" -m mypy vmlx/src/
    run "pytest vmlx/ (non-metal)" bash -c "cd vmlx && '$PY' -m pytest -q -m 'not metal'"
  fi
fi

# Loom gateway
if [ -f loom/gateway/pyproject.toml ]; then
  if require_importable loom/gateway/pyproject.toml loom.gateway; then
    run "ruff loom/gateway/"         "$PY" -m ruff check loom/gateway/src/ loom/gateway/tests/
    run "mypy loom/gateway/"          "$PY" -m mypy loom/gateway/src/
    run "pytest loom/gateway/ (unit)" bash -c "cd loom/gateway && '$PY' -m pytest -q"
  fi
fi

# Loom web
if [ -f loom/web/package.json ]; then
  run "tsc loom/web"  bash -c "cd loom/web && pnpm tsc --noEmit"
  run "test loom/web" bash -c "cd loom/web && pnpm test --run"
fi

if [ "$ran" -eq 0 ]; then
  echo
  echo "✗ No checks ran — verify script has nothing to verify."
  exit 1
fi

if [ "$fail" -ne 0 ]; then
  echo
  echo "✗ Verification failed ($ran checks attempted)"
  exit 1
fi

echo
echo "✓ All $ran verification checks passed"
