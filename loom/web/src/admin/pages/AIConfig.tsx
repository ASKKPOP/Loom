import { useEffect, useState } from "react";

interface AIConfig {
  temperature: number;
  max_tokens: number;
  top_p: number;
  system_prompt: string;
}

const DEFAULT: AIConfig = { temperature: 0.7, max_tokens: 512, top_p: 1.0, system_prompt: "" };

async function fetchConfig(): Promise<AIConfig> {
  const res = await fetch("/api/admin/config");
  if (!res.ok) throw new Error(`${res.status}`);
  return res.json();
}

async function saveConfig(config: AIConfig): Promise<void> {
  const res = await fetch("/api/admin/config", {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(config),
  });
  if (!res.ok) throw new Error(`${res.status}: ${await res.text()}`);
}

function Slider({ label, value, min, max, step, onChange }: {
  label: string; value: number; min: number; max: number; step: number;
  onChange: (v: number) => void;
}) {
  return (
    <div>
      <div className="flex justify-between mb-1.5">
        <label className="text-sm text-[var(--loom-fg)]">{label}</label>
        <span className="text-sm font-mono text-[var(--loom-fg-soft)]">{value}</span>
      </div>
      <input
        type="range"
        min={min} max={max} step={step}
        value={value}
        onChange={(e) => onChange(Number(e.target.value))}
        className="w-full accent-[var(--loom-accent)]"
      />
      <div className="flex justify-between text-[10px] text-[var(--loom-fg-soft)] opacity-60 mt-0.5">
        <span>{min}</span><span>{max}</span>
      </div>
    </div>
  );
}

export function AIConfigPage() {
  const [config, setConfig] = useState<AIConfig>(DEFAULT);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    fetchConfig()
      .then(setConfig)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  const handleSave = async () => {
    setSaving(true);
    setError(null);
    try {
      await saveConfig(config);
      setSaved(true);
      setTimeout(() => setSaved(false), 2000);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setSaving(false);
    }
  };

  if (loading) return <div className="p-8 text-sm text-[var(--loom-fg-soft)]">Loading…</div>;

  return (
    <div className="p-8 max-w-2xl">
      <div className="mb-6">
        <h1 className="text-lg font-semibold text-[var(--loom-fg)]">AI Config</h1>
        <p className="text-sm text-[var(--loom-fg-soft)] mt-0.5">Default generation parameters applied to all conversations.</p>
      </div>

      {error && <p className="text-sm text-[var(--loom-danger)] mb-4">{error}</p>}

      <div className="space-y-6">
        <div className="rounded-xl border border-[var(--loom-border)] bg-[var(--loom-bg-soft)] p-5 space-y-5">
          <Slider
            label="Temperature"
            value={config.temperature}
            min={0} max={2} step={0.05}
            onChange={(v) => setConfig((c) => ({ ...c, temperature: v }))}
          />
          <Slider
            label="Max tokens"
            value={config.max_tokens}
            min={64} max={4096} step={64}
            onChange={(v) => setConfig((c) => ({ ...c, max_tokens: v }))}
          />
          <Slider
            label="Top-p"
            value={config.top_p}
            min={0} max={1} step={0.05}
            onChange={(v) => setConfig((c) => ({ ...c, top_p: v }))}
          />
        </div>

        <div>
          <label className="block text-sm text-[var(--loom-fg)] mb-2">Default system prompt</label>
          <textarea
            value={config.system_prompt}
            onChange={(e) => setConfig((c) => ({ ...c, system_prompt: e.target.value }))}
            rows={5}
            placeholder="Optional default system prompt for all new conversations…"
            className="w-full rounded-xl border border-[var(--loom-border)] bg-[var(--loom-bg-soft)] px-4 py-3 text-sm outline-none focus:ring-1 focus:ring-[var(--loom-accent)] resize-y"
          />
        </div>

        <button
          onClick={handleSave}
          disabled={saving}
          className="text-sm rounded-lg bg-[var(--loom-accent)] text-white px-4 py-2 hover:opacity-90 disabled:opacity-50 transition-opacity"
        >
          {saving ? "Saving…" : saved ? "Saved ✓" : "Save changes"}
        </button>
      </div>
    </div>
  );
}
