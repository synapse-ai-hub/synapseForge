import { useState, useEffect, useCallback } from "react";
import { Wrench, Puzzle, Brain, Server, Cpu, Globe, Database, Trash2 } from "lucide-react";
import configService, { type SkillInfo, type ToolInfo, type AgentInfo, type McpServerStatus } from "../services/configService";

type AgentTab = "tools" | "skills" | "agents" | "mcp" | "rag";

export function AgentInfoTab() {
  const [tab, setTab] = useState<AgentTab>("tools");
  const [mcpServers, setMcpServers] = useState<McpServerStatus[]>([]);
  const [mcpLoading, setMcpLoading] = useState(true);

  const loadMcp = useCallback(async () => {
    try {
      setMcpLoading(true);
      const data = await configService.getMcp();
      setMcpServers(data);
    } catch (err) {
      console.error("Error cargando MCP:", err);
    } finally {
      setMcpLoading(false);
    }
  }, []);

  useEffect(() => { loadMcp(); }, [loadMcp]);

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
        {tab === "mcp" && <McpPanel servers={mcpServers} loading={mcpLoading} onRefresh={loadMcp} />}
        {tab === "rag" && <RagPanel />}
      </div>
    </div>
  );
}

// ─── Delete button with confirmation ──────────────────────────────

function DeleteBtn({ label, onDelete }: { label: string; onDelete: () => Promise<void> }) {
  const [confirming, setConfirming] = useState(false);
  const [deleting, setDeleting] = useState(false);

  if (confirming) {
    return (
      <div className="flex items-center gap-1">
        <button
          type="button"
          disabled={deleting}
          onClick={async () => {
            setDeleting(true);
            try {
              await onDelete();
              // Success — confirm stays visible but disabled briefly
              setTimeout(() => { setConfirming(false); setDeleting(false); }, 500);
            } catch {
              setDeleting(false);
              setConfirming(false);
            }
          }}
          className="text-xs bg-red-500 hover:bg-red-600 text-white px-2 py-0.5 rounded disabled:opacity-50"
        >
          {deleting ? "..." : "Sí"}
        </button>
        <button
          type="button"
          onClick={() => setConfirming(false)}
          className="text-xs bg-gray-200 hover:bg-gray-300 text-gray-700 px-2 py-0.5 rounded"
        >
          No
        </button>
      </div>
    );
  }

  return (
    <button
      type="button"
      onClick={() => setConfirming(true)}
      className="text-app-text-secondary hover:text-red-500 transition-colors shrink-0"
      title={`Eliminar ${label}`}
    >
      <Trash2 size={14} />
    </button>
  );
}

// ─── Tools ────────────────────────────────────────────────────────

