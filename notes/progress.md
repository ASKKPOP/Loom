# Progress Notes

Running log across sessions. Most recent at the bottom. One block per session.

Format:
```md
## YYYY-MM-DD — <task-id>: <short title>
- What I did: <one line>
- How I verified: <one line>
- Surprises / follow-ups: <bullets or "none">
```

---

## 2026-04-20 — harness-bootstrap: initial scaffolding + PRD + API schema + harness
- What I did: Created repo scaffolding (vmlx/, loom/, docs/, tasks/, scripts/, notes/). Wrote PRD and API registration schema. Built agent harness per celesteanders/harness best-practices: CLAUDE.md entry point, docs/harness/ (session-protocol, conventions, planner/generator/evaluator roles), tasks/tasks.json with Phase 0 vMLX tasks, scripts/ for session lifecycle.
- How I verified: Directory structure inspected; tasks.json parses as valid JSON; scripts have expected shebang + bash -n implicit via set -euo pipefail.
- Surprises / follow-ups:
  - gh CLI was missing, installed via /opt/homebrew/bin/brew — user needs to add brew to PATH and run `gh auth login` before push
  - Git committer identity is auto-detected (eklotho) — user should set their own
  - Leaked GitHub token in chat (handled — advised user to revoke and switch to gh auth)
  - Not yet pushed to origin (awaiting auth)

## 2026-04-20 — vmlx-001: bootstrap vmlx Python package skeleton (6 tests passing, ruff+mypy clean)
- Branch: main
- Commits this session:
  - 4fb4b1e feat(vmlx): vmlx-001 bootstrap Python package skeleton
  - d91b8e2 chore(tasks): mark vmlx-001 in_progress; add local Claude permissions
  - 934b423 chore(harness): add agent harness per celesteanders/harness best-practices
  - 56990f7 chore: initial repo scaffolding, PRD, and API registration schema

## 2026-04-20 — vmlx-002: SingleRequestEngine baseline — 5 unit + 3 metal tests passing, real Qwen 0.5B inference on M4
- Branch: main
- Commits this session:
  - ec8fcf8 feat(vmlx): vmlx-002 SingleRequestEngine — baseline MLX inference
  - 099b52c docs(harness): session note — vmlx-001: bootstrap vmlx Python package skeleton (6 tests passing, ruff+mypy clean)
  - 4fb4b1e feat(vmlx): vmlx-001 bootstrap Python package skeleton
  - d91b8e2 chore(tasks): mark vmlx-001 in_progress; add local Claude permissions
  - 934b423 chore(harness): add agent harness per celesteanders/harness best-practices

## 2026-04-21 — vmlx-003: benchmark harness + ROADMAP + PHILOSOPHY (29 unit, 4 metal passing; first run: 241 tok/s Qwen-0.5B)
- Branch: main
- Commits this session:
  - 71fa742 feat(vmlx): vmlx-003 benchmark harness + top-level docs
  - 6761121 docs(harness): session note — vmlx-002: SingleRequestEngine baseline — 5 unit + 3 metal tests passing, real Qwen 0.5B inference on M4
  - ec8fcf8 feat(vmlx): vmlx-002 SingleRequestEngine — baseline MLX inference
  - 099b52c docs(harness): session note — vmlx-001: bootstrap vmlx Python package skeleton (6 tests passing, ruff+mypy clean)
  - 4fb4b1e feat(vmlx): vmlx-001 bootstrap Python package skeleton
