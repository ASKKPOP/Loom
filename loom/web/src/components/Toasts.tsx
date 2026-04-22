import type { Toast } from "../types";

interface Props {
  toasts: Toast[];
  onDismiss: (id: string) => void;
}

export function Toasts({ toasts, onDismiss }: Props) {
  if (toasts.length === 0) return null;
  return (
    <div className="fixed bottom-4 right-4 z-40 flex flex-col gap-2 max-w-sm">
      {toasts.map((t) => (
        <div
          key={t.id}
          className={`rounded-lg border shadow-md px-3 py-2 text-sm flex items-start gap-2 ${
            t.kind === "error"
              ? "border-[var(--loom-danger)] bg-[var(--loom-bg)]"
              : "border-[var(--loom-border)] bg-[var(--loom-bg)]"
          }`}
          role="alert"
        >
          <span className="flex-1">{t.message}</span>
          {t.retry && (
            <button
              onClick={() => { t.retry?.(); onDismiss(t.id); }}
              className="text-xs rounded bg-[var(--loom-accent)] text-white px-2 py-0.5"
            >
              Retry
            </button>
          )}
          <button
            onClick={() => onDismiss(t.id)}
            className="text-xs text-[var(--loom-fg-soft)] hover:text-[var(--loom-fg)]"
            aria-label="Dismiss"
          >
            ✕
          </button>
        </div>
      ))}
    </div>
  );
}
