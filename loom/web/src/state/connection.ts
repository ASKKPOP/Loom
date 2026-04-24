import { useEffect, useState } from "react";
import { checkHealth } from "../lib/api";

export type ConnectionStatus = "unknown" | "ok" | "down";

export function useConnection(pollMs = 10000, baseUrl = ""): ConnectionStatus {
  const [status, setStatus] = useState<ConnectionStatus>("unknown");
  useEffect(() => {
    let stopped = false;
    const tick = async () => {
      const ok = await checkHealth(baseUrl);
      if (!stopped) setStatus(ok ? "ok" : "down");
    };
    tick();
    const t = setInterval(tick, pollMs);
    return () => {
      stopped = true;
      clearInterval(t);
    };
  }, [pollMs, baseUrl]);
  return status;
}
