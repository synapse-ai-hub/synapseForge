import { useState, useCallback, useEffect, useRef } from "react";
import { ChatInterface, WELCOME_MESSAGE } from "./components/ChatInterface";
import { HistoryModal } from "./components/HistoryModal";
import { MetricsModal } from "./components/MetricsModal";
import { Sidebar } from "./components/Sidebar";
import sessionService, {
  type SessionMessage,
  type ContentBlock,
} from "./services/sessionService";
import configService from "./services/configService";

export type { ContentBlock };

export interface SubagentEvent {
  child_session_id: string;
  agent_name: string;
  tool_calls?: Array<{ name: string; args: Record<string, any> }>;
  tool_results?: Array<{ name: string; result: any }>;
  content?: string;
  reasoning?: string;
}

export interface Message {
  id: string;
  type: "user" | "assistant";
  content: string;
  isStreaming?: boolean;
  reasoning?: string;
  blocks?: ContentBlock[];
  /** Attached files for user messages (shown as chips) */
  files?: Array<{ name: string; size?: number }>;
  /** Legacy – kept for backward compat during streaming */
  toolCalls?: Array<{ tool: string; parameters: Record<string, any> }>;
  toolResults?: Array<{ tool: string; result: any }>;
  subagentEvents?: Record<string, SubagentEvent>;
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
    content: m.type === "user" ? m.content : "",
    files: m.files,
    blocks: m.blocks ?? (
      // Fallback for old sessions without blocks: build from toolCalls + toolResults
      m.type === "assistant" && (m.toolCalls || m.content)
        ? buildLegacyBlocks(m.content, m.toolCalls ?? [], m.toolResults ?? [])
        : undefined
    ),
    // Keep legacy fields for backward compat during streaming
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

/** Build blocks from the legacy flat toolCalls+toolResults format (old sessions). */
function buildLegacyBlocks(
  content: string,
  toolCalls: Array<{ name: string; args: Record<string, any> }>,
  toolResults: Array<{ tool_name?: string; result: any }>,
): ContentBlock[] {
  const blocks: ContentBlock[] = [];
  if (content) {
    blocks.push({ type: "text", content });
  }
  toolCalls.forEach((tc, i) => {
    const result =
      i < toolResults.length ? toolResults[i].result : undefined;
    blocks.push({
      type: "tool",
      name: tc.name ?? "unknown",
      args: tc.args ?? {},
      result,
    });
  });
  return blocks;
}

function App() {
  const [messages, setMessages] = useState<Message[]>([WELCOME_MESSAGE]);
  const [isStreaming, setIsStreaming] = useState(false);
  const [showHistory, setShowHistory] = useState(false);

  const [currentSessionId, setCurrentSessionId] = useState<string | null>(null);
  const [refreshTrigger, setRefreshTrigger] = useState(0);
  const [showMetrics, setShowMetrics] = useState(false);
  const [verboseMode, setVerboseMode] = useState<boolean>(
    () => localStorage.getItem("verboseMode") === "true"
  );

  const initialLoadRef = useRef(true);

  // Load persisted verbose mode from backend on mount
  useEffect(() => {
    configService.getVerbose().then((vm) => {
      if (!initialLoadRef.current) return; // stale: user already toggled
      initialLoadRef.current = false;
      setVerboseMode(vm);
      localStorage.setItem("verboseMode", String(vm));
    }).catch(() => {
      // Fallback to localStorage value if backend not reachable
      initialLoadRef.current = false;
    });
  }, []);

  // Heartbeat: ping backend every 10s so watchdog knows frontend is alive
  useEffect(() => {
    const API_BASE_URL = import.meta.env.VITE_URL_BASE || "http://localhost:8000";
    const interval = setInterval(() => {
      fetch(`${API_BASE_URL}/api/heartbeat`, { method: "POST", keepalive: true }).catch(() => {});
    }, 10000);
    // Initial ping
    fetch(`${API_BASE_URL}/api/heartbeat`, { method: "POST", keepalive: true }).catch(() => {});
    return () => clearInterval(interval);
  }, []);

  const handleVerboseModeChange = useCallback((val: boolean) => {
    initialLoadRef.current = false;
    setVerboseMode(val);
    localStorage.setItem("verboseMode", String(val));
    configService.setVerbose(val).catch((err) => {
      console.error("Error persistiendo verbose mode:", err);
    });
  }, []);

  const handleNewChat = useCallback(() => {
    const id = generateId();
    setCurrentSessionId(id);
    setMessages([WELCOME_MESSAGE]);
    setIsStreaming(false);
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

  const handleSessionEnd = useCallback(() => {
    setRefreshTrigger((t) => t + 1);
  }, []);

  const handleSessionTitleUpdate = useCallback((id: string, title: string) => {
    setRefreshTrigger((t) => t + 1);
  }, []);

  return (
    <div className="h-screen bg-app-bg flex">
      <Sidebar
        activeSessionId={currentSessionId}
        onSelectSession={handleSelectSession}
        onNewChat={handleNewChat}
        refreshTrigger={refreshTrigger}
        verboseMode={verboseMode}
        onVerboseModeChange={handleVerboseModeChange}
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
          onSessionEnd={handleSessionEnd}
          onShowMetrics={() => setShowMetrics(true)}
          onSessionTitleUpdate={handleSessionTitleUpdate}
          verboseMode={verboseMode}
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
