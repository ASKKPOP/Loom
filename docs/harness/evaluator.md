# Role: Evaluator

**Status:** Documented role. In single-agent mode, adopt this hat at the end of a session as an honesty check. Becomes a separate agent only if single-agent self-evaluation proves unreliable.

## Purpose

Review the session's work as a user would — not as the person who just wrote it. Prevent "passing the typecheck = done" thinking.

## When to adopt this hat

After step 6 (Test) of the session protocol, before updating state.

## Evaluation checklist

For the task just completed:

1. **Does the acceptance criteria actually pass?**
   - Re-read each criterion
   - For UI/API work: actually hit the endpoint or click the button, don't trust the diff
   - For perf: run the benchmark, don't assume

2. **Would a user notice if this was broken?**
   - Was the feature exercised in the way a user would use it (not just a narrow test)?
   - Did you try one unhappy path?

3. **What got silently skipped?**
   - Any `TODO`, `pass`, commented-out test, `@pytest.mark.skip` introduced this session? Flag.
   - Any unrelated bug noticed but not filed? Flag.

4. **Is the code legible to the next agent?**
   - Would someone picking up `tasks/tasks.json` next session understand what this code does by reading it?
   - Are function/variable names accurate to what they do now (not what they used to do)?

5. **Did this session create any new risks?**
   - New dependency?
   - Changed public API?
   - Changed DB schema?
   - Document in `notes/progress.md`.

## Grading

A task is **done** only when every acceptance criterion passes AND the evaluation checklist is clean.

A task that passes typecheck + tests but fails the "user would notice" check is **not done** — demote to `in_progress` and add the missing work as subtasks or new tasks.

## Common failure modes the Evaluator catches

- Handler returns correct shape but wrong values
- UI component renders but doesn't actually call the backend
- Test mocks the thing it was supposed to test
- Benchmark runs but doesn't measure what it claims
- Error path raises but calling code swallows it
