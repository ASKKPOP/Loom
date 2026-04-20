# Customer API Registration Schema

**Status:** Draft v1
**Owner:** Loom integration team
**Applies to:** Loom Phase 3 (Customer API Integration)

---

## 1. Purpose

Defines the schema customers use to register their existing business application APIs with Loom so the AI can call them as tools.

**Design goals:**
- Cover 90% of APIs via **OpenAPI import** (zero custom config)
- Cover the rest via **manual registration** with the same underlying schema
- Make **security controls explicit** — scopes, rate limits, destructive-op gating
- Credentials **never** stored in plaintext files — always OS keyring
- Every registration is **fully auditable** and reproducible

---

## 2. The Two-Layer Model

```
┌────────────────────────────────────────────┐
│  Layer 1: API Source (customer provides)   │
│  - Base URL                                │
│  - Auth method + credentials               │
│  - Schema (OpenAPI / GraphQL / manual)     │
└──────────────────┬─────────────────────────┘
                   │  admin imports
                   ▼
┌────────────────────────────────────────────┐
│  Layer 2: Tool Definitions (Loom-managed)  │
│  - One tool per selected operation         │
│  - Scopes, rate limits, write-approval     │
│  - AI-facing name, description, schema     │
└────────────────────────────────────────────┘
```

Layer 1 describes **what exists**. Layer 2 describes **what AI is allowed to do**.

---

## 3. API Source Schema

Stored in `storage/api-sources.db` (SQLite). Example JSON representation:

```jsonc
{
  "id": "altbiolab",
  "name": "ALTBioLab LIMS",
  "description": "Laboratory sample tracking and QC system",
  "base_url": "https://app.altbiolab.com/api",
  "source_type": "openapi",       // openapi | graphql | manual | sql

  "spec": {
    "format": "openapi-3.1",
    "url": "https://app.altbiolab.com/api/openapi.json",
    "cached_hash": "sha256:abc123...",
    "last_fetched": "2026-04-20T10:00:00Z"
  },

  "auth": {
    "type": "bearer",             // see §5 for all auth types
    "credential_ref": "keychain:loom.altbiolab.token",
    "refresh": null               // or OAuth2 refresh config
  },

  "network": {
    "timeout_ms": 30000,
    "max_response_bytes": 10485760,
    "allow_redirects": false,
    "verify_tls": true,
    "proxy": null
  },

  "global_limits": {
    "max_requests_per_minute": 60,
    "max_concurrent": 4
  },

  "pii_redaction": {
    "enabled": true,
    "rules": ["email", "ssn", "phone"]   // built-in rule set IDs
  },

  "created_at": "2026-04-20T10:00:00Z",
  "created_by": "admin@company.local",
  "enabled": true
}
```

### Field notes

| Field | Notes |
|---|---|
| `id` | Machine-safe identifier, used as tool name prefix (e.g. `altbiolab_list_samples`) |
| `source_type` | Determines which import pipeline runs |
| `spec.cached_hash` | Detects upstream API changes — admin re-approves on change |
| `auth.credential_ref` | **Never** contains the actual secret; points to keychain entry |
| `network.max_response_bytes` | Hard cap to prevent context blow-up from runaway responses |
| `global_limits` | Applied on top of per-tool limits |

---

## 4. Tool Definition Schema

Generated from the API source (auto for OpenAPI, manual for others). Stored in `storage/tools.db`.

