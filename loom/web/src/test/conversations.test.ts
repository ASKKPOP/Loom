import { describe, expect, it } from "vitest";
import {
  deriveTitle,
  emptyState,
  newMessage,
  reducer,
  type ConversationsState,
} from "../state/conversations";

function freshWithConv(model: string | null = "m-x"): ConversationsState {
  return reducer(emptyState(), { type: "create", model });
}

describe("conversations reducer", () => {
  it("creates a conversation and sets it active", () => {
    const s = freshWithConv();
    expect(s.conversations).toHaveLength(1);
    expect(s.activeId).toBe(s.conversations[0]!.id);
    expect(s.conversations[0]!.model).toBe("m-x");
  });

  it("activates only existing conversations", () => {
    const s = freshWithConv();
    const bogus = reducer(s, { type: "activate", id: "nope" });
    expect(bogus).toBe(s);
  });

  it("appends messages and auto-titles from the first user message", () => {
    const s1 = freshWithConv();
    const id = s1.conversations[0]!.id;
    const user = newMessage("user", "Hello there, help me refactor this function");
    const s2 = reducer(s1, { type: "append-message", id, message: user });
    expect(s2.conversations[0]!.messages).toHaveLength(1);
    expect(s2.conversations[0]!.title).toBe("Hello there, help me refactor this function");
  });

  it("streams tokens into an assistant message", () => {
    const s1 = freshWithConv();
    const id = s1.conversations[0]!.id;
    const asst = newMessage("assistant", "", true);
    let s = reducer(s1, { type: "append-message", id, message: asst });
    s = reducer(s, { type: "append-token", id, messageId: asst.id, token: "hel" });
    s = reducer(s, { type: "append-token", id, messageId: asst.id, token: "lo" });
    s = reducer(s, { type: "finish-message", id, messageId: asst.id });
    const m = s.conversations[0]!.messages[0]!;
    expect(m.content).toBe("hello");
    expect(m.streaming).toBe(false);
  });

  it("renames conversations", () => {
    const s1 = freshWithConv();
    const id = s1.conversations[0]!.id;
    const s2 = reducer(s1, { type: "rename", id, title: "Debug session" });
    expect(s2.conversations[0]!.title).toBe("Debug session");
  });

  it("delete picks a new active id", () => {
    const a = reducer(emptyState(), { type: "create", model: "a" });
    const b = reducer(a, { type: "create", model: "b" });
    // `create` prepends and activates; b is active, a is second.
    const bId = b.conversations[0]!.id;
    const aId = b.conversations[1]!.id;
    const after = reducer(b, { type: "delete", id: bId });
    expect(after.conversations).toHaveLength(1);
    expect(after.activeId).toBe(aId);
  });

  it("delete clears active when removing the last conversation", () => {
    const s = freshWithConv();
    const id = s.activeId!;
    const after = reducer(s, { type: "delete", id });
    expect(after.conversations).toHaveLength(0);
    expect(after.activeId).toBeNull();
  });

  it("updates user message content and truncates the tail", () => {
    const s0 = freshWithConv();
    const id = s0.conversations[0]!.id;
    const u = newMessage("user", "first");
    const a = newMessage("assistant", "reply");
    let s = reducer(s0, { type: "append-message", id, message: u });
    s = reducer(s, { type: "append-message", id, message: a });
    expect(s.conversations[0]!.messages).toHaveLength(2);
    s = reducer(s, { type: "update-message", id, messageId: u.id, content: "edited" });
    s = reducer(s, { type: "truncate-after", id, messageId: u.id });
    expect(s.conversations[0]!.messages).toHaveLength(1);
    expect(s.conversations[0]!.messages[0]!.content).toBe("edited");
  });

  it("hydrate from an empty/unknown active id falls back to first", () => {
    const base = freshWithConv();
    const s = reducer(emptyState(), {
      type: "hydrate",
      conversations: base.conversations,
      activeId: "nonexistent",
    });
    expect(s.activeId).toBe(base.conversations[0]!.id);
  });

  it("deriveTitle handles long and empty inputs", () => {
    expect(deriveTitle("")).toBe("New chat");
    expect(deriveTitle("  \n  ")).toBe("New chat");
    expect(deriveTitle("a".repeat(100)).endsWith("…")).toBe(true);
    expect(deriveTitle("a".repeat(100)).length).toBeLessThanOrEqual(48);
  });
});
