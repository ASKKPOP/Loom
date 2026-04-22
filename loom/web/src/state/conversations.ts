import type { Conversation, Message, Role } from "../types";
import { uid } from "../lib/id";

export type ConversationsState = {
  conversations: Conversation[];
  activeId: string | null;
};

export type ConversationsAction =
  | { type: "hydrate"; conversations: Conversation[]; activeId: string | null }
  | { type: "create"; model: string | null; systemPrompt?: string }
  | { type: "activate"; id: string }
  | { type: "rename"; id: string; title: string }
  | { type: "delete"; id: string }
  | { type: "set-system-prompt"; id: string; prompt: string }
  | { type: "set-model"; id: string; model: string | null }
  | { type: "append-message"; id: string; message: Message }
  | { type: "append-token"; id: string; messageId: string; token: string }
  | { type: "finish-message"; id: string; messageId: string; error?: string }
  | { type: "remove-message"; id: string; messageId: string }
  | { type: "update-message"; id: string; messageId: string; content: string }
  | { type: "truncate-after"; id: string; messageId: string };

export const DEFAULT_SYSTEM_PROMPT =
  "You are Loom, a helpful local AI assistant. Answer concisely and accurately.";

export function emptyState(): ConversationsState {
  return { conversations: [], activeId: null };
}

function now(): number {
  return Date.now();
}

export function newConversation(model: string | null, systemPrompt?: string): Conversation {
  const t = now();
  return {
    id: uid("c_"),
    title: "New chat",
    systemPrompt: systemPrompt ?? DEFAULT_SYSTEM_PROMPT,
    model,
    messages: [],
    createdAt: t,
    updatedAt: t,
  };
}

export function newMessage(role: Role, content: string, streaming = false): Message {
  return { id: uid("m_"), role, content, createdAt: now(), streaming };
}

function mapConv(
  state: ConversationsState,
  id: string,
  fn: (c: Conversation) => Conversation
): ConversationsState {
  let changed = false;
  const conversations = state.conversations.map((c) => {
    if (c.id !== id) return c;
    const next = fn(c);
    if (next !== c) changed = true;
    return next;
  });
  return changed ? { ...state, conversations } : state;
}

function touch(c: Conversation): Conversation {
  return { ...c, updatedAt: now() };
}

export function reducer(state: ConversationsState, action: ConversationsAction): ConversationsState {
  switch (action.type) {
    case "hydrate": {
      return {
        conversations: action.conversations,
        activeId:
          action.activeId && action.conversations.some((c) => c.id === action.activeId)
            ? action.activeId
            : action.conversations[0]?.id ?? null,
      };
    }
    case "create": {
      const conv = newConversation(action.model, action.systemPrompt);
      return {
        conversations: [conv, ...state.conversations],
        activeId: conv.id,
      };
    }
    case "activate": {
      if (!state.conversations.some((c) => c.id === action.id)) return state;
      if (state.activeId === action.id) return state;
      return { ...state, activeId: action.id };
    }
    case "rename": {
      return mapConv(state, action.id, (c) => ({ ...touch(c), title: action.title }));
    }
    case "delete": {
      const remaining = state.conversations.filter((c) => c.id !== action.id);
      const active =
        state.activeId === action.id ? (remaining[0]?.id ?? null) : state.activeId;
      return { conversations: remaining, activeId: active };
    }
    case "set-system-prompt": {
      return mapConv(state, action.id, (c) => ({ ...touch(c), systemPrompt: action.prompt }));
    }
    case "set-model": {
      return mapConv(state, action.id, (c) => ({ ...touch(c), model: action.model }));
    }
    case "append-message": {
      return mapConv(state, action.id, (c) => {
        const messages = [...c.messages, action.message];
        const title =
          c.title === "New chat" && action.message.role === "user"
            ? deriveTitle(action.message.content)
            : c.title;
        return { ...touch(c), title, messages };
      });
    }
    case "append-token": {
      return mapConv(state, action.id, (c) => {
        let hit = false;
        const messages = c.messages.map((m) => {
          if (m.id !== action.messageId) return m;
          hit = true;
          return { ...m, content: m.content + action.token };
        });
        if (!hit) return c;
        return { ...touch(c), messages };
      });
    }
    case "finish-message": {
      return mapConv(state, action.id, (c) => {
        let hit = false;
        const messages = c.messages.map((m) => {
          if (m.id !== action.messageId) return m;
          hit = true;
          return { ...m, streaming: false, error: action.error };
        });
        if (!hit) return c;
        return { ...touch(c), messages };
      });
    }
    case "remove-message": {
      return mapConv(state, action.id, (c) => {
        const messages = c.messages.filter((m) => m.id !== action.messageId);
        if (messages.length === c.messages.length) return c;
        return { ...touch(c), messages };
      });
    }
    case "update-message": {
      return mapConv(state, action.id, (c) => {
        let hit = false;
        const messages = c.messages.map((m) => {
          if (m.id !== action.messageId) return m;
          hit = true;
          return { ...m, content: action.content };
        });
        if (!hit) return c;
        return { ...touch(c), messages };
      });
    }
    case "truncate-after": {
      return mapConv(state, action.id, (c) => {
        const idx = c.messages.findIndex((m) => m.id === action.messageId);
        if (idx === -1) return c;
        const messages = c.messages.slice(0, idx + 1);
        if (messages.length === c.messages.length) return c;
        return { ...touch(c), messages };
      });
    }
    default:
      return state;
  }
}

export function deriveTitle(text: string): string {
  const trimmed = text.trim().replace(/\s+/g, " ");
  if (!trimmed) return "New chat";
  return trimmed.length <= 48 ? trimmed : trimmed.slice(0, 45) + "…";
}

export function activeConversation(state: ConversationsState): Conversation | null {
  if (!state.activeId) return null;
  return state.conversations.find((c) => c.id === state.activeId) ?? null;
}
