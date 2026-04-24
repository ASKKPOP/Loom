import type { Message, ModelInfo, ChatCompletionChunk } from "../types";
import { SseParser } from "./sse";

export interface ChatRequestInit {
  model: string;
  messages: Pick<Message, "role" | "content">[];
  temperature: number;
  maxTokens: number;
  topP: number;
  signal: AbortSignal;
  onToken: (token: string) => void;
  onDone: () => void;
  /** Base URL for the backend (empty string = same-origin proxy). */
  baseUrl?: string;
}

function base(url: string | undefined): string {
  return (url ?? "").replace(/\/$/, "");
}

/** Returns true when the model output looks like a runaway repetition or unprompted list. */
function hasRepetition(content: string): boolean {
  const lines = content.split("\n").map((l) => l.trim()).filter((l) => l.length > 2);
  if (lines.length < 4) return false;

  // Any line repeats 2+ times → loop detected.
  const counts = new Map<string, number>();
  for (const line of lines) {
    const n = (counts.get(line) ?? 0) + 1;
    if (n >= 2) return true;
    counts.set(line, n);
  }

  // 5+ consecutive numbered list items → unprompted enumeration.
  const numbered = lines.filter((l) => /^\d+\.\s+\S/.test(l));
  if (numbered.length >= 5) return true;

  return false;
}

export async function listModels(baseUrl = ""): Promise<ModelInfo[]> {
  const res = await fetch(`${base(baseUrl)}/v1/models`);
  if (!res.ok) throw new Error(`GET /v1/models → ${res.status}`);
  const body = (await res.json()) as { data?: Array<{ id: string }> };
  return (body.data ?? []).map((m) => ({ id: m.id }));
}

export async function checkHealth(baseUrl = ""): Promise<boolean> {
  try {
    const res = await fetch(`${base(baseUrl)}/health`, { method: "GET" });
    return res.ok;
  } catch {
    return false;
  }
}

export async function streamChatCompletion(init: ChatRequestInit): Promise<void> {
  const body = {
    model: init.model,
    messages: init.messages,
    stream: true,
    temperature: init.temperature,
    max_tokens: init.maxTokens,
    top_p: init.topP,
  };
  const res = await fetch(`${base(init.baseUrl)}/v1/chat/completions`, {
    method: "POST",
    headers: { "Content-Type": "application/json", Accept: "text/event-stream" },
    body: JSON.stringify(body),
    signal: init.signal,
  });
  if (!res.ok || !res.body) {
    const text = await res.text().catch(() => "");
    throw new Error(`POST /v1/chat/completions → ${res.status}: ${text.slice(0, 200)}`);
  }
  const parser = new SseParser();
  const reader = res.body.getReader();
  let accumulated = "";
  try {
    for (;;) {
      const { value, done } = await reader.read();
      if (done) break;
      for (const ev of parser.push(value)) {
        if (ev.data === "[DONE]") {
          init.onDone();
          return;
        }
        try {
          const chunk = JSON.parse(ev.data) as ChatCompletionChunk;
          const delta = chunk.choices?.[0]?.delta?.content;
          if (delta) {
            accumulated += delta;
            if (hasRepetition(accumulated)) {
              init.onDone();
              return;
            }
            init.onToken(delta);
          }
        } catch {
          // malformed chunk — skip
        }
      }
    }
    for (const ev of parser.flush()) {
      if (ev.data === "[DONE]") break;
      try {
        const chunk = JSON.parse(ev.data) as ChatCompletionChunk;
        const delta = chunk.choices?.[0]?.delta?.content;
        if (delta) init.onToken(delta);
      } catch { /* skip */ }
    }
    init.onDone();
  } finally {
    try { reader.releaseLock(); } catch { /* noop */ }
  }
}
