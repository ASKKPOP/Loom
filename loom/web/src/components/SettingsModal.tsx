import { useState } from "react";
import type { Settings } from "../types";
import { checkHealth } from "../lib/api";

interface Props {
  open: boolean;
  settings: Settings;
  systemPrompt: string;
  onClose: () => void;
  onSave: (settings: Settings, systemPrompt: string) => void;
}

type Tab = "chat" | "server";

type TestState = "idle" | "testing" | "ok" | "fail";

export function SettingsModal({ open, settings, systemPrompt, onClose, onSave }: Props) {
  const [tab, setTab] = useState<Tab>("chat");
  const [draft, setDraft] = useState<Settings>(settings);
  const [prompt, setPrompt] = useState(systemPrompt);
  const [testState, setTestState] = useState<TestState>("idle");
  const [testMsg, setTestMsg] = useState("");

  if (!open) return null;

  const save = () => {
    onSave(draft, prompt);
    onClose();
  };

  const testConnection = async () => {
    setTestState("testing");
    setTestMsg("");
    try {
      const ok = await checkHealth(draft.serverUrl);
      if (ok) {
        setTestState("ok");
        setTestMsg("Connected");
      } else {
        setTestState("fail");
        setTestMsg("Server returned an error");
      }
    } catch (e) {
      setTestState("fail");
      setTestMsg(e instanceof Error ? e.message : "Connection failed");
    }
  };

  const tabCls = (t: Tab) =>
    `px-3 py-1.5 text-sm rounded-t border-b-2 transition-colors ${
      tab === t
        ? "border-[var(--loom-accent)] text-[var(--loom-accent)] font-medium"
        : "border-transparent text-[var(--loom-fg-soft)] hover:text-[var(--loom-fg)]"
    }`;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/40"
      onClick={onClose}
    >
      <div
        className="w-full max-w-md rounded-lg bg-[var(--loom-bg)] border border-[var(--loom-border)] shadow-xl"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="px-5 pt-5 pb-0">
          <h2 className="text-base font-semibold mb-3">Settings</h2>
          <div className="flex gap-1 border-b border-[var(--loom-border)]">
            <button className={tabCls("chat")} onClick={() => setTab("chat")}>Chat</button>
            <button className={tabCls("server")} onClick={() => setTab("server")}>Server</button>
          </div>
        </div>

        {/* Body */}
        <div className="px-5 py-4 space-y-4">

          {tab === "chat" && (
            <>
              <div>
                <label className="block text-xs text-[var(--loom-fg-soft)] mb-1">
                  System prompt (this conversation)
                </label>
                <textarea
                  value={prompt}
                  onChange={(e) => setPrompt(e.target.value)}
                  rows={3}
                  className="w-full rounded border border-[var(--loom-border)] bg-[var(--loom-bg-soft)] p-2 text-sm"
                />
              </div>

              <div>
                <label className="flex justify-between text-xs text-[var(--loom-fg-soft)] mb-1">
                  <span>Temperature</span>
                  <span className="font-mono">{draft.temperature.toFixed(2)}</span>
                </label>
                <input
                  type="range" min={0} max={2} step={0.05}
                  value={draft.temperature}
                  onChange={(e) => setDraft({ ...draft, temperature: Number(e.target.value) })}
                  className="w-full accent-[var(--loom-accent)]"
                />
                <div className="flex justify-between text-[10px] text-[var(--loom-fg-soft)] mt-0.5">
                  <span>Precise (0)</span><span>Creative (2)</span>
                </div>
              </div>

              <div>
                <label className="flex justify-between text-xs text-[var(--loom-fg-soft)] mb-1">
                  <span>Top-p</span>
                  <span className="font-mono">{draft.topP.toFixed(2)}</span>
                </label>
                <input
                  type="range" min={0} max={1} step={0.01}
                  value={draft.topP}
                  onChange={(e) => setDraft({ ...draft, topP: Number(e.target.value) })}
                  className="w-full accent-[var(--loom-accent)]"
                />
              </div>

              <div>
                <label className="block text-xs text-[var(--loom-fg-soft)] mb-1">Max tokens</label>
                <input
                  type="number" min={16} max={32000}
                  value={draft.maxTokens}
                  onChange={(e) => setDraft({ ...draft, maxTokens: Number(e.target.value) })}
                  className="w-full rounded border border-[var(--loom-border)] bg-[var(--loom-bg-soft)] px-2 py-1 text-sm"
                />
              </div>

              <div>
                <label className="block text-xs text-[var(--loom-fg-soft)] mb-1">Theme</label>
                <select
                  value={draft.theme}
                  onChange={(e) => setDraft({ ...draft, theme: e.target.value as Settings["theme"] })}
                  className="w-full rounded border border-[var(--loom-border)] bg-[var(--loom-bg-soft)] px-2 py-1 text-sm"
                >
                  <option value="system">System</option>
                  <option value="light">Light</option>
                  <option value="dark">Dark</option>
                </select>
              </div>
            </>
          )}

          {tab === "server" && (
            <>
              <div>
                <label className="block text-xs text-[var(--loom-fg-soft)] mb-1">
                  Backend URL
                </label>
                <input
                  type="url"
                  placeholder="http://127.0.0.1:8080  (empty = same-origin proxy)"
                  value={draft.serverUrl}
                  onChange={(e) => {
                    setDraft({ ...draft, serverUrl: e.target.value });
                    setTestState("idle");
                    setTestMsg("");
                  }}
                  className="w-full rounded border border-[var(--loom-border)] bg-[var(--loom-bg-soft)] px-2 py-1 text-sm font-mono"
                />
                <p className="text-[11px] text-[var(--loom-fg-soft)] mt-1">
                  Where the Loom gateway is running. Leave empty to use the Vite dev-proxy
                  (same-origin <code>/v1</code>).
                </p>
              </div>

              <div className="flex items-center gap-3">
                <button
                  onClick={testConnection}
                  disabled={testState === "testing"}
                  className="text-sm rounded border border-[var(--loom-border)] px-3 py-1 disabled:opacity-50"
                >
                  {testState === "testing" ? "Testing…" : "Test connection"}
                </button>
                {testState === "ok" && (
                  <span className="text-xs text-green-600 dark:text-green-400">✓ {testMsg}</span>
                )}
                {testState === "fail" && (
                  <span className="text-xs text-red-500">✗ {testMsg}</span>
                )}
              </div>

              <div className="rounded border border-[var(--loom-border)] bg-[var(--loom-bg-soft)] p-3 text-xs space-y-1 text-[var(--loom-fg-soft)]">
                <p className="font-medium text-[var(--loom-fg)] mb-1">Current stack</p>
                <p>
                  <span className="font-mono">vMLX</span> — inference engine on{" "}
                  <span className="font-mono">:8000</span>
                </p>
                <p>
                  <span className="font-mono">Gateway</span> — API proxy on{" "}
                  <span className="font-mono">:8080</span>
                </p>
                <p>
                  <span className="font-mono">Web</span> — this UI on{" "}
                  <span className="font-mono">:5173</span>
                </p>
              </div>
            </>
          )}
        </div>

        {/* Footer */}
        <div className="flex justify-end gap-2 px-5 pb-5">
          <button
            onClick={onClose}
            className="text-sm rounded border border-[var(--loom-border)] px-3 py-1"
          >
            Cancel
          </button>
          <button
            onClick={save}
            className="text-sm rounded bg-[var(--loom-accent)] text-white px-3 py-1"
          >
            Save
          </button>
        </div>
      </div>
    </div>
  );
}
