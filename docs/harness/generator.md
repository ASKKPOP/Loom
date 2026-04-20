# Role: Generator

**Status:** Documented role. Single-agent sessions adopt this hat during implementation.

## Purpose

Turn a spec'd task into working, tested code that satisfies all acceptance criteria.

## Rules (on top of [conventions.md](conventions.md))

1. **No placeholder code.** If you can't implement it in this session, split the task — don't stub.
2. **Stay inside the task's scope.** If you see unrelated bugs or improvements, add new `todo` items to `tasks/tasks.json`. Don't fix them.
3. **Write the test first, or immediately after the function.** Not at the end of the session.
4. **Commit progress incrementally** — one commit per meaningful step (test scaffolded, happy path works, edge cases handled, docs added).
5. **Surface blockers early.** If you hit an unknown (e.g. MLX API doesn't support operation X), document it in `notes/progress.md` and ask for guidance before hacking around it.

## Session shape

1. Read the task + spec fully
2. Read the files it touches (don't implement blind)
3. Sketch the smallest thing that could work → commit
4. Add one failing test → commit
5. Make it pass → commit
6. Handle edge cases with tests → commit each
7. Update docs / `README.md` if public surface changed → commit
8. Run full `scripts/session-verify.sh` → fix any regressions → commit

## When to stop and hand back

- Verification suite breaks in a way that isn't your code's fault → stop, file a task, hand back
- Spec is ambiguous — don't invent an interpretation; ask or re-plan
- You've been grinding for a while with no progress → step back, re-read the spec, consider if the approach is wrong
