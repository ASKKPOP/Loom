import { useState } from "react";
import { Link } from "react-router-dom";

interface Skill {
  id: string;
  name: string;
  description: string;
  category: string;
  systemPrompt: string;
  icon: string;
  tags: string[];
}

const BUILT_IN_SKILLS: Skill[] = [
  {
    id: "code-reviewer",
    name: "Code Reviewer",
    description: "Review code for bugs, security issues, performance and best practices.",
    category: "Engineering",
    icon: "🔍",
    tags: ["code", "security", "review"],
    systemPrompt: `You are an expert code reviewer. When reviewing code:
- Identify bugs, logic errors, and edge cases
- Flag security vulnerabilities (injection, auth issues, data exposure)
- Suggest performance improvements
- Check adherence to best practices and design patterns
- Keep feedback constructive and actionable
- Prioritize issues by severity: Critical > High > Medium > Low`,
  },
  {
    id: "python-expert",
    name: "Python Expert",
    description: "Expert Python developer focused on clean, idiomatic, production-ready code.",
    category: "Engineering",
    icon: "🐍",
    tags: ["python", "code", "engineering"],
    systemPrompt: `You are an expert Python developer. You write clean, idiomatic Python that follows PEP 8 and modern best practices.
- Prefer standard library over third-party when possible
- Use type hints throughout
- Write clear docstrings for public APIs
- Prefer dataclasses or Pydantic for data models
- Use context managers, generators, and comprehensions where appropriate
- Always consider error handling and edge cases`,
  },
  {
    id: "sql-expert",
    name: "SQL Expert",
    description: "Database and SQL query optimization, schema design, and performance tuning.",
    category: "Data",
    icon: "🗄️",
    tags: ["sql", "database", "data"],
    systemPrompt: `You are a senior database engineer and SQL expert. You help with:
- Writing efficient, readable SQL queries
- Query optimization and execution plan analysis
- Schema design and normalization
- Index strategy and performance tuning
- Database-specific dialects (PostgreSQL, MySQL, SQLite, etc.)
Always explain the reasoning behind your suggestions and highlight any potential performance concerns.`,
  },
  {
    id: "data-analyst",
    name: "Data Analyst",
    description: "Analyze data, identify trends, and generate actionable insights.",
    category: "Data",
    icon: "📊",
    tags: ["data", "analysis", "insights"],
    systemPrompt: `You are a skilled data analyst. When analyzing data:
- Start with descriptive statistics and data quality checks
- Identify patterns, trends, and anomalies
- Use clear, precise language when describing findings
- Suggest appropriate visualizations
- Quantify uncertainty and confidence
- Translate technical findings into business insights
- Recommend next steps and further analyses`,
  },
  {
    id: "writing-assistant",
    name: "Writing Assistant",
    description: "Improve clarity, structure, and impact of any written content.",
    category: "Productivity",
    icon: "✍️",
    tags: ["writing", "editing", "content"],
    systemPrompt: `You are a professional writing coach and editor. You help improve writing by:
- Enhancing clarity and conciseness (cut unnecessary words)
- Strengthening structure and flow
- Matching tone to the target audience
- Correcting grammar and punctuation
- Suggesting more precise or impactful word choices
- Preserving the author's voice while improving quality
Provide specific, actionable feedback rather than vague praise.`,
  },
  {
    id: "devops-engineer",
    name: "DevOps Engineer",
    description: "Infrastructure, CI/CD, containerization, and deployment automation.",
    category: "Engineering",
    icon: "⚙️",
    tags: ["devops", "docker", "kubernetes", "ci/cd"],
    systemPrompt: `You are a senior DevOps engineer. You help with:
- Docker and container orchestration (Kubernetes, Compose)
- CI/CD pipeline design (GitHub Actions, GitLab CI, etc.)
- Infrastructure as code (Terraform, Pulumi)
- Cloud platforms (AWS, GCP, Azure)
- Monitoring, logging, and alerting
- Security and compliance in infrastructure
Always prioritize reliability, reproducibility, and least-privilege security principles.`,
  },
  {
    id: "security-researcher",
    name: "Security Researcher",
    description: "Security analysis, threat modeling, and vulnerability assessment.",
    category: "Security",
    icon: "🛡️",
    tags: ["security", "pentest", "vulnerability"],
    systemPrompt: `You are a security researcher focused on defensive security. You help with:
- Threat modeling and attack surface analysis
- Code security review (OWASP Top 10 and beyond)
- Security architecture and design review
- Explaining vulnerabilities and their mitigations
- Security tooling and methodology
Focus on educational, defensive use cases. Always recommend responsible disclosure.`,
  },
  {
    id: "product-manager",
    name: "Product Manager",
    description: "Product strategy, PRDs, user stories, and prioritization frameworks.",
    category: "Productivity",
    icon: "📋",
    tags: ["product", "strategy", "ux"],
    systemPrompt: `You are an experienced product manager. You help with:
- Writing clear PRDs and product specs
- Crafting user stories with acceptance criteria
- Prioritization frameworks (RICE, MoSCoW, etc.)
- Competitive analysis and market positioning
- OKR and goal-setting
- Stakeholder communication
Focus on user value and business impact. Always tie features to measurable outcomes.`,
  },
  {
    id: "ml-engineer",
    name: "ML Engineer",
    description: "Machine learning, model training, evaluation, and MLX/PyTorch workflows.",
    category: "Data",
    icon: "🤖",
    tags: ["ml", "pytorch", "mlx", "ai"],
    systemPrompt: `You are a machine learning engineer. You help with:
- Model architecture selection and design
- Training loops, loss functions, and optimizers
- Data preprocessing and feature engineering
- Model evaluation and debugging
- MLX, PyTorch, and Hugging Face workflows
- Inference optimization and quantization
- Experiment tracking and reproducibility
Prefer practical, runnable code examples with clear explanations.`,
  },
];

