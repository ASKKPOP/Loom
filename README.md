# Loom

> **Local AI that weaves your business together.**
> A private, on-premise AI platform for Mac Silicon — powered by **vMLX**, integrated with **your company's existing business applications via their own APIs**, and connected to online knowledge when you need it.

**Target:** Companies that want to add AI to their existing legacy business applications — without rewriting them, without sending data to the cloud, and without vendor lock-in.

[![License: Apache 2.0](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)
[![Platform: macOS](https://img.shields.io/badge/Platform-macOS%2015%2B-lightgrey)](https://www.apple.com/macos/)
[![MLX](https://img.shields.io/badge/Powered%20by-MLX-orange)](https://github.com/ml-explore/mlx)

---

## What is Loom?

Loom is two products in one repository:

1. **Loom** — A Claude-quality AI workspace (desktop + web + API) that runs entirely on your Mac Studio. **Connects to your company's existing business applications through their own APIs** so AI can work on your real data, in your real workflows — without migration, replatforming, or cloud egress.

2. **vMLX** — A high-throughput MLX serving engine (think *vLLM for Apple Silicon*). Powers Loom, and stands alone as an open-source serving layer for the MLX community.

### The Integration Model

Loom does **not** try to replace your existing CRM / WMS / IMS / ERP. Instead:

```
Your existing apps (already have APIs)
    ↓
  https://app.altbiolab.com/api
  https://your-crm.internal/api
  https://your-wms.local/api
       ↓
   Loom registers each company API as a tool
       ↓
   AI uses your APIs to answer questions, take actions,
   generate reports, automate workflows
```

**Example:** An ALTBioLab user asks Loom *"Which samples failed QC this week and why?"* — Loom calls `app.altbiolab.com`'s API, retrieves the data, analyzes it locally with a 70B model, and answers. Data never leaves the premises.

**Each customer = their own API set.** Loom ships a framework, connectors, and an admin UI to register any REST/GraphQL/SQL/ODBC endpoint as an AI-accessible tool.

---

## Why Loom?

| Current tools | Gap Loom fills |
|---|---|
| **LM Studio** | No online resources, no business integration, no production API |
| **mlxstudio** | MLX inference only, no agent runtime or UI polish |
| **Ollama** | No business connectors, basic UI |
| **Claude.ai** | Cloud-only — data leaves your premises |
| **mlx-lm server** | No continuous batching, not production-grade |

Loom keeps your data on your hardware while giving you the UX and capability of the best cloud AI.

---

## Key Features

### 🧵 Loom Platform
- **Claude-quality chat** with streaming, artifacts, projects, and persistent memory
- **Desktop** (Tauri, native macOS) + **Web** (React) + **REST API**
- **Bring Your Own API integration** — register any REST/GraphQL/SQL endpoint from your existing business apps, Loom exposes them to the AI as tools
- **OpenAPI / Swagger import** — point Loom at your existing API spec, it auto-generates tool definitions
- **Online resources** — opt-in web search and URL fetching
- **Industry-agnostic** — works for CRM, CCM, RPM, WMS, IMS, LIMS, ERP, or any custom legacy system with an API
- **Zero data egress** by default — everything local unless you say otherwise
- **OpenAI + Anthropic API compatible** — drop-in replacement for existing AI clients your apps already use

### ⚡ vMLX Engine
- **Continuous batching** — dynamic request merging on Metal
- **Paged KV cache** — adapted for Apple unified memory
- **Prefix caching** — reuse KV across shared prompts / multi-turn chats
- **Speculative decoding** — 2–3× single-request speedup
- **Multi-model hot-swap**
- **OpenAI + Anthropic API endpoints** out of the box

---

## System Requirements

| Tier | Hardware | Models supported |
|---|---|---|
| Minimum | Mac Studio / MacBook Pro M4 Max, 64GB RAM | Up to 30B (Q4) |
| Recommended | Mac Studio M4 Ultra, 128GB+ | Up to 70B (Q4) |
| Power | Mac Studio M4 Ultra, 256–512GB | 70B+ (Q8/FP16), multi-model concurrent |

- **macOS:** 15.0 (Sequoia) or later
- **Disk:** 200GB+ for model storage

---

## Quick Start

> ⚠️ **Status:** Early development. No installable release yet. See [Roadmap](#roadmap).

### Developer setup (when ready)

```bash
# Clone
git clone https://github.com/ASKKPOP/Loom.git
cd Loom

# vMLX engine
cd vmlx
pip install -e .
vmlx serve mlx-community/Qwen2.5-72B-Instruct-4bit

# Loom app (separate terminal)
cd ../loom
pnpm install
pnpm dev
```

Open http://localhost:3000 — sign in locally, start chatting.

---

## Architecture

```
┌──────────────────────────────────────────────────────────┐
│  Desktop (Tauri)  │  Web UI (React)  │  API Clients     │
└─────────────┬──────────────────┬─────────────┬───────────┘
              └──────────────────┴─────────────┘
                         │
                  ┌──────▼───────┐
                  │ API Gateway  │ (FastAPI)
                  └──────┬───────┘
                         │
        ┌────────────────┼────────────────┐
        │                │                │
  ┌─────▼──────┐  ┌──────▼──────┐  ┌──────▼─────┐
  │   Agent    │  │  Storage    │  │            │
  │  Runtime   │  │             │  │            │
  │            │  │ SQLite      │  │            │
  │ Tool use   │  │ LanceDB     │  │            │
  │ Planning   │  │ Files       │  │            │
  │ Memory     │  └─────────────┘  │            │
  └─────┬──────┘                   │            │
        │                          │            │
        ▼                          │            │
  ┌─────────────────────────────────▼────────────┐
  │                vMLX Engine                   │
  │  Scheduler · Paged KV · Prefix Cache · SpecDec│
  │              MLX Runtime (Metal)             │
  │  OpenAI API  │  Anthropic API  │  gRPC       │
  └────────────────────────┬─────────────────────┘
                           │
              ┌────────────▼────────────┐
              │       MCP Layer         │
              └────────────┬────────────┘
                           │
         ┌─────────────────┼─────────────────┐
         │                 │                 │
    ┌────▼────┐      ┌─────▼─────┐    ┌──────▼────┐
    │   CRM   │      │  WMS/IMS  │    │ Web/URL   │
    └─────────┘      └───────────┘    └───────────┘
```

---

## Repository Structure

```
Loom/
├── vmlx/                    # vMLX serving engine (Apache 2.0)
│   ├── scheduler/           # Continuous batching
│   ├── cache/               # Paged KV + prefix cache
│   ├── kernels/             # Metal kernels
│   ├── api/                 # OpenAI / Anthropic API surface
│   └── benchmarks/
├── loom/
│   ├── gateway/             # FastAPI gateway
│   ├── agent/               # Agent runtime (tool use, planning, memory)
│   ├── mcp/                 # MCP adapters
│   ├── storage/             # SQLite, LanceDB, files
│   ├── web/                 # React + TypeScript + Tailwind
│   └── desktop/             # Tauri app
├── docs/
│   ├── PRD.md
│   ├── vmlx/
│   └── loom/
└── README.md
```

---

## Tech Stack

| Layer | Choice | Why |
|---|---|---|
| Inference | **vMLX** (in-house) | No mature high-throughput MLX server exists |
| Fallback runtime | llama.cpp (Metal) | Universal model support via GGUF |
| Desktop shell | Tauri (Rust + WebView) | Small binary, native macOS feel |
| Web UI | React + TypeScript + Tailwind | Fast iteration, ecosystem |
| API | FastAPI (Python) | OpenAI/Anthropic compatibility, async |
| Integration | MCP (Model Context Protocol) | Open standard, growing ecosystem |
| Vector DB | LanceDB (embedded) | No separate server, Apple Silicon friendly |
| Auth | Local-first, optional OIDC | Privacy by default |

---

## Roadmap

See **[ROADMAP.md](ROADMAP.md)** for the full, living roadmap. Short version:

- **Phase 0 — vMLX Foundation** (current)
  - ✅ Package skeleton, SingleRequestEngine, benchmark harness, OpenAI-compatible API (vmlx-001 … vmlx-004)
  - ⏳ Next: continuous batching scheduler (vmlx-005), paged KV cache, prefix cache, v0.1 release
- **Phase 1 — Loom MVP** — web chat UI on vMLX, model management, single-user local
- **Phase 2 — Productization** — desktop app (Tauri), artifacts/projects/memory, Anthropic API compat
- **Phase 3 — Customer API Integration** ⭐ — the wedge: OpenAPI import, auth adapters, audit log
- **Phase 4 — Launch** — multi-user, connector marketplace, Loom 1.0 + vMLX 1.0

Full requirements: [docs/PRD.md](docs/PRD.md).

---

## Design Principles

Full detail in **[PHILOSOPHY.md](PHILOSOPHY.md)**. Short version:

1. **Meet companies where they are** — Loom sits on top of existing systems, never replaces them.
2. **Local is the product** — privacy, auditability, on-premise operation are the default, not a fallback.
3. **Open foundation, commercial edge** — vMLX and Loom core are Apache 2.0; enterprise features are the paid tier.
4. **Build on legitimate sources** — public papers, open specs, OSS. No reverse engineering of closed products.
5. **Respect the Mac** — MLX-native, unified memory aware, Metal-first.
6. **Single-agent first; complexity must be earned** — harness and product both start monolithic.
7. **Full implementations only** — no placeholders, stubs, or `TODO: later` in committed code.

---

## Licensing

| Component | License |
|---|---|
| vMLX | Apache 2.0 |
| Loom Core (chat, API, basic MCP) | Apache 2.0 |
| Loom Business (enterprise connectors, audit, priority support) | Commercial |

---

## Contributing

Loom is early-stage. Contributions welcome in:
- vMLX kernels and scheduler work
- MCP connectors for business systems
- UI components and UX polish
- Documentation and translations

See `CONTRIBUTING.md` (coming soon) for development setup and conventions.

---

## References

- [Apple MLX](https://github.com/ml-explore/mlx)
- [mlx-lm](https://github.com/ml-explore/mlx-lm)
- [Model Context Protocol](https://modelcontextprotocol.io)
- [vLLM / PagedAttention paper](https://arxiv.org/abs/2309.06180) — algorithmic inspiration
- [Building effective agents](https://www.anthropic.com/research/building-effective-agents)

---

## Links

- **Repo:** https://github.com/ASKKPOP/Loom
- **Issues:** https://github.com/ASKKPOP/Loom/issues
- **Discussions:** https://github.com/ASKKPOP/Loom/discussions

---

*Loom — where your business threads meet intelligence.*
