export type Role = "system" | "user" | "assistant";

export interface Message {
  id: string;
  role: Role;
  content: string;
  createdAt: number;
  // Populated while streaming an assistant reply. Cleared when the turn finishes.
  streaming?: boolean;
  // On error we keep the partial content and attach the error text.
  error?: string;
}

export interface Conversation {
  id: string;
  title: string;
  systemPrompt: string;
  model: string | null;
  messages: Message[];
  createdAt: number;
  updatedAt: number;
}

export interface Settings {
  temperature: number;
  maxTokens: number;
  topP: number;
  theme: "light" | "dark" | "system";
  /** Base URL for the gateway (empty string = same-origin proxy). */
  serverUrl: string;
}

export interface ModelInfo {
  id: string;
}

export interface ChatCompletionDelta {
  content?: string;
  role?: Role;
}

export interface ChatCompletionChunk {
  id?: string;
  choices: Array<{
    delta?: ChatCompletionDelta;
    finish_reason?: string | null;
    index?: number;
  }>;
}

export interface Toast {
  id: string;
  kind: "error" | "info";
  message: string;
  retry?: () => void;
}
