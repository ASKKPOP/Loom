# Session Protocol

Every session — human-led or agent-led — follows this eight-step lifecycle.

```
┌────────────────────────────────────────────────┐
│ 1. Orient   →  2. Setup   →  3. Verify baseline│
│                                    │           │
│                                    ▼           │
│ 8. Exit    ←  7. Update state  ←  4. Select    │
│                                    │           │
│                                    ▼           │
│             5. Implement  →  6. Test           │
└────────────────────────────────────────────────┘
```

## 1. Orient

```bash
./scripts/session-start.sh
```

Reads:
- Last 10 git commits (`git log --oneline -10`)
- Tail of `notes/progress.md`
- Open tasks from `tasks/tasks.json`
- Current branch & uncommitted changes

**Output:** you know what happened last, what's in flight, and what's next.

## 2. Setup

Initialization scripts run automatically as part of `session-start.sh`. Extend `scripts/session-start.sh` when new services/tools need bootstrapping — don't require the next agent to remember.

Typical setup:
- Ensure Python venv / node_modules exist
- Start local dev services if the current task needs them
- Warm model cache if testing inference

## 3. Verify baseline

```bash
./scripts/session-verify.sh
```

Runs the project's verification suite. **Must pass before you change anything.**

> **CI parity:** `.github/workflows/ci.yml` invokes this exact same script on macos-15 arm64 for every push to `main` and every PR. If verify passes locally and fails on CI (or vice versa), that's a real bug in the script — fix it, don't patch around it.

If it fails on entry: the previous session left broken state. First task of this session becomes *fix the baseline*. Do not pile new work on a broken baseline.

Verification suite (as the project grows):
- `vmlx/` — `pytest vmlx/tests/`, `ruff check vmlx/`, `mypy vmlx/`
- `loom/` — `pytest loom/tests/`, frontend `pnpm test`, typecheck
- Integration smoke test — bring up vMLX + gateway + one sample API call

## 4. Select one task

- Open `tasks/tasks.json`
- Pick the highest `priority` item with `status: "todo"` and all `depends_on` satisfied
- Set its status to `in_progress`
- **Commit the status change** — the task board is shared state

Do **not** pick multiple tasks. If the chosen task feels too big mid-session, split it before implementing.

## 5. Implement

- Work on the one task
- Follow [conventions.md](conventions.md)
- **No placeholder code.** Every function written must be fully implemented. If you can't implement it in one session, split the task instead.
- Commit progress as you go (not just at the end) — small commits are recovery points
- If you discover unrelated bugs, add them to `tasks/tasks.json` as new `todo` items. Do **not** fix them in this session.

## 6. Test

Every task has `acceptance_criteria`. Verify each one:
- **Automated:** add tests to the verification suite; they run every session after
- **Manual (for UI/API work):** actually click through or curl the endpoint; a passing typecheck is not a passing test
- **Performance:** if the task has a perf target, run the benchmark

If any criterion fails, either fix now or split the unsatisfied piece into a new task.

## 7. Update state

- Mark task `status: "done"` in `tasks/tasks.json`
- Append a note to `notes/progress.md` in this format:

  ```md
  ## 2026-04-20 — <task-id>: <short title>
  - What I did: <one line>
  - How I verified: <one line>
  - Surprises / follow-ups: <bullets or "none">
  ```
- Commit with descriptive message (see CLAUDE.md commit style)

## 8. Clean exit

```bash
./scripts/session-end.sh "<one-line summary>"
```

This re-runs verification (catches last-minute breakage), commits if needed, and prints the next task for the next session.

If verification fails at exit: **do not force-push, do not `git reset --hard`**. Commit current state on a `wip/<task-id>` branch, note the breakage in `notes/progress.md`, and let the next session fix it.

## Rules of thumb

- If you find yourself running the same diagnostic command more than twice, add it to a script and document it.
- If the baseline fails mid-session from your changes, **stop and fix** — don't keep piling.
- If you're tempted to "just quickly also…" — write it as a new task instead.
