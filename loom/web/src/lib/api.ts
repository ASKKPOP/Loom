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
}

export async function listModels(): Promise<ModelInfo[]> {
  const res = await fetch("/v1/models");
  if (!res.ok) throw new Error(`GET /v1/models → ${res.status}`);
  const body = (await res.json()) as { data?: Array<{ id: string }> };
  return (body.data ?? []).map((m) => ({ id: m.id }));
}

export async function checkHealth(): Promise<boolean> {
  try {
    const res = await fetch("/health", { method: "GET" });
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
  const res = await fetch("/v1/chat/completions", {
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
          if (delta) init.onToken(delta);
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
