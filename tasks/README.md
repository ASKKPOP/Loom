# Tasks

`tasks.json` is the authoritative list of work for Loom. Both agents and humans read from it.

## Why JSON not Markdown?

JSON resists model-induced corruption. A missing bullet or mangled indent in a Markdown list is invisible; a malformed JSON file fails to parse and forces a fix.

## Schema

```jsonc
{
  "version": 1,
  "updated_at": "2026-04-20T00:00:00Z",
  "tasks": [
    {
      "id": "vmlx-001",                      // unique, stable, <scope>-<nnn>
      "scope": "vmlx",                        // vmlx | loom | harness | docs
      "phase": 0,                             // roadmap phase from PRD
      "title": "Short imperative title",
      "status": "todo",                       // todo | in_progress | done | blocked
      "priority": "P0",                       // P0 (critical) | P1 | P2
      "depends_on": [],                       // other task ids that must be done first
      "spec": "One paragraph: what to build and how.",
      "acceptance_criteria": [
        "Measurable criterion 1",
        "Measurable criterion 2"
      ],
      "created_at": "2026-04-20T00:00:00Z",
      "updated_at": "2026-04-20T00:00:00Z",
      "notes": null                           // optional free text, e.g. blocker reasons
    }
  ]
}
```

## Rules

- One task = one session of implementation. If the spec implies more, split it.
- `status` transitions: `todo → in_progress → done` (or `blocked` with `notes` explaining)
- A `blocked` task must say in `notes` what unblocks it
- `depends_on` prevents grabbing tasks out of order — don't pick a task whose deps aren't `done`
- When you complete a task, update `updated_at` on both the task and the top-level `updated_at`
- Commit `tasks.json` changes with message `chore(tasks): ...`

## Discovering new tasks

When you notice work that's out of scope for your current task:
1. Append a new `todo` task to `tasks.json`
2. Commit that change separately from your implementation commits
3. Do NOT fix the discovered issue in your current session

This keeps sessions focused and makes the backlog visible.

## Selecting a task (from `session-start.sh`)

Rules applied in order:
1. `status == "todo"` and all `depends_on` are `"done"`
2. Highest priority (P0 > P1 > P2)
3. Lowest `phase` first (don't jump phases ahead of schedule)
4. Tiebreak: earliest `created_at`
