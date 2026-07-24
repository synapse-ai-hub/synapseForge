import { useState, useEffect, useCallback, useRef } from "react";
import { Plus, MessageSquare, Settings, Bot, Trash2 } from "lucide-react";
import { Button } from "./ui/button";
import { Input } from "./ui/input";
import sessionService, { type ChatSession } from "../services/sessionService";
import configService, { type McpServer, type McpServerHealth } from "../services/configService";
import contextFilesService, { type ContextFile } from "../services/contextFilesService";
import SessionsTab from "./sessionsTab";
import ConfigTab from "./configTab";
import AgentInfoTab from "./agentInfoTab";
import CreateTab from "./createTab";

type SidebarTab = "sessions" | "config" | "agent" | "create";

interface SidebarProps {
  activeSessionId: string | null;
  onSelectSession: (id: string) => void;
  onNewChat: () => void;
  refreshTrigger: number;
  verboseMode: boolean;
  onVerboseModeChange: (val: boolean) => void;
}

function formatTimestamp(value: string): string {
  try {
    const d = new Date(value);
    if (isNaN(d.getTime())) return "";
    return d.toLocaleString("es-AR", {
      day: "2-digit",
      month: "2-digit",
      hour: "2-digit",
      minute: "2-digit",
    });
  } catch {
    return "";
  }
}

function tabClass(active: boolean): string {
  return `flex items-center gap-2 px-3 py-2.5 text-xs font-medium transition-colors border-l-2 ${
    active
      ? "border-app-primary text-app-primary bg-app-bg-secondary/50"
      : "border-transparent text-app-text-secondary hover:text-app-text hover:bg-app-bg-tertiary"
  }`;
}