```jsonc
{
  "id": "altbiolab_list_samples",
  "source_id": "altbiolab",
  "enabled": true,

  "operation": {
    "method": "GET",
    "path": "/v1/samples",
    "operation_id": "listSamples"     // from OpenAPI
  },

  "ai_facing": {
    "name": "altbiolab_list_samples",
    "description": "List biological samples in ALTBioLab, filtered by status, date range, or project. Returns up to 100 samples per call.",
    "input_schema": {
      "type": "object",
      "properties": {
        "status": {
          "type": "string",
          "enum": ["pending", "in_progress", "qc_passed", "qc_failed"]
        },
        "from_date": { "type": "string", "format": "date" },
        "to_date":   { "type": "string", "format": "date" },
        "limit":     { "type": "integer", "maximum": 100, "default": 20 }
      }
    },
    "output_transform": "summary"   // full | summary | custom_jq
  },

  "security": {
    "classification": "read",        // read | write | destructive | admin
    "requires_confirmation": false,  // AI must ask user before calling
    "requires_admin_approval": false,// admin must approve each call (for high-risk)
    "max_requests_per_minute": 30,
    "max_concurrent": 2,
    "redact_response_fields": ["patient.ssn", "patient.dob"]
  },

  "audit": {
    "log_params": true,
    "log_response_preview": true,
    "log_response_preview_bytes": 512
  }
}
```

### Security classification — defaults

| Classification | Default confirmation | Default admin approval | Typical HTTP verbs |
|---|---|---|---|
| `read` | No | No | GET, HEAD, OPTIONS |
| `write` | No | Yes (at registration) | POST, PUT, PATCH |
| `destructive` | **Yes (per call)** | Yes (at registration) | DELETE, destructive POST |
| `admin` | **Yes (per call)** | **Yes (per call)** | Anything touching users/permissions |

Admin can override these per tool.

### Output transforms

Responses can be huge. Options:
- `full` — pass full JSON to AI (only for small, structured responses)
- `summary` — auto-summarize: top-level fields, array length, first N items
- `custom_jq` — admin-provided jq expression to shape the response
- `none` — raw passthrough (last resort)

---

## 5. Auth Adapter Types

All stored credentials are references to OS keychain entries.

### 5.1 `api_key`
```jsonc
{
  "type": "api_key",
  "in": "header",              // header | query | cookie
  "name": "X-API-Key",
  "credential_ref": "keychain:loom.<source>.apikey"
}
```

### 5.2 `bearer`
```jsonc
{
  "type": "bearer",
  "credential_ref": "keychain:loom.<source>.token"
}
```

### 5.3 `basic`
```jsonc
{
  "type": "basic",
  "credential_ref": "keychain:loom.<source>.basic"   // stores user:pass
}
```

### 5.4 `oauth2_client_credentials`
```jsonc
{
  "type": "oauth2_client_credentials",
  "token_url": "https://auth.example.com/oauth/token",
  "client_id_ref": "keychain:loom.<source>.client_id",
  "client_secret_ref": "keychain:loom.<source>.client_secret",
  "scopes": ["read:samples", "read:qc"],
  "audience": "https://app.altbiolab.com/api"
}
```

### 5.5 `oauth2_authorization_code`
```jsonc
{
  "type": "oauth2_authorization_code",
  "auth_url": "https://auth.example.com/oauth/authorize",
  "token_url": "https://auth.example.com/oauth/token",
  "client_id_ref": "keychain:loom.<source>.client_id",
  "client_secret_ref": "keychain:loom.<source>.client_secret",
  "redirect_uri": "http://localhost:3456/oauth/callback",
  "scopes": ["read:samples"],
  "refresh_token_ref": "keychain:loom.<source>.refresh_token"
}
```

### 5.6 `jwt_bearer`
Self-signed JWT assertion (for service-to-service).
```jsonc
{
  "type": "jwt_bearer",
  "issuer": "loom-local",
  "audience": "https://app.altbiolab.com",
  "subject": "ai-agent",
  "private_key_ref": "keychain:loom.<source>.jwt_privkey",
  "algorithm": "RS256",
  "ttl_seconds": 300,
  "extra_claims": { "scope": "read" }
}
```

### 5.7 `mtls`
```jsonc
{
  "type": "mtls",
  "client_cert_ref": "keychain:loom.<source>.cert",
  "client_key_ref":  "keychain:loom.<source>.privkey",
  "ca_bundle_ref":   "keychain:loom.<source>.ca",
  "bearer_token_ref": "keychain:loom.<source>.token"  // optional, layered
}
```

### 5.8 `custom`
Escape hatch — a JS/Python script registered as an adapter. Sandboxed, reviewed at registration, no filesystem access.

