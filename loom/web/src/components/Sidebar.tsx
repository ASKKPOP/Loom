import { useState } from "react";
import { Link, useLocation } from "react-router-dom";
import type { ConnectionStatus } from "../state/connection";
import type { Conversation, ModelInfo } from "../types";

interface Props {
  conversations: Conversation[];
  activeId: string | null;
  onNew: () => void;
  onActivate: (id: string) => void;
  onRename: (id: string, title: string) => void;
  onDelete: (id: string) => void;
  models: ModelInfo[];
  model: string | null;
  canPickModel: boolean;
  onModelChange: (id: string) => void;
  status: ConnectionStatus;
  theme: "light" | "dark" | "system";
  onToggleTheme: () => void;
  onOpenSettings: () => void;
}

type Group = { label: string; items: Conversation[] };

function groupConversations(convs: Conversation[]): Group[] {
  const now = Date.now();
  const DAY = 86_400_000;
  const todayStart = new Date().setHours(0, 0, 0, 0);
  const weekAgo = todayStart - 6 * DAY;

  const today: Conversation[] = [];
  const week: Conversation[] = [];
  const older: Conversation[] = [];

  for (const c of convs) {
    const t = c.updatedAt ?? c.createdAt ?? now;
    if (t >= todayStart) today.push(c);
    else if (t >= weekAgo) week.push(c);
    else older.push(c);
  }

  const groups: Group[] = [];
  if (today.length) groups.push({ label: "Today", items: today });
  if (week.length) groups.push({ label: "Last 7 days", items: week });
  if (older.length) groups.push({ label: "Older", items: older });
  return groups;
}

const ADMIN_NAV = [
  {
    label: "Models", href: "/admin/models", icon: (
      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <rect x="2" y="3" width="20" height="14" rx="2"/><path d="M8 21h8M12 17v4"/>
      </svg>
    ),
  },
  {
    label: "AI Config", href: "/admin/ai-config", icon: (
      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <path d="M12 20h9"/><path d="M16.5 3.5a2.121 2.121 0 013 3L7 19l-4 1 1-4L16.5 3.5z"/>
      </svg>
    ),
  },
  {
    label: "Users", href: "/admin/users", icon: (
      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <path d="M17 21v-2a4 4 0 00-4-4H5a4 4 0 00-4 4v2"/><circle cx="9" cy="7" r="4"/>
        <path d="M23 21v-2a4 4 0 00-3-3.87M16 3.13a4 4 0 010 7.75"/>
      </svg>
    ),
  },
  {
    label: "Security", href: "/admin/security", icon: (
      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/>
      </svg>
    ),
  },
];

const CUSTOMIZE_NAV = [
  {
    label: "Skills", href: "/customize/skills", icon: (
      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <path d="M12 2l3.09 6.26L22 9.27l-5 4.87 1.18 6.88L12 17.77l-6.18 3.25L7 14.14 2 9.27l6.91-1.01L12 2z"/>
      </svg>
    ),
  },
  {
    label: "Connectors", href: "/customize/connectors", icon: (
      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <rect x="2" y="2" width="8" height="8" rx="2"/><rect x="14" y="2" width="8" height="8" rx="2"/>
        <rect x="2" y="14" width="8" height="8" rx="2"/><rect x="14" y="14" width="8" height="8" rx="2"/>
      </svg>
    ),
  },
];

// Icon-only tooltip wrapper
function NavIcon({ title, children, href, active }: { title: string; children: React.ReactNode; href: string; active: boolean }) {
  return (
    <Link
      to={href}
      title={title}
      className={`relative group w-9 h-9 rounded-lg flex items-center justify-center transition-colors no-underline ${
        active
          ? "bg-[var(--loom-accent-soft)] text-[var(--loom-accent)]"
          : "text-[var(--loom-fg-soft)] hover:bg-[var(--loom-border)] hover:text-[var(--loom-fg)]"
      }`}
    >
      {children}
      <span className="absolute left-full ml-2 z-50 whitespace-nowrap text-xs bg-[var(--loom-fg)] text-[var(--loom-bg)] rounded px-2 py-1 opacity-0 group-hover:opacity-100 pointer-events-none transition-opacity">
        {title}
      </span>
    </Link>
  );
}

