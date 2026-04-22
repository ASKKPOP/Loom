import { useEffect, useState, useCallback } from "react";
import { createStorage } from "../lib/storage";

const storage = createStorage();

export type ResolvedTheme = "light" | "dark";

function systemPrefersDark(): boolean {
  if (typeof window === "undefined" || !window.matchMedia) return false;
  return window.matchMedia("(prefers-color-scheme: dark)").matches;
}

export function useTheme() {
  const [stored, setStored] = useState<"light" | "dark" | null>(() => storage.loadTheme());
  const [resolved, setResolved] = useState<ResolvedTheme>(() =>
    stored ?? (systemPrefersDark() ? "dark" : "light")
  );

  // React to OS theme changes when the user hasn't set an explicit override.
  useEffect(() => {
    if (stored) return;
    if (typeof window === "undefined" || !window.matchMedia) return;
    const mq = window.matchMedia("(prefers-color-scheme: dark)");
    const handler = (e: MediaQueryListEvent) => setResolved(e.matches ? "dark" : "light");
    mq.addEventListener("change", handler);
    return () => mq.removeEventListener("change", handler);
  }, [stored]);

  // Apply to <html> class so Tailwind dark: variant flips.
  useEffect(() => {
    const root = document.documentElement;
    if (resolved === "dark") root.classList.add("dark");
    else root.classList.remove("dark");
  }, [resolved]);

  const toggle = useCallback(() => {
    const next: ResolvedTheme = resolved === "dark" ? "light" : "dark";
    setStored(next);
    storage.saveTheme(next);
    setResolved(next);
  }, [resolved]);

  const useSystem = useCallback(() => {
    setStored(null);
    storage.saveTheme(null);
    setResolved(systemPrefersDark() ? "dark" : "light");
  }, []);

  return { theme: resolved, override: stored, toggle, useSystem };
}
