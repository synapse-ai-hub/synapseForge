import { useState, useEffect, useCallback } from "react";
import { Server, Cpu, Database, Globe, Trash2 } from "lucide-react";
import configService, { type McpServer, type McpServerHealth } from "../services/configService";

interface AgentInfoTabProps {
  agentInfo: {
    tools: string[];
    skills: string[];
    agents: string[];
  } | null;
  loading: boolean;
}

export function AgentInfoTab({ agentInfo, loading }: AgentInfoTabProps) {
  const [mcpServers, setMcpServers] = useState<McpServer[]>([]);
  const [mcpHealth, setMcpHealth] = useState<Record<string, McpServerHealth>>({});
  const [mcpLoading, setMcpLoading] = useState(true);

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

  useEffect(() => {
    loadMcpServers();
  }, [loadMcpServers]);

  useEffect(() => {
    loadMcpHealth();
  }, [loadMcpHealth]);

  if (loading || mcpLoading) {
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
                <Server size={12} className="text-app-primary shrink-0" />
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
                <Cpu size={12} className="text-app-primary shrink-0" />
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
                <Globe size={12} className="text-app-primary shrink-0" />
                <span className="truncate">{agent}</span>
              </div>
            ))}
          </div>
        ) : (
          <p className="text-xs text-app-text-secondary">No hay agentes configurados.</p>
        )}
      </div>

      {/* MCP servers section */}
      <div>
        <div className="text-xs font-medium text-app-text-secondary mb-2">
          Servidores MCP
        </div>
        {mcpLoading ? (
          <div className="text-center py-4 text-xs text-app-text-secondary">
            Cargando...
          </div>
        ) : mcpServers.length === 0 ? (
          <div className="text-center py-4 text-xs text-app-text-secondary">
            No hay servidores MCP configurados.
          </div>
        ) : (
          <div className="space-y-2">
            {mcpServers.map((server) => {
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
            })}
          </div>
        )}
      </div>
    </div>
  );
}

export default AgentInfoTab;