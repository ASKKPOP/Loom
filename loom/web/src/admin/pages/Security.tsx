import { useEffect, useState } from "react";

interface ApiKey {
  id: string;
  name: string;
  prefix: string;
  created_at: string;
}

interface NewKeyResult {
  key: ApiKey;
  secret: string;
}

async function fetchKeys(): Promise<ApiKey[]> {
  const res = await fetch("/api/admin/security/keys");
  if (!res.ok) throw new Error(`${res.status}`);
  return res.json();
}

async function createKey(name: string): Promise<NewKeyResult> {
  const res = await fetch("/api/admin/security/keys", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ name }),
  });
  if (!res.ok) throw new Error(`${res.status}: ${await res.text()}`);
  return res.json();
}

async function deleteKey(id: string): Promise<void> {
  const res = await fetch(`/api/admin/security/keys/${encodeURIComponent(id)}`, { method: "DELETE" });
  if (!res.ok) throw new Error(`${res.status}`);
}

export function SecurityPage() {
  const [keys, setKeys] = useState<ApiKey[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [adding, setAdding] = useState(false);
  const [newName, setNewName] = useState("");
  const [formError, setFormError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [revealed, setRevealed] = useState<NewKeyResult | null>(null);
  const [copied, setCopied] = useState(false);

  const load = () => {
    setLoading(true);
    fetchKeys()
      .then(setKeys)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  };

  useEffect(load, []);

  const handleCreate = async () => {
    if (!newName.trim()) { setFormError("Key name is required."); return; }
    setSaving(true);
    setFormError(null);
    try {
      const result = await createKey(newName.trim());
      setKeys((prev) => [...prev, result.key]);
      setRevealed(result);
      setNewName("");
      setAdding(false);
    } catch (e) {
      setFormError(e instanceof Error ? e.message : String(e));
    } finally {
      setSaving(false);
    }
  };

  const copySecret = async (secret: string) => {
    try {
      await navigator.clipboard.writeText(secret);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch { /* blocked */ }
  };

  const handleDelete = async (id: string) => {
    try {
      await deleteKey(id);
      setKeys((prev) => prev.filter((k) => k.id !== id));
      if (revealed?.key.id === id) setRevealed(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  };

  return (
    <div className="p-8 max-w-3xl">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-lg font-semibold text-[var(--loom-fg)]">Security</h1>
          <p className="text-sm text-[var(--loom-fg-soft)] mt-0.5">Manage API keys for programmatic access to the gateway.</p>
        </div>
        <button
          onClick={() => { setAdding(true); setFormError(null); }}
          className="text-sm rounded-lg bg-[var(--loom-accent)] text-white px-3.5 py-2 hover:opacity-90 transition-opacity"
        >
          + Create key
        </button>
      </div>

      {/* New key secret reveal */}
      {revealed && (
        <div className="mb-6 rounded-xl border border-[var(--loom-ok)] bg-[var(--loom-bg-soft)] p-5">
          <p className="text-sm font-semibold text-[var(--loom-ok)] mb-1">Key created — copy it now</p>
          <p className="text-xs text-[var(--loom-fg-soft)] mb-3">This secret will not be shown again.</p>
          <div className="flex gap-2">
            <code className="flex-1 bg-[var(--loom-bg)] border border-[var(--loom-border)] rounded-lg px-3 py-2 text-xs font-mono truncate">
              {revealed.secret}
            </code>
            <button
              onClick={() => copySecret(revealed.secret)}
              className="shrink-0 text-xs rounded-lg border border-[var(--loom-border)] px-3 py-2 hover:bg-[var(--loom-border)]"
            >
              {copied ? "Copied ✓" : "Copy"}
            </button>
          </div>
          <button
            onClick={() => setRevealed(null)}
            className="mt-3 text-xs text-[var(--loom-fg-soft)] hover:text-[var(--loom-fg)]"
          >
            Dismiss
          </button>
        </div>
      )}

      {adding && (
        <div className="mb-6 rounded-xl border border-[var(--loom-border)] bg-[var(--loom-bg-soft)] p-5 space-y-3">
          <h2 className="text-sm font-semibold text-[var(--loom-fg)]">New API key</h2>
          {formError && <p className="text-xs text-[var(--loom-danger)]">{formError}</p>}
          <input
            placeholder="Key name (e.g. local-dev)"
            value={newName}
            onChange={(e) => setNewName(e.target.value)}
            onKeyDown={(e) => { if (e.key === "Enter") handleCreate(); }}
            className="w-full rounded-lg border border-[var(--loom-border)] bg-[var(--loom-bg)] px-3 py-2 text-sm outline-none focus:ring-1 focus:ring-[var(--loom-accent)]"
          />
          <div className="flex gap-2">
            <button
              onClick={handleCreate}
              disabled={saving}
              className="text-sm rounded-lg bg-[var(--loom-accent)] text-white px-3.5 py-2 hover:opacity-90 disabled:opacity-50"
            >
              {saving ? "Creating…" : "Create"}
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
      ) : keys.length === 0 ? (
        <div className="rounded-xl border border-dashed border-[var(--loom-border)] p-10 text-center">
          <p className="text-sm text-[var(--loom-fg-soft)]">No API keys yet.</p>
        </div>
      ) : (
        <div className="space-y-2">
          {keys.map((k) => (
            <div key={k.id} className="flex items-center gap-4 rounded-xl border border-[var(--loom-border)] bg-[var(--loom-bg-soft)] px-4 py-3">
              <div className="flex-1 min-w-0">
                <p className="text-sm font-medium text-[var(--loom-fg)]">{k.name}</p>
                <p className="text-xs text-[var(--loom-fg-soft)] mt-0.5 font-mono">
                  {k.prefix}… · created {new Date(k.created_at).toLocaleDateString()}
                </p>
              </div>
              <button
                onClick={() => handleDelete(k.id)}
                className="shrink-0 text-xs text-[var(--loom-fg-soft)] hover:text-[var(--loom-danger)] transition-colors"
              >
                Revoke
              </button>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
