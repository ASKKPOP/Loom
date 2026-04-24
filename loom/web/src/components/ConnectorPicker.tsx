import { useEffect, useRef, useState } from "react";
import type { Connector } from "../pages/CustomizeConnectors";
import { queryConnector } from "../pages/CustomizeConnectors";

interface Props {
  onInject: (text: string) => void;
  onClose: () => void;
}

function formatResult(result: unknown, connector: Connector): string {
  if (connector.type === "filesystem") {
    const r = result as { type: string; path: string; content?: string; entries?: { name: string; type: string; size: number | null }[]; truncated?: boolean };
    if (r.type === "directory") {
      const lines = (r.entries ?? []).map((e) => `${e.type === "dir" ? "📁" : "📄"} ${e.name}${e.size != null ? ` (${(e.size / 1024).toFixed(1)} KB)` : ""}`);
      return `**Directory: ${r.path}**\n\`\`\`\n${lines.join("\n")}\n\`\`\``;
    }
    const suffix = r.truncated ? "\n\n_(truncated at 128 KB)_" : "";
    return `**File: ${r.path}**\n\`\`\`\n${r.content ?? ""}\n\`\`\`${suffix}`;
  }

  if (connector.type === "sqlite") {
    const r = result as { columns: string[]; rows: Record<string, unknown>[]; count: number };
    if (r.rows.length === 0) return "_(query returned no rows)_";
    const header = `| ${r.columns.join(" | ")} |`;
    const sep = `| ${r.columns.map(() => "---").join(" | ")} |`;
    const rows = r.rows.map((row) => `| ${r.columns.map((c) => String(row[c] ?? "")).join(" | ")} |`);
    return `**SQLite query result** (${r.count} rows)\n\n${header}\n${sep}\n${rows.join("\n")}`;
  }

  if (connector.type === "http") {
    const r = result as { status: number; body: unknown; content_type: string };
    const body = typeof r.body === "string" ? r.body : JSON.stringify(r.body, null, 2);
    return `**HTTP ${r.status}** (${r.content_type})\n\`\`\`\n${body}\n\`\`\``;
  }

  return `\`\`\`json\n${JSON.stringify(result, null, 2)}\n\`\`\``;
}