---

## 6. Registration Flow (UX)

### 6.1 Happy path — OpenAPI
```
1. Admin: "Add API"
2. Paste URL: https://app.altbiolab.com/api/openapi.json
3. Loom fetches, parses, shows list of operations
4. Admin configures auth (e.g. Bearer token → paste into secure field)
5. Loom stores token in Keychain
6. Admin selects operations to expose (default: only GETs enabled)
7. For each selected op, Loom auto-generates tool definition
8. Admin reviews AI-facing descriptions, adjusts
9. Admin clicks "Test" — calls each tool with sample params
10. Admin saves → tools available to AI
```

### 6.2 Manual registration
Same as above but Admin fills in each operation by hand using a form that matches §4 schema.

### 6.3 SQL/ODBC registration
```
1. Admin: "Add Data Source" → SQL
2. Connection string (stored in Keychain)
3. Admin writes a set of named parameterized queries:
   - "list_low_stock_items(threshold INT)"
   - "find_customer_by_email(email TEXT)"
4. Each named query becomes a tool
5. Raw SQL execution by AI is OFF by default
```

Raw SQL is too dangerous to expose generically. Named queries give AI flexibility within admin-defined safety.

---

## 7. Invocation Flow

When AI decides to call a tool:

```
1. Agent runtime receives tool call from model
2. Lookup tool by id → fetch definition + source
3. Check scopes/enabled/rate limits
4. If `requires_confirmation` → pause, ask user in UI
5. Resolve credentials from Keychain
6. Build HTTP request per operation spec
7. Execute with timeout + size cap
8. Apply `output_transform` to response
9. Apply `redact_response_fields`
10. Log to audit trail
11. Return shaped response to model
```

---

## 8. Audit Log Schema

```jsonc
{
  "id": "01J...",
  "timestamp": "2026-04-20T10:15:32.123Z",
  "user_id": "alice@lab.local",
  "conversation_id": "conv_abc123",
  "tool_id": "altbiolab_list_samples",
  "source_id": "altbiolab",
  "params": { "status": "qc_failed", "from_date": "2026-04-13" },
  "params_redacted": false,
  "http": {
    "method": "GET",
    "url": "https://app.altbiolab.com/api/v1/samples?status=qc_failed&from_date=2026-04-13",
    "status": 200,
    "latency_ms": 187,
    "response_bytes": 4821
  },
  "response_preview": "{ \"samples\": [ { \"id\": \"S-1042\", ... } ], \"total\": 7 }",
  "outcome": "success",           // success | error | denied | timeout
  "denial_reason": null
}
```

Stored in append-only SQLite with optional export to SIEM.

---

## 9. Future Extensions (v2+)

- **GraphQL field-level scoping** — per-field read permissions
- **Response caching** — reduce load on customer APIs for repeated AI calls
- **Batch tool calls** — AI can declare multiple calls to execute in parallel
- **Webhook integrations** — AI reacts to events from customer systems
- **Streaming responses** — for long-running customer API operations
- **API versioning** — track customer API spec changes, flag breaking changes

---

## 10. Reference: ALTBioLab Example

Full walkthrough of registering [app.altbiolab.com](https://app.altbiolab.com) as a Loom API source:

```bash
# 1. Admin opens Loom → Settings → APIs → Add

# 2. Form values:
Name:         ALTBioLab LIMS
OpenAPI URL:  https://app.altbiolab.com/api/openapi.json
Auth:         OAuth2 (Authorization Code)
              Client ID:     <from ALTBioLab admin console>
              Client Secret: <pasted, stored in Keychain>
              Scopes:        read:samples read:qc

# 3. After OAuth flow:
Loom imports 47 operations.
Admin enables 12 (all read-only).
Admin disables 35 (writes, admin, unused).

# 4. Test: "AI, list samples that failed QC this week"
→ AI calls altbiolab_list_samples(status="qc_failed", from_date="2026-04-13")
→ Receives 7 samples
→ Summarizes with local 70B model
→ User reads answer. Zero data left premises.
```

This is the core Loom experience.
