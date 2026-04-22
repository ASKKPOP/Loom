import type { ModelInfo } from "../types";

interface Props {
  models: ModelInfo[];
  value: string | null;
  onChange: (id: string) => void;
  disabled?: boolean;
}

export function ModelPicker({ models, value, onChange, disabled }: Props) {
  const options = models.length > 0 ? models : value ? [{ id: value }] : [];
  return (
    <select
      className="text-sm rounded border border-[var(--loom-border)] bg-[var(--loom-bg-soft)] px-2 py-1"
      value={value ?? ""}
      disabled={disabled || options.length === 0}
      onChange={(e) => onChange(e.target.value)}
    >
      {options.length === 0 && <option value="">No models</option>}
      {options.map((m) => (
        <option key={m.id} value={m.id}>
          {m.id}
        </option>
      ))}
    </select>
  );
}
