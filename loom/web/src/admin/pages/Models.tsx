import { useEffect, useState } from "react";

interface ModelEntry {
  id: string;
  path: string;
  description?: string;
}

async function fetchModels(): Promise<ModelEntry[]> {
  const res = await fetch("/api/admin/models");
  if (!res.ok) throw new Error(`${res.status}`);
  return res.json();
}

async function addModel(entry: ModelEntry): Promise<ModelEntry> {
  const res = await fetch("/api/admin/models", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(entry),
  });
  if (!res.ok) throw new Error(`${res.status}: ${await res.text()}`);
  return res.json();
}

async function removeModel(id: string): Promise<void> {
  const res = await fetch(`/api/admin/models/${encodeURIComponent(id)}`, { method: "DELETE" });
  if (!res.ok) throw new Error(`${res.status}`);
}

export function ModelsPage() {
  const [models, setModels] = useState<ModelEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [adding, setAdding] = useState(false);
  const [form, setForm] = useState({ id: "", path: "", description: "" });
  const [formError, setFormError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  const load = () => {
    setLoading(true);
    fetchModels()
      .then(setModels)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  };

  useEffect(load, []);

  const handleAdd = async () => {
    if (!form.id.trim() || !form.path.trim()) {
      setFormError("Model ID and path are required.");
      return;
    }
    setSaving(true);
    setFormError(null);
    try {
      const m = await addModel({ id: form.id.trim(), path: form.path.trim(), description: form.description.trim() || undefined });
      setModels((prev) => [...prev, m]);
      setForm({ id: "", path: "", description: "" });
      setAdding(false);
    } catch (e) {
      setFormError(e instanceof Error ? e.message : String(e));
    } finally {
      setSaving(false);
    }
  };

  const handleRemove = async (id: string) => {
    try {
      await removeModel(id);
      setModels((prev) => prev.filter((m) => m.id !== id));
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  };

  return (
    <div className="p-8 max-w-3xl">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-lg font-semibold text-[var(--loom-fg)]">Models</h1>
          <p className="text-sm text-[var(--loom-fg-soft)] mt-0.5">Manage MLX model files available for inference.</p>
        </div>
        <button
          onClick={() => { setAdding(true); setFormError(null); }}
          className="text-sm rounded-lg bg-[var(--loom-accent)] text-white px-3.5 py-2 hover:opacity-90 transition-opacity"
        >
          + Add model
        </button>
      </div>

      {adding && (
        <div className="mb-6 rounded-xl border border-[var(--loom-border)] bg-[var(--loom-bg-soft)] p-5 space-y-3">
          <h2 className="text-sm font-semibold text-[var(--loom-fg)]">Add model</h2>
          {formError && <p className="text-xs text-[var(--loom-danger)]">{formError}</p>}
          <div className="space-y-2">
            <input
              placeholder="Model ID (e.g. qwen-0.5b)"
              value={form.id}
              onChange={(e) => setForm((f) => ({ ...f, id: e.target.value }))}
              className="w-full rounded-lg border border-[var(--loom-border)] bg-[var(--loom-bg)] px-3 py-2 text-sm outline-none focus:ring-1 focus:ring-[var(--loom-accent)]"
            />
            <input
              placeholder="Local path (e.g. /Users/you/models/qwen-0.5b)"
              value={form.path}
              onChange={(e) => setForm((f) => ({ ...f, path: e.target.value }))}
              className="w-full rounded-lg border border-[var(--loom-border)] bg-[var(--loom-bg)] px-3 py-2 text-sm outline-none focus:ring-1 focus:ring-[var(--loom-accent)]"
            />
            <input
              placeholder="Description (optional)"
              value={form.description}
              onChange={(e) => setForm((f) => ({ ...f, description: e.target.value }))}
              className="w-full rounded-lg border border-[var(--loom-border)] bg-[var(--loom-bg)] px-3 py-2 text-sm outline-none focus:ring-1 focus:ring-[var(--loom-accent)]"
            />
          </div>
          <div className="flex gap-2">
            <button
              onClick={handleAdd}
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
      ) : models.length === 0 ? (
        <div className="rounded-xl border border-dashed border-[var(--loom-border)] p-10 text-center">
          <p className="text-sm text-[var(--loom-fg-soft)]">No models registered yet.</p>
          <p className="text-xs text-[var(--loom-fg-soft)] mt-1 opacity-70">Add an MLX model path to get started.</p>
        </div>
      ) : (
        <div className="space-y-2">
          {models.map((m) => (
            <div key={m.id} className="flex items-start gap-4 rounded-xl border border-[var(--loom-border)] bg-[var(--loom-bg-soft)] px-4 py-3">
              <div className="flex-1 min-w-0">
                <p className="text-sm font-medium text-[var(--loom-fg)] truncate">{m.id}</p>
                <p className="text-xs text-[var(--loom-fg-soft)] truncate mt-0.5">{m.path}</p>
                {m.description && <p className="text-xs text-[var(--loom-fg-soft)] mt-0.5 opacity-70">{m.description}</p>}
              </div>
              <button
                onClick={() => handleRemove(m.id)}
                className="shrink-0 text-xs text-[var(--loom-fg-soft)] hover:text-[var(--loom-danger)] transition-colors"
              >
                Remove
              </button>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