function ToolsPanel() {
  const [tools, setTools] = useState<ToolInfo[]>([]);
  const [loading, setLoading] = useState(true);
  const [msg, setMsg] = useState("");

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
      {msg && <p className="text-xs text-green-600 mb-1">{msg}</p>}
      {tools.length === 0 ? (
        <p className="text-sm text-app-text-secondary">No hay herramientas disponibles.</p>
      ) : (
        tools.map((t) => (
          <div key={t.name} className="flex items-start justify-between rounded-lg border border-app-primary-light bg-white px-3 py-2">
            <div className="min-w-0 flex-1">
              <span className="text-sm font-medium text-app-text break-words">{t.name}</span>
              {t.description && (
                <p className="text-xs text-app-text-secondary mt-0.5">{t.description}</p>
              )}
            </div>
            <DeleteBtn
              label={t.name}
              onDelete={async () => {
                await configService.deleteTool(t.name);
                setTools((prev) => prev.filter((x) => x.name !== t.name));
                setMsg(`Tool «${t.name}» eliminada.`);
                setTimeout(() => setMsg(""), 3000);
              }}
            />
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
  const [msg, setMsg] = useState("");

  const load = useCallback(async () => {
    try {
      const data = await configService.getSkills();
      setSkills(data);
    } catch (err) {
      console.error("Error cargando skills:", err);
    } finally {
      setLoading(false);
    }
  }, []);

  // Cargar al montar y recargar cuando la ventana recupera el foco
  // (por si se creó/borró una skill en otra pestaña)
  useEffect(() => { load(); }, [load]);

  useEffect(() => {
    const onFocus = () => { setLoading(true); load(); };
    window.addEventListener("focus", onFocus);
    return () => window.removeEventListener("focus", onFocus);
  }, [load]);

  if (loading) return <p className="text-sm text-app-text-secondary">Cargando...</p>;

  return (
    <div className="space-y-1">
      {msg && <p className="text-xs text-green-600 mb-1">{msg}</p>}
      {skills.length === 0 ? (
        <p className="text-sm text-app-text-secondary">No hay skills instaladas.</p>
      ) : (
        skills.map((s) => (
          <div key={s.name} className="flex items-start justify-between rounded-lg border border-app-primary-light bg-white px-3 py-2">
            <div className="min-w-0 flex-1">
              <span className="text-sm font-medium text-app-text break-words">{s.name}</span>
              {s.description && (
                <p className="text-xs text-app-text-secondary mt-0.5">{s.description}</p>
              )}
            </div>
            <DeleteBtn
              label={s.name}
              onDelete={async () => {
                await configService.deleteSkill(s.name);
                setSkills((prev) => prev.filter((x) => x.name !== s.name));
                setMsg(`Skill «${s.name}» eliminada.`);
                setTimeout(() => setMsg(""), 3000);
              }}
            />
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
  const [msg, setMsg] = useState("");

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
      {msg && <p className="text-xs text-green-600 mb-1">{msg}</p>}
      {agents.length === 0 ? (
        <p className="text-sm text-app-text-secondary">No hay agentes configurados.</p>
      ) : (
        agents.map((a) => (
          <div key={a.name} className="flex items-start justify-between rounded-lg border border-app-primary-light bg-white px-3 py-2">
            <div className="min-w-0 flex-1">
              <span className="text-sm font-medium text-app-text break-words">{a.name}</span>
              {a.description && (
                <p className="text-xs text-app-text-secondary mt-0.5">{a.description}</p>
              )}
            </div>
            <DeleteBtn
              label={a.name}
              onDelete={async () => {
                await configService.deleteAgent(a.name);
                setAgents((prev) => prev.filter((x) => x.name !== a.name));
                setMsg(`Agente «${a.name}» eliminado.`);
                setTimeout(() => setMsg(""), 3000);
              }}
            />
          </div>
        ))
      )}
    </div>
  );
}

// ─── MCP ──────────────────────────────────────────────────────────

function McpPanel({ servers, loading, onRefresh }: { servers: McpServerStatus[]; loading: boolean; onRefresh: () => Promise<void> }) {
  const [msg, setMsg] = useState("");

  if (loading) return <p className="text-sm text-app-text-secondary">Cargando...</p>;

  return (
    <div className="space-y-1">
      {msg && <p className="text-xs text-green-600 mb-1">{msg}</p>}
      {servers.length === 0 ? (
        <p className="text-sm text-app-text-secondary">No hay servidores MCP configurados.</p>
      ) : (
        servers.map((s) => (
          <div key={s.label} className="flex items-start justify-between rounded-lg border border-app-primary-light bg-white px-3 py-2">
            <div className="flex flex-col gap-1 min-w-0 flex-1">
              <div className="flex items-center gap-2">
                {s.status === "connected" ? (
                  <Globe size={14} className="shrink-0 text-green-600" />
                ) : (
                  <Database size={14} className="shrink-0 text-app-text-secondary" />
                )}
                <span className="text-sm font-medium text-app-text min-w-0 break-words">{s.label}</span>
              </div>
              <span className={`text-xs px-1.5 py-0.5 rounded font-medium self-start ${
                s.status === "connected"
                  ? "bg-green-100 text-green-700"
                  : s.status === "failed"
                  ? "bg-red-100 text-red-700"
                  : "bg-gray-100 text-gray-500"
              }`}>
                {s.status === "connected" ? "Conectado" : s.status === "failed" ? "Error" : s.status}
              </span>
            </div>
            <DeleteBtn
              label={s.label}
              onDelete={async () => {
                await configService.deleteMcp(s.label);
                await onRefresh();
                setMsg(`Servidor MCP «${s.label}» eliminado.`);
                setTimeout(() => setMsg(""), 3000);
              }}
            />
          </div>
        ))
      )}
    </div>
  );
}

function RagPanel() {
  const [collections, setCollections] = useState<string[]>([]);
  const [loading, setLoading] = useState(true);
  const [msg, setMsg] = useState("");

  const load = useCallback(async () => {
    try {
      setLoading(true);
      const data = await configService.listKnowledge();
      setCollections(data);
    } catch {
      setCollections([]);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  if (loading) return <p className="text-sm text-app-text-secondary">Cargando...</p>;

  return (
    <div className="space-y-1">
      {msg && <p className="text-xs text-green-600 mb-1">{msg}</p>}
      {collections.length === 0 ? (
        <p className="text-sm text-app-text-secondary">No hay colecciones RAG.</p>
      ) : (
        collections.map((c) => (
          <div key={c} className="flex items-start justify-between rounded-lg border border-app-primary-light bg-white px-3 py-2">
            <span className="text-sm font-medium text-app-text min-w-0 flex-1 break-words">{c}</span>
            <DeleteBtn
              label={c}
              onDelete={async () => {
                await configService.deleteKnowledge(c);
                setCollections((prev) => prev.filter((x) => x !== c));
                setMsg(`Colección «${c}» eliminada.`);
                setTimeout(() => setMsg(""), 3000);
              }}
            />
          </div>
        ))
      )}
    </div>
  );
}

export default AgentInfoTab;
