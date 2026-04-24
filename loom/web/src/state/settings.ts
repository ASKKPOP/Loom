import type { Settings } from "../types";

export const DEFAULT_SETTINGS: Settings = {
  temperature: 0.7,
  maxTokens: 1024,
  topP: 1.0,
  theme: "system",
  serverUrl: "",
};

export function mergeSettings(partial: Partial<Settings>, base = DEFAULT_SETTINGS): Settings {
  return { ...base, ...partial };
}