export function Sidebar({
  activeSessionId,
  onSelectSession,
  onNewChat,
  refreshTrigger,
  verboseMode,
  onVerboseModeChange,
}: SidebarProps) {
  const [tab, setTab] = useState<SidebarTab>("sessions");
  const [sessions, setSessions] = useState<ChatSession[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [deletingId, setDeletingId] = useState<string | null>(null);
  const [mcpServers, setMcpServers] = useState<McpServer[]>([]);
  const [mcpHealth, setMcpHealth] = useState<Record<string, McpServerHealth>>({});
  const [mcpLoading, setMcpLoading] = useState(true);
  const [agentInfo, setAgentInfo] = useState<{
    tools: string[];
    skills: string[];
    agents: string[];
  } | null>(null);
  const [agentInfoLoading, setAgentInfoLoading] = useState(true);

  const isDevMode = import.meta.env.VITE_MODE !== "prod";

  const loadSessions = useCallback(async () => {
    try {
      setIsLoading(true);
      const data = await sessionService.listSessions();
      setSessions(data);
    } catch (err) {
      console.error("Error cargando sesiones:", err);
      setSessions([]);
    } finally {
      setIsLoading(false);
    }
  }, []);

  const loadMcpServers = useCallback(async () => {
    try {
      setMcpLoading(true);
      const data = await configService.getMcpServers();
      setMcpServers(data.servers || []);
    } catch (err) {
      console.error("Error cargando servidores MCP:", err);
      setMcpServers([]);
    } finally {
      setMcpLoading(false);
    }
  }, []);

  const loadMcpHealth = useCallback(async () => {
    if (mcpServers.length === 0) return;
    try {
      const healthData = await configService.getMcpHealth();
      const healthMap: Record<string, McpServerHealth> = {};
      for (const h of healthData.servers || []) {
        healthMap[h.label] = h;
      }
      setMcpHealth(healthMap);
    } catch (err) {
      console.error("Error cargando salud MCP:", err);
    }
  }, [mcpServers]);

  const loadAgentInfo = useCallback(async () => {
    try {
      setAgentInfoLoading(true);
      // Load tools, skills, and agents from the backend config endpoint
      const [providersResp, mcpResp] = await Promise.all([
        configService.getProviders(),
        configService.getMcpServers(),
      ]);
      const tools: string[] = [];
      const skills: string[] = [];
      const agents: string[] = [];

      // Tools come from MCP servers
      for (const server of mcpResp.servers || []) {
        if (server.label) tools.push(server.label);
      }

      // Skills and agents would be loaded from their respective endpoints
      // For now, we show what's available from the config
      setAgentInfo({ tools, skills, agents });
    } catch (err) {
      console.error("Error cargando información del agente:", err);
      setAgentInfo({ tools: [], skills: [], agents: [] });
    } finally {
      setAgentInfoLoading(false);
    }
  }, []);

  // Load sessions on mount
  useEffect(() => {
    loadSessions();
  }, [loadSessions]);

  // Load MCP servers on mount
  useEffect(() => {
    loadMcpServers();
  }, [loadMcpServers]);

  // Load MCP health when servers change
  useEffect(() => {
    loadMcpHealth();
  }, [loadMcpHealth]);

  // Load agent info when switching to agent tab
  useEffect(() => {
    if (tab === "agent") {
      loadAgentInfo();
    }
  }, [tab, loadAgentInfo]);

  // Recargar en silencio cuando se abre el sidebar, cambia el tab o refreshTrigger
  useEffect(() => {
    if (tab === "sessions") {
      sessionService.listSessions()
        .then((data) => setSessions(data))
        .catch((err) => console.error("Error refrescando sesiones:", err));
    }
  }, [refreshTrigger]);

  const handleDelete = async (id: string, e: React.MouseEvent) => {
    e.stopPropagation();
    if (!window.confirm("¿Eliminar esta conversación?")) return;
    try {
      setDeletingId(id);
      await sessionService.deleteSession(id);
      setSessions((prev) => prev.filter((s) => s.session_id !== id));
      if (activeSessionId === id) {
        onNewChat();
      }
    } catch (err) {
      console.error("Error eliminando sesión:", err);
    } finally {
      setDeletingId(null);
    }
  };

  const isDevOnly = import.meta.env.VITE_MODE === "dev";

  // Menu items
  const menuItems: Array<{ key: SidebarTab; label: string; icon: React.ReactNode; devOnly?: boolean }> = [
    { key: "sessions", label: "Conversaciones", icon: <MessageSquare size={14} /> },
    { key: "config", label: "Configuración", icon: <Settings size={14} /> },
    { key: "agent", label: "Agente", icon: <Bot size={14} /> },
    ...(isDevOnly ? [{ key: "create" as SidebarTab, label: "Crear", icon: <Wrench size={14} /> }] : []),
  ];

  return (
    <aside className="w-64 shrink-0 h-full flex flex-col border-r border-app-border bg-app-bg-secondary">
      {/* Menu header */}
      <div
        className="flex items-center gap-2 px-4 border-b border-app-border bg-white"
        style={{ height: "52px" }}
      >
        <MessageSquare size={16} className="text-app-primary" />
        <span className="text-sm font-semibold text-app-text">synapseForge</span>
      </div>

      {/* Menu items */}
      <nav className="flex flex-col py-2 border-b border-app-border">
        {menuItems.map((item) => (
          <button
            key={item.key}
            type="button"
            onClick={() => setTab(item.key)}
            className={`flex items-center gap-2 px-3 py-2.5 text-xs font-medium transition-colors border-l-2 ${
              tab === item.key
                ? "border-app-primary text-app-primary bg-app-btn-nuevo-chat-bg/10"
                : "border-transparent text-app-text-secondary hover:text-app-text hover:bg-app-bg-tertiary"
            }`}
          >
            {item.icon}
            <span>{item.label}</span>
          </button>
        ))}
      </nav>

      {/* Content area */}
      <div className="flex-1 flex flex-col min-h-0">
        {/* Sessions tab */}
        <div
          className="flex-1 flex flex-col min-h-0"
          style={{ display: tab === "sessions" ? "flex" : "none" }}
        >
          <SessionsTab
            activeSessionId={activeSessionId}
            onSelectSession={onSelectSession}
            onNewChat={onNewChat}
            refreshTrigger={refreshTrigger}
            sessions={sessions}
            isLoading={isLoading}
            deletingId={deletingId}
            handleDelete={handleDelete}
          />
        </div>

        {/* Config tab */}
        <div
          className="flex-1 flex flex-col min-h-0 overflow-y-auto"
          style={{ display: tab === "config" ? "flex" : "none" }}
        >
          <ConfigTab verboseMode={verboseMode} onVerboseModeChange={onVerboseModeChange} />
        </div>

        {/* Agent info tab */}
        <div
          className="flex-1 flex flex-col min-h-0 overflow-y-auto"
          style={{ display: tab === "agent" ? "flex" : "none" }}
        >
          <AgentInfoTab
            agentInfo={agentInfo}
            loading={agentInfoLoading}
          />
        </div>

        {/* Create tab (dev only) */}
        {isDevOnly && (
          <div
            className="flex-1 flex flex-col min-h-0 overflow-y-auto"
            style={{ display: tab === "create" ? "flex" : "none" }}
          >
            <CreateTab />
          </div>
        )}
      </div>
    </aside>
  );
}

export default Sidebar;