import { describe, expect, it } from "vitest";
import { SseParser } from "../lib/sse";

function encode(s: string): Uint8Array {
  return new TextEncoder().encode(s);
}

describe("SseParser", () => {
  it("parses a single complete event", () => {
    const p = new SseParser();
    const out = p.push(encode('data: {"choices":[{"delta":{"content":"hi"}}]}\n\n'));
    expect(out).toHaveLength(1);
    expect(out[0]!.data).toBe('{"choices":[{"delta":{"content":"hi"}}]}');
  });

  it("handles events split across chunks", () => {
    const p = new SseParser();
    expect(p.push(encode("data: hel"))).toEqual([]);
    expect(p.push(encode("lo\n"))).toEqual([]);
    const out = p.push(encode("\ndata: world\n\n"));
    expect(out.map((e) => e.data)).toEqual(["hello", "world"]);
  });

  it("skips comments and empty lines", () => {
    const p = new SseParser();
    const out = p.push(encode(": keepalive\n\ndata: ok\n\n"));
    expect(out.map((e) => e.data)).toEqual(["ok"]);
  });

  it("handles [DONE] sentinel as a normal data line", () => {
    const p = new SseParser();
    const out = p.push(encode("data: [DONE]\n\n"));
    expect(out[0]!.data).toBe("[DONE]");
  });

  it("joins multi-line data fields with newlines", () => {
    const p = new SseParser();
    const out = p.push(encode("data: line one\ndata: line two\n\n"));
    expect(out[0]!.data).toBe("line one\nline two");
  });

  it("supports \\r\\n delimiters", () => {
    const p = new SseParser();
    const out = p.push(encode("data: hi\r\n\r\n"));
    expect(out[0]!.data).toBe("hi");
  });

  it("decodes multi-byte UTF-8 across chunk boundaries", () => {
    const p = new SseParser();
    // "日本" = E6 97 A5 E6 9C AC — split in the middle of the first code point.
    const full = encode("data: 日本\n\n");
    const first = full.slice(0, 7);
    const rest = full.slice(7);
    expect(p.push(first)).toEqual([]);
    const out = p.push(rest);
    expect(out[0]!.data).toBe("日本");
  });

  it("flush yields nothing if buffer is empty", () => {
    const p = new SseParser();
    expect(p.flush()).toEqual([]);
  });
});
