import { useState, useCallback } from "react";
import { ChatInterface, WELCOME_MESSAGE } from "./components/ChatInterface";
import { HistoryModal } from "./components/HistoryModal";
import { MetricsModal } from "./components/MetricsModal";
import { Sidebar } from "./components/Sidebar";
import sessionService, { type SessionMessage } from "./services/sessionService";

export interface Message {
  id: string;
  type: "user" | "assistant";
  content: string;
  isStreaming?: boolean;
  reasoning?: string;
  toolCalls?: Array<{ tool: string; parameters: Record<string, any> }>;
  toolResults?: Array<{ tool: string; result: any }>;
}

/** Generate a unique ID with safe fallback when crypto is unavailable. */
function generateId(): string {
  if (typeof crypto !== "undefined" && typeof crypto.randomUUID === "function") {
    return crypto.randomUUID();
  }
  return `${Date.now()}-${Math.random().toString(36).substring(2, 11)}`;
}

/** Map backend session messages to the frontend Message shape. */
function mapSessionMessages(raw: SessionMessage[]): Message[] {
  return raw.map((m) => ({
    id: m.id,
    type: m.type,
    content: m.content,
    toolCalls: m.toolCalls
      ? m.toolCalls.map((tc) => ({
          tool: tc.name ?? "unknown",
          parameters: tc.args ?? {},
        }))
      : undefined,
    toolResults: m.toolResults
      ? m.toolResults.map((tr) => ({
          tool: tr.tool_name ?? "unknown",
          result: tr.result ?? {},
        }))
      : undefined,
  }));
}

function App() {
  const [messages, setMessages] = useState<Message[]>([WELCOME_MESSAGE]);
  const [isStreaming, setIsStreaming] = useState(false);
  const [showHistory, setShowHistory] = useState(false);

  const [currentSessionId, setCurrentSessionId] = useState<string | null>(null);
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [refreshTrigger, setRefreshTrigger] = useState(0);
  const [showMetrics, setShowMetrics] = useState(false);

  const handleNewChat = useCallback(() => {
    const id = generateId();
    setCurrentSessionId(id);
    setMessages([WELCOME_MESSAGE]);
    setIsStreaming(false);
    setSidebarOpen(true);
    setRefreshTrigger((t) => t + 1);
  }, []);

  const handleSessionStart = useCallback((id: string) => {
    setCurrentSessionId(id);
    setRefreshTrigger((t) => t + 1);
  }, []);

  const handleSelectSession = useCallback(async (id: string) => {
    if (id === currentSessionId) return;
    try {
      const data = await sessionService.getSession(id);
      setCurrentSessionId(id);
      setMessages(mapSessionMessages(data.messages));
      setIsStreaming(false);
    } catch (err) {
      console.error("Error cargando la sesión:", err);
    }
  }, [currentSessionId]);

  const handleToggleSidebar = useCallback(() => {
    setSidebarOpen((open) => !open);
  }, []);

  const handleSessionEnd = useCallback(() => {
    setRefreshTrigger((t) => t + 1);
  }, []);

  const handleSessionTitleUpdate = useCallback((id: string, title: string) => {
    setRefreshTrigger((t) => t + 1);
  }, []);

  return (
    <div className="h-screen bg-app-bg flex">
      <Sidebar
        open={sidebarOpen}
        onClose={() => setSidebarOpen(false)}
        activeSessionId={currentSessionId}
        onSelectSession={handleSelectSession}
        onNewChat={handleNewChat}
        refreshTrigger={refreshTrigger}
      />

      <div className="flex-1 min-w-0">
        <ChatInterface
          messages={messages}
          setMessages={setMessages}
          isStreaming={isStreaming}
          setIsStreaming={setIsStreaming}
          onShowHistory={() => setShowHistory(true)}
          sessionId={currentSessionId}
          onSessionStart={handleSessionStart}
          onNewChat={handleNewChat}
          onToggleSidebar={handleToggleSidebar}
          onSessionEnd={handleSessionEnd}
          onShowMetrics={() => setShowMetrics(true)}
          onSessionTitleUpdate={handleSessionTitleUpdate}
        />
      </div>

      <HistoryModal
        open={showHistory}
        onClose={() => setShowHistory(false)}
      />

      <MetricsModal
        open={showMetrics}
        onClose={() => setShowMetrics(false)}
      />
    </div>
  );
}

export default App;
