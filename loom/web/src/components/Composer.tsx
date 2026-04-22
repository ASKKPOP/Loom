import { forwardRef, useImperativeHandle, useRef, useState, type KeyboardEvent } from "react";

export interface ComposerHandle {
  focus: () => void;
  submit: () => void;
}

interface Props {
  onSubmit: (text: string) => void;
  onStop: () => void;
  streaming: boolean;
  disabled?: boolean;
}

export const Composer = forwardRef<ComposerHandle, Props>(function Composer(
  { onSubmit, onStop, streaming, disabled },
  ref
) {
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const [value, setValue] = useState("");

  const send = () => {
    const trimmed = value.trim();
    if (!trimmed || disabled || streaming) return;
    onSubmit(trimmed);
    setValue("");
    // Collapse back to single row after send.
    if (textareaRef.current) textareaRef.current.style.height = "auto";
  };

  useImperativeHandle(ref, () => ({
    focus() { textareaRef.current?.focus(); },
    submit() { send(); },
  }));

  const onKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    // ⌘/Ctrl+Enter is handled by the global shortcut; let it bubble.
    if ((e.metaKey || e.ctrlKey) && e.key === "Enter") return;
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      send();
    }
  };

  const autoGrow = (el: HTMLTextAreaElement) => {
    el.style.height = "auto";
    el.style.height = Math.min(el.scrollHeight, 260) + "px";
  };

  return (
    <div className="border-t border-[var(--loom-border)] bg-[var(--loom-bg)] p-3">
      <div className="mx-auto max-w-3xl flex items-end gap-2">
        <textarea
          ref={textareaRef}
          value={value}
          onChange={(e) => { setValue(e.target.value); autoGrow(e.currentTarget); }}
          onKeyDown={onKeyDown}
          disabled={disabled}
          rows={1}
          placeholder={disabled ? "Select or create a conversation…" : "Message Loom…  (⌘Enter to send, Esc to stop)"}
          className="flex-1 resize-none rounded-lg border border-[var(--loom-border)] bg-[var(--loom-bg-soft)] px-3 py-2 text-sm outline-none focus:ring-1 focus:ring-[var(--loom-accent)] disabled:opacity-50"
        />
        {streaming ? (
          <button
            onClick={onStop}
            className="rounded-lg bg-[var(--loom-danger)] text-white px-3 py-2 text-sm"
          >
            Stop
          </button>
        ) : (
          <button
            onClick={send}
            disabled={disabled || !value.trim()}
            className="rounded-lg bg-[var(--loom-accent)] text-white px-3 py-2 text-sm disabled:opacity-40"
          >
            Send
          </button>
        )}
      </div>
    </div>
  );
});
