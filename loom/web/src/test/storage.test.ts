import { beforeEach, describe, expect, it } from "vitest";
import { createStorage, type StorageLike } from "../lib/storage";
import type { Conversation } from "../types";

function fakeStore(): StorageLike {
  const map = new Map<string, string>();
  return {
    getItem: (k) => (map.has(k) ? (map.get(k) ?? null) : null),
    setItem: (k, v) => { map.set(k, v); },
    removeItem: (k) => { map.delete(k); },
  };
}

describe("storage", () => {
  let s: ReturnType<typeof createStorage>;
  beforeEach(() => { s = createStorage(fakeStore()); });

  it("round-trips conversations", () => {
    const conv: Conversation = {
      id: "c1",
      title: "Test",
      systemPrompt: "you are a test",
      model: "x",
      messages: [{ id: "m1", role: "user", content: "hi", createdAt: 1 }],
      createdAt: 1,
      updatedAt: 2,
    };
    s.saveConversations([conv]);
    expect(s.loadConversations()).toEqual([conv]);
  });

  it("returns [] for malformed conversations payload", () => {
    const store = fakeStore();
    store.setItem("loom:conversations", "not json");
    const bad = createStorage(store);
    expect(bad.loadConversations()).toEqual([]);
  });

  it("tracks the active conversation id", () => {
    s.saveActive("c-xyz");
    expect(s.loadActive()).toBe("c-xyz");
    s.saveActive(null);
    expect(s.loadActive()).toBeNull();
  });

  it("persists settings", () => {
    s.saveSettings({ temperature: 0.3, maxTokens: 512, topP: 0.9, theme: "dark" });
    expect(s.loadSettings()).toEqual({ temperature: 0.3, maxTokens: 512, topP: 0.9, theme: "dark" });
  });

  it("persists theme override", () => {
    expect(s.loadTheme()).toBeNull();
    s.saveTheme("dark");
    expect(s.loadTheme()).toBe("dark");
    s.saveTheme(null);
    expect(s.loadTheme()).toBeNull();
  });

  it("ignores invalid theme values", () => {
    const store = fakeStore();
    store.setItem("loom:theme", "neon");
    const bad = createStorage(store);
    expect(bad.loadTheme()).toBeNull();
  });
});
