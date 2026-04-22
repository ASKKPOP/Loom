import { useCallback, useRef, useState } from "react";
import type { Toast } from "../types";
import { uid } from "../lib/id";

export function useToasts() {
  const [toasts, setToasts] = useState<Toast[]>([]);
  const timers = useRef<Map<string, ReturnType<typeof setTimeout>>>(new Map());

  const dismiss = useCallback((id: string) => {
    const t = timers.current.get(id);
    if (t) {
      clearTimeout(t);
      timers.current.delete(id);
    }
    setToasts((prev) => prev.filter((x) => x.id !== id));
  }, []);

  const push = useCallback(
    (toast: Omit<Toast, "id">, ttlMs = 6000) => {
      const id = uid("t_");
      setToasts((prev) => [...prev, { ...toast, id }]);
      if (ttlMs > 0) {
        const handle = setTimeout(() => dismiss(id), ttlMs);
        timers.current.set(id, handle);
      }
      return id;
    },
    [dismiss]
  );

  return { toasts, push, dismiss };
}
