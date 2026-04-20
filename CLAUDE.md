# CLAUDE.md — Loom Agent Entry Point

You are working on **Loom**: a local AI platform for Mac Silicon that integrates customer business APIs. Subsystems: `vmlx/` (MLX serving engine) and `loom/` (product).

## Before you do anything

Run the session-start protocol:

```bash
./scripts/session-start.sh
```

This orients you: reads recent git history, loads progress notes, shows the task list, and verifies the baseline.

## Core rules

1. **One task per session.** Pick the highest-priority incomplete item in `tasks/tasks.json`. Don't grab multiple.
2. **Verify before building.** Baseline must pass before any changes. See [docs/harness/session-protocol.md](docs/harness/session-protocol.md).
3. **Persist state to disk.** Context is ephemeral. Update `tasks/tasks.json`, append to `notes/progress.md`, commit descriptively.
4. **Full implementations only — no placeholders.** Stubs, `TODO`, `pass`, or fake returns are rejected. If scope is too big, split the task.
5. **Test through the UI/API, not just type checks.** A passing type checker is not a working feature. See [docs/harness/conventions.md](docs/harness/conventions.md#testing).
6. **Repo is the source of truth.** If a fact isn't in the repo, it effectively doesn't exist next session. Write it down.
7. **Update this harness when you learn something.** If commands aren't obvious, write them down. If a rule here is wrong, fix it.

## Where to read next (progressive disclosure)

| If you need to… | Read |
|---|---|
| Understand product scope | [docs/PRD.md](docs/PRD.md) |
| Understand customer API integration model | [docs/schemas/api-registration.md](docs/schemas/api-registration.md) |
| Run a session correctly | [docs/harness/session-protocol.md](docs/harness/session-protocol.md) |
| Code quality rules | [docs/harness/conventions.md](docs/harness/conventions.md) |
| Task format | [tasks/README.md](tasks/README.md) |
| Multi-agent pattern (future) | [docs/harness/planner.md](docs/harness/planner.md), [generator.md](docs/harness/generator.md), [evaluator.md](docs/harness/evaluator.md) |

## Current phase

**Phase 0 — vMLX Foundation.** See `tasks/tasks.json`. Goal: ship vMLX 0.1 with continuous batching scheduler, paged KV cache, and OpenAI-compatible API.

## Session exit

Before ending:
```bash
./scripts/session-end.sh "<one-line summary>"
```
This: runs verification, commits staged changes with your message, appends a progress note, and prints the next task.

## Commit style

```
<type>(<scope>): <subject>

<body explaining WHY, not what the diff shows>
```

Types: `feat`, `fix`, `refactor`, `docs`, `chore`, `test`, `perf`
Scopes: `vmlx`, `loom`, `harness`, `docs`

Example: `feat(vmlx): add paged KV cache block allocator`

## Non-negotiables

- ❌ Never commit secrets. Credentials go in macOS Keychain, never in files.
- ❌ Never use leaked third-party source code for "ideas" or anything else. Architecture inspiration comes from public papers, open specs, and OSS projects listed in [docs/PRD.md](docs/PRD.md#16-references).
- ❌ Never skip verification with `--no-verify`, `--force`, etc. unless the user explicitly asks.
- ✅ Always use legitimate auth (gh CLI, SSH) — never paste tokens into chat or URLs.
