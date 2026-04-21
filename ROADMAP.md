# Loom Roadmap

Living document. Updated whenever a phase milestone shifts. Task-level detail lives in [tasks/tasks.json](tasks/tasks.json); this file is the narrative.

---

## Current phase: **Phase 0 — vMLX Foundation**

Goal: ship **vMLX 0.1** — a high-throughput MLX serving engine with continuous batching, paged KV cache, prefix caching, and OpenAI-compatible API.

### Progress

| Task | Status | Notes |
|------|--------|-------|
| [vmlx-001](tasks/tasks.json) Bootstrap vmlx package skeleton | ✅ Done | Python 3.12, mlx + mlx-lm deps, src/ layout |
| [vmlx-002](tasks/tasks.json) Baseline SingleRequestEngine | ✅ Done | mlx-lm wrapper; TTFT + peak memory in GenerationResult |
| [vmlx-003](tasks/tasks.json) Benchmark harness | ✅ Done | `python -m vmlx.benchmarks.run`; ttft p50/p95, tok/s, peak RSS; history.jsonl |
| [vmlx-004](tasks/tasks.json) OpenAI-compatible API endpoint | ⏳ Next | `/v1/chat/completions`, `/v1/models`, SSE streaming |
| [vmlx-005](tasks/tasks.json) Continuous batching scheduler | ⏳ | Target ≥ 3× throughput at N=8 concurrent vs single-request baseline |
| [vmlx-006](tasks/tasks.json) Paged KV cache | ⏳ | Block allocator adapted for Apple unified memory |
| [vmlx-007](tasks/tasks.json) Prefix caching | ⏳ | Content-addressed prefix reuse across requests |
| [vmlx-008](tasks/tasks.json) **vMLX 0.1 release** | ⏳ | Tag, benchmarks vs mlx-lm, launch README |

---

## Upcoming phases

### Phase 1 — Loom MVP (Months 3–5)
- Web chat UI on vMLX
- Model download / management
- Single-user local deployment

### Phase 2 — Productization (Months 5–7)
- vMLX: prefix caching refinement, speculative decoding
- Loom: Anthropic API compatibility, Tauri desktop app, artifacts/projects/memory

### Phase 3 — Customer API Integration (Months 7–9) ⭐
- OpenAPI/Swagger import flow
- Auth adapters (API key, Bearer, Basic, OAuth2 CC + AC, JWT, mTLS)
- Per-tool scope + rate limit controls
- Audit log viewer, test console
- Reference integration: [ALTBioLab](https://app.altbiolab.com) (biotech LIMS)

### Phase 4 — Scale & Launch (Months 10–12)
- Multi-user local deployment
- MCP connector marketplace
- **Milestone:** Loom 1.0 + vMLX 1.0

---

## Success targets (v1.0)

### vMLX
| Metric | Target |
|---|---|
| Throughput (8 concurrent, 70B Q4) vs mlx-lm | ≥ 3× |
| P50 TTFT (warm cache) | < 200 ms |
| Single-request tok/s (70B Q4, M4 Ultra) | ≥ 30 tok/s |

### Loom
| Metric | Target |
|---|---|
| Time-to-first-integration (new customer API) | < 30 min |
| Paid business deployments | 20+ |
| D30 retention | > 40% |

---

## What moves this roadmap

- **Customer signal** (design partners like ALTBioLab) can re-prioritize phases
- **Performance ceilings** — if a vMLX layer ceilings out, we invest more there
- **Model landscape shifts** — new OSS models may change workload priorities

When the roadmap changes, update this file AND the README summary AND notify design partners.