export function ConnectorPicker({ onInject, onClose }: Props) {
  const [connectors, setConnectors] = useState<Connector[]>([]);
  const [loading, setLoading] = useState(true);
  const [selected, setSelected] = useState<Connector | null>(null);
  const [params, setParams] = useState<Record<string, string>>({});
  const [querying, setQuerying] = useState(false);
  const [queryError, setQueryError] = useState<string | null>(null);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    fetch("/api/connectors")
      .then((r) => r.json())
      .then((data) => { setConnectors(data); setLoading(false); })
      .catch(() => setLoading(false));
  }, []);

  // Close on click outside
  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) onClose();
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, [onClose]);

  const handleQuery = async () => {
    if (!selected) return;
    setQuerying(true);
    setQueryError(null);
    try {
      const result = await queryConnector(selected.id, params as Record<string, unknown>);
      onInject(formatResult(result, selected));
      onClose();
    } catch (e) {
      setQueryError(e instanceof Error ? e.message : String(e));
    } finally {
      setQuerying(false);
    }
  };

  const PARAM_FIELDS: Record<Connector["type"], { key: string; label: string; placeholder: string; multiline?: boolean }[]> = {
    filesystem: [{ key: "path", label: "Path", placeholder: "/path/to/file-or-directory" }],
    sqlite: [{ key: "query", label: "SQL query", placeholder: "SELECT * FROM table LIMIT 20", multiline: true }],
    http: [
      { key: "endpoint", label: "Endpoint (appended to base URL)", placeholder: "/users/1" },
      { key: "method", label: "Method", placeholder: "GET" },
    ],
  };

  return (
    <div
      ref={ref}
      className="absolute bottom-full left-0 mb-2 w-96 rounded-2xl border border-[var(--loom-border)] bg-[var(--loom-bg)] shadow-lg z-50 overflow-hidden"
    >
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-[var(--loom-border)]">
        <div className="flex items-center gap-2">
          {selected && (
            <button
              onClick={() => { setSelected(null); setParams({}); setQueryError(null); }}
              className="text-[var(--loom-fg-soft)] hover:text-[var(--loom-fg)] text-sm"
            >
              ←
            </button>
          )}
          <span className="text-sm font-semibold text-[var(--loom-fg)]">
            {selected ? selected.name : "Connectors"}
          </span>
        </div>
        <button onClick={onClose} className="text-[var(--loom-fg-soft)] hover:text-[var(--loom-fg)] text-lg leading-none">×</button>
      </div>

      {/* Body */}
      <div className="p-4">
        {loading ? (
          <p className="text-sm text-[var(--loom-fg-soft)] text-center py-4">Loading…</p>
        ) : !selected ? (
          connectors.length === 0 ? (
            <div className="text-center py-6">
              <p className="text-sm text-[var(--loom-fg-soft)]">No connectors configured.</p>
              <a href="/customize/connectors" className="text-xs text-[var(--loom-accent)] mt-1 block" onClick={onClose}>
                Add one in Customize →
              </a>
            </div>
          ) : (
            <div className="space-y-1.5">
              {connectors.map((c) => (
                <button
                  key={c.id}
                  onClick={() => { setSelected(c); setParams({}); setQueryError(null); }}
                  className="w-full flex items-center gap-3 px-3 py-2.5 rounded-xl text-left hover:bg-[var(--loom-bg-soft)] transition-colors"
                >
                  <span className="text-xl">
                    {c.type === "filesystem" ? "📁" : c.type === "sqlite" ? "🗃️" : "🌐"}
                  </span>
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-medium text-[var(--loom-fg)] truncate">{c.name}</p>
                    {c.description && (
                      <p className="text-xs text-[var(--loom-fg-soft)] truncate">{c.description}</p>
                    )}
                  </div>
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="text-[var(--loom-fg-soft)] shrink-0">
                    <path d="M9 18l6-6-6-6"/>
                  </svg>
                </button>
              ))}
            </div>
          )
        ) : (
          <div className="space-y-3">
            {queryError && (
              <p className="text-xs text-[var(--loom-danger)] bg-red-50 dark:bg-red-900/20 rounded-lg px-3 py-2">{queryError}</p>
            )}
            {PARAM_FIELDS[selected.type].map((f) => (
              <div key={f.key}>
                <label className="block text-xs text-[var(--loom-fg-soft)] mb-1">{f.label}</label>
                {f.multiline ? (
                  <textarea
                    value={params[f.key] ?? ""}
                    onChange={(e) => setParams((p) => ({ ...p, [f.key]: e.target.value }))}
                    placeholder={f.placeholder}
                    rows={3}
                    className="w-full rounded-lg border border-[var(--loom-border)] bg-[var(--loom-bg-soft)] px-3 py-2 text-sm font-mono outline-none focus:ring-1 focus:ring-[var(--loom-accent)] resize-y"
                  />
                ) : (
                  <input
                    value={params[f.key] ?? ""}
                    onChange={(e) => setParams((p) => ({ ...p, [f.key]: e.target.value }))}
                    placeholder={f.placeholder}
                    onKeyDown={(e) => { if (e.key === "Enter") handleQuery(); }}
                    className="w-full rounded-lg border border-[var(--loom-border)] bg-[var(--loom-bg-soft)] px-3 py-2 text-sm outline-none focus:ring-1 focus:ring-[var(--loom-accent)]"
                  />
                )}
              </div>
            ))}
            <button
              onClick={handleQuery}
              disabled={querying}
              className="w-full py-2.5 rounded-xl bg-[var(--loom-accent)] text-white text-sm font-medium hover:opacity-90 disabled:opacity-50 transition-opacity"
            >
              {querying ? "Fetching…" : "Fetch & insert into message"}
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
