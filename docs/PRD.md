# Loom — Product Requirements Document (PRD)

**Repository:** https://github.com/ASKKPOP/Loom
**Version:** 1.2
**Date:** 2026-04-20
**Status:** Draft

---

## 1. Vision

**Loom weaves local AI, online knowledge, and your company's existing business applications into one private fabric — running entirely on your Mac.**

Loom is an AI layer that sits **on top of** your existing business systems, not a replacement for them. Companies point Loom at their APIs (CRM, CCM, RPM, WMS, IMS, LIMS, ERP, or any custom legacy system), and Loom makes those APIs available to AI — safely, privately, and without sending data to the cloud.

Two products in one repo:

1. **Loom** — the business AI platform (desktop + web + API)
2. **vMLX** — high-throughput MLX serving engine (open to the MLX community like vLLM is to CUDA)

---

## 2. Problem Statement

### 2.1 The business integration gap
Most companies already have business systems with APIs (often internal REST/GraphQL services). They want AI-powered workflows on their real data, but the current options fail:

| Option | Why it fails |
|---|---|
| Cloud AI (Claude, GPT) | Data leaves premises — unacceptable for regulated industries |
| Replatform to AI-native SaaS | 12–24 month migrations, unrealistic for most mid-market |
| Build custom integration | Requires AI + systems expertise most companies lack |
| Local LLM tools (LM Studio, Ollama) | No business integration, no online resources, no production API |

**Loom's wedge:** give companies a local, private AI platform that adapts to *their* APIs, not the other way around.

### 2.2 The MLX serving gap
There is no vLLM equivalent for Apple Silicon. `mlx-lm`'s server lacks continuous batching, paged KV cache, and production-grade concurrent handling. Every serious MLX deployment rebuilds the same serving layer. **vMLX fills this gap.**

---

## 3. Target Users

