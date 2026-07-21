import { useState, useEffect, useCallback } from "react";
import { Plus, MessageSquare, Trash2, X, Bot, Settings, Server, Cpu, Database, Globe } from "lucide-react";
import { Button } from "./ui/button";
import { Input } from "./ui/input";
import sessionService, { type ChatSession } from "../services/sessionService";
import configService, { type McpServer, type McpServerHealth } from "../services/configService";

type SidebarTab = "sessions" | "config";

interface SidebarProps {
  open: boolean;
  onClose: () => void;
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
  return `flex-1 px-3 py-2 text-xs font-medium transition-colors border-b-2 ${
    active
      ? "border-app-primary text-app-primary"
      : "border-transparent text-app-text-secondary hover:text-app-text"
  }`;
}

export function Sidebar({
  open,
  onClose,
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

  // Cargar sesiones al montar el componente
  useEffect(() => {
    loadSessions();
  }, [loadSessions]);

  // Cargar servidores MCP al montar
  useEffect(() => {
    loadMcpServers();
  }, [loadMcpServers]);

  // Cargar salud MCP cuando cambian los servidores
  useEffect(() => {
    loadMcpHealth();
  }, [loadMcpHealth]);

  // Recargar en silencio cuando se abre el sidebar, cambia el tab o refreshTrigger
  // (sin mostrar "Cargando..." para evitar el flicker)
  useEffect(() => {
    if (open && tab === "sessions") {
      sessionService.listSessions()
        .then((data) => setSessions(data))
        .catch((err) => console.error("Error refrescando sesiones:", err));
    }
  }, [open, tab, refreshTrigger]);

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

  if (!open) return null;

  return (
    <aside className="w-72 shrink-0 h-full flex flex-col border-r border-app-border bg-app-bg-secondary">
      {/* Header */}
      <div
        className="flex items-center justify-between px-4 border-b border-app-border bg-white"
        style={{ height: "60px" }}
      >
        <div className="flex items-center gap-2">
          {tab === "config" ? (
            <Settings size={18} className="text-app-primary" />
          ) : (
            <Bot size={18} className="text-app-primary" />
          )}
          <span className="text-sm font-semibold text-app-text">
            {tab === "config" ? "Configuración" : "Conversaciones"}
          </span>
        </div>
        <button
          type="button"
          onClick={onClose}
          className="rounded-full p-1.5 text-app-text-secondary hover:bg-app-bg-secondary hover:text-app-text transition-colors"
          aria-label="Cerrar panel"
        >
          <X size={18} />
        </button>
      </div>

      {/* Tabs */}
      <div className="flex border-b border-app-border bg-white">
        <button
          type="button"
          onClick={() => setTab("sessions")}
          className={tabClass(tab === "sessions")}
        >
          Conversaciones
        </button>
        <button
          type="button"
          onClick={() => setTab("config")}
          className={tabClass(tab === "config")}
        >
          Configuración
        </button>
      </div>

      {/* Sessions tab — always mounted, hidden via CSS when inactive */}
      <div
        className="flex-1 flex flex-col min-h-0"
        style={{ display: tab === 'sessions' ? 'flex' : 'none' }}
      >
        {/* New chat */}
        <div className="p-3 border-b border-app-border bg-white">
          <Button onClick={onNewChat} className="w-full gap-2">
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
              <div className="w-full max-w-[calc(100%-1.5rem)] mx-auto rounded-md bg-app-primary px-3 py-2 text-center">
                <div className="flex justify-center items-center gap-2 text-xs font-medium text-white">
                  <Server size={12} className="text-white" />
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

      {/* Config tab — always mounted too, hidden via CSS when inactive */}
      <div
        className="flex-1 flex flex-col min-h-0 overflow-y-auto"
        style={{ display: tab === 'config' ? 'flex' : 'none' }}
      >
        <ConfigTab verboseMode={verboseMode} onVerboseModeChange={onVerboseModeChange} />
      </div>
    </aside>
  );
}

function ConfigTab({ verboseMode, onVerboseModeChange }: { verboseMode: boolean; onVerboseModeChange: (val: boolean) => void }) {
  const [providers, setProviders] = useState<Array<{ provider: string; label: string }>>([]);
  const [models, setModels] = useState<string[]>([]);
  const [currentModel, setCurrentModel] = useState<string | null>(null);
  const [selectedProvider, setSelectedProvider] = useState<string>("");
  const [maxTurns, setMaxTurns] = useState<number>(-1);
  const [loading, setLoading] = useState(true);
  const [savingModel, setSavingModel] = useState(false);
  const [savingContext, setSavingContext] = useState(false);

  const load = useCallback(async (prov?: string) => {
    let label: string | undefined;
    try {
      setLoading(true);
      label = "[ConfigTab] load " + Date.now();
      console.time(label);
      // Individual timing per endpoint
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
      // If no provider is selected yet, pick the first available one
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
          Contexto (turnos)
        </div>
        <p className="text-[11px] text-app-text-secondary mt-1">
          Cantidad de turnos a mantener en el contexto. -1 = todo el historial.
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
    </div>
  );
}

export default Sidebar;
