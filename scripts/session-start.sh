#!/usr/bin/env bash
# session-start.sh — Orient + Setup + Verify baseline (steps 1-3 of the session protocol)
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

cyan() { printf "\033[36m%s\033[0m\n" "$1"; }
yellow() { printf "\033[33m%s\033[0m\n" "$1"; }
red() { printf "\033[31m%s\033[0m\n" "$1"; }
green() { printf "\033[32m%s\033[0m\n" "$1"; }

cyan "═══ Loom session-start ═══"
echo

# ─── 1. Orient ──────────────────────────────────────────────────────────
cyan "── Recent commits (last 10) ──"
git log --oneline -10 2>/dev/null || yellow "  (no commits yet)"
echo

cyan "── Uncommitted changes ──"
if [ -n "$(git status --porcelain 2>/dev/null)" ]; then
  git status --short
  yellow "  ⚠  Uncommitted changes present — review before starting new work"
else
  green "  (clean working tree)"
fi
echo

cyan "── Tail of notes/progress.md ──"
if [ -f notes/progress.md ]; then
  tail -30 notes/progress.md
else
  yellow "  (notes/progress.md not yet created)"
fi
echo

cyan "── Next task (highest priority, unblocked) ──"
if [ -f tasks/tasks.json ]; then
  python3 - <<'PY' || yellow "  (could not parse tasks.json)"
import json, sys
from pathlib import Path

data = json.loads(Path("tasks/tasks.json").read_text())
tasks = data.get("tasks", [])
done = {t["id"] for t in tasks if t["status"] == "done"}
priority_rank = {"P0": 0, "P1": 1, "P2": 2}

candidates = [
    t for t in tasks
    if t["status"] == "todo"
    and all(dep in done for dep in t.get("depends_on", []))
]
if not candidates:
    print("  ✓ No unblocked todo tasks — check in-progress or blocked items")
    sys.exit(0)

candidates.sort(key=lambda t: (
    priority_rank.get(t.get("priority", "P2"), 9),
    t.get("phase", 99),
    t.get("created_at", ""),
))
t = candidates[0]
print(f"  [{t['priority']}] {t['id']} — {t['title']}")
print(f"       scope={t['scope']} phase={t['phase']}")
print(f"       {t.get('spec', '')[:120]}...")
PY
else
  yellow "  (tasks/tasks.json not yet created)"
fi
echo

# ─── 2. Setup ───────────────────────────────────────────────────────────
cyan "── Setup checks ──"
command -v python3 >/dev/null 2>&1 && green "  ✓ python3: $(python3 --version)" || red "  ✗ python3 not found"
command -v git >/dev/null 2>&1 && green "  ✓ git: $(git --version)" || red "  ✗ git not found"
if command -v gh >/dev/null 2>&1; then
  green "  ✓ gh: $(gh --version | head -1)"
elif [ -x /opt/homebrew/bin/gh ]; then
  green "  ✓ gh: $(/opt/homebrew/bin/gh --version | head -1) (not in PATH)"
else
  yellow "  - gh CLI not installed (optional, needed for GitHub ops)"
fi
echo

# ─── 3. Verify baseline ─────────────────────────────────────────────────
cyan "── Verify baseline ──"
if [ -x "$ROOT/scripts/session-verify.sh" ]; then
  if "$ROOT/scripts/session-verify.sh"; then
    green "  ✓ Baseline OK"
  else
    red "  ✗ Baseline failed — first task of this session is to fix it"
    exit 1
  fi
else
  yellow "  - session-verify.sh not executable; skipping"
fi
echo

cyan "═══ Ready. Remember: one task per session. ═══"
