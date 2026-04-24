import { Link } from "react-router-dom";

const CONNECTORS = [
  {
    id: "filesystem",
    name: "Filesystem",
    description: "Read files and directories from your Mac.",
    icon: "📁",
    status: "coming-soon",
  },
  {
    id: "github",
    name: "GitHub",
    description: "Read repositories, issues, and pull requests.",
    icon: "🐙",
    status: "coming-soon",
  },
  {
    id: "postgres",
    name: "PostgreSQL",
    description: "Query your local or remote PostgreSQL databases.",
    icon: "🐘",
    status: "coming-soon",
  },
  {
    id: "sqlite",
    name: "SQLite",
    description: "Query SQLite databases on your filesystem.",
    icon: "🗃️",
    status: "coming-soon",
  },
  {
    id: "http",
    name: "HTTP / REST",
    description: "Call any HTTP API with configurable auth headers.",
    icon: "🌐",
    status: "coming-soon",
  },
];

export function CustomizeConnectorsPage() {
  return (
    <div className="flex-1 overflow-y-auto p-8">
      <div className="mb-8 max-w-2xl">
        <div className="w-14 h-14 rounded-2xl bg-[var(--loom-accent-soft)] flex items-center justify-center mb-4">
          <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="var(--loom-accent)" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
            <rect x="2" y="2" width="8" height="8" rx="2"/><rect x="14" y="2" width="8" height="8" rx="2"/>
            <rect x="2" y="14" width="8" height="8" rx="2"/><rect x="14" y="14" width="8" height="8" rx="2"/>
          </svg>
        </div>
        <h1 className="text-2xl font-semibold text-[var(--loom-fg)] mb-2">Customize Loom</h1>
        <p className="text-[var(--loom-fg-soft)] text-sm leading-relaxed">
          Connectors let Loom read and write to the tools you already use.
        </p>
        <div className="flex gap-3 mt-5">
          <Link
            to="/customize/skills"
            className="flex items-center gap-2 px-4 py-2.5 rounded-xl text-sm font-medium no-underline text-[var(--loom-fg-soft)] hover:bg-[var(--loom-border)] transition-colors"
          >
            <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M12 2l3.09 6.26L22 9.27l-5 4.87 1.18 6.88L12 17.77l-6.18 3.25L7 14.14 2 9.27l6.91-1.01L12 2z"/>
            </svg>
            Skills
          </Link>
          <Link
            to="/customize/connectors"
            className="flex items-center gap-2 px-4 py-2.5 rounded-xl text-sm font-medium no-underline bg-[var(--loom-border)] text-[var(--loom-fg)] transition-colors"
          >
            <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <rect x="2" y="2" width="8" height="8" rx="2"/><rect x="14" y="2" width="8" height="8" rx="2"/>
              <rect x="2" y="14" width="8" height="8" rx="2"/><rect x="14" y="14" width="8" height="8" rx="2"/>
            </svg>
            Connectors
          </Link>
        </div>
      </div>

      <div className="grid grid-cols-1 gap-3 max-w-2xl">
        {CONNECTORS.map((c) => (
          <div
            key={c.id}
            className="flex items-start gap-4 rounded-xl border border-[var(--loom-border)] bg-[var(--loom-bg-soft)] p-4"
          >
            <span className="text-2xl mt-0.5">{c.icon}</span>
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2">
                <p className="text-sm font-semibold text-[var(--loom-fg)]">{c.name}</p>
                <span className="text-[10px] px-2 py-0.5 rounded-full bg-[var(--loom-border)] text-[var(--loom-fg-soft)]">
                  Coming soon
                </span>
              </div>
              <p className="text-xs text-[var(--loom-fg-soft)] mt-1">{c.description}</p>
            </div>
            <button
              disabled
              className="shrink-0 text-xs rounded-lg border border-[var(--loom-border)] px-3 py-1 text-[var(--loom-fg-soft)] opacity-40 cursor-not-allowed"
            >
              Connect
            </button>
          </div>
        ))}
      </div>
    </div>
  );
}
