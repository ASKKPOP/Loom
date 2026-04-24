import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

export interface Connector {
  id: string;
  name: string;
  type: "filesystem" | "sqlite" | "http";
  description: string;
  config: Record<string, string>;
  created_at: string;
}

type ConnectorType = Connector["type"];

const TYPE_META: Record<ConnectorType, { label: string; icon: string; description: string; fields: { key: string; label: string; placeholder: string; required: boolean }[] }> = {
  filesystem: {
    label: "Filesystem",
    icon: "📁",
    description: "Read files and list directories from your Mac.",
    fields: [
      { key: "root_path", label: "Root path (optional)", placeholder: "/Users/you/projects", required: false },
    ],
  },
  sqlite: {
    label: "SQLite",
    icon: "🗃️",
    description: "Run SELECT queries against a local SQLite database.",
    fields: [
      { key: "db_path", label: "Database path", placeholder: "/Users/you/data.db", required: true },
    ],
  },
  http: {
    label: "HTTP / REST",
    icon: "🌐",
    description: "Call any HTTP API with configurable base URL and auth headers.",
    fields: [
      { key: "base_url", label: "Base URL", placeholder: "https://api.example.com", required: true },
      { key: "headers_raw", label: "Headers (JSON, optional)", placeholder: '{"Authorization": "Bearer tok"}', required: false },
    ],
  },
};

async function fetchConnectors(): Promise<Connector[]> {
  const res = await fetch("/api/connectors");
  if (!res.ok) throw new Error(`${res.status}`);
  return res.json();
}

async function addConnector(body: { name: string; type: string; description: string; config: Record<string, unknown> }): Promise<Connector> {
  const res = await fetch("/api/connectors", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(`${res.status}: ${await res.text()}`);
  return res.json();
}

async function deleteConnector(id: string): Promise<void> {
  const res = await fetch(`/api/connectors/${id}`, { method: "DELETE" });
  if (!res.ok) throw new Error(`${res.status}`);
}

export async function queryConnector(id: string, params: Record<string, unknown>): Promise<unknown> {
  const res = await fetch(`/api/connectors/${id}/query`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ params }),
  });
  if (!res.ok) throw new Error(`${res.status}: ${await res.text()}`);
  return res.json();
}

function TypeBadge({ type }: { type: ConnectorType }) {
  const meta = TYPE_META[type];
  return (
    <span className="flex items-center gap-1 text-[10px] px-2 py-0.5 rounded-full bg-[var(--loom-border)] text-[var(--loom-fg-soft)]">
      {meta.icon} {meta.label}
    </span>
  );
}

