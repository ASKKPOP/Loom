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
    if (draft.trim() && onEdit) onEdit(message.id, draft.trim());
    setEditing(false);
  };

  if (isUser) {
    return (
      <div className="flex justify-end px-4 py-2 group" data-role="user">
        <div className="max-w-[70%]">
          {editing ? (
            <div className="space-y-2">
              <textarea
                value={draft}
                onChange={(e) => setDraft(e.target.value)}
                rows={Math.min(12, Math.max(3, draft.split("\n").length))}
                className="w-full rounded-2xl border border-[var(--loom-border)] bg-[var(--loom-bg)] p-3 text-sm resize-y outline-none focus:ring-1 focus:ring-[var(--loom-accent)]"
              />
              <div className="flex gap-2 justify-end">
                <button
                  onClick={() => { setEditing(false); setDraft(message.content); }}
                  className="text-xs rounded-lg border border-[var(--loom-border)] px-3 py-1.5"
                >
                  Cancel
                </button>
                <button
                  onClick={submitEdit}
                  className="text-xs rounded-lg bg-[var(--loom-accent)] text-white px-3 py-1.5"
                >
                  Save & resend
                </button>
              </div>
            </div>
          ) : (
            <>
              <div className="rounded-2xl bg-[var(--loom-user-bubble)] text-[var(--loom-fg)] px-4 py-2.5 text-sm leading-relaxed whitespace-pre-wrap break-words">
                {message.content}
              </div>
              <div className="flex gap-2 justify-end mt-1 opacity-0 group-hover:opacity-100 transition-opacity">
                <button onClick={copy} className="text-xs text-[var(--loom-fg-soft)] hover:text-[var(--loom-fg)]">
                  {copied ? "Copied" : "Copy"}
                </button>
                {onEdit && (
                  <button onClick={() => setEditing(true)} className="text-xs text-[var(--loom-fg-soft)] hover:text-[var(--loom-fg)]">
                    Edit
                  </button>
                )}
              </div>
            </>
          )}
        </div>
      </div>
    );
  }

  return (
    <div className="flex gap-3 px-4 py-3 group" data-role="assistant">
      {/* Avatar */}
      <div className="shrink-0 w-7 h-7 rounded-full bg-[var(--loom-accent)] text-white flex items-center justify-center text-xs font-bold mt-0.5">
        L
      </div>
      <div className="flex-1 min-w-0">
        {message.content === "" && message.streaming ? (
          <span className="text-[var(--loom-fg-soft)] text-sm italic">Thinking…</span>
        ) : (
          <div className="loom-prose text-sm text-[var(--loom-fg)]">
            <Markdown text={message.content} />
          </div>
        )}
        {message.error && (
          <p className="mt-1.5 text-xs text-[var(--loom-danger)]">{message.error}</p>
        )}
        <div className="mt-1.5 flex gap-2.5 opacity-0 group-hover:opacity-100 transition-opacity">
          <button onClick={copy} className="text-xs text-[var(--loom-fg-soft)] hover:text-[var(--loom-fg)]">
            {copied ? "Copied" : "Copy"}
          </button>
          {canRegenerate && onRegenerate && (
            <button onClick={() => onRegenerate(message.id)} className="text-xs text-[var(--loom-fg-soft)] hover:text-[var(--loom-fg)]">
              Regenerate
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
