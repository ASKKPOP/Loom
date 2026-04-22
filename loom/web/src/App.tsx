import { useCallback, useEffect, useMemo, useReducer, useRef, useState } from "react";
import type { ComposerHandle } from "./components/Composer";
import { Composer } from "./components/Composer";
import { Header } from "./components/Header";
import { MessageList } from "./components/MessageList";
import { SettingsModal } from "./components/SettingsModal";
import { Sidebar } from "./components/Sidebar";
import { Toasts } from "./components/Toasts";
import { listModels, streamChatCompletion } from "./lib/api";
import { createStorage } from "./lib/storage";
import { useGlobalShortcuts } from "./lib/shortcuts";
import { useConnection } from "./state/connection";
import {
  activeConversation,
  newMessage,
  reducer,
  type ConversationsState,
} from "./state/conversations";
import { DEFAULT_SETTINGS } from "./state/settings";
import { useTheme } from "./state/theme";
import { useToasts } from "./state/toasts";
import type { ModelInfo, Settings } from "./types";

const storage = createStorage();

function loadInitial(): ConversationsState {
  const convs = storage.loadConversations();
  const active = storage.loadActive();
  return {
    conversations: convs,
    activeId: active && convs.some((c) => c.id === active) ? active : (convs[0]?.id ?? null),
  };
}

