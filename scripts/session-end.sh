#!/usr/bin/env bash
# session-end.sh — Re-verify, commit staged changes, append progress note.
# Usage: ./scripts/session-end.sh "<task-id>: <one-line summary>"
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

if [ "${1:-}" = "" ]; then
  echo "usage: $0 \"<task-id>: <one-line summary>\""
  exit 2
fi
SUMMARY="$1"

cyan() { printf "\033[36m%s\033[0m\n" "$1"; }
red() { printf "\033[31m%s\033[0m\n" "$1"; }
green() { printf "\033[32m%s\033[0m\n" "$1"; }

cyan "── Verify before exit ──"
if ! "$ROOT/scripts/session-verify.sh"; then
  red "Verification failed. Do NOT force exit. Fix or commit to wip/ branch manually."
  exit 1
fi
echo

cyan "── Append progress note ──"
mkdir -p notes
{
  echo
  echo "## $(date -u +%Y-%m-%d) — ${SUMMARY}"
  echo "- Branch: $(git branch --show-current)"
  echo "- Commits this session:"
  # commits since last progress-marker tag (fallback: last 5)
  git log --oneline -5 | sed 's/^/  - /'
} >> notes/progress.md
green "  ✓ appended to notes/progress.md"
echo

cyan "── Commit progress note if changed ──"
if ! git diff --quiet notes/progress.md 2>/dev/null; then
  git add notes/progress.md
  git commit -m "docs(harness): session note — ${SUMMARY}"
  green "  ✓ committed progress note"
else
  green "  (no progress note changes to commit)"
fi
echo

cyan "── Next task ──"
if [ -f tasks/tasks.json ]; then
  python3 - <<'PY'
import json
from pathlib import Path
data = json.loads(Path("tasks/tasks.json").read_text())
tasks = data.get("tasks", [])
done = {t["id"] for t in tasks if t["status"] == "done"}
priority_rank = {"P0": 0, "P1": 1, "P2": 2}
candidates = [
    t for t in tasks
    if t["status"] == "todo" and all(dep in done for dep in t.get("depends_on", []))
]
if not candidates:
    print("  ✓ No unblocked todo tasks remaining")
else:
    candidates.sort(key=lambda t: (
        priority_rank.get(t.get("priority", "P2"), 9),
        t.get("phase", 99),
        t.get("created_at", ""),
    ))
    t = candidates[0]
    print(f"  [{t['priority']}] {t['id']} — {t['title']}")
PY
fi
echo
green "✓ Session ended cleanly"
