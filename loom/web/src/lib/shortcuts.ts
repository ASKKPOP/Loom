import { useEffect } from "react";

export interface Shortcuts {
  newChat: () => void;
  focusComposer: () => void;
  sendMessage: () => void;
  stop: () => void;
}

export function useGlobalShortcuts(s: Shortcuts): void {
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const mod = e.metaKey || e.ctrlKey;
      if (mod && e.key === "Enter") {
        e.preventDefault();
        s.sendMessage();
        return;
      }
      if (mod && e.key.toLowerCase() === "n") {
        e.preventDefault();
        s.newChat();
        return;
      }
      if (mod && e.key.toLowerCase() === "k") {
        e.preventDefault();
        s.focusComposer();
        return;
      }
      if (e.key === "Escape") {
        s.stop();
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [s]);
}
