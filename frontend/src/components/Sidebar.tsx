import { useState, useEffect, useCallback, useRef } from "react";
import { Plus, MessageSquare, Settings, Server, Cpu, Database, Upload, Wrench, Puzzle, Bot, Trash2, Globe } from "lucide-react";
import { Button } from "./ui/button";
import { Input } from "./ui/input";
import sessionService, { type ChatSession } from "../services/sessionService";
import configService, { type McpServer, type McpServerHealth } from "../services/configService";
import contextFilesService, { type ContextFile } from "../services/contextFilesService";

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
          {/* New chat */}
          <div className="p-3 border-b border-app-border bg-white">
            <Button onClick={onNewChat} className="w-full gap-2 bg-app-btn-nuevo-chat-bg text-app-btn-nuevo-chat-text hover:bg-app-btn-nuevo-chat-bg/90">
              <Plus size={16} />
              Nuevo Chat
            </Button>
          </div>

          {/* Session list + MCP panel */}
          <div className="flex-1 flex flex-col min-h-0">
            {/* History - 70% */}
            <div className="flex-1 overflow-y-auto px-3 py-3 space-y-1.5 min-h-0" style={{ maxHeight: "70%" }}>
              {isLoading ? (
                <div className="text-center py-4 text-sm text-app-text-secondary">
                  Cargando...
                </div>
              ) : sessions.length === 0 ? (
                <div className="text-center py-4 text-sm text-app-text-secondary">
                  No hay conversaciones todavía.
                </div>
              ) : (
                sessions.map((s) => {
                  const isActive = activeSessionId === s.session_id;
                  return (
                    <div
                      key={s.session_id}
                      onClick={() => onSelectSession(s.session_id)}
                      role="button"
                      tabIndex={0}
                      onKeyDown={(e) => {
                        if (e.key === "Enter" || e.key === " ") {
                          e.preventDefault();
                          onSelectSession(s.session_id);
                        }
                      }}
                      className={`group w-full text-left p-2.5 rounded-lg border cursor-pointer transition-colors ${
                        isActive
                          ? "border-app-primary bg-white"
                          : "border-transparent bg-white hover:bg-app-bg-tertiary"
                      }`}
                    >
                      <div className="flex items-start gap-2">
                        <MessageSquare
                          size={14}
                          className="mt-0.5 shrink-0 text-app-primary"
                        />
                        <div className="flex-1 min-w-0">
                          <div className="text-xs font-medium text-app-text truncate">
                            {s.title}
                          </div>
                          {s.preview ? (
                            <div className="text-[11px] text-app-text-secondary truncate mt-0.5">
                              {s.preview}
                            </div>
                          ) : null}
                          <div className="text-[11px] text-app-text-secondary mt-0.5">
                            {formatTimestamp(s.updated_at)}
                          </div>
                        </div>
                        <button
                          type="button"
                          onClick={(e) => handleDelete(s.session_id, e)}
                          disabled={deletingId === s.session_id}
                          className="shrink-0 rounded p-1 text-app-text-secondary opacity-0 group-hover:opacity-100 hover:bg-red-100 hover:text-app-error transition-all"
                          aria-label="Eliminar conversación"
                        >
                          {deletingId === s.session_id ? (
                            <div
                              style={{
                                width: "14px",
                                height: "14px",
                                border: "2px solid #9ca3af",
                                borderTop: "2px solid #C2413D",
                                borderRadius: "50%",
                                animation: "spin 1s linear infinite",
                              }}
                            />
                          ) : (
                            <Trash2 size={14} />
                          )}
                        </button>
                      </div>
                    </div>
                  );
                })
              )}
            </div>

            {/* MCP Panel - 30% */}
            <div className="border-t border-app-border bg-app-bg-secondary flex-shrink-0" style={{ height: "30%" }}>
              <div className="p-3 border-b border-app-border bg-white">
                <div className="w-full max-w-[calc(100%-1.5rem)] mx-auto rounded-md bg-app-btn-nuevo-chat-bg px-3 py-2 text-center">
                  <div className="flex justify-center items-center gap-2 text-xs font-medium text-app-btn-nuevo-chat-text">
                    <Server size={12} />
                    Servidores MCP
                  </div>
                </div>
              </div>
              <div className="flex-1 overflow-y-auto px-3 py-2 space-y-2 min-h-0">
                {mcpLoading ? (
                  <div className="text-center py-4 text-xs text-app-text-secondary">
                    Cargando...
                  </div>
                ) : mcpServers.length === 0 ? (
                  <div className="text-center py-4 text-xs text-app-text-secondary">
                    No hay servidores MCP configurados.
                  </div>
                ) : (
                  mcpServers.map((server) => {
                    const health = mcpHealth[server.label];
                    const isConnected = health?.status === "connected";
                    const isFailed = health?.status === "failed";
                    const isDisabled = health?.status === "disabled" || server.disabled;

                    const statusBadgeClass = isConnected
                      ? "bg-app-primary text-white"
                      : isFailed
                      ? "bg-app-error/10 text-app-error"
                      : isDisabled
                      ? "bg-app-bg-tertiary text-app-text-secondary"
                      : "bg-app-warning/10 text-app-warning";
                    const statusText = isConnected
                      ? "Conectado"
                      : isFailed
                      ? "Error"
                      : isDisabled
                      ? "Deshabilitado"
                      : "Desconocido";

                    const transportBadgeClass = server.transport === "http"
                      ? "bg-app-primary/10 text-app-primary"
                      : "bg-app-success/10 text-app-success";

                    return (
                      <div
                        key={server.label}
                        className="p-2 rounded-lg border border-app-border bg-app-bg hover:bg-app-bg-tertiary transition-colors"
                      >
                        <div className="flex items-center gap-2">
                          {server.transport === "http" ? (
                            <Globe size={14} className="text-app-primary" />
                          ) : server.command?.includes("mssql") || server.command?.includes("sql") ? (
                            <Database size={14} className="text-app-primary" />
                          ) : (
                            <Cpu size={14} className="text-app-primary" />
                          )}
                          <div className="flex-1 min-w-0">
                            <div className="flex items-center gap-1.5">
                              <div className="text-xs font-medium text-app-text truncate">
                                {server.label}
                              </div>
                              <span className={`inline-flex items-center px-1.5 py-0.5 rounded text-[9px] font-medium ${statusBadgeClass}`}>
                                {statusText}
                              </span>
                            </div>
                            {server.description && (
                              <div className="text-[10px] text-app-text-secondary truncate mt-0.5">
                                {server.description}
                              </div>
                            )}
                            <div className="flex items-center gap-1.5 mt-1">
                              <span className={`inline-flex items-center px-1.5 py-0.5 rounded text-[9px] font-medium ${transportBadgeClass}`}>
                                {server.transport === "http" ? "HTTP" : "STDIO"}
                              </span>
                              {isConnected && health?.tools_count !== undefined && (
                                <span className="inline-flex items-center px-1.5 py-0.5 rounded text-[9px] font-medium bg-app-primary/10 text-app-primary">
                                  {health.tools_count} tools
                                </span>
                              )}
                              {isFailed && health?.error && (
                                <span className="inline-flex items-center px-1.5 py-0.5 rounded text-[9px] font-medium bg-app-error/10 text-app-error" title={health.error}>
                                  Error
                                </span>
                              )}
                              {server.disabled && (
                                <span className="inline-flex items-center px-1.5 py-0.5 rounded text-[9px] font-medium bg-app-bg-tertiary text-app-text-secondary">
                                  Deshabilitado
                                </span>
                              )}
                            </div>
                          </div>
                        </div>
                      </div>
                    );
                  })
                )}
              </div>
            </div>
          </div>
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

