import { useState } from "react";
import type { Message as Msg } from "../types";
import { Markdown } from "../lib/markdown";

interface Props {
  message: Msg;
  onEdit?: (id: string, content: string) => void;
  onRegenerate?: (id: string) => void;
  canRegenerate?: boolean;
}

export function Message({ message, onEdit, onRegenerate, canRegenerate }: Props) {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(message.content);
  const [copied, setCopied] = useState(false);

  const isUser = message.role === "user";

  const copy = async () => {
    try {
      await navigator.clipboard.writeText(message.content);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch { /* clipboard blocked */ }
  };

  const submitEdit = () => {
    if (draft.trim() && onEdit) {
      onEdit(message.id, draft.trim());
    }
    setEditing(false);
  };

  return (
    <div
      className={`group flex gap-3 px-6 py-5 ${
        isUser ? "bg-[var(--loom-bg)]" : "bg-[var(--loom-bg-soft)]"
      }`}
      data-role={message.role}
    >
      <div className="shrink-0 w-8 h-8 rounded-full bg-[var(--loom-accent)] text-white flex items-center justify-center text-xs font-semibold">
        {isUser ? "You" : "AI"}
      </div>
      <div className="flex-1 min-w-0">
        {editing ? (
          <div className="space-y-2">
            <textarea
              value={draft}
              onChange={(e) => setDraft(e.target.value)}
              rows={Math.min(12, Math.max(3, draft.split("\n").length))}
              className="w-full rounded border border-[var(--loom-border)] bg-[var(--loom-bg)] p-2 text-sm resize-y"
            />
            <div className="flex gap-2">
              <button
                onClick={submitEdit}
                className="text-xs rounded bg-[var(--loom-accent)] text-white px-2 py-1"
              >
                Save & resend
              </button>
              <button
                onClick={() => { setEditing(false); setDraft(message.content); }}
                className="text-xs rounded border border-[var(--loom-border)] px-2 py-1"
              >
                Cancel
              </button>
            </div>
          </div>
        ) : (
          <>
            {message.content === "" && message.streaming ? (
              <span className="text-[var(--loom-fg-soft)] text-sm italic">Thinking…</span>
            ) : (
              <Markdown text={message.content} />
            )}
            {message.error && (
              <p className="mt-2 text-xs text-[var(--loom-danger)]">
                {message.error}
              </p>
            )}
          </>
        )}
        <div className="mt-2 flex gap-2 opacity-0 group-hover:opacity-100 transition-opacity">
          <button
            onClick={copy}
            className="text-xs text-[var(--loom-fg-soft)] hover:text-[var(--loom-fg)]"
          >
            {copied ? "Copied" : "Copy"}
          </button>
          {isUser && onEdit && !editing && (
            <button
              onClick={() => setEditing(true)}
              className="text-xs text-[var(--loom-fg-soft)] hover:text-[var(--loom-fg)]"
            >
              Edit
            </button>
          )}
          {!isUser && canRegenerate && onRegenerate && (
            <button
              onClick={() => onRegenerate(message.id)}
              className="text-xs text-[var(--loom-fg-soft)] hover:text-[var(--loom-fg)]"
            >
              Regenerate
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
