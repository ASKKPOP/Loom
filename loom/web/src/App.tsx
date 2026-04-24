import { lazy, Suspense, useCallback, useEffect, useMemo, useReducer, useRef, useState } from "react";
import { Navigate, Route, Routes } from "react-router-dom";
import type { ComposerHandle } from "./components/Composer";
import { Composer } from "./components/Composer";
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

// Lazy-loaded admin pages
const AdminModels = lazy(() => import("./admin/pages/Models").then(m => ({ default: m.ModelsPage })));
const AdminAIConfig = lazy(() => import("./admin/pages/AIConfig").then(m => ({ default: m.AIConfigPage })));
const AdminUsers = lazy(() => import("./admin/pages/Users").then(m => ({ default: m.UsersPage })));
const AdminSecurity = lazy(() => import("./admin/pages/Security").then(m => ({ default: m.SecurityPage })));

// Lazy-loaded customize pages
const CustomizeSkills = lazy(() => import("./pages/CustomizeSkills").then(m => ({ default: m.CustomizeSkillsPage })));
const CustomizeConnectors = lazy(() => import("./pages/CustomizeConnectors").then(m => ({ default: m.CustomizeConnectorsPage })));

const storage = createStorage();

function loadInitial(): ConversationsState {
  const convs = storage.loadConversations();
  const active = storage.loadActive();
  return {
    conversations: convs,
    activeId: active && convs.some((c) => c.id === active) ? active : (convs[0]?.id ?? null),
  };
}

function AdminFallback() {
  return (
    <div className="flex-1 flex items-center justify-center text-sm text-[var(--loom-fg-soft)]">
      Loading…
    </div>
  );
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

  const connection = useConnection(10000, settings.serverUrl);
  const { theme, toggle: toggleTheme } = useTheme();
  const { toasts, push: pushToast, dismiss } = useToasts();

  useEffect(() => {
    storage.saveConversations(state.conversations);
    storage.saveActive(state.activeId);
  }, [state]);

  useEffect(() => {
    storage.saveSettings(settings);
  }, [settings]);

  useEffect(() => {
    if (connection !== "ok") return;
    let cancelled = false;
    listModels(settings.serverUrl)
      .then((m) => { if (!cancelled) setModels(m); })
      .catch((e) => {
        if (!cancelled) pushToast({ kind: "error", message: `Couldn't load models: ${e.message}` });
      });
    return () => { cancelled = true; };
  }, [connection, pushToast, settings.serverUrl]);

  const active = activeConversation(state);

  useEffect(() => {
    if (state.conversations.length === 0) {
      dispatch({ type: "create", model: null });
    }
  }, [state.conversations.length]);

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
          baseUrl: settings.serverUrl,
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
      queueMicrotask(() => runTurn(active.id));
    },
    [active, runTurn]
  );

  const stop = useCallback(() => { abortRef.current?.abort(); }, []);

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

  const sidebar = (
    <Sidebar
      conversations={state.conversations}
      activeId={state.activeId}
      onNew={() => dispatch({ type: "create", model: models[0]?.id ?? null })}
      onActivate={(id) => dispatch({ type: "activate", id })}
      onRename={(id, title) => dispatch({ type: "rename", id, title })}
      onDelete={(id) => dispatch({ type: "delete", id })}
      models={models}
      model={active?.model ?? null}
      canPickModel={Boolean(active)}
      onModelChange={(id) => active && dispatch({ type: "set-model", id: active.id, model: id })}
      status={connection}
      theme={theme}
      onToggleTheme={toggleTheme}
      onOpenSettings={() => setSettingsOpen(true)}
    />
  );

  return (
    <div className="flex h-full bg-[var(--loom-bg)]">
      {sidebar}

      <Routes>
        {/* Chat view */}
        <Route
          path="/"
          element={
            <div className="flex-1 flex flex-col min-w-0">
              {active ? (
                <MessageList
                  messages={active.messages}
                  onEdit={editUserMessage}
                  onRegenerate={regenerate}
                  lastAssistantId={lastAssistantId}
                />
              ) : (
                <div className="flex-1 flex items-center justify-center text-sm text-[var(--loom-fg-soft)]">
                  Create a conversation to get started.
                </div>
              )}
              <Composer
                ref={composerRef}
                disabled={!active}
                streaming={streamingId !== null}
                onSubmit={send}
                onStop={stop}
              />
            </div>
          }
        />

        {/* Customize views */}
        <Route path="/customize" element={<Navigate to="/customize/skills" replace />} />
        <Route
          path="/customize/*"
          element={
            <div className="flex-1 flex min-w-0 overflow-hidden">
              <Suspense fallback={<AdminFallback />}>
                <Routes>
                  <Route path="skills" element={<CustomizeSkills />} />
                  <Route path="connectors" element={<CustomizeConnectors />} />
                  <Route path="*" element={<Navigate to="/customize/skills" replace />} />
                </Routes>
              </Suspense>
            </div>
          }
        />

        {/* Admin views */}
        <Route path="/admin" element={<Navigate to="/admin/models" replace />} />
        <Route
          path="/admin/*"
          element={
            <div className="flex-1 flex flex-col min-w-0 overflow-y-auto">
              <Suspense fallback={<AdminFallback />}>
                <Routes>
                  <Route path="models" element={<AdminModels />} />
                  <Route path="ai-config" element={<AdminAIConfig />} />
                  <Route path="users" element={<AdminUsers />} />
                  <Route path="security" element={<AdminSecurity />} />
                  <Route path="*" element={<Navigate to="/admin/models" replace />} />
                </Routes>
              </Suspense>
            </div>
          }
        />
      </Routes>

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