const CATEGORIES = [...new Set(BUILT_IN_SKILLS.map((s) => s.category))];
const STORAGE_KEY = "loom:active-skills";

function loadActive(): Set<string> {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    return new Set(raw ? JSON.parse(raw) : []);
  } catch {
    return new Set();
  }
}

function saveActive(ids: Set<string>) {
  localStorage.setItem(STORAGE_KEY, JSON.stringify([...ids]));
}

export function CustomizeSkillsPage() {
  const [active, setActive] = useState<Set<string>>(loadActive);
  const [search, setSearch] = useState("");
  const [category, setCategory] = useState<string | null>(null);
  const [detail, setDetail] = useState<Skill | null>(null);

  const toggle = (id: string) => {
    setActive((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      saveActive(next);
      return next;
    });
  };

  const filtered = BUILT_IN_SKILLS.filter((s) => {
    if (category && s.category !== category) return false;
    if (search) {
      const q = search.toLowerCase();
      return s.name.toLowerCase().includes(q) || s.description.toLowerCase().includes(q) || s.tags.some((t) => t.includes(q));
    }
    return true;
  });

  return (
    <div className="flex h-full">
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
            Skills shape how Loom responds. Enable a skill to apply its system prompt to new conversations.
          </p>
          <div className="flex gap-3 mt-5">
            <Link
              to="/customize/skills"
              className={`flex items-center gap-2 px-4 py-2.5 rounded-xl text-sm font-medium no-underline transition-colors ${
                true ? "bg-[var(--loom-border)] text-[var(--loom-fg)]" : "text-[var(--loom-fg-soft)] hover:bg-[var(--loom-border)]"
              }`}
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

        {/* Active skills summary */}
        {active.size > 0 && (
          <div className="mb-6 max-w-2xl rounded-xl border border-[var(--loom-accent)] bg-[var(--loom-accent-soft)] px-4 py-3 flex items-center gap-3">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="var(--loom-accent)" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M12 2l3.09 6.26L22 9.27l-5 4.87 1.18 6.88L12 17.77l-6.18 3.25L7 14.14 2 9.27l6.91-1.01L12 2z"/>
            </svg>
            <p className="text-sm text-[var(--loom-accent)]">
              <span className="font-semibold">{active.size} skill{active.size !== 1 ? "s" : ""} active</span>
              {" — "}applied to new conversations automatically.
            </p>
          </div>
        )}

        {/* Search + filter */}
        <div className="flex gap-2 mb-5 max-w-2xl">
          <div className="relative flex-1">
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
          <div className="flex gap-1 flex-wrap">
            <button
              onClick={() => setCategory(null)}
              className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-colors ${
                !category ? "bg-[var(--loom-accent)] text-white" : "border border-[var(--loom-border)] text-[var(--loom-fg-soft)] hover:bg-[var(--loom-border)]"
              }`}
            >
              All
            </button>
            {CATEGORIES.map((cat) => (
              <button
                key={cat}
                onClick={() => setCategory(category === cat ? null : cat)}
                className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-colors ${
                  category === cat ? "bg-[var(--loom-accent)] text-white" : "border border-[var(--loom-border)] text-[var(--loom-fg-soft)] hover:bg-[var(--loom-border)]"
                }`}
              >
                {cat}
              </button>
            ))}
          </div>
        </div>

        {/* Skills grid */}
        <div className="grid grid-cols-1 gap-3 max-w-2xl">
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
                  <span className="text-2xl mt-0.5">{skill.icon}</span>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center justify-between gap-2">
                      <p className="text-sm font-semibold text-[var(--loom-fg)]">{skill.name}</p>
                      <button
                        onClick={(e) => { e.stopPropagation(); toggle(skill.id); }}
                        className={`shrink-0 text-xs rounded-lg px-3 py-1 font-medium transition-colors ${
                          enabled
                            ? "bg-[var(--loom-accent)] text-white"
                            : "border border-[var(--loom-border)] text-[var(--loom-fg-soft)] hover:bg-[var(--loom-border)]"
                        }`}
                      >
                        {enabled ? "Enabled" : "Enable"}
                      </button>
                    </div>
                    <p className="text-xs text-[var(--loom-fg-soft)] mt-1 leading-relaxed">{skill.description}</p>
                    <div className="flex gap-1 mt-2 flex-wrap">
                      <span className="text-[10px] px-2 py-0.5 rounded-full bg-[var(--loom-border)] text-[var(--loom-fg-soft)]">{skill.category}</span>
                      {skill.tags.slice(0, 2).map((t) => (
                        <span key={t} className="text-[10px] px-2 py-0.5 rounded-full bg-[var(--loom-border)] text-[var(--loom-fg-soft)] opacity-70">{t}</span>
                      ))}
                    </div>
                  </div>
                </div>
              </div>
            );
          })}
          {filtered.length === 0 && (
            <div className="text-center py-12 text-sm text-[var(--loom-fg-soft)]">No skills match your search.</div>
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
              <p className="text-xs text-[var(--loom-fg-soft)] mt-1">{detail.category}</p>
            </div>
            <button
              onClick={() => setDetail(null)}
              className="text-[var(--loom-fg-soft)] hover:text-[var(--loom-fg)] text-lg leading-none"
            >
              ×
            </button>
          </div>
          <p className="text-sm text-[var(--loom-fg-soft)] leading-relaxed">{detail.description}</p>
          <div>
            <p className="text-xs font-semibold text-[var(--loom-fg)] mb-2 uppercase tracking-wide">System prompt</p>
            <pre className="text-xs bg-[var(--loom-bg)] border border-[var(--loom-border)] rounded-lg p-3 whitespace-pre-wrap text-[var(--loom-fg-soft)] leading-relaxed font-mono">
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
        </div>
      )}
    </div>
  );
}
