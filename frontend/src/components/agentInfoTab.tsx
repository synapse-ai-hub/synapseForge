import { useState, useEffect, useCallback } from "react";
import { Wrench, Puzzle, Brain, Server, Cpu, Globe, Database } from "lucide-react";
import configService, { type SkillInfo, type ToolInfo, type AgentInfo, type McpServerStatus } from "../services/configService";

type AgentTab = "tools" | "skills" | "agents" | "mcp" | "rag";

export function AgentInfoTab() {
  const [tab, setTab] = useState<AgentTab>("tools");

  return (
    <div className="flex-1 flex flex-col min-h-0">
      {/* Sidebar nav — vertical tabs one below the other */}
      <nav className="flex flex-col py-2 border-b border-app-border bg-app-bg-secondary">
        {([
          { key: "tools" as AgentTab, label: "Tools", icon: <Wrench size={14} /> },
          { key: "skills" as AgentTab, label: "Skills", icon: <Puzzle size={14} /> },
          { key: "agents" as AgentTab, label: "Agentes", icon: <Brain size={14} /> },
          { key: "mcp" as AgentTab, label: "MCP", icon: <Server size={14} /> },
          { key: "rag" as AgentTab, label: "RAG", icon: <Database size={14} /> },
        ]).map((item) => (
          <button
            key={item.key}
            type="button"
            onClick={() => setTab(item.key)}
            className={`flex items-center gap-2 px-3 py-2.5 text-xs font-medium transition-colors border-l-2 ${
              tab === item.key
                ? "border-app-primary text-app-primary bg-app-primary/10"
                : "border-transparent text-app-text-secondary hover:text-app-text hover:bg-app-bg-tertiary"
            }`}
          >
            {item.icon}
            <span>{item.label}</span>
          </button>
        ))}
      </nav>

      {/* Content — below the nav tabs (same as Sidebar layout) */}
      <div className="flex-1 overflow-y-auto p-3">
        {tab === "tools" && <ToolsPanel />}
        {tab === "skills" && <SkillsPanel />}
        {tab === "agents" && <AgentsPanel />}
        {tab === "mcp" && <McpPanel />}
        {tab === "rag" && <RagPanel />}
      </div>
    </div>
  );
}

// ─── Tools ────────────────────────────────────────────────────────

function ToolsPanel() {
  const [tools, setTools] = useState<ToolInfo[]>([]);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    try {
      setLoading(true);
      const data = await configService.getTools();
      setTools(data);
    } catch (err) {
      console.error("Error cargando tools:", err);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  if (loading) return <p className="text-sm text-app-text-secondary">Cargando...</p>;

  return (
    <div className="space-y-1">
      {tools.length === 0 ? (
        <p className="text-sm text-app-text-secondary">No hay herramientas disponibles.</p>
      ) : (
        tools.map((t) => (
          <div key={t.name} className="rounded-lg border border-app-border bg-white px-3 py-2">
            <span className="text-sm font-medium text-app-text">{t.name}</span>
            {t.description && (
              <p className="text-xs text-app-text-secondary mt-0.5">{t.description}</p>
            )}
          </div>
        ))
      )}
    </div>
  );
}

// ─── Skills ───────────────────────────────────────────────────────

function SkillsPanel() {
  const [skills, setSkills] = useState<SkillInfo[]>([]);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    try {
      setLoading(true);
      const data = await configService.getSkills();
      setSkills(data);
    } catch (err) {
      console.error("Error cargando skills:", err);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  if (loading) return <p className="text-sm text-app-text-secondary">Cargando...</p>;

  return (
    <div className="space-y-1">
      {skills.length === 0 ? (
        <p className="text-sm text-app-text-secondary">No hay skills instaladas.</p>
      ) : (
        skills.map((s) => (
          <div key={s.name} className="rounded-lg border border-app-border bg-white px-3 py-2">
            <span className="text-sm font-medium text-app-text">{s.name}</span>
            {s.description && (
              <p className="text-xs text-app-text-secondary mt-0.5">{s.description}</p>
            )}
          </div>
        ))
      )}
    </div>
  );
}

// ─── Agents ───────────────────────────────────────────────────────

function AgentsPanel() {
  const [agents, setAgents] = useState<AgentInfo[]>([]);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    try {
      setLoading(true);
      const data = await configService.getAgents();
      setAgents(data);
    } catch (err) {
      console.error("Error cargando agentes:", err);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  if (loading) return <p className="text-sm text-app-text-secondary">Cargando...</p>;

  return (
    <div className="space-y-1">
      {agents.length === 0 ? (
        <p className="text-sm text-app-text-secondary">No hay agentes configurados.</p>
      ) : (
        agents.map((a) => (
          <div key={a.name} className="rounded-lg border border-app-border bg-white px-3 py-2">
            <span className="text-sm font-medium text-app-text">{a.name}</span>
            {a.description && (
              <p className="text-xs text-app-text-secondary mt-0.5">{a.description}</p>
            )}
          </div>
        ))
      )}
    </div>
  );
}

// ─── MCP ──────────────────────────────────────────────────────────

function McpPanel() {
  const [servers, setServers] = useState<McpServerStatus[]>([]);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    try {
      setLoading(true);
      const data = await configService.getMcp();
      setServers(data);
    } catch (err) {
      console.error("Error cargando MCP:", err);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  if (loading) return <p className="text-sm text-app-text-secondary">Cargando...</p>;

  return (
    <div className="space-y-1">
      {servers.length === 0 ? (
        <p className="text-sm text-app-text-secondary">No hay servidores MCP configurados.</p>
      ) : (
        servers.map((s) => (
          <div key={s.label} className="rounded-lg border border-app-border bg-white px-3 py-2">
            <div className="flex items-center gap-2">
              {s.status === "connected" ? (
                <Globe size={14} className="shrink-0 text-green-600" />
              ) : (
                <Database size={14} className="shrink-0 text-app-text-secondary" />
              )}
              <span className="text-sm font-medium text-app-text">{s.label}</span>
              <span className={`ml-auto text-xs px-1.5 py-0.5 rounded font-medium ${
                s.status === "connected"
                  ? "bg-green-100 text-green-700"
                  : s.status === "failed"
                  ? "bg-red-100 text-red-700"
                  : "bg-gray-100 text-gray-500"
              }`}>
                {s.status === "connected" ? "Conectado" : s.status === "failed" ? "Error" : s.status}
              </span>
            </div>
          </div>
        ))
      )}
    </div>
  );
}

function RagPanel() {
  return (
    <div className="space-y-1">
      <p className="text-sm text-app-text-secondary">RAG panel content goes here.</p>
    </div>
  );
}

export default AgentInfoTab;
