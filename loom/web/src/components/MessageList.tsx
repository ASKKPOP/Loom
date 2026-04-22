import { useEffect, useRef } from "react";
import type { Message as Msg } from "../types";
import { Message } from "./Message";

interface Props {
  messages: Msg[];
  onEdit: (id: string, content: string) => void;
  onRegenerate: (id: string) => void;
  lastAssistantId: string | null;
}

export function MessageList({ messages, onEdit, onRegenerate, lastAssistantId }: Props) {
  const bottomRef = useRef<HTMLDivElement>(null);
  const lastContentLen = useRef(0);

  useEffect(() => {
    const total = messages.reduce((n, m) => n + m.content.length, 0);
    if (total !== lastContentLen.current) {
      lastContentLen.current = total;
      bottomRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
    }
  }, [messages]);

  return (
    <div className="flex-1 overflow-y-auto">
      {messages.length === 0 ? (
        <div className="h-full flex items-center justify-center text-sm text-[var(--loom-fg-soft)] px-6">
          <div className="text-center">
            <p className="text-base font-medium mb-1">Start a new chat</p>
            <p>Type a message below. Your data stays on this Mac.</p>
          </div>
        </div>
      ) : (
        <div>
          {messages.map((m) => (
            <Message
              key={m.id}
              message={m}
              onEdit={m.role === "user" ? onEdit : undefined}
              onRegenerate={m.role === "assistant" ? onRegenerate : undefined}
              canRegenerate={m.id === lastAssistantId && !m.streaming}
            />
          ))}
        </div>
      )}
      <div ref={bottomRef} />
    </div>
  );
}
