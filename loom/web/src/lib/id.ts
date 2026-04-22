// Prefer crypto.randomUUID when available; fall back to a short random id.
export function uid(prefix = ""): string {
  const c = typeof crypto !== "undefined" ? crypto : undefined;
  if (c && typeof c.randomUUID === "function") {
    return prefix + c.randomUUID();
  }
  const rand = Math.random().toString(36).slice(2, 10);
  const time = Date.now().toString(36);
  return `${prefix}${time}-${rand}`;
}
