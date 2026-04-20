# Role: Planner

**Status:** Documented role, not a separate agent yet. Single-agent sessions adopt this hat during the planning phase of a task.

## Purpose

Turn a high-level task (from `tasks/tasks.json`) into a concrete spec the Generator can implement without further guesswork.

## When to put on the Planner hat

- Task has no `spec` field yet
- Task was written at product level ("support OAuth2") without implementation shape
- Task touches architecture (changes module boundaries, API contracts)

## Planner output

Add a `spec` section to the task in `tasks/tasks.json`, or (for larger tasks) write `docs/proposals/<task-id>.md` and link it.

Spec must include:

1. **Intent** — one sentence: what success looks like for a user
2. **Approach** — 3–10 bullet points on how it will work technically
3. **Interfaces touched** — public APIs, DB schema, config
4. **Out of scope** — explicit list of what this task does NOT do
5. **Acceptance criteria** — measurable, testable (populates `acceptance_criteria` in task)
6. **Risks** — what could go wrong, how we mitigate

## Good vs bad planning

❌ "Implement OAuth2 support."
✅ "Add `oauth2_authorization_code` auth adapter conforming to section 5.5 of api-registration.md. Callback runs on localhost:3456. Tokens stored via Keychain ref. Refresh token flow implemented. Out of scope: PKCE (separate task), device flow (separate task). Acceptance: ALTBioLab end-to-end OAuth flow succeeds in a test that hits a stubbed IdP."

## Rules

- Plan at the granularity of *one session of implementation*. If the spec implies more than one session, split it into multiple tasks.
- Prefer writing the test first (or at least naming it) as part of planning.
- If a task's spec grows beyond a page, it's too big — split.