### 3.1 Loom — primary target
**Mid-market companies (50–500 employees) with existing legacy business applications:**
- Biotech / pharma (LIMS, sample tracking — example: [ALTBioLab](https://app.altbiolab.com))
- Manufacturing (WMS, IMS, MES)
- Healthcare (EHR, PMS)
- Finance (custom risk/compliance systems)
- Logistics (TMS, WMS)
- Any regulated industry with data privacy requirements

**Characteristics:**
- Already have internal APIs (or could expose them with modest effort)
- Data privacy is mandatory, not optional
- Budget for Mac Studio hardware (~$5K–15K) beats ongoing cloud AI fees
- Have 1–2 engineers who can describe their APIs but not build full AI stacks

### 3.2 vMLX — secondary audience
MLX developers, researchers, and anyone serving MLX models in production.

---

## 4. Goals & Non-Goals

### Loom goals
- ✅ Run 70B-class models locally on Mac Studio M4
- ✅ Match Claude.ai UX quality (chat, artifacts, projects, memory)
- ✅ **Integrate any customer REST/GraphQL API as AI tools via OpenAPI import**
- ✅ Support legacy auth (API key, OAuth2, JWT, mTLS, basic auth)
- ✅ Access online resources (web search, URL fetch) on-demand
- ✅ Desktop (macOS native) + web + REST API from day one
- ✅ Zero data egress by default

### vMLX goals
- ✅ 3–5× throughput vs current mlx-lm server
- ✅ Continuous batching on Metal
- ✅ Paged KV cache for unified memory
- ✅ OpenAI + Anthropic API compatibility
- ✅ Prefix caching + speculative decoding

### Non-goals (v1)
- ❌ Model training/fine-tuning UI (v2)
- ❌ Windows/Linux desktop (web covers them)
- ❌ Multi-tenant SaaS (single-org deployment model)
- ❌ Mobile apps (v2)
- ❌ Replacing customers' existing business systems

---

## 5. Core Concept — The Integration Model

```
Customer's existing apps (already have APIs)
    ┌─────────────────────────────────────────────┐
    │  https://app.altbiolab.com/api              │
    │  https://your-crm.internal/api              │
    │  https://your-wms.local/api                 │
    │  postgresql://warehouse.local/inventory     │
    └─────────────────────────────────────────────┘
                         │
                         │  1. Admin registers API
                         │     (paste OpenAPI spec + auth)
                         ▼
    ┌─────────────────────────────────────────────┐
    │            Loom API Registry                │
    │  - Parses spec                              │
    │  - Generates AI tool definitions            │
    │  - Stores credentials (local keychain)      │
    │  - Applies scopes & rate limits             │
    └─────────────────────────────────────────────┘
                         │
                         │  2. AI uses tools
                         ▼
    ┌─────────────────────────────────────────────┐
    │      Agent Runtime (powered by vMLX)        │
    │  User: "Which samples failed QC this week?" │
    │  AI:   calls altbiolab_list_samples(...)    │
    │        calls altbiolab_get_qc_results(...)  │
    │        summarizes locally with 70B model    │
    └─────────────────────────────────────────────┘
```

**Key properties:**
- Customer's API is the **source of truth** — Loom doesn't copy or mirror data
- Credentials stored locally (macOS Keychain), never logged
- Every AI call is auditable (what tool, what params, what response)
- Customer can scope which endpoints AI can reach

See [`docs/schemas/api-registration.md`](schemas/api-registration.md) for the full registration schema.

---

## 6. Platform Requirements

### Hardware
| Tier | Config | Target models |
|---|---|---|
| Minimum | M4 Max, 64GB | 7B–30B (Q4) |
| Recommended | M4 Ultra, 128GB | Up to 70B (Q4) |
| Power | M4 Ultra, 256–512GB | 70B+ (Q8/FP16), multi-model concurrent |

**macOS:** 15.0+ (Sequoia). **Disk:** 200GB+ for models.

### Software Stack
| Layer | Choice |
|---|---|
| Inference | **vMLX** (in-house) + llama.cpp fallback |
| Desktop | Tauri (Rust + WebView) |
| Web UI | React + TypeScript + Tailwind |
| API | FastAPI (Python) |
| Integration | MCP (Model Context Protocol) + custom API registry |
| Vector DB | LanceDB (embedded) |
| Secrets | macOS Keychain / OS keyring |
| Auth | Local-first, optional OIDC |

---

## 7. Loom Features

### 7.1 Conversational AI (MVP)
- Multi-turn chat with streaming
- Model picker
- Conversation history, search, export
- **Artifacts** — rich inline outputs
- **Projects** — scoped conversations with shared context
- **Memory** — persistent cross-conversation facts

### 7.2 Model Management
- Hugging Face model download (MLX + GGUF)
- Quantization selector
- Load/unload models, memory usage indicator
- Curated models for business use cases

### 7.3 Customer API Integration ⭐ (core differentiator)
- **OpenAPI/Swagger import** — paste URL or upload JSON/YAML
- **GraphQL schema import**
- **SQL/ODBC endpoint registration** with query scope controls
- **Auth adapters:** API key, Bearer token, OAuth2 (client credentials + authorization code), JWT, Basic auth, mTLS
- **Per-tool scoping** — admin selects which operations AI can call
- **Per-tool rate limits + concurrency limits**
- **Test console** — call any registered endpoint manually to verify
- **Audit log** — every AI tool call recorded with actor, params, response, timing

### 7.4 Online Resource Layer
- Pluggable web search (Brave, SearXNG, Tavily)
- URL fetch with content extraction
- Opt-in per conversation — offline by default
- Clear UI indicator when "going online"

### 7.5 Generic MCP Layer
- MCP client for community servers
- MCP server mode (expose Loom itself as MCP to other tools)

### 7.6 Loom API Service
- OpenAI-compatible endpoints
- Anthropic-compatible endpoints
- API key management, rate limits
- Binds to localhost or LAN by default

### 7.7 Admin & Observability
- User management (for multi-seat local deployment)
- Audit logs (required for regulated industries)
- Model performance metrics
- Export/backup/restore

---

## 8. vMLX — Detailed Requirements

### 8.1 Core engine
| Feature | Priority |
|---|---|
| Continuous batching | P0 |
| Paged KV cache | P0 |
| Prefix caching | P0 |
| Streaming (SSE + Anthropic events) | P0 |
| Quantization (4/8/FP16 MLX) | P0 |
| Speculative decoding | P1 |
| Multi-model hot-swap | P1 |
| LoRA adapters | P2 |
| Multi-Mac tensor parallelism | P2 |

### 8.2 API surface
- **OpenAI:** `/v1/chat/completions`, `/v1/completions`, `/v1/embeddings`, `/v1/models`
- **Anthropic:** `/v1/messages` with tool use + streaming
- **Native:** gRPC for internal low-latency calls from Loom
- **Admin:** `/admin/models`, `/admin/stats`, `/admin/health`

### 8.3 Observability
- Prometheus metrics (TTFT, tok/s, queue depth, cache hit rate)
- Per-request trace logs
- Web dashboard (standalone, embeddable in Loom UI)

### 8.4 Deployment
- Single binary (`vmlx serve <model>`)
- Python package (`pip install vmlx`)
- Homebrew formula (`brew install vmlx`)
- Docker (CPU fallback, for CI only)

### 8.5 Licensing
Apache 2.0.

---

## 9. Architecture

```
┌──────────────────────────────────────────────────────────┐
│  Desktop (Tauri)  │  Web UI (React)  │  API Clients     │
└─────────────┬──────────────────┬─────────────┬───────────┘
              └──────────────────┴─────────────┘
                         │
                  ┌──────▼───────┐
                  │ API Gateway  │ (FastAPI)
                  │  auth/router │
                  └──────┬───────┘
                         │
        ┌────────────────┼────────────────┐
        │                │                │
  ┌─────▼──────┐  ┌──────▼──────┐  ┌──────▼─────┐
  │   Agent    │  │  Storage    │  │   Admin    │
  │  Runtime   │  │  SQLite     │  │  API Reg.  │
  │            │  │  LanceDB    │  │  Audit     │
  │            │  │  Keychain   │  │  Users     │
  └─────┬──────┘  └─────────────┘  └────────────┘
        │
        ├──── tool calls ────┐
        ▼                    ▼
  ┌────────────┐      ┌──────────────────┐
  │   vMLX     │      │  Tool Router     │
  │  Engine    │      │  - Customer APIs │
  └────────────┘      │  - MCP servers   │
                      │  - Online (web)  │
                      │  - Built-in      │
                      └────────┬─────────┘
                               │
           ┌───────────────────┼───────────────────┐
           │                   │                   │
      ┌────▼────┐        ┌─────▼─────┐       ┌─────▼─────┐
      │Customer │        │    MCP    │       │ Web/URL   │
      │  APIs   │        │  servers  │       │  fetch    │
      └─────────┘        └───────────┘       └───────────┘
```

---

## 10. Roadmap

### Phase 0 — vMLX Foundation (Months 1–3)
- Continuous batching scheduler
- Paged KV cache for Metal
- OpenAI API compatibility
- Benchmark harness vs mlx-lm
- **Milestone:** vMLX 0.1 public release

### Phase 1 — Loom MVP (Months 3–5)
- Web chat UI on vMLX
- Model download/management
- Single-user local deployment

### Phase 2 — Productization (Months 5–7)
- Prefix caching + speculative decoding in vMLX
- Anthropic API compatibility
- Tauri desktop app
- Artifacts, projects, memory

### Phase 3 — Customer API Integration (Months 7–9) ⭐
- OpenAPI/Swagger import flow
- Auth adapter library (API key, OAuth2, JWT, mTLS, Basic)
- Per-tool scope + rate limit controls
- Audit log viewer
- Test console
- Web search + URL fetch
- **Reference integration:** ALTBioLab (biotech LIMS)

### Phase 4 — Scale & Launch (Months 10–12)
- Multi-user local deployment
- MCP connector marketplace
- **Milestone:** Loom 1.0 + vMLX 1.0

---

## 11. Success Metrics

### vMLX
| Metric | Target |
|---|---|
| Throughput vs mlx-lm (8 concurrent, 70B Q4) | ≥ 3× |
| P50 TTFT (warm cache) | < 200ms |
| Single-request tok/s (70B Q4, M4 Ultra) | ≥ 30 tok/s |
| GitHub stars | 3,000+ |
| Downstream projects | 10+ |

### Loom
| Metric | Target |
|---|---|
| Paid business deployments | 20+ |
| Time-to-first-integration (new customer API) | < 30 min |
| GitHub stars | 2,000+ |
| D30 retention | > 40% |

---

## 12. Licensing & Business Model

- **vMLX:** Apache 2.0
- **Loom Core:** Apache 2.0 (chat UI, API, OpenAPI import, basic auth adapters)
- **Loom Business (paid):** Advanced auth (mTLS, SAML SSO), audit compliance features, multi-user, priority support, custom connector development

---

## 13. Risks & Mitigations

| Risk | Mitigation |
|---|---|
| Customer APIs have no OpenAPI spec | Provide manual tool definition UI; offer "inspect & generate" for undocumented APIs |
| Customer API auth is unusual | Modular auth adapter system; SDK for custom adapters |
| AI makes destructive API calls (e.g. DELETE) | Default to read-only scope; require explicit admin approval per write-capable tool; confirm-before-execute for mutations |
| vMLX scope too large | Phase gates; ship basic batching first |
| Apple ships competing MLX server | Contribute upstream, position as higher-level product |
| Long enterprise sales cycle | Developer-first OSS adoption, upsell to business tier |

---

## 14. Security Model

- All customer API credentials stored in macOS Keychain (never in plaintext files)
- Every AI tool call logged with: timestamp, user, tool, params (redacted), response size, latency, success/fail
- **Write operations** require per-tool admin approval at registration time
- **Destructive operations** (DELETE) require per-call user confirmation by default
- PII redaction rules configurable per tool
- No telemetry to Loom or third parties without explicit opt-in

---

## 15. Repository Structure

```
Loom/
├── vmlx/                    # Apache 2.0
│   ├── scheduler/           # Continuous batching
│   ├── cache/               # Paged KV + prefix cache
│   ├── kernels/             # Metal kernels
│   ├── api/                 # OpenAI / Anthropic surface
│   └── benchmarks/
├── loom/
│   ├── gateway/             # FastAPI
│   ├── agent/               # Agent runtime
│   ├── mcp/                 # MCP client + adapters
│   ├── storage/
│   ├── web/                 # React UI
│   └── desktop/             # Tauri
├── docs/
│   ├── PRD.md
│   ├── schemas/
│   │   └── api-registration.md
│   ├── vmlx/
│   └── loom/
└── README.md
```

---

## 16. References

- [Apple MLX](https://github.com/ml-explore/mlx)
- [mlx-lm](https://github.com/ml-explore/mlx-lm)
- [vLLM / PagedAttention paper](https://arxiv.org/abs/2309.06180) — algorithm inspiration
- [Building effective agents](https://www.anthropic.com/research/building-effective-agents)
- [Model Context Protocol](https://modelcontextprotocol.io)
- [OpenAPI 3.1 spec](https://spec.openapis.org/oas/v3.1.0)

---

## 17. Open Questions

1. **First design-partner customer?** ALTBioLab mentioned — formal partnership?
2. **Primary vertical for launch marketing?** Biotech, manufacturing, or horizontal?
3. **Pricing?** Per-seat, per-deployment, or value-based?
4. **Open-source vs business boundary?** Where exactly is the line drawn?
