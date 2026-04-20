# Conventions

Enforceable code quality rules for Loom + vMLX. Prefer mechanical enforcement (linters, tests, CI) over documentation.

## Language/framework

| Component | Language | Key tools |
|---|---|---|
| `vmlx/` | Python 3.12+ | mlx, mlx-lm, pytest, ruff, mypy |
| `loom/gateway` | Python 3.12+ | FastAPI, uvicorn, pytest |
| `loom/agent` | Python 3.12+ | — |
| `loom/web` | TypeScript | React 18, Tailwind, Vite, vitest |
| `loom/desktop` | Rust + TS | Tauri 2.x |

## Code style

- **Python:** `ruff` (both format + lint), `mypy --strict` for new modules. No `# type: ignore` without a linked issue.
- **TypeScript:** `eslint` + `prettier`. `strict: true` in `tsconfig.json`. No `any` without justification comment.
- **Rust:** `cargo fmt`, `clippy -- -D warnings`.

## Core rules

### 1. No placeholders
`TODO`, `pass`, `NotImplementedError`, `throw new Error("not implemented")`, or fake returns in committed code = instant reject. Either implement fully or split the task and defer to a new `todo`.

Exception: tests that document expected-future-behavior may use `@pytest.mark.skip(reason=...)` if the task is tracked in `tasks/tasks.json`.

### 2. No silent fallbacks
Don't catch-and-ignore exceptions or return sentinel values on error. Raise, log, or bubble up. Silent fallbacks hide bugs for sessions.

### 3. Comments = WHY, not WHAT
Identifiers explain what. Comments exist for hidden constraints, subtle invariants, and non-obvious design decisions only.

### 4. No speculative generality
Don't add abstractions, interfaces, or hooks for hypothetical future needs. Three similar lines beats a premature abstraction.

### 5. Trust internal code boundaries
Only validate at system boundaries (HTTP handlers, customer API responses, user input). Internal calls trust their types.

### 6. Errors must include context
Error messages name the failing operation, the input that failed, and (if possible) the remediation. `raise ValueError("bad input")` is bad; `raise ValueError(f"api_registration: invalid auth.type={auth_type!r}; expected one of {ALLOWED}")` is good.

## Testing

### Verification hierarchy (fastest to slowest)
1. **Type check** — `mypy`, `tsc --noEmit`. Must pass.
2. **Lint** — `ruff`, `eslint`. Must pass.
3. **Unit tests** — `pytest`, `vitest`. New code ships with tests.
4. **Integration tests** — exercise real boundaries (real MLX load, real HTTP).
5. **UI smoke** — Playwright navigates the actual UI for features with UI impact.

A passing (1) + (2) is **not** a completed task. Tasks with behavior require (3)–(5) as applicable.

### Metal (Apple Silicon GPU) tests
Tests that load real MLX models are marked `@pytest.mark.metal`. They are **skipped by default** in `session-verify.sh` because they're slow and require the machine to actually have Apple Silicon. Run them explicitly before committing any change that touches inference code:

```bash
cd vmlx && ../.venv/bin/python -m pytest -m metal -v
```

### Test writing rules
- One behavior per test. Name: `test_<unit>_<behavior>_<condition>`.
- No mocking what you can construct (real SQLite > mocked DB).
- Integration tests that need Metal/MLX are marked `@pytest.mark.metal` and skipped in CI fallback.
- Any bug fixed gets a regression test in the same commit.

## Dependencies

- **Add a dep?** Justify in commit message. Prefer standard library / already-present deps.
- **Pin** major versions in `pyproject.toml` / `package.json`.
- **No abandoned packages** — last release within 24 months.

## Documentation

- **Public APIs** (FastAPI endpoints, vMLX API, exported TS components) get docstrings with: purpose, params, return, raises, example.
- **Internal functions** don't need docstrings unless non-obvious.
- **Design decisions** go in `docs/` as proposals, not in code comments.
- **README per subsystem** — `vmlx/README.md`, `loom/gateway/README.md` etc. — so agents can navigate without reading everything.

## Security

- Secrets in macOS Keychain only (see [docs/schemas/api-registration.md](../schemas/api-registration.md)).
- No secrets in commits, logs, error messages, or `.env` files committed to git.
- User input crossing into shell commands → `shlex.quote` or use list-form subprocess.
- User input crossing into SQL → parameterized queries only.
- Customer API calls → respect per-tool rate limits, timeouts, and response size caps.

## Performance

- vMLX tok/s: never regress without explicit exception in the PR.
- Benchmarks live in `vmlx/benchmarks/` and run on tagged releases.

## Git hygiene

- Small commits. Each commit should compile and pass tests.
- Commit messages follow the style in `CLAUDE.md`.
- Never force-push to `main`.
- Never amend published commits.
