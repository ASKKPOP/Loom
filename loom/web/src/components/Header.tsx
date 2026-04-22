import type { ModelInfo } from "../types";
import type { ConnectionStatus } from "../state/connection";
import { ConnectionDot } from "./ConnectionDot";
import { ModelPicker } from "./ModelPicker";

interface Props {
  title: string;
  models: ModelInfo[];
  model: string | null;
  onModelChange: (id: string) => void;
  status: ConnectionStatus;
  theme: "light" | "dark";
  onToggleTheme: () => void;
  onOpenSettings: () => void;
  canPickModel: boolean;
}

export function Header(p: Props) {
  return (
    <header className="h-12 shrink-0 border-b border-[var(--loom-border)] bg-[var(--loom-bg)] flex items-center justify-between px-4">
      <div className="flex items-center gap-3 min-w-0">
        <span className="font-semibold text-sm">Loom</span>
        <span className="text-[var(--loom-fg-soft)] text-sm truncate">{p.title}</span>
      </div>
      <div className="flex items-center gap-3">
        <ConnectionDot status={p.status} />
        <ModelPicker
          models={p.models}
          value={p.model}
          onChange={p.onModelChange}
          disabled={!p.canPickModel}
        />
        <button
          onClick={p.onOpenSettings}
          className="text-xs rounded border border-[var(--loom-border)] px-2 py-1"
          title="Settings"
        >
          ⚙
        </button>
        <button
          onClick={p.onToggleTheme}
          className="text-xs rounded border border-[var(--loom-border)] px-2 py-1"
          title="Toggle theme"
        >
          {p.theme === "dark" ? "☀" : "☾"}
        </button>
      </div>
    </header>
  );
}
