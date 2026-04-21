# Philosophy

The principles that shape Loom and vMLX. When a decision comes up, the answer lives here.

---

## 1. Meet companies where they are

Loom does not replace your CRM / WMS / ERP / LIMS. It sits **on top** of them and talks to them through their own APIs. Your legacy apps stay. Your data stays. The AI adapts.

**What this means in practice:**
- Customer API registration is the core product flow, not a plugin
- Integrations are expected to be **messy** — unusual auth, inconsistent schemas, rate-limited endpoints — and we build for that reality
- We never ask customers to migrate, normalize, or restructure anything as a prerequisite

**What it rules out:**
- "Ingest everything into our warehouse first" patterns
- Forcing a common data model across customers
- Replatform-or-nothing adoption stories

---

## 2. Local is the product, not a fallback

Loom is designed for on-premise operation. Privacy, auditability, and customer control are not features added on top of a cloud default — they are the default.

**What this means in practice:**
- Zero data egress by default; online features are explicit opt-in with UI indicators
- Credentials live in OS keychain, never in files
- Audit logs are standard, not a premium add-on
- Target hardware (Mac Studio) is picked because it can actually run 70B models locally

**What it rules out:**
- "Privacy-preserving cloud" handwaves
- Designs that require any data to leave the premises for a core feature to work
- Telemetry-by-default

---

## 3. Open foundation, commercial edge

vMLX and Loom core (chat UI, API, OpenAPI-import basics) are **Apache 2.0**. The commercial tier is advanced connectors, enterprise auth (mTLS, SAML SSO), audit/compliance features, and priority support.

**Why:** OSS wins developer trust and mindshare; enterprise customers pay for what lets them sleep at night.

**What this rules out:**
- Closed-source gates on basic functionality
- Rugpull licensing where free turns into paid
- Feature gates that break interoperability

---

## 4. Build on legitimate sources

Architecture inspiration comes from **public papers, open specs, and OSS projects** — ReAct, vLLM paper (algorithm), MCP spec, Aider, Continue.dev, OpenHands. We do not derive from leaked or unlicensed source, even for "ideas."

**Why:** Trade-secret exposure would kill enterprise sales. IP provenance has to be clean. Public sources are usually better documented anyway.

**What this rules out:**
- Reverse-engineering closed competitors
- Using leaked materials as a shortcut
- Copying interface patterns so closely they create derivative-work ambiguity

---

## 5. Respect the Mac

Apple Silicon is not a second-class citizen here — it's the primary target. We use MLX-native paths, unified memory, Metal kernels, and macOS-native UX (Tauri desktop, keychain secrets).

**What this means in practice:**
- vMLX is designed around unified memory, not ported from a CUDA assumption
- Performance work prioritizes Metal kernels over generic CPU fallback
- Desktop feels like a Mac app, not a browser in a window

**What it rules out:**
- Pretending macOS is just another Linux
- Dropping to generic cross-platform code where native would clearly win

---

## 6. Single-agent first; complexity must be earned

Our agent harness runs a single agent that adopts planner / generator / evaluator roles sequentially. Multi-agent systems, distributed pipelines, and fancy orchestration only enter when the simpler thing demonstrably ceilings out.

**Why:** Every layer of coordination is a bug surface. Simpler systems ship, iterate, and win.

**What this rules out:**
- Premature abstraction
- Multi-agent pipelines where one agent is enough
- Microservice boundaries that don't correspond to real team/deployment boundaries

---

## 7. Persist to disk, not context

Context windows are ephemeral. The repository is eternal. Task lists in JSON, progress notes in markdown, decisions in docs, verified state in git history. If a fact isn't on disk, it doesn't exist for next session.

**This is a harness principle but also a product principle** — Loom persists conversation memory, artifacts, and audit logs to disk with the same discipline.

---

## 8. Full implementations only

No placeholder stubs, `TODO: implement later`, or fake returns land in the repo. If scope is too big for one session, the task gets split. The bar for "done" is: it actually works, end-to-end, verified by a test or a real interaction.

**Why:** Placeholders compound into unmaintainable codebases. "Works on the happy path" is the only definition of working.

---

## 9. Verify through the real thing

Type checks and lints are necessary but not sufficient. For behavior that touches MLX inference, the verification is a Metal-backed integration test. For UI, it's a Playwright run. For customer API integrations, it's a real HTTP call to the real endpoint in the test console.

A passing typecheck is not a completed task.

---

## 10. Keep the core docs current

**README, PHILOSOPHY, and ROADMAP** are the public face of the project. They get updated alongside the changes that warrant it — never in a later sweep. Drift here is expensive: new contributors and customers form their first impression from these three files.

---

When a proposed change violates one of these principles, the principle wins until we make a conscious decision to revise the principle itself.