export function CustomizeConnectorsPage() {
  const [connectors, setConnectors] = useState<Connector[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [adding, setAdding] = useState(false);
  const [selectedType, setSelectedType] = useState<ConnectorType>("filesystem");
  const [form, setForm] = useState<Record<string, string>>({ name: "", description: "" });
  const [formError, setFormError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  const load = () => {
    setLoading(true);
    fetchConnectors()
      .then(setConnectors)
      .catch((e: Error) => setError(e.message))
      .finally(() => setLoading(false));
  };
  useEffect(load, []);

  const startAdding = () => {
    setAdding(true);
    setFormError(null);
    setForm({ name: "", description: "" });
    setSelectedType("filesystem");
  };

  const handleSave = async () => {
    if (!form.name?.trim()) { setFormError("Name is required."); return; }
    const meta = TYPE_META[selectedType];
    for (const f of meta.fields) {
      if (f.required && !form[f.key]?.trim()) {
        setFormError(`${f.label} is required.`);
        return;
      }
    }

    // Build config from form fields
    const config: Record<string, unknown> = {};
    for (const f of meta.fields) {
      if (f.key === "headers_raw") {
        if (form.headers_raw?.trim()) {
          try { config.headers = JSON.parse(form.headers_raw); }
          catch { setFormError("Headers must be valid JSON."); return; }
        }
      } else {
        if (form[f.key]) config[f.key] = form[f.key];
      }
    }

    setSaving(true);
    setFormError(null);
    try {
      const c = await addConnector({ name: form.name.trim(), type: selectedType, description: form.description?.trim() || "", config });
      setConnectors((prev) => [...prev, c]);
      setAdding(false);
    } catch (e) {
      setFormError(e instanceof Error ? e.message : String(e));
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async (id: string) => {
    try {
      await deleteConnector(id);
      setConnectors((prev) => prev.filter((c) => c.id !== id));
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  };

  return (
    <div className="flex-1 overflow-y-auto p-8">
      {/* Header */}
      <div className="mb-8 max-w-2xl">
        <div className="w-14 h-14 rounded-2xl bg-[var(--loom-accent-soft)] flex items-center justify-center mb-4">
          <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="var(--loom-accent)" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
            <rect x="2" y="2" width="8" height="8" rx="2"/><rect x="14" y="2" width="8" height="8" rx="2"/>
            <rect x="2" y="14" width="8" height="8" rx="2"/><rect x="14" y="14" width="8" height="8" rx="2"/>
          </svg>
        </div>
        <h1 className="text-2xl font-semibold text-[var(--loom-fg)] mb-2">Customize Loom</h1>
        <p className="text-[var(--loom-fg-soft)] text-sm leading-relaxed">
          Connectors let Loom read from files, databases, and APIs. Use the 📎 button in chat to query and inject data into your messages.
        </p>
        <div className="flex gap-3 mt-5">
          <Link
            to="/customize/skills"
            className="flex items-center gap-2 px-4 py-2.5 rounded-xl text-sm font-medium no-underline text-[var(--loom-fg-soft)] hover:bg-[var(--loom-border)] transition-colors"
          >
            <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M12 2l3.09 6.26L22 9.27l-5 4.87 1.18 6.88L12 17.77l-6.18 3.25L7 14.14 2 9.27l6.91-1.01L12 2z"/>
            </svg>
            Skills
          </Link>
          <Link
            to="/customize/connectors"
            className="flex items-center gap-2 px-4 py-2.5 rounded-xl text-sm font-medium no-underline bg-[var(--loom-border)] text-[var(--loom-fg)] transition-colors"
          >
            <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <rect x="2" y="2" width="8" height="8" rx="2"/><rect x="14" y="2" width="8" height="8" rx="2"/>
              <rect x="2" y="14" width="8" height="8" rx="2"/><rect x="14" y="14" width="8" height="8" rx="2"/>
            </svg>
            Connectors
          </Link>
        </div>
      </div>

      <div className="max-w-2xl">
        {/* Add connector button */}
        <div className="flex justify-end mb-4">
          <button
            onClick={startAdding}
            className="text-sm rounded-lg bg-[var(--loom-accent)] text-white px-3.5 py-2 hover:opacity-90 transition-opacity"
          >
            + Add connector
          </button>
        </div>

        {/* Add connector form */}
        {adding && (
          <div className="mb-6 rounded-xl border border-[var(--loom-border)] bg-[var(--loom-bg-soft)] p-5 space-y-4">
            <h2 className="text-sm font-semibold text-[var(--loom-fg)]">New connector</h2>
            {formError && <p className="text-xs text-[var(--loom-danger)]">{formError}</p>}

            {/* Type picker */}
            <div>
              <label className="block text-xs text-[var(--loom-fg-soft)] mb-2">Type</label>
              <div className="flex gap-2 flex-wrap">
                {(Object.keys(TYPE_META) as ConnectorType[]).map((t) => (
                  <button
                    key={t}
                    onClick={() => setSelectedType(t)}
                    className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition-colors ${
                      selectedType === t
                        ? "bg-[var(--loom-accent)] text-white"
                        : "border border-[var(--loom-border)] text-[var(--loom-fg-soft)] hover:bg-[var(--loom-border)]"
                    }`}
                  >
                    {TYPE_META[t].icon} {TYPE_META[t].label}
                  </button>
                ))}
              </div>
              <p className="text-xs text-[var(--loom-fg-soft)] mt-1.5 opacity-70">{TYPE_META[selectedType].description}</p>
            </div>

            {/* Common fields */}
            <input
              placeholder="Name (e.g. My project files)"
              value={form.name ?? ""}
              onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))}
              className="w-full rounded-lg border border-[var(--loom-border)] bg-[var(--loom-bg)] px-3 py-2 text-sm outline-none focus:ring-1 focus:ring-[var(--loom-accent)]"
            />
            <input
              placeholder="Description (optional)"
              value={form.description ?? ""}
              onChange={(e) => setForm((f) => ({ ...f, description: e.target.value }))}
              className="w-full rounded-lg border border-[var(--loom-border)] bg-[var(--loom-bg)] px-3 py-2 text-sm outline-none focus:ring-1 focus:ring-[var(--loom-accent)]"
            />

            {/* Type-specific config fields */}
            {TYPE_META[selectedType].fields.map((f) => (
              <div key={f.key}>
                <label className="block text-xs text-[var(--loom-fg-soft)] mb-1">{f.label}</label>
                {f.key === "headers_raw" ? (
                  <textarea
                    placeholder={f.placeholder}
                    value={form[f.key] ?? ""}
                    onChange={(e) => setForm((prev) => ({ ...prev, [f.key]: e.target.value }))}
                    rows={3}
                    className="w-full rounded-lg border border-[var(--loom-border)] bg-[var(--loom-bg)] px-3 py-2 text-sm font-mono outline-none focus:ring-1 focus:ring-[var(--loom-accent)] resize-y"
                  />
                ) : (
                  <input
                    placeholder={f.placeholder}
                    value={form[f.key] ?? ""}
                    onChange={(e) => setForm((prev) => ({ ...prev, [f.key]: e.target.value }))}
                    className="w-full rounded-lg border border-[var(--loom-border)] bg-[var(--loom-bg)] px-3 py-2 text-sm outline-none focus:ring-1 focus:ring-[var(--loom-accent)]"
                  />
                )}
              </div>
            ))}

            <div className="flex gap-2 pt-1">
              <button
                onClick={handleSave}
                disabled={saving}
                className="text-sm rounded-lg bg-[var(--loom-accent)] text-white px-3.5 py-2 hover:opacity-90 disabled:opacity-50"
              >
                {saving ? "Saving…" : "Save"}
              </button>
              <button
                onClick={() => setAdding(false)}
                className="text-sm rounded-lg border border-[var(--loom-border)] px-3.5 py-2 hover:bg-[var(--loom-border)]"
              >
                Cancel
              </button>
            </div>
          </div>
        )}

        {error && <p className="text-sm text-[var(--loom-danger)] mb-4">{error}</p>}

        {loading ? (
          <p className="text-sm text-[var(--loom-fg-soft)]">Loading…</p>
        ) : connectors.length === 0 ? (
          <div className="rounded-xl border border-dashed border-[var(--loom-border)] p-10 text-center">
            <p className="text-sm text-[var(--loom-fg-soft)]">No connectors yet.</p>
            <p className="text-xs text-[var(--loom-fg-soft)] mt-1 opacity-70">
              Add a connector, then use 📎 in chat to inject data into your messages.
            </p>
          </div>
        ) : (
          <div className="space-y-2">
            {connectors.map((c) => (
              <div key={c.id} className="flex items-start gap-4 rounded-xl border border-[var(--loom-border)] bg-[var(--loom-bg-soft)] px-4 py-3">
                <span className="text-xl mt-0.5">{TYPE_META[c.type]?.icon ?? "🔌"}</span>
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-medium text-[var(--loom-fg)]">{c.name}</p>
                  {c.description && (
                    <p className="text-xs text-[var(--loom-fg-soft)] mt-0.5">{c.description}</p>
                  )}
                  <div className="mt-1.5">
                    <TypeBadge type={c.type} />
                  </div>
                </div>
                <button
                  onClick={() => handleDelete(c.id)}
                  className="shrink-0 text-xs text-[var(--loom-fg-soft)] hover:text-[var(--loom-danger)] transition-colors"
                >
                  Remove
                </button>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
