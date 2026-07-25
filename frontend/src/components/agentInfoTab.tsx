import { useState, useEffect, useCallback } from "react";
import { Wrench, Puzzle, Brain, Server, Globe, Database, Cpu } from "lucide-react";
import configService, { type McpServer, type McpServerHealth, type AgentInfo } from "../services/configService";

interface ParsedSkill {
  name: string;
  description: string;
  triggers: string;
}

/** Parse skills markdown text into structured skill objects. */
function parseSkillsText(text: string): ParsedSkill[] {
  if (!text) return [];
  const skills: ParsedSkill[] = [];
  const blocks = text.split("\n\n");
  for (const block of blocks) {
    const nameMatch = block.match(/^###\s+(.+)$/m);
    if (!nameMatch) continue;
    const name = nameMatch[1].trim();
    const descMatch = block.match(/\*\*Descripción\*\*:\s*(.+)/);
    const triggerMatch = block.match(/\*\*Triggers\*\*:\s*(.+)/);
    skills.push({
      name,
      description: descMatch ? descMatch[1].trim() : "",
      triggers: triggerMatch ? triggerMatch[1].trim() : "",
    });
  }
  return skills;
}

export function AgentInfoTab() {
  const [loading, setLoading] = useState(true);

  // Tools from MCP servers (list of tool names from health)
  const [tools, setTools] = useState<{ name: string; server: string }[]>([]);

  // Skills
  const [skills, setSkills] = useState<ParsedSkill[]>([]);

  // Agents
  const [agents, setAgents] = useState<AgentInfo[]>([]);

  // MCP servers
  const [mcpServers, setMcpServers] = useState<McpServer[]>([]);
  const [mcpHealth, setMcpHealth] = useState<Record<string, McpServerHealth>>({});

  const loadAll = useCallback(async () => {
    try {
      setLoading(true);

      // Load everything in parallel
      const [mcpServersData, healthData, agentsData, skillsText] = await Promise.all([
        configService.getMcpServers(),
        configService.getMcpHealth(),
        configService.getAgents(),
        configService.getSkills(),
      ]);

      // MCP servers
      setMcpServers(mcpServersData.servers || []);

      // Health
      const healthMap: Record<string, McpServerHealth> = {};
      for (const h of healthData.servers || []) {
        healthMap[h.label] = h;
      }
      setMcpHealth(healthMap);

      // Tools (from MCP health — tool names reported by each server)
      const toolEntries: { name: string; server: string }[] = [];
      for (const h of healthData.servers || []) {
        if (h.status === "connected" && h.tools) {
          for (const tool of h.tools) {
            toolEntries.push({ name: tool, server: h.label });
          }
        }
      }
      setTools(toolEntries);

      // Agents
      setAgents(agentsData);

      // Skills
      setSkills(parseSkillsText(skillsText));

    } catch (err) {
      console.error("Error cargando información del agente:", err);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadAll();
  }, [loadAll]);

  if (loading) {
    return (
      <div className="flex-1 flex items-center justify-center p-4">
        <p className="text-sm text-app-text-secondary">Cargando información del agente...</p>
      </div>
    );
  }

  return (
    <div className="flex-1 overflow-y-auto p-3 space-y-4">

      {/* ── Tools ── */}
      <Section icon={<Wrench size={14} />} title="Herramientas disponibles" count={tools.length}>
        {tools.length > 0 ? (
          tools.map((t, i) => (
            <div key={`tool-${i}`} className="py-1.5 flex items-center gap-2 text-xs text-app-text">
              <Cpu size={12} className="shrink-0 text-app-primary" />
              <span className="truncate">{t.name}</span>
              <span className="shrink-0 text-[10px] px-1.5 py-0.5 rounded bg-app-bg-tertiary text-app-text-secondary ml-auto">
                {t.server}
              </span>
            </div>
          ))
        ) : (
          <p className="text-xs text-app-text-secondary py-1">No hay herramientas disponibles.</p>
        )}
      </Section>

      {/* ── Skills ── */}
      <Section icon={<Puzzle size={14} />} title="Skills disponibles" count={skills.length}>
        {skills.length > 0 ? (
          skills.map((s) => (
            <div key={s.name} className="py-1.5 text-xs text-app-text">
              <span className="font-medium">{s.name}</span>
              {s.description && (
                <span className="block text-app-text-secondary truncate text-[11px] mt-0.5">
                  {s.description}
                </span>
              )}
              {s.triggers && (
                <span className="inline-block mt-0.5 text-[10px] px-1.5 py-0.5 rounded bg-app-bg-tertiary text-app-text-secondary">
                  Triggers: {s.triggers}
                </span>
              )}
            </div>
          ))
        ) : (
          <p className="text-xs text-app-text-secondary py-1">No hay skills instaladas.</p>
        )}
      </Section>

      {/* ── Agents ── */}
      <Section icon={<Brain size={14} />} title="Agentes disponibles" count={agents.length}>
        {agents.length > 0 ? (
          agents.map((a) => (
            <div key={a.name} className="py-1.5 text-xs text-app-text">
              <span className="font-medium">{a.name}</span>
              {a.description && (
                <span className="block text-app-text-secondary truncate text-[11px] mt-0.5">
                  {a.description}
                </span>
              )}
            </div>
          ))
        ) : (
          <p className="text-xs text-app-text-secondary py-1">No hay agentes configurados.</p>
        )}
      </Section>

      {/* ── MCP Servers ── */}
      <Section icon={<Server size={14} />} title="Servidores MCP" count={mcpServers.length}>
        {mcpServers.length > 0 ? (
          mcpServers.map((server) => {
            const health = mcpHealth[server.label];
            const isConnected = health?.status === "connected";
            const isFailed = health?.status === "failed";

            return (
              <div key={server.label} className="py-1.5 flex items-center gap-2 text-xs text-app-text">
                {server.transport === "http" ? (
                  <Globe size={12} className="shrink-0 text-app-primary" />
                ) : (
                  <Database size={12} className="shrink-0 text-app-primary" />
                )}
                <span className="truncate">{server.label}</span>
                <span className={`shrink-0 ml-auto text-[10px] px-1.5 py-0.5 rounded font-medium ${
                  isConnected
                    ? "bg-app-primary/10 text-app-primary"
                    : isFailed
                    ? "bg-app-error/10 text-app-error"
                    : "bg-app-bg-tertiary text-app-text-secondary"
                }`}>
                  {isConnected ? "Conectado" : isFailed ? "Error" : "Desconocido"}
                </span>
              </div>
            );
          })
        ) : (
          <p className="text-xs text-app-text-secondary py-1">No hay servidores MCP configurados.</p>
        )}
      </Section>

    </div>
  );
}

// ─── Section component with colored header ───

function Section({
  icon,
  title,
  count,
  children,
}: {
  icon: React.ReactNode;
  title: string;
  count: number;
  children: React.ReactNode;
}) {
  return (
    <div className="rounded-lg overflow-hidden border border-app-border">
      {/* Colored header */}
      <div className="flex items-center gap-1.5 px-3 py-2 bg-gradient-to-r from-app-primary to-app-gradient-secondary">
        <span className="text-app-primary-text shrink-0">{icon}</span>
        <span className="text-xs font-medium text-app-primary-text truncate">{title}</span>
        {count > 0 && (
          <span className="inline-flex items-center justify-center min-w-[16px] h-4 px-1 rounded-full text-[9px] font-medium ml-auto bg-white text-app-primary">
            {count}
          </span>
        )}
      </div>
      {/* White content */}
      <div className="px-3 py-1.5 bg-white">
        {children}
      </div>
    </div>
  );
}

export default AgentInfoTab;