function ActionIcon({ title, onClick, children }: { title: string; onClick: () => void; children: React.ReactNode }) {
  return (
    <button
      onClick={onClick}
      title={title}
      className="relative group w-9 h-9 rounded-lg flex items-center justify-center text-[var(--loom-fg-soft)] hover:bg-[var(--loom-border)] hover:text-[var(--loom-fg)] transition-colors"
    >
      {children}
      <span className="absolute left-full ml-2 z-50 whitespace-nowrap text-xs bg-[var(--loom-fg)] text-[var(--loom-bg)] rounded px-2 py-1 opacity-0 group-hover:opacity-100 pointer-events-none transition-opacity">
        {title}
      </span>
    </button>
  );
}

const COLLAPSED_KEY = "loom:sidebar-collapsed";

export function Sidebar({
  conversations, activeId, onNew, onActivate, onRename, onDelete,
  models, model, canPickModel, onModelChange,
  status, theme, onToggleTheme, onOpenSettings,
}: Props) {
  const location = useLocation();
  const [collapsed, setCollapsed] = useState(() => localStorage.getItem(COLLAPSED_KEY) === "1");
  const [editing, setEditing] = useState<string | null>(null);
  const [draft, setDraft] = useState("");

  const toggleCollapse = () => {
    setCollapsed((v) => {
      const next = !v;
      localStorage.setItem(COLLAPSED_KEY, next ? "1" : "0");
      return next;
    });
  };

  const isAdmin = location.pathname.startsWith("/admin");
  const isCustomize = location.pathname.startsWith("/customize");

  const startEdit = (c: Conversation) => { setEditing(c.id); setDraft(c.title); };
  const commitEdit = () => {
    if (editing && draft.trim()) onRename(editing, draft.trim());
    setEditing(null); setDraft("");
  };

  const groups = groupConversations(conversations);

  const dotColor = status === "ok"
    ? "bg-[var(--loom-ok)]"
    : status === "unknown"
    ? "bg-yellow-400"
    : "bg-[var(--loom-danger)]";

  const isDark = theme === "dark" || (theme === "system" && window.matchMedia("(prefers-color-scheme: dark)").matches);

  // ── Collapsed (icon-rail) mode ─────────────────────────────────────────────
  if (collapsed) {
    return (
      <aside className="w-14 shrink-0 bg-[var(--loom-sidebar)] border-r border-[var(--loom-border)] h-full flex flex-col items-center py-3 gap-1">
        {/* Expand */}
        <button
          onClick={toggleCollapse}
          title="Expand sidebar"
          className="w-9 h-9 rounded-lg flex items-center justify-center text-[var(--loom-fg-soft)] hover:bg-[var(--loom-border)] hover:text-[var(--loom-fg)] transition-colors mb-1"
        >
          <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M9 18l6-6-6-6"/>
          </svg>
        </button>

        {/* New session */}
        <button
          onClick={onNew}
          title="New session (⌘N)"
          className="w-9 h-9 rounded-lg flex items-center justify-center text-[var(--loom-fg-soft)] hover:bg-[var(--loom-border)] hover:text-[var(--loom-fg)] transition-colors"
        >
          <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M12 5v14M5 12h14"/>
          </svg>
        </button>

        <div className="flex-1" />

        {/* Customize */}
        <NavIcon title="Customize" href="/customize/skills" active={isCustomize}>
          <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M12 2l3.09 6.26L22 9.27l-5 4.87 1.18 6.88L12 17.77l-6.18 3.25L7 14.14 2 9.27l6.91-1.01L12 2z"/>
          </svg>
        </NavIcon>

        {/* Admin */}
        <NavIcon title="Admin" href="/admin/models" active={isAdmin}>
          <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <circle cx="12" cy="12" r="3"/>
            <path d="M19.4 15a1.65 1.65 0 00.33 1.82l.06.06a2 2 0 010 2.83 2 2 0 01-2.83 0l-.06-.06a1.65 1.65 0 00-1.82-.33 1.65 1.65 0 00-1 1.51V21a2 2 0 01-4 0v-.09A1.65 1.65 0 009 19.4a1.65 1.65 0 00-1.82.33l-.06.06a2 2 0 01-2.83-2.83l.06-.06A1.65 1.65 0 004.68 15a1.65 1.65 0 00-1.51-1H3a2 2 0 010-4h.09A1.65 1.65 0 004.6 9a1.65 1.65 0 00-.33-1.82l-.06-.06a2 2 0 012.83-2.83l.06.06A1.65 1.65 0 009 4.68a1.65 1.65 0 001-1.51V3a2 2 0 014 0v.09a1.65 1.65 0 001 1.51 1.65 1.65 0 001.82-.33l.06-.06a2 2 0 012.83 2.83l-.06.06A1.65 1.65 0 0019.4 9a1.65 1.65 0 001.51 1H21a2 2 0 010 4h-.09a1.65 1.65 0 00-1.51 1z"/>
          </svg>
        </NavIcon>

        {/* Theme */}
        <ActionIcon title="Toggle theme" onClick={onToggleTheme}>
          {isDark ? (
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <circle cx="12" cy="12" r="5"/><path d="M12 1v2M12 21v2M4.22 4.22l1.42 1.42M18.36 18.36l1.42 1.42M1 12h2M21 12h2M4.22 19.78l1.42-1.42M18.36 5.64l1.42-1.42"/>
            </svg>
          ) : (
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M21 12.79A9 9 0 1111.21 3 7 7 0 0021 12.79z"/>
            </svg>
          )}
        </ActionIcon>

        {/* Settings */}
        <ActionIcon title="Settings" onClick={onOpenSettings}>
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <circle cx="12" cy="12" r="3"/>
            <path d="M19.4 15a1.65 1.65 0 00.33 1.82l.06.06a2 2 0 010 2.83 2 2 0 01-2.83 0l-.06-.06a1.65 1.65 0 00-1.82-.33 1.65 1.65 0 00-1 1.51V21a2 2 0 01-4 0v-.09A1.65 1.65 0 009 19.4a1.65 1.65 0 00-1.82.33l-.06.06a2 2 0 01-2.83-2.83l.06-.06A1.65 1.65 0 004.68 15a1.65 1.65 0 00-1.51-1H3a2 2 0 010-4h.09A1.65 1.65 0 004.6 9a1.65 1.65 0 00-.33-1.82l-.06-.06a2 2 0 012.83-2.83l.06.06A1.65 1.65 0 009 4.68a1.65 1.65 0 001-1.51V3a2 2 0 014 0v.09a1.65 1.65 0 001 1.51 1.65 1.65 0 001.82-.33l.06-.06a2 2 0 012.83 2.83l-.06.06A1.65 1.65 0 0019.4 9a1.65 1.65 0 001.51 1H21a2 2 0 010 4h-.09a1.65 1.65 0 00-1.51 1z"/>
          </svg>
        </ActionIcon>

        {/* Connection dot */}
        <span title={`Server: ${status}`} className={`w-2 h-2 rounded-full ${dotColor} mt-1 mb-1`} />
      </aside>
    );
  }

  // ── Expanded mode ──────────────────────────────────────────────────────────
  return (
    <aside className="w-64 shrink-0 bg-[var(--loom-sidebar)] h-full flex flex-col select-none border-r border-[var(--loom-border)]">
      {/* Top bar */}
      <div className="flex items-center justify-between px-3 pt-3 pb-2">
        <Link to="/" className="flex items-center gap-2 text-sm font-semibold text-[var(--loom-fg)] no-underline min-w-0">
          <img src="/logo.svg" alt="eKlotho" className="w-7 h-7 shrink-0" />
          <span className="truncate">eKlotho Loom</span>
        </Link>
        <div className="flex items-center gap-0.5">
          {/* New session */}
          <button
            onClick={onNew}
            title="New session (⌘N)"
            className="w-7 h-7 rounded-md flex items-center justify-center text-[var(--loom-fg-soft)] hover:bg-[var(--loom-border)] hover:text-[var(--loom-fg)] transition-colors"
          >
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M12 5v14M5 12h14"/>
            </svg>
          </button>
          {/* Collapse */}
          <button
            onClick={toggleCollapse}
            title="Collapse sidebar"
            className="w-7 h-7 rounded-md flex items-center justify-center text-[var(--loom-fg-soft)] hover:bg-[var(--loom-border)] hover:text-[var(--loom-fg)] transition-colors"
          >
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M15 18l-6-6 6-6"/>
            </svg>
          </button>
        </div>
      </div>

      {/* + New session button */}
      <div className="px-3 pb-2">
        <button
          onClick={onNew}
          className="w-full flex items-center gap-2 rounded-lg border border-[var(--loom-border)] px-3 py-2 text-sm text-[var(--loom-fg-soft)] hover:bg-[var(--loom-border)] hover:text-[var(--loom-fg)] transition-colors"
        >
          <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
            <path d="M12 5v14M5 12h14"/>
          </svg>
          New session
        </button>
      </div>

      {/* Main scrollable area */}
      <div className="flex-1 overflow-y-auto px-2">

        {/* Customize section */}
        {(isCustomize || (!isAdmin && !isCustomize)) && (
          <div className="mb-2">
            <div className="flex items-center justify-between px-1 mb-0.5">
              <span className="text-[10px] font-semibold uppercase tracking-wide text-[var(--loom-fg-soft)] opacity-60">Customize</span>
            </div>
            {CUSTOMIZE_NAV.map((item) => {
              const active = location.pathname === item.href || location.pathname.startsWith(item.href + "/");
              return (
                <Link
                  key={item.href}
                  to={item.href}
                  className={`flex items-center gap-2.5 px-2.5 py-1.5 rounded-lg text-sm no-underline transition-colors mb-0.5 ${
                    active
                      ? "bg-[var(--loom-accent-soft)] text-[var(--loom-accent)]"
                      : "text-[var(--loom-fg-soft)] hover:bg-[var(--loom-border)] hover:text-[var(--loom-fg)]"
                  }`}
                >
                  <span className="shrink-0">{item.icon}</span>
                  {item.label}
                </Link>
              );
            })}
          </div>
        )}

        {/* Admin nav (only when in admin) */}
        {isAdmin && (
          <div className="mb-2">
            <div className="px-1 mb-0.5">
              <span className="text-[10px] font-semibold uppercase tracking-wide text-[var(--loom-fg-soft)] opacity-60">Admin</span>
            </div>
            {ADMIN_NAV.map((item) => {
              const active = location.pathname === item.href;
              return (
                <Link
                  key={item.href}
                  to={item.href}
                  className={`flex items-center gap-2.5 px-2.5 py-1.5 rounded-lg text-sm no-underline transition-colors mb-0.5 ${
                    active
                      ? "bg-[var(--loom-accent-soft)] text-[var(--loom-accent)]"
                      : "text-[var(--loom-fg-soft)] hover:bg-[var(--loom-border)] hover:text-[var(--loom-fg)]"
                  }`}
                >
                  <span className="shrink-0">{item.icon}</span>
                  {item.label}
                </Link>
              );
            })}
            <div className="pt-2 pb-1 px-1">
              <Link to="/" className="flex items-center gap-2 text-xs text-[var(--loom-fg-soft)] hover:text-[var(--loom-fg)] no-underline">
                <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M19 12H5M12 19l-7-7 7-7"/>
                </svg>
                Back to chat
              </Link>
            </div>
          </div>
        )}

        {/* Conversation list (only when in chat mode) */}
        {!isAdmin && !isCustomize && (
          <>
            {conversations.length === 0 ? (
              <p className="text-xs text-[var(--loom-fg-soft)] px-2.5 py-4 text-center opacity-60">No conversations yet.</p>
            ) : (
              groups.map((group) => (
                <div key={group.label} className="mb-3">
                  <p className="text-[10px] font-semibold uppercase tracking-wide text-[var(--loom-fg-soft)] px-2.5 py-1 opacity-60">
                    {group.label}
                  </p>
                  {group.items.map((c) => {
                    const active = c.id === activeId;
                    return (
                      <div
                        key={c.id}
                        onClick={() => { setEditing(null); onActivate(c.id); }}
                        className={`group flex items-center gap-1.5 rounded-lg px-2.5 py-1.5 text-sm cursor-pointer transition-colors mb-0.5 ${
                          active
                            ? "bg-[var(--loom-border)] text-[var(--loom-fg)]"
                            : "text-[var(--loom-fg-soft)] hover:bg-[var(--loom-border)] hover:text-[var(--loom-fg)]"
                        }`}
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
                            className="flex-1 bg-transparent outline-none border-b border-[var(--loom-border)] text-sm"
                          />
                        ) : (
                          <span
                            className="flex-1 truncate text-sm"
                            onDoubleClick={(e) => { e.stopPropagation(); startEdit(c); }}
                          >
                            {c.title}
                          </span>
                        )}
                        <button
                          onClick={(e) => { e.stopPropagation(); startEdit(c); }}
                          className="opacity-0 group-hover:opacity-60 hover:!opacity-100 text-[var(--loom-fg-soft)] shrink-0"
                          title="Rename"
                        >
                          <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                            <path d="M11 4H4a2 2 0 00-2 2v14a2 2 0 002 2h14a2 2 0 002-2v-7"/>
                            <path d="M18.5 2.5a2.121 2.121 0 013 3L12 15l-4 1 1-4 9.5-9.5z"/>
                          </svg>
                        </button>
                        <button
                          onClick={(e) => { e.stopPropagation(); onDelete(c.id); }}
                          className="opacity-0 group-hover:opacity-60 hover:!opacity-100 text-[var(--loom-fg-soft)] hover:text-[var(--loom-danger)] shrink-0"
                          title="Delete"
                        >
                          <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                            <path d="M3 6h18M8 6V4h8v2M19 6l-1 14H6L5 6"/>
                          </svg>
                        </button>
                      </div>
                    );
                  })}
                </div>
              ))
            )}
          </>
        )}
      </div>

      {/* Bottom controls */}
      <div className="px-2 pb-3 pt-2 border-t border-[var(--loom-border)] space-y-2">
        {/* Model picker (chat mode only) */}
        {!isAdmin && !isCustomize && (
          <select
            value={model ?? ""}
            onChange={(e) => onModelChange(e.target.value)}
            disabled={!canPickModel || models.length === 0}
            className="w-full text-xs rounded-lg border border-[var(--loom-border)] bg-[var(--loom-bg)] text-[var(--loom-fg)] px-2.5 py-1.5 disabled:opacity-50 outline-none focus:ring-1 focus:ring-[var(--loom-accent)] cursor-pointer"
          >
            {models.length === 0 && <option value="">No models</option>}
            {models.map((m) => (
              <option key={m.id} value={m.id}>{m.id}</option>
            ))}
          </select>
        )}

        {/* Icon row */}
        <div className="flex items-center gap-1">
          {/* Connection status */}
          <span title={`Server: ${status}`} className="flex items-center gap-1.5 text-xs text-[var(--loom-fg-soft)] px-1 flex-1">
            <span className={`inline-block w-2 h-2 rounded-full shrink-0 ${dotColor}`} />
            <span className="truncate">{status}</span>
          </span>

          {/* Theme toggle */}
          <button
            onClick={onToggleTheme}
            title="Toggle theme"
            className="w-7 h-7 rounded-md flex items-center justify-center text-[var(--loom-fg-soft)] hover:bg-[var(--loom-border)] hover:text-[var(--loom-fg)] transition-colors"
          >
            {isDark ? (
              <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <circle cx="12" cy="12" r="5"/><path d="M12 1v2M12 21v2M4.22 4.22l1.42 1.42M18.36 18.36l1.42 1.42M1 12h2M21 12h2M4.22 19.78l1.42-1.42M18.36 5.64l1.42-1.42"/>
              </svg>
            ) : (
              <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M21 12.79A9 9 0 1111.21 3 7 7 0 0021 12.79z"/>
              </svg>
            )}
          </button>

          {/* Customize link */}
          <Link
            to="/customize/skills"
            title="Customize"
            className={`w-7 h-7 rounded-md flex items-center justify-center transition-colors no-underline ${
              isCustomize
                ? "text-[var(--loom-accent)]"
                : "text-[var(--loom-fg-soft)] hover:bg-[var(--loom-border)] hover:text-[var(--loom-fg)]"
            }`}
          >
            <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M12 2l3.09 6.26L22 9.27l-5 4.87 1.18 6.88L12 17.77l-6.18 3.25L7 14.14 2 9.27l6.91-1.01L12 2z"/>
            </svg>
          </Link>

          {/* Admin link */}
          <Link
            to="/admin/models"
            title="Admin"
            className={`w-7 h-7 rounded-md flex items-center justify-center transition-colors no-underline ${
              isAdmin
                ? "text-[var(--loom-accent)]"
                : "text-[var(--loom-fg-soft)] hover:bg-[var(--loom-border)] hover:text-[var(--loom-fg)]"
            }`}
          >
            <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <circle cx="12" cy="12" r="3"/>
              <path d="M19.4 15a1.65 1.65 0 00.33 1.82l.06.06a2 2 0 010 2.83 2 2 0 01-2.83 0l-.06-.06a1.65 1.65 0 00-1.82-.33 1.65 1.65 0 00-1 1.51V21a2 2 0 01-4 0v-.09A1.65 1.65 0 009 19.4a1.65 1.65 0 00-1.82.33l-.06.06a2 2 0 01-2.83-2.83l.06-.06A1.65 1.65 0 004.68 15a1.65 1.65 0 00-1.51-1H3a2 2 0 010-4h.09A1.65 1.65 0 004.6 9a1.65 1.65 0 00-.33-1.82l-.06-.06a2 2 0 012.83-2.83l.06.06A1.65 1.65 0 009 4.68a1.65 1.65 0 001-1.51V3a2 2 0 014 0v.09a1.65 1.65 0 001 1.51 1.65 1.65 0 001.82-.33l.06-.06a2 2 0 012.83 2.83l-.06.06A1.65 1.65 0 0019.4 9a1.65 1.65 0 001.51 1H21a2 2 0 010 4h-.09a1.65 1.65 0 00-1.51 1z"/>
            </svg>
          </Link>

          {/* Settings */}
          <button
            onClick={onOpenSettings}
            title="Settings"
            className="w-7 h-7 rounded-md flex items-center justify-center text-[var(--loom-fg-soft)] hover:bg-[var(--loom-border)] hover:text-[var(--loom-fg)] transition-colors"
          >
            <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <circle cx="12" cy="12" r="3"/>
              <path d="M19.4 15a1.65 1.65 0 00.33 1.82l.06.06a2 2 0 010 2.83 2 2 0 01-2.83 0l-.06-.06a1.65 1.65 0 00-1.82-.33 1.65 1.65 0 00-1 1.51V21a2 2 0 01-4 0v-.09A1.65 1.65 0 009 19.4a1.65 1.65 0 00-1.82.33l-.06.06a2 2 0 01-2.83-2.83l.06-.06A1.65 1.65 0 004.68 15a1.65 1.65 0 00-1.51-1H3a2 2 0 010-4h.09A1.65 1.65 0 004.6 9a1.65 1.65 0 00-.33-1.82l-.06-.06a2 2 0 012.83-2.83l.06.06A1.65 1.65 0 009 4.68a1.65 1.65 0 001-1.51V3a2 2 0 014 0v.09a1.65 1.65 0 001 1.51 1.65 1.65 0 001.82-.33l.06-.06a2 2 0 012.83 2.83l-.06.06A1.65 1.65 0 0019.4 9a1.65 1.65 0 001.51 1H21a2 2 0 010 4h-.09a1.65 1.65 0 00-1.51 1z"/>
            </svg>
          </button>
        </div>
      </div>
    </aside>
  );
}