// ── Config Tab (same as before) ──────────────────────────────────────────

function ConfigTab({ verboseMode, onVerboseModeChange }: { verboseMode: boolean; onVerboseModeChange: (val: boolean) => void }) {
  const [providers, setProviders] = useState<Array<{ provider: string; label: string }>>([]);
  const [models, setModels] = useState<string[]>([]);
  const [currentModel, setCurrentModel] = useState<string | null>(null);
  const [selectedProvider, setSelectedProvider] = useState<string>("");
  const [maxTurns, setMaxTurns] = useState<number>(-1);
  const [loading, setLoading] = useState(true);
  const [savingModel, setSavingModel] = useState(false);
  const [savingContext, setSavingContext] = useState(false);
  const [contextFiles, setContextFiles] = useState<ContextFile[]>([]);
  const [uploadingContext, setUploadingContext] = useState(false);
  const contextFileInputRef = useRef<HTMLInputElement>(null);

  const load = useCallback(async (prov?: string) => {
    let label: string | undefined;
    try {
      setLoading(true);
      label = "[ConfigTab] load " + Date.now();
      console.time(label);
      const tProv = "[ConfigTab] getProviders " + Date.now();
      const tModels = "[ConfigTab] getModels " + Date.now();
      const tCW = "[ConfigTab] getContextWindow " + Date.now();
      console.time(tProv);
      console.time(tModels);
      console.time(tCW);
      const [provResp, m, cw] = await Promise.all([
        configService.getProviders().finally(() => console.timeEnd(tProv)),
        configService.getModels(prov).finally(() => console.timeEnd(tModels)),
        configService.getContextWindow().finally(() => console.timeEnd(tCW)),
      ]);
      setProviders(provResp.providers || []);
      setModels(m.models || []);
      setCurrentModel(m.model);
      const effective = prov || m.provider || (provResp.providers?.[0]?.provider ?? "");
      setSelectedProvider(effective);
      setMaxTurns(typeof cw.max_turns === "number" ? cw.max_turns : -1);
    } catch (err) {
      console.error("Error cargando configuración:", err);
    } finally {
      setLoading(false);
      if (label) console.timeEnd(label);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  useEffect(() => {
    contextFilesService.list()
      .then((files) => setContextFiles(files || []))
      .catch((err) => console.error("Error cargando archivos de contexto:", err));
  }, []);

  const handleProviderChange = (value: string) => {
    setSelectedProvider(value);
    load(value);
  };

  const handleSelectModel = async (model: string) => {
    try {
      setSavingModel(true);
      await configService.selectModel(model, selectedProvider);
      setCurrentModel(model);
    } catch (err) {
      console.error("Error seleccionando modelo:", err);
    } finally {
      setSavingModel(false);
    }
  };

  const handleSaveContext = async () => {
    try {
      setSavingContext(true);
      await configService.setContextWindow(maxTurns);
    } catch (err) {
      console.error("Error guardando contexto:", err);
    } finally {
      setSavingContext(false);
    }
  };

  const handleUploadContextFile = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    try {
      setUploadingContext(true);
      await contextFilesService.upload(file);
      const files = await contextFilesService.list();
      setContextFiles(files || []);
    } catch (err) {
      console.error("Error subiendo archivo de contexto:", err);
    } finally {
      setUploadingContext(false);
      if (e.target) e.target.value = "";
    }
  };

  const handleDeleteContextFile = async (id: number) => {
    try {
      await contextFilesService.delete(id);
      setContextFiles((prev) => prev.filter((f) => f.id !== id));
    } catch (err) {
      console.error("Error eliminando archivo de contexto:", err);
    }
  };

  if (loading) {
    return (
      <div className="p-4 text-sm text-app-text-secondary">Cargando...</div>
    );
  }

  return (
    <div className="flex-1 overflow-y-auto p-4 space-y-5">
      <div>
        <div className="text-xs font-medium text-app-text-secondary">
          Proveedor
        </div>
        <select
          value={selectedProvider}
          onChange={(e) => handleProviderChange(e.target.value)}
          className="mt-1 w-full rounded-lg border border-app-border bg-white px-3 py-2 text-sm text-app-text focus:outline-none focus:ring-2 focus:ring-app-primary-light"
        >
          {providers.length === 0 ? (
            <option value="">No hay proveedores disponibles</option>
          ) : (
            providers.map((p) => (
              <option key={p.provider} value={p.provider}>
                {p.label}
              </option>
            ))
          )}
        </select>
      </div>

      <div>
        <div className="text-xs font-medium text-app-text-secondary">
          Modelo
        </div>
        <select
          value={currentModel || ""}
          onChange={(e) => handleSelectModel(e.target.value)}
          disabled={savingModel || models.length === 0}
          className="mt-1 w-full rounded-lg border border-app-border bg-white px-3 py-2 text-sm text-app-text focus:outline-none focus:ring-2 focus:ring-app-primary-light"
        >
          {models.length === 0 ? (
            <option value="">No hay modelos disponibles</option>
          ) : (
            models.map((m) => (
              <option key={m} value={m}>
                {m}
              </option>
            ))
          )}
        </select>
      </div>

      <div>
        <div className="text-xs font-medium text-app-text-secondary">
          Ventana de contexto
        </div>
        <p className="text-[11px] text-app-text-secondary mt-1">
          Controla cuántos turnos de la conversación se recuerdan al responder. -1 = todo el historial.
        </p>
        <div className="flex gap-2 mt-2">
          <Input
            type="number"
            min={-1}
            value={maxTurns}
            onChange={(e) => {
              const v = Number(e.target.value);
              setMaxTurns(Number.isNaN(v) ? -1 : v < -1 ? -1 : v);
            }}
            className="flex-1"
          />
          <Button onClick={handleSaveContext} disabled={savingContext}>
            Guardar
          </Button>
        </div>
      </div>

      <div className="flex items-center justify-between py-2">
        <div>
          <div className="text-xs font-medium text-app-text-secondary">
            Modo verbose
          </div>
          <p className="text-[11px] text-app-text-secondary mt-1">
            Muestra herramientas y sub-agentes en la conversación.
          </p>
        </div>
        <button
          type="button"
          role="switch"
          aria-checked={verboseMode}
          onClick={() => onVerboseModeChange(!verboseMode)}
          className={`relative inline-flex h-5 w-9 shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors focus:outline-none focus:ring-2 focus:ring-app-primary-light ${
            verboseMode ? "bg-app-primary" : "bg-app-bg-tertiary"
          }`}
        >
          <span
            className={`pointer-events-none inline-block h-4 w-4 rounded-full bg-white shadow transition-transform ${
              verboseMode ? "translate-x-4" : "translate-x-0"
            }`}
          />
        </button>
      </div>

      {/* Instrucciones y documentos */}
      <div className="pt-2">
        <div className="text-xs font-medium text-app-text-secondary">
          Instrucciones y documentos
        </div>
        <p className="text-[11px] text-app-text-secondary mt-1">
          Archivos con instrucciones, reglas de comportamiento, reglas de negocio o información que el agente debe conocer al responder.
        </p>
        <div className="mt-2">
          <button
            type="button"
            onClick={() => contextFileInputRef.current?.click()}
            disabled={uploadingContext}
            className="flex w-full cursor-pointer items-center justify-center gap-2 rounded-lg border border-dashed border-app-border bg-white px-3 py-4 text-xs text-app-text-secondary hover:border-app-primary/50 hover:text-app-primary transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
          >
            <Upload size={16} />
            <span>{uploadingContext ? "Subiendo..." : "Subir archivos (PDF, Word, TXT)"}</span>
          </button>
          <input
            ref={contextFileInputRef}
            type="file"
            accept=".pdf,.docx,.doc,.txt,.md,.csv,.json,.yaml,.yml,.xml,.py"
            className="hidden"
            onChange={handleUploadContextFile}
          />
        </div>

        {contextFiles.length > 0 && (
          <div className="mt-3 space-y-1">
            {contextFiles.map((f) => (
              <div
                key={f.id}
                className="flex items-center justify-between rounded-md bg-white px-2 py-1.5 text-xs"
              >
                <span className="truncate text-app-text flex-1 min-w-0">{f.filename}</span>
                <button
                  type="button"
                  onClick={() => handleDeleteContextFile(f.id)}
                  className="ml-2 shrink-0 rounded p-0.5 text-app-text-secondary hover:text-red-500 hover:bg-red-50 transition-colors"
                  aria-label="Eliminar archivo de contexto"
                >
                  <Trash2 size={14} />
                </button>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

// ── Agent Info Tab ────────────────────────────────────────────────────────

function AgentInfoTab({ agentInfo, loading }: { agentInfo: { tools: string[]; skills: string[]; agents: string[] } | null; loading: boolean }) {
  if (loading) {
    return (
      <div className="p-4 text-sm text-app-text-secondary">Cargando información del agente...</div>
    );
  }

  return (
    <div className="flex-1 overflow-y-auto p-4 space-y-5">
      <div>
        <div className="text-xs font-medium text-app-text-secondary mb-2">
          Herramientas disponibles
        </div>
        {agentInfo?.tools && agentInfo.tools.length > 0 ? (
          <div className="space-y-1">
            {agentInfo.tools.map((tool) => (
              <div key={tool} className="flex items-center gap-2 text-xs text-app-text">
                <Wrench size={12} className="text-app-primary shrink-0" />
                <span className="truncate">{tool}</span>
              </div>
            ))}
          </div>
        ) : (
          <p className="text-xs text-app-text-secondary">No hay herramientas configuradas.</p>
        )}
      </div>

      <div>
        <div className="text-xs font-medium text-app-text-secondary mb-2">
          Skills disponibles
        </div>
        {agentInfo?.skills && agentInfo.skills.length > 0 ? (
          <div className="space-y-1">
            {agentInfo.skills.map((skill) => (
              <div key={skill} className="flex items-center gap-2 text-xs text-app-text">
                <Puzzle size={12} className="text-app-primary shrink-0" />
                <span className="truncate">{skill}</span>
              </div>
            ))}
          </div>
        ) : (
          <p className="text-xs text-app-text-secondary">No hay skills instaladas.</p>
        )}
      </div>

      <div>
        <div className="text-xs font-medium text-app-text-secondary mb-2">
          Agentes disponibles
        </div>
        {agentInfo?.agents && agentInfo.agents.length > 0 ? (
          <div className="space-y-1">
            {agentInfo.agents.map((agent) => (
              <div key={agent} className="flex items-center gap-2 text-xs text-app-text">
                <Bot size={12} className="text-app-primary shrink-0" />
                <span className="truncate">{agent}</span>
              </div>
            ))}
          </div>
        ) : (
          <p className="text-xs text-app-text-secondary">No hay agentes configurados.</p>
        )}
      </div>
    </div>
  );
}

// ── Create Tab (dev only) ─────────────────────────────────────────────────

function CreateTab() {
  return (
    <div className="flex-1 overflow-y-auto p-4 space-y-4">
      <div className="text-xs font-medium text-app-text-secondary">
        Crear herramientas, skills y agentes
      </div>
      <p className="text-[11px] text-app-text-secondary">
        Esta funcionalidad está disponible en modo dev. Selecciona qué tipo de elemento crear y sigue las instrucciones.
      </p>
      <div className="space-y-2">
        <Button className="w-full justify-start gap-2" variant="outline">
          <Wrench size={14} />
          Crear Tool
        </Button>
        <Button className="w-full justify-start gap-2" variant="outline">
          <Puzzle size={14} />
          Crear Skill
        </Button>
        <Button className="w-full justify-start gap-2" variant="outline">
          <Bot size={14} />
          Crear Agente
        </Button>
      </div>
    </div>
  );
}

export default Sidebar;