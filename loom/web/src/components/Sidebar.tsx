import { useState } from "react";
import type { Conversation } from "../types";

interface Props {
  conversations: Conversation[];
  activeId: string | null;
  onNew: () => void;
  onActivate: (id: string) => void;
  onRename: (id: string, title: string) => void;
  onDelete: (id: string) => void;
}

export function Sidebar(props: Props) {
  const [editing, setEditing] = useState<string | null>(null);
  const [draft, setDraft] = useState("");

  const startEdit = (c: Conversation) => {
    setEditing(c.id);
    setDraft(c.title);
  };

  const commitEdit = () => {
    if (editing && draft.trim()) {
      props.onRename(editing, draft.trim());
    }
    setEditing(null);
    setDraft("");
  };

  return (
    <aside className="w-64 shrink-0 border-r border-[var(--loom-border)] bg-[var(--loom-bg-soft)] h-full flex flex-col">
      <div className="px-3 py-3 flex items-center justify-between">
        <span className="text-sm font-semibold">Conversations</span>
        <button
          onClick={props.onNew}
          className="text-xs rounded bg-[var(--loom-accent)] text-white px-2 py-1 hover:opacity-90"
          title="New chat (⌘N)"
        >
          + New
        </button>
      </div>
      <nav className="flex-1 overflow-y-auto px-1 pb-3">
        {props.conversations.length === 0 && (
          <p className="text-xs text-[var(--loom-fg-soft)] px-2 py-4">No conversations yet.</p>
        )}
        {props.conversations.map((c) => {
          const active = c.id === props.activeId;
          return (
            <div
              key={c.id}
              className={`group flex items-center gap-1 rounded px-2 py-1.5 text-sm cursor-pointer ${
                active ? "bg-[var(--loom-bg)] ring-1 ring-[var(--loom-border)]" : "hover:bg-[var(--loom-bg)]"
              }`}
              onClick={() => props.onActivate(c.id)}
            >
              {editing === c.id ? (
                <input
                  autoFocus
                  value={draft}
                  onChange={(e) => setDraft(e.target.value)}
                  onBlur={commitEdit}
                  onKeyDown={(e) => {
                    if (e.key === "Enter") commitEdit();
                    if (e.key === "Escape") { setEditing(null); setDraft(""); }
                  }}
                  onClick={(e) => e.stopPropagation()}
                  className="flex-1 bg-transparent outline-none border-b border-[var(--loom-border)]"
                />
              ) : (
                <span
                  className="flex-1 truncate"
                  onDoubleClick={(e) => { e.stopPropagation(); startEdit(c); }}
                >
                  {c.title}
                </span>
              )}
              <button
                onClick={(e) => { e.stopPropagation(); startEdit(c); }}
                className="opacity-0 group-hover:opacity-100 text-xs text-[var(--loom-fg-soft)] hover:text-[var(--loom-fg)]"
                title="Rename"
                aria-label="Rename"
              >
                ✎
              </button>
              <button
                onClick={(e) => { e.stopPropagation(); props.onDelete(c.id); }}
                className="opacity-0 group-hover:opacity-100 text-xs text-[var(--loom-fg-soft)] hover:text-[var(--loom-danger)]"
                title="Delete"
                aria-label="Delete"
              >
                ✕
              </button>
            </div>
          );
        })}
      </nav>
    </aside>
  );
}
