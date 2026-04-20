# Loom Harness

The **harness** is the set of files, scripts, and conventions that make AI agents effective and honest collaborators on this repo. Based on [celesteanders/harness best-practices](https://github.com/celesteanders/harness/blob/main/docs/best-practices.md).

## Philosophy

1. **Context is ephemeral; the repo is eternal.** Anything the agent needs next session must live on disk.
2. **One task per session.** Focus + recoverability beat speed.
3. **Verify before building.** Baseline must pass first.
4. **Single-agent first.** We do not run planner/generator/evaluator as separate processes yet — they are documented roles the same agent adopts sequentially. Multi-agent pattern activates only if the single-agent loop demonstrably ceilings out.
5. **Simplicity relentlessly.** Add harness complexity only when it solves a pain we've hit.

## What's in the harness

| File | Purpose |
|---|---|
| [CLAUDE.md](../../CLAUDE.md) | Entry point — every session starts here |
| [session-protocol.md](session-protocol.md) | 8-step session lifecycle |
| [conventions.md](conventions.md) | Code quality rules, testing, documentation |
| [planner.md](planner.md) | Planner role — spec-writing phase |
| [generator.md](generator.md) | Generator role — implementation phase |
| [evaluator.md](evaluator.md) | Evaluator role — QA phase |
| [../../tasks/tasks.json](../../tasks/tasks.json) | Authoritative task list |
| [../../tasks/README.md](../../tasks/README.md) | Task schema |
| [../../notes/progress.md](../../notes/progress.md) | Running log across sessions |
| [../../scripts/session-start.sh](../../scripts/session-start.sh) | Orient + baseline |
| [../../scripts/session-verify.sh](../../scripts/session-verify.sh) | Run verification suite |
| [../../scripts/session-end.sh](../../scripts/session-end.sh) | Verify + commit + notes |

## When to update the harness

Update it whenever you learn something the next agent needs. Examples:
- You had to run a non-obvious command three times → add it to `conventions.md` or a script
- A rule in CLAUDE.md is misleading → rewrite it
- A task was broken down incorrectly → fix the task schema

Harness changes are first-class work. Commit them with `chore(harness): ...`.

## When to NOT add to the harness

- Information that only matters to this one session (use `notes/progress.md` instead)
- Rules no one will enforce — if a lint/test can't catch it, don't write it down as a rule
- Aspirational architecture that doesn't exist yet (put in `docs/` proposals, not harness)
