import type { Conversation, Settings } from "../types";

const CONVERSATIONS_KEY = "loom:conversations";
const ACTIVE_KEY = "loom:active-conversation";
const SETTINGS_KEY = "loom:settings";
const THEME_KEY = "loom:theme";

export interface StorageLike {
  getItem(key: string): string | null;
  setItem(key: string, value: string): void;
  removeItem(key: string): void;
}

const memoryStore: Record<string, string> = {};
const memoryStorage: StorageLike = {
  getItem: (k) => (k in memoryStore ? memoryStore[k]! : null),
  setItem: (k, v) => { memoryStore[k] = v; },
  removeItem: (k) => { delete memoryStore[k]; },
};

function defaultStore(): StorageLike {
  try {
    if (typeof localStorage !== "undefined") {
      // Probe — Safari private mode throws on setItem.
      const k = "__loom_probe__";
      localStorage.setItem(k, "1");
      localStorage.removeItem(k);
      return localStorage;
    }
  } catch {
    /* fall through to memory */
  }
  return memoryStorage;
}

export function createStorage(store: StorageLike = defaultStore()) {
  return {
    loadConversations(): Conversation[] {
      const raw = store.getItem(CONVERSATIONS_KEY);
      if (!raw) return [];
      try {
        const parsed = JSON.parse(raw);
        return Array.isArray(parsed) ? parsed : [];
      } catch {
        return [];
      }
    },
    saveConversations(convs: Conversation[]): void {
      store.setItem(CONVERSATIONS_KEY, JSON.stringify(convs));
    },
    loadActive(): string | null {
      return store.getItem(ACTIVE_KEY);
    },
    saveActive(id: string | null): void {
      if (id) store.setItem(ACTIVE_KEY, id);
      else store.removeItem(ACTIVE_KEY);
    },
    loadSettings(): Settings | null {
      const raw = store.getItem(SETTINGS_KEY);
      if (!raw) return null;
      try {
        return JSON.parse(raw) as Settings;
      } catch {
        return null;
      }
    },
    saveSettings(s: Settings): void {
      store.setItem(SETTINGS_KEY, JSON.stringify(s));
    },
    loadTheme(): "light" | "dark" | null {
      const v = store.getItem(THEME_KEY);
      return v === "light" || v === "dark" ? v : null;
    },
    saveTheme(theme: "light" | "dark" | null): void {
      if (theme) store.setItem(THEME_KEY, theme);
      else store.removeItem(THEME_KEY);
    },
  };
}

export type Storage = ReturnType<typeof createStorage>;
