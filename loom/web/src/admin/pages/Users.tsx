import { useEffect, useState } from "react";

interface User {
  username: string;
  role: "admin" | "user";
  created_at: string;
}

async function fetchUsers(): Promise<User[]> {
  const res = await fetch("/api/admin/users");
  if (!res.ok) throw new Error(`${res.status}`);
  return res.json();
}

async function createUser(data: { username: string; password: string; role: User["role"] }): Promise<User> {
  const res = await fetch("/api/admin/users", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
  if (!res.ok) throw new Error(`${res.status}: ${await res.text()}`);
  return res.json();
}

async function deleteUser(username: string): Promise<void> {
  const res = await fetch(`/api/admin/users/${encodeURIComponent(username)}`, { method: "DELETE" });
  if (!res.ok) throw new Error(`${res.status}`);
}

export function UsersPage() {
  const [users, setUsers] = useState<User[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [adding, setAdding] = useState(false);
  const [form, setForm] = useState({ username: "", password: "", role: "user" as User["role"] });
  const [formError, setFormError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  const load = () => {
    setLoading(true);
    fetchUsers()
      .then(setUsers)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  };

  useEffect(load, []);

  const handleAdd = async () => {
    if (!form.username.trim() || !form.password.trim()) {
      setFormError("Username and password are required.");
      return;
    }
    setSaving(true);
    setFormError(null);
    try {
      const u = await createUser({ username: form.username.trim(), password: form.password, role: form.role });
      setUsers((prev) => [...prev, u]);
      setForm({ username: "", password: "", role: "user" });
      setAdding(false);
    } catch (e) {
      setFormError(e instanceof Error ? e.message : String(e));
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async (username: string) => {
    try {
      await deleteUser(username);
      setUsers((prev) => prev.filter((u) => u.username !== username));
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  };

  return (
    <div className="p-8 max-w-3xl">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-lg font-semibold text-[var(--loom-fg)]">Users</h1>
          <p className="text-sm text-[var(--loom-fg-soft)] mt-0.5">Manage local user accounts.</p>
        </div>
        <button
          onClick={() => { setAdding(true); setFormError(null); }}
          className="text-sm rounded-lg bg-[var(--loom-accent)] text-white px-3.5 py-2 hover:opacity-90 transition-opacity"
        >
          + Add user
        </button>
      </div>

      {adding && (
        <div className="mb-6 rounded-xl border border-[var(--loom-border)] bg-[var(--loom-bg-soft)] p-5 space-y-3">
          <h2 className="text-sm font-semibold text-[var(--loom-fg)]">New user</h2>
          {formError && <p className="text-xs text-[var(--loom-danger)]">{formError}</p>}
          <div className="space-y-2">
            <input
              placeholder="Username"
              value={form.username}
              onChange={(e) => setForm((f) => ({ ...f, username: e.target.value }))}
              className="w-full rounded-lg border border-[var(--loom-border)] bg-[var(--loom-bg)] px-3 py-2 text-sm outline-none focus:ring-1 focus:ring-[var(--loom-accent)]"
            />
            <input
              type="password"
              placeholder="Password"
              value={form.password}
              onChange={(e) => setForm((f) => ({ ...f, password: e.target.value }))}
              className="w-full rounded-lg border border-[var(--loom-border)] bg-[var(--loom-bg)] px-3 py-2 text-sm outline-none focus:ring-1 focus:ring-[var(--loom-accent)]"
            />
            <select
              value={form.role}
              onChange={(e) => setForm((f) => ({ ...f, role: e.target.value as User["role"] }))}
              className="w-full rounded-lg border border-[var(--loom-border)] bg-[var(--loom-bg)] px-3 py-2 text-sm outline-none focus:ring-1 focus:ring-[var(--loom-accent)]"
            >
              <option value="user">User</option>
              <option value="admin">Admin</option>
            </select>
          </div>
          <div className="flex gap-2">
            <button
              onClick={handleAdd}
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
      ) : users.length === 0 ? (
        <div className="rounded-xl border border-dashed border-[var(--loom-border)] p-10 text-center">
          <p className="text-sm text-[var(--loom-fg-soft)]">No users yet.</p>
        </div>
      ) : (
        <div className="space-y-2">
          {users.map((u) => (
            <div key={u.username} className="flex items-center gap-4 rounded-xl border border-[var(--loom-border)] bg-[var(--loom-bg-soft)] px-4 py-3">
              <div className="flex-1 min-w-0">
                <p className="text-sm font-medium text-[var(--loom-fg)]">{u.username}</p>
                <p className="text-xs text-[var(--loom-fg-soft)] mt-0.5">
                  {u.role} · created {new Date(u.created_at).toLocaleDateString()}
                </p>
              </div>
              <span className={`text-xs px-2 py-0.5 rounded-full ${
                u.role === "admin"
                  ? "bg-[var(--loom-accent-soft)] text-[var(--loom-accent)]"
                  : "bg-[var(--loom-border)] text-[var(--loom-fg-soft)]"
              }`}>
                {u.role}
              </span>
              <button
                onClick={() => handleDelete(u.username)}
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
