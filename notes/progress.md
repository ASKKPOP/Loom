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

## 2026-04-21 — vmlx-004: OpenAI-compatible /v1/chat/completions (streaming + non-streaming) — openai SDK works unchanged
- Branch: main
- Commits this session:
  - a756424 feat(vmlx): vmlx-004 OpenAI-compatible /v1/chat/completions endpoint
  - afd8d0c docs(harness): session note — vmlx-003: benchmark harness + ROADMAP + PHILOSOPHY (29 unit, 4 metal passing; first run: 241 tok/s Qwen-0.5B)
  - 71fa742 feat(vmlx): vmlx-003 benchmark harness + top-level docs
  - 6761121 docs(harness): session note — vmlx-002: SingleRequestEngine baseline — 5 unit + 3 metal tests passing, real Qwen 0.5B inference on M4
  - ec8fcf8 feat(vmlx): vmlx-002 SingleRequestEngine — baseline MLX inference

## 2026-04-21 — vmlx-005: continuous batching — 4.09× throughput at N=8, faster TTFT under load, 100-req stress in 1.5s
- Branch: main
- Commits this session:
  - 2b5f0c9 feat(vmlx): vmlx-005 continuous batching scheduler (BatchingEngine)
  - 4995533 docs(harness): session note — vmlx-004: OpenAI-compatible /v1/chat/completions (streaming + non-streaming) — openai SDK works unchanged
  - a756424 feat(vmlx): vmlx-004 OpenAI-compatible /v1/chat/completions endpoint
  - afd8d0c docs(harness): session note — vmlx-003: benchmark harness + ROADMAP + PHILOSOPHY (29 unit, 4 metal passing; first run: 241 tok/s Qwen-0.5B)
  - 71fa742 feat(vmlx): vmlx-003 benchmark harness + top-level docs

## 2026-04-21 — loom-001: FastAPI gateway scaffold with /health and vMLX proxy
- What I did: Created loom/gateway as installable Python package (src/ layout). FastAPI app with /health, CORSMiddleware, JSON-line structured logging. Async httpx proxy for all /v1/* routes — SSE streaming pass-through preserved for chat completions. Config from env: LOOM_BIND (127.0.0.1), LOOM_PORT (8080), LOOM_VMLX_URL (http://127.0.0.1:8000), LOOM_LOG_LEVEL. loom-gateway CLI entrypoint. Updated session-verify.sh to cover gateway.
- How I verified: 11 unit tests pass (respx-mocked backend), ruff + mypy clean on src/ and tests/. Manual: `uvicorn loom.gateway.main:app` starts; /health returns 200.
- Surprises / follow-ups:
  - FastAPI needs `response_model=None` on Union-return endpoints — raised FastAPIError otherwise.
  - TestClient only triggers lifespan when used as a context manager; added `http_client` injection parameter to `create_app()` so tests can bypass the lifespan and supply a mock-transport httpx client directly.
- Commits this session: ebca530 feat(loom): loom-001 FastAPI gateway scaffold with /health and vMLX proxy

## 2026-04-21 — harness-001: CI parity via GitHub Actions
- What I did: Added .github/workflows/ci.yml on macos-15 (arm64; mlx is Apple Silicon only) that creates .venv, installs vmlx + loom/gateway with dev extras, then invokes `bash scripts/session-verify.sh` — so the local verify path IS the CI verify path. Hardened session-verify.sh against silent passes: added `ran` counter (fails if zero checks execute) and require_importable() guard that fails loudly if a package's pyproject.toml exists but the package isn't installed.
- How I verified: First CI run completed green in 1m40s (run 24756610203). All 7 checks executed and reported in the CI log, matching local session-verify output byte-for-byte.
- Surprises / follow-ups:
  - macos-15 runners cold-install mlx wheels in ~10s; session-verify itself ran in ~30s; most CI wall time is pip install.
  - Metal-tagged tests remain skipped in CI — model weight downloads are too heavy. Gated explicitly on local M-series hardware.
- Commits this session: 7d2ab06 chore(harness): wire session-verify to CI parity (harness-001)

## 2026-04-22 — loom-002: web chat UI shipped (24/24 vitest, 10/10 verify, ⌘Enter global shortcut fixed, browser smoke passed)
- Branch: main
- Commits this session:
  - 2e3d1ec feat(loom): loom-002 web chat UI — streaming, history, markdown
  - 7229af5 chore(tasks): add loom-002 (web chat UI) as in_progress
  - 6371bd0 docs(harness): session notes for loom-001 + harness-001, CI badge, parity note
  - f83cc4b chore(harness): wire session-verify to CI parity (harness-001)
  - d46acef loom-001: FastAPI gateway scaffold with /health and vMLX proxy
