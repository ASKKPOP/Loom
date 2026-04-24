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
    if (textareaRef.current) textareaRef.current.style.height = "auto";
  };

  useImperativeHandle(ref, () => ({
    focus() { textareaRef.current?.focus(); },
    submit() { send(); },
  }));

  const onKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if ((e.metaKey || e.ctrlKey) && e.key === "Enter") return;
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      send();
    }
  };

  const autoGrow = (el: HTMLTextAreaElement) => {
    el.style.height = "auto";
    el.style.height = Math.min(el.scrollHeight, 240) + "px";
  };

  const canSend = !disabled && value.trim().length > 0;

  return (
    <div className="px-4 pb-4 pt-2 bg-[var(--loom-bg)]">
      <div className="mx-auto max-w-3xl relative">
        <textarea
          ref={textareaRef}
          value={value}
          onChange={(e) => { setValue(e.target.value); autoGrow(e.currentTarget); }}
          onKeyDown={onKeyDown}
          disabled={disabled}
          rows={1}
          placeholder={disabled ? "Select or create a conversation…" : "Message Loom…"}
          className="w-full resize-none rounded-2xl border border-[var(--loom-border)] bg-[var(--loom-bg-soft)] pl-4 pr-12 py-3 text-sm outline-none focus:ring-1 focus:ring-[var(--loom-accent)] disabled:opacity-50 leading-relaxed"
        />
        <div className="absolute right-2 bottom-2">
          {streaming ? (
            <button
              onClick={onStop}
              className="w-8 h-8 rounded-xl bg-[var(--loom-danger)] text-white flex items-center justify-center hover:opacity-90 transition-opacity"
              title="Stop (Esc)"
            >
              <svg width="12" height="12" viewBox="0 0 24 24" fill="currentColor">
                <rect x="4" y="4" width="16" height="16" rx="2"/>
              </svg>
            </button>
          ) : (
            <button
              onClick={send}
              disabled={!canSend}
              className="w-8 h-8 rounded-xl bg-[var(--loom-accent)] text-white flex items-center justify-center disabled:opacity-30 hover:opacity-90 transition-opacity"
              title="Send (Enter)"
            >
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                <path d="M22 2L11 13M22 2l-7 20-4-9-9-4 20-7z"/>
              </svg>
            </button>
          )}
        </div>
      </div>
      <p className="mt-1.5 text-center text-[10px] text-[var(--loom-fg-soft)] opacity-50">
        Enter to send · Shift+Enter for new line · Esc to stop
      </p>
    </div>
  );
});
