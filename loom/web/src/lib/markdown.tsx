import { useEffect, useState } from "react";
import ReactMarkdown, { type Components } from "react-markdown";
import remarkGfm from "remark-gfm";

// Shiki is heavy; we lazy-init a singleton highlighter on first use.
// eslint-disable-next-line @typescript-eslint/no-explicit-any
let highlighterPromise: Promise<any> | null = null;

async function getHighlighter() {
  if (!highlighterPromise) {
    highlighterPromise = (async () => {
      const shiki = await import("shiki");
      return shiki.createHighlighter({
        themes: ["github-light", "github-dark"],
        langs: [
          "bash",
          "typescript",
          "javascript",
          "tsx",
          "jsx",
          "python",
          "json",
          "yaml",
          "markdown",
          "rust",
          "go",
          "swift",
          "sql",
          "html",
          "css",
        ],
      });
    })();
  }
  return highlighterPromise;
}

function themeForDocument(): "github-light" | "github-dark" {
  if (typeof document === "undefined") return "github-light";
  return document.documentElement.classList.contains("dark") ? "github-dark" : "github-light";
}

function CodeBlock({ lang, code }: { lang: string; code: string }) {
  const [html, setHtml] = useState<string | null>(null);
  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const hl = await getHighlighter();
        const supported = hl.getLoadedLanguages().includes(lang);
        const effectiveLang = supported ? lang : "text";
        const out = hl.codeToHtml(code, { lang: effectiveLang, theme: themeForDocument() });
        if (!cancelled) setHtml(out);
      } catch {
        if (!cancelled) setHtml(null);
      }
    })();
    return () => { cancelled = true; };
  }, [code, lang]);

  if (!html) {
    return (
      <pre>
        <code>{code}</code>
      </pre>
    );
  }
  return (
    <div
      className="loom-code"
      // html produced by shiki; content is trusted local output.
      dangerouslySetInnerHTML={{ __html: html }}
    />
  );
}

const components: Components = {
  code(props) {
    const { className, children, ...rest } = props;
    const text = String(children ?? "");
    const match = /language-([\w-]+)/.exec(className ?? "");
    // Inline vs fenced block: inline has no className and is single-line.
    const isBlock = Boolean(match) || text.includes("\n");
    if (!isBlock) {
      return <code className={className} {...rest}>{children}</code>;
    }
    const lang = match?.[1] ?? "text";
    return <CodeBlock lang={lang} code={text.replace(/\n$/, "")} />;
  },
  a({ href, children, ...rest }) {
    return (
      <a href={href} target="_blank" rel="noreferrer noopener" {...rest}>
        {children}
      </a>
    );
  },
};

export function Markdown({ text }: { text: string }) {
  return (
    <div className="loom-prose">
      <ReactMarkdown remarkPlugins={[remarkGfm]} components={components}>
        {text}
      </ReactMarkdown>
    </div>
  );
}
