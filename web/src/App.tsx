import { useCallback, useEffect, useState } from "react";
import {
  createConversation,
  getConversation,
  getMessages,
  listConversations,
  postMessage,
  type ChatMessage,
  type Conversation,
  type StatusPayload,
} from "./api";
import { ChatPane } from "./components/ChatPane";
import { NewChatModal } from "./components/NewChatModal";
import { StatusBar } from "./components/StatusBar";
import { SystemConfigPanel } from "./components/SystemConfigPanel";
import { Workbench } from "./components/Workbench";
import { CastPage } from "./pages/CastPage";
import { JobsPage } from "./pages/JobsPage";
import { LiteraryPage } from "./pages/LiteraryPage";
import { parseHash, type Route } from "./routing";
import "./styles.css";

export default function App() {
  const [route, setRoute] = useState<Route>(() => parseHash());
  const [convs, setConvs] = useState<Conversation[]>([]);
  const [activeId, setActiveId] = useState<string | null>(null);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [status, setStatus] = useState<StatusPayload | null>(null);
  const [sending, setSending] = useState(false);
  const [modalOpen, setModalOpen] = useState(false);
  const [loadError, setLoadError] = useState("");

  useEffect(() => {
    const onHash = () => setRoute(parseHash());
    window.addEventListener("hashchange", onHash);
    return () => window.removeEventListener("hashchange", onHash);
  }, []);

  const refreshList = useCallback(async () => {
    try {
      const rows = await listConversations();
      setConvs(rows);
      setLoadError("");
      return rows;
    } catch (err) {
      setLoadError(
        err instanceof Error
          ? `无法连接 API：${err.message}`
          : "无法连接 Hermes API",
      );
      return [];
    }
  }, []);

  const selectConversation = useCallback(async (id: string) => {
    setActiveId(id);
    try {
      const [detail, msgs] = await Promise.all([
        getConversation(id),
        getMessages(id),
      ]);
      setStatus(detail.status);
      setMessages(msgs.filter((m) => m.role === "user" || m.role === "assistant"));
      setLoadError("");
    } catch (err) {
      setLoadError(err instanceof Error ? err.message : String(err));
    }
  }, []);

  useEffect(() => {
    void (async () => {
      const rows = await refreshList();
      if (rows.length && !activeId) {
        await selectConversation(rows[0].conversation_id);
      }
    })();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // When opening literary/cast deep link, sync active conversation
  useEffect(() => {
    if (route.name === "literary" || route.name === "cast" || route.name === "jobs") {
      if (route.conversationId !== activeId) {
        void selectConversation(route.conversationId);
      }
    }
  }, [route, activeId, selectConversation]);

  async function handleCreate(title: string, premise?: string) {
    const row = await createConversation(title, premise);
    await refreshList();
    await selectConversation(row.conversation_id);
  }

  async function handleSend(text: string) {
    if (!activeId) return;
    setSending(true);
    setMessages((prev) => [...prev, { role: "user", content: text }]);
    try {
      const res = await postMessage(activeId, text);
      setStatus(res.status);
      setMessages((prev) => [...prev, res.assistant_message]);
    } catch (err) {
      setMessages((prev) => [
        ...prev,
        {
          role: "assistant",
          content: `发送失败：${err instanceof Error ? err.message : String(err)}`,
        },
      ]);
    } finally {
      setSending(false);
    }
  }

  if (route.name === "literary") {
    return (
      <LiteraryPage
        conversationId={route.conversationId}
        episodeId={route.episodeId}
      />
    );
  }
  if (route.name === "cast") {
    return <CastPage conversationId={route.conversationId} />;
  }
  if (route.name === "jobs") {
    return <JobsPage conversationId={route.conversationId} />;
  }

  return (
    <div className="shell">
      <header className="tabs">
        <div className="brand">Hermes</div>
        <div className="tab-list">
          {convs.map((c) => (
            <button
              key={c.conversation_id}
              type="button"
              className={`tab ${c.conversation_id === activeId ? "active" : ""}`}
              onClick={() => void selectConversation(c.conversation_id)}
            >
              {c.title || c.series_id}
            </button>
          ))}
          <button
            type="button"
            className="tab new"
            onClick={() => setModalOpen(true)}
          >
            + 新建
          </button>
        </div>
      </header>

      <SystemConfigPanel conversationId={activeId} />

      <StatusBar status={status} />

      {loadError && <div className="banner-error">{loadError}</div>}

      <div className="main-row">
        <ChatPane
          messages={messages}
          sending={sending}
          onSend={handleSend}
          disabled={!activeId}
        />
        <Workbench
          conversationId={activeId}
          status={status}
          onStatus={setStatus}
          onAssistantNote={(text) =>
            setMessages((prev) => [...prev, { role: "assistant", content: text }])
          }
        />
      </div>

      <NewChatModal
        open={modalOpen}
        onClose={() => setModalOpen(false)}
        onCreate={handleCreate}
      />
    </div>
  );
}
