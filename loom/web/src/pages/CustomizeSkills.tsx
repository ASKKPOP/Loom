import { useState } from "react";
import { Link } from "react-router-dom";
import {
  BUILT_IN_SKILLS,
  loadActiveSkillIds,
  saveActiveSkillIds,
  type Skill,
} from "../lib/skills";

const CATEGORIES = [...new Set(BUILT_IN_SKILLS.map((s) => s.category))];

export function CustomizeSkillsPage() {
  const [active, setActive] = useState<Set<string>>(loadActiveSkillIds);
  const [search, setSearch] = useState("");
  const [category, setCategory] = useState<string | null>(null);
  const [detail, setDetail] = useState<Skill | null>(null);

  const toggle = (id: string) => {
    setActive((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      saveActiveSkillIds(next);
      return next;
    });
  };

  const filtered = BUILT_IN_SKILLS.filter((s) => {
    if (category && s.category !== category) return false;
    if (search) {
      const q = search.toLowerCase();
      return (
        s.name.toLowerCase().includes(q) ||
        s.description.toLowerCase().includes(q) ||
        s.tags.some((t) => t.includes(q))
      );
    }
    return true;
  });

  return (
    <div className="flex h-full w-full">
      {/* Main list */}
      <div className="flex-1 overflow-y-auto p-8">
        {/* Header */}
        <div className="mb-8 max-w-2xl">
          <div className="w-14 h-14 rounded-2xl bg-[var(--loom-accent-soft)] flex items-center justify-center mb-4">
            <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="var(--loom-accent)" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
              <path d="M12 2l3.09 6.26L22 9.27l-5 4.87 1.18 6.88L12 17.77l-6.18 3.25L7 14.14 2 9.27l6.91-1.01L12 2z"/>
            </svg>
          </div>
          <h1 className="text-2xl font-semibold text-[var(--loom-fg)] mb-2">Customize Loom</h1>
          <p className="text-[var(--loom-fg-soft)] text-sm leading-relaxed">
            Skills shape how Loom responds. Enable a skill to apply its system prompt to new sessions.
          </p>
          <div className="flex gap-3 mt-5">
            <Link
              to="/customize/skills"
              className="flex items-center gap-2 px-4 py-2.5 rounded-xl text-sm font-medium no-underline bg-[var(--loom-border)] text-[var(--loom-fg)] transition-colors"
            >
              <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M12 2l3.09 6.26L22 9.27l-5 4.87 1.18 6.88L12 17.77l-6.18 3.25L7 14.14 2 9.27l6.91-1.01L12 2z"/>
              </svg>
              Skills
            </Link>
            <Link
              to="/customize/connectors"
              className="flex items-center gap-2 px-4 py-2.5 rounded-xl text-sm font-medium no-underline text-[var(--loom-fg-soft)] hover:bg-[var(--loom-border)] transition-colors"
            >
              <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <rect x="2" y="2" width="8" height="8" rx="2"/><rect x="14" y="2" width="8" height="8" rx="2"/>
                <rect x="2" y="14" width="8" height="8" rx="2"/><rect x="14" y="14" width="8" height="8" rx="2"/>
              </svg>
              Connectors
            </Link>
          </div>
        </div>

        {/* Active skills banner */}
        {active.size > 0 && (
          <div className="mb-6 max-w-2xl rounded-xl border border-[var(--loom-accent)] bg-[var(--loom-accent-soft)] px-4 py-3 flex items-center gap-3">
            <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="var(--loom-accent)" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M12 2l3.09 6.26L22 9.27l-5 4.87 1.18 6.88L12 17.77l-6.18 3.25L7 14.14 2 9.27l6.91-1.01L12 2z"/>
            </svg>
            <p className="text-sm text-[var(--loom-accent)]">
              <span className="font-semibold">{active.size} skill{active.size !== 1 ? "s" : ""} active</span>
              {" — "}system prompt applied to all new sessions automatically.
            </p>
          </div>
        )}

        {/* Search + category filters */}
        <div className="flex flex-col gap-2 mb-5 max-w-2xl">
          <div className="relative">
            <svg className="absolute left-3 top-1/2 -translate-y-1/2 text-[var(--loom-fg-soft)]" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <circle cx="11" cy="11" r="8"/><path d="M21 21l-4.35-4.35"/>
            </svg>
            <input
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search skills…"
              className="w-full pl-9 pr-3 py-2 text-sm rounded-xl border border-[var(--loom-border)] bg-[var(--loom-bg-soft)] outline-none focus:ring-1 focus:ring-[var(--loom-accent)]"
            />
          </div>
          <div className="flex gap-1.5 flex-wrap">
            <button
              onClick={() => setCategory(null)}
              className={`px-3 py-1 rounded-lg text-xs font-medium transition-colors ${
                !category
                  ? "bg-[var(--loom-accent)] text-white"
                  : "border border-[var(--loom-border)] text-[var(--loom-fg-soft)] hover:bg-[var(--loom-border)]"
              }`}
            >
              All
            </button>
            {CATEGORIES.map((cat) => (
              <button
                key={cat}
                onClick={() => setCategory(category === cat ? null : cat)}
                className={`px-3 py-1 rounded-lg text-xs font-medium transition-colors ${
                  category === cat
                    ? "bg-[var(--loom-accent)] text-white"
                    : "border border-[var(--loom-border)] text-[var(--loom-fg-soft)] hover:bg-[var(--loom-border)]"
                }`}
              >
                {cat}
              </button>
            ))}
          </div>
        </div>

        {/* Skills list */}
        <div className="space-y-2 max-w-2xl">
          {filtered.map((skill) => {
            const enabled = active.has(skill.id);
            return (
              <div
                key={skill.id}
                className={`group rounded-xl border transition-all cursor-pointer ${
                  enabled
                    ? "border-[var(--loom-accent)] bg-[var(--loom-accent-soft)]"
                    : "border-[var(--loom-border)] bg-[var(--loom-bg-soft)] hover:border-[var(--loom-accent)]"
                }`}
                onClick={() => setDetail(skill)}
              >
                <div className="flex items-start gap-4 p-4">
                  <span className="text-2xl mt-0.5 select-none">{skill.icon}</span>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center justify-between gap-3">
                      <p className="text-sm font-semibold text-[var(--loom-fg)]">{skill.name}</p>
                      <button
                        onClick={(e) => { e.stopPropagation(); toggle(skill.id); }}
                        className={`shrink-0 text-xs rounded-lg px-3 py-1 font-medium transition-colors ${
                          enabled
                            ? "bg-[var(--loom-accent)] text-white"
                            : "border border-[var(--loom-border)] text-[var(--loom-fg-soft)] hover:bg-[var(--loom-border)]"
                        }`}
                      >
                        {enabled ? "Enabled ✓" : "Enable"}
                      </button>
                    </div>
                    <p className="text-xs text-[var(--loom-fg-soft)] mt-1 leading-relaxed">{skill.description}</p>
                    <div className="flex gap-1 mt-2 flex-wrap">
                      <span className="text-[10px] px-2 py-0.5 rounded-full bg-[var(--loom-border)] text-[var(--loom-fg-soft)]">
                        {skill.category}
                      </span>
                      {skill.tags.slice(0, 2).map((t) => (
                        <span key={t} className="text-[10px] px-2 py-0.5 rounded-full bg-[var(--loom-border)] text-[var(--loom-fg-soft)] opacity-70">
                          {t}
                        </span>
                      ))}
                    </div>
                  </div>
                </div>
              </div>
            );
          })}
          {filtered.length === 0 && (
            <div className="text-center py-12 text-sm text-[var(--loom-fg-soft)]">
              No skills match your search.
            </div>
          )}
        </div>
      </div>

      {/* Detail panel */}
      {detail && (
        <div className="w-80 shrink-0 border-l border-[var(--loom-border)] bg-[var(--loom-bg-soft)] overflow-y-auto p-6 flex flex-col gap-4">
          <div className="flex items-start justify-between">
            <div>
              <span className="text-3xl">{detail.icon}</span>
              <h2 className="text-base font-semibold text-[var(--loom-fg)] mt-2">{detail.name}</h2>
              <p className="text-xs text-[var(--loom-fg-soft)] mt-0.5">{detail.category}</p>
            </div>
            <button
              onClick={() => setDetail(null)}
              className="text-[var(--loom-fg-soft)] hover:text-[var(--loom-fg)] text-xl leading-none mt-1"
              aria-label="Close"
            >
              ×
            </button>
          </div>
          <p className="text-sm text-[var(--loom-fg-soft)] leading-relaxed">{detail.description}</p>
          <div>
            <p className="text-xs font-semibold text-[var(--loom-fg)] mb-2 uppercase tracking-wide opacity-60">
              System prompt
            </p>
            <pre className="text-xs bg-[var(--loom-bg)] border border-[var(--loom-border)] rounded-lg p-3 whitespace-pre-wrap text-[var(--loom-fg-soft)] leading-relaxed font-mono overflow-x-auto">
              {detail.systemPrompt}
            </pre>
          </div>
          <button
            onClick={() => toggle(detail.id)}
            className={`w-full py-2.5 rounded-xl text-sm font-medium transition-colors ${
              active.has(detail.id)
                ? "bg-[var(--loom-danger)] text-white hover:opacity-90"
                : "bg-[var(--loom-accent)] text-white hover:opacity-90"
            }`}
          >
            {active.has(detail.id) ? "Disable skill" : "Enable skill"}
          </button>
          {active.has(detail.id) && (
            <p className="text-xs text-center text-[var(--loom-fg-soft)] opacity-70">
              Active — applied to new sessions
            </p>
          )}
        </div>
      )}
    </div>
  );
}