export default function App() {
  const [state, dispatch] = useReducer(reducer, null, loadInitial);
  const [settings, setSettings] = useState<Settings>(() =>
    storage.loadSettings() ?? DEFAULT_SETTINGS
  );
  const [models, setModels] = useState<ModelInfo[]>([]);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [streamingId, setStreamingId] = useState<string | null>(null);
  const abortRef = useRef<AbortController | null>(null);
  const composerRef = useRef<ComposerHandle>(null);

  const connection = useConnection(10000);
  const { theme, toggle: toggleTheme } = useTheme();
  const { toasts, push: pushToast, dismiss } = useToasts();

  // Persist state whenever it changes.
  useEffect(() => {
    storage.saveConversations(state.conversations);
    storage.saveActive(state.activeId);
  }, [state]);

  useEffect(() => {
    storage.saveSettings(settings);
  }, [settings]);

  // Fetch model list on connect. Retry when the connection comes back.
  useEffect(() => {
    if (connection !== "ok") return;
    let cancelled = false;
    listModels()
      .then((m) => { if (!cancelled) setModels(m); })
      .catch((e) => {
        if (!cancelled) {
          pushToast({ kind: "error", message: `Couldn't load models: ${e.message}` });
        }
      });
    return () => { cancelled = true; };
  }, [connection, pushToast]);

  const active = activeConversation(state);

  // On first run, auto-create a conversation so the UI has something to show.
  useEffect(() => {
    if (state.conversations.length === 0) {
      dispatch({ type: "create", model: null });
    }
  }, [state.conversations.length]);

  // Default a newly-created conversation's model to the first available model.
  useEffect(() => {
    if (active && !active.model && models.length > 0 && models[0]) {
      dispatch({ type: "set-model", id: active.id, model: models[0].id });
    }
  }, [active, models]);

  const runTurn = useCallback(
    async (convId: string) => {
      const conv = state.conversations.find((c) => c.id === convId);
      if (!conv) return;
      if (!conv.model) {
        pushToast({ kind: "error", message: "Select a model first." });
        return;
      }

      const assistant = newMessage("assistant", "", true);
      dispatch({ type: "append-message", id: convId, message: assistant });
      setStreamingId(assistant.id);

      const ac = new AbortController();
      abortRef.current = ac;

      const messagesForApi: { role: "system" | "user" | "assistant"; content: string }[] = [];
      if (conv.systemPrompt) messagesForApi.push({ role: "system", content: conv.systemPrompt });
      for (const m of conv.messages) {
        // Skip previous erroring assistant messages with empty bodies.
        if (m.role === "assistant" && m.error && !m.content) continue;
        messagesForApi.push({ role: m.role, content: m.content });
      }

      try {
        await streamChatCompletion({
          model: conv.model,
          messages: messagesForApi,
          temperature: settings.temperature,
          maxTokens: settings.maxTokens,
          topP: settings.topP,
          signal: ac.signal,
          onToken: (tok) =>
            dispatch({ type: "append-token", id: convId, messageId: assistant.id, token: tok }),
          onDone: () =>
            dispatch({ type: "finish-message", id: convId, messageId: assistant.id }),
        });
      } catch (err) {
        const aborted = ac.signal.aborted;
        const msg = err instanceof Error ? err.message : String(err);
        dispatch({
          type: "finish-message",
          id: convId,
          messageId: assistant.id,
          error: aborted ? "Stopped." : msg,
        });
        if (!aborted) {
          pushToast({
            kind: "error",
            message: `Chat error: ${msg}`,
            retry: () => runTurn(convId),
          });
        }
      } finally {
        if (abortRef.current === ac) abortRef.current = null;
        setStreamingId((cur) => (cur === assistant.id ? null : cur));
      }
    },
    [pushToast, settings, state.conversations]
  );

  const send = useCallback(
    (text: string) => {
      if (!active) return;
      const user = newMessage("user", text);
      dispatch({ type: "append-message", id: active.id, message: user });
      // Kick off the assistant turn on the next tick so the dispatch lands first.
      queueMicrotask(() => runTurn(active.id));
    },
    [active, runTurn]
  );

  const stop = useCallback(() => {
    abortRef.current?.abort();
  }, []);

  const regenerate = useCallback(
    (messageId: string) => {
      if (!active) return;
      dispatch({ type: "remove-message", id: active.id, messageId });
      queueMicrotask(() => runTurn(active.id));
    },
    [active, runTurn]
  );

  const editUserMessage = useCallback(
    (messageId: string, content: string) => {
      if (!active) return;
      dispatch({ type: "update-message", id: active.id, messageId, content });
      dispatch({ type: "truncate-after", id: active.id, messageId });
      queueMicrotask(() => runTurn(active.id));
    },
    [active, runTurn]
  );

  useGlobalShortcuts(
    useMemo(
      () => ({
        newChat: () => dispatch({ type: "create", model: models[0]?.id ?? null }),
        focusComposer: () => composerRef.current?.focus(),
        sendMessage: () => composerRef.current?.submit(),
        stop,
      }),
      [models, stop]
    )
  );

  const lastAssistantId = useMemo(() => {
    if (!active) return null;
    for (let i = active.messages.length - 1; i >= 0; i--) {
      const m = active.messages[i];
      if (m && m.role === "assistant") return m.id;
    }
    return null;
  }, [active]);

  return (
    <div className="flex h-full">
      <Sidebar
        conversations={state.conversations}
        activeId={state.activeId}
        onNew={() => dispatch({ type: "create", model: models[0]?.id ?? null })}
        onActivate={(id) => dispatch({ type: "activate", id })}
        onRename={(id, title) => dispatch({ type: "rename", id, title })}
        onDelete={(id) => dispatch({ type: "delete", id })}
      />
      <div className="flex-1 flex flex-col min-w-0">
        <Header
          title={active?.title ?? "No conversation"}
          models={models}
          model={active?.model ?? null}
          canPickModel={Boolean(active)}
          onModelChange={(id) => active && dispatch({ type: "set-model", id: active.id, model: id })}
          status={connection}
          theme={theme}
          onToggleTheme={toggleTheme}
          onOpenSettings={() => setSettingsOpen(true)}
        />
        {active ? (
          <MessageList
            messages={active.messages}
            onEdit={editUserMessage}
            onRegenerate={regenerate}
            lastAssistantId={lastAssistantId}
          />
        ) : (
          <div className="flex-1" />
        )}
        <Composer
          ref={composerRef}
          disabled={!active}
          streaming={streamingId !== null}
          onSubmit={send}
          onStop={stop}
        />
      </div>

      {active && (
        <SettingsModal
          open={settingsOpen}
          settings={settings}
          systemPrompt={active.systemPrompt}
          onClose={() => setSettingsOpen(false)}
          onSave={(s, prompt) => {
            setSettings(s);
            dispatch({ type: "set-system-prompt", id: active.id, prompt });
          }}
        />
      )}

      <Toasts toasts={toasts} onDismiss={dismiss} />
    </div>
  );
}
