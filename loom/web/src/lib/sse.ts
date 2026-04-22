// Minimal, spec-shaped SSE parser for OpenAI-compatible chat completion streams.
//
// The server emits events as UTF-8 lines: `data: <json>\n\n`, with `data: [DONE]`
// as the terminator. We buffer bytes, split on `\n\n`, drop the `data: ` prefix,
// and hand the caller each event as a string. The caller decodes the JSON.

export interface SseEvent {
  data: string;
}

export class SseParser {
  private buffer = "";
  private decoder = new TextDecoder("utf-8");

  /** Feed a raw chunk and yield completed events. */
  push(chunk: Uint8Array): SseEvent[] {
    this.buffer += this.decoder.decode(chunk, { stream: true });
    return this.drain();
  }

  /** Flush any trailing content (e.g. if the stream ended without a final \n\n). */
  flush(): SseEvent[] {
    this.buffer += this.decoder.decode();
    return this.drain();
  }

  private drain(): SseEvent[] {
    const events: SseEvent[] = [];
    // Events are separated by a blank line. Accept both \n\n and \r\n\r\n.
    for (;;) {
      const found = firstDelimiter(this.buffer);
      if (!found) break;
      const rawEvent = this.buffer.slice(0, found.at);
      this.buffer = this.buffer.slice(found.at + found.len);
      const ev = parseEvent(rawEvent);
      if (ev) events.push(ev);
    }
    return events;
  }
}

function firstDelimiter(s: string): { at: number; len: number } | null {
  const a = s.indexOf("\n\n");
  const b = s.indexOf("\r\n\r\n");
  if (a === -1 && b === -1) return null;
  if (a === -1) return { at: b, len: 4 };
  if (b === -1) return { at: a, len: 2 };
  return a < b ? { at: a, len: 2 } : { at: b, len: 4 };
}

function parseEvent(raw: string): SseEvent | null {
  const lines = raw.split(/\r?\n/);
  const dataParts: string[] = [];
  for (const line of lines) {
    if (!line || line.startsWith(":")) continue; // comment / keepalive
    if (line.startsWith("data:")) {
      dataParts.push(line.slice(5).replace(/^ /, ""));
    }
  }
  if (dataParts.length === 0) return null;
  return { data: dataParts.join("\n") };
}
