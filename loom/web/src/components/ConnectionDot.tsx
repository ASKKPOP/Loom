import type { ConnectionStatus } from "../state/connection";

export function ConnectionDot({ status }: { status: ConnectionStatus }) {
  const label =
    status === "ok" ? "Connected to gateway" : status === "down" ? "Gateway unreachable" : "Checking…";
  const color =
    status === "ok" ? "bg-green-500" : status === "down" ? "bg-red-500" : "bg-yellow-400";
  return (
    <span className="inline-flex items-center gap-1.5 text-xs text-[var(--loom-fg-soft)]" title={label}>
      <span className={`h-2 w-2 rounded-full ${color}`} />
      <span>{label}</span>
    </span>
  );
}
