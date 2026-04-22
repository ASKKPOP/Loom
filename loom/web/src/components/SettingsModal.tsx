import { useState } from "react";
import type { Settings } from "../types";

interface Props {
  open: boolean;
  settings: Settings;
  systemPrompt: string;
  onClose: () => void;
  onSave: (settings: Settings, systemPrompt: string) => void;
}

export function SettingsModal({ open, settings, systemPrompt, onClose, onSave }: Props) {
  const [draft, setDraft] = useState<Settings>(settings);
  const [prompt, setPrompt] = useState(systemPrompt);

  if (!open) return null;

  const save = () => {
    onSave(draft, prompt);
    onClose();
  };

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/40"
      onClick={onClose}
    >
      <div
        className="w-full max-w-md rounded-lg bg-[var(--loom-bg)] border border-[var(--loom-border)] shadow-xl p-5"
        onClick={(e) => e.stopPropagation()}
      >
        <h2 className="text-base font-semibold mb-4">Settings</h2>

        <label className="block text-xs text-[var(--loom-fg-soft)] mb-1">
          System prompt (this conversation)
        </label>
        <textarea
          value={prompt}
          onChange={(e) => setPrompt(e.target.value)}
          rows={3}
          className="w-full rounded border border-[var(--loom-border)] bg-[var(--loom-bg-soft)] p-2 text-sm mb-4"
        />

        <label className="block text-xs text-[var(--loom-fg-soft)] mb-1">
          Temperature: {draft.temperature.toFixed(2)}
        </label>
        <input
          type="range"
          min={0}
          max={2}
          step={0.05}
          value={draft.temperature}
          onChange={(e) => setDraft({ ...draft, temperature: Number(e.target.value) })}
          className="w-full mb-4"
        />

        <label className="block text-xs text-[var(--loom-fg-soft)] mb-1">
          Top-p: {draft.topP.toFixed(2)}
        </label>
        <input
          type="range"
          min={0}
          max={1}
          step={0.01}
          value={draft.topP}
          onChange={(e) => setDraft({ ...draft, topP: Number(e.target.value) })}
          className="w-full mb-4"
        />

        <label className="block text-xs text-[var(--loom-fg-soft)] mb-1">
          Max tokens
        </label>
        <input
          type="number"
          min={16}
          max={32000}
          value={draft.maxTokens}
          onChange={(e) => setDraft({ ...draft, maxTokens: Number(e.target.value) })}
          className="w-full rounded border border-[var(--loom-border)] bg-[var(--loom-bg-soft)] px-2 py-1 text-sm mb-4"
        />

        <div className="flex justify-end gap-2">
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
