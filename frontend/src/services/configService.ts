const MODE = import.meta.env.VITE_MODE || "dev";
const API_BASE_URL = MODE === "prod"
  ? (import.meta.env.VITE_URL_PROD || "http://localhost:8000")
  : (import.meta.env.VITE_URL_DEV || "http://localhost:8000");

export interface ModelsResponse {
  status: string;
  provider: string;
  provider_label?: string;
  models: string[];
  model: string | null;
}

export interface ContextWindowResponse {
  status: string;
  max_turns: number;
  context_window_tokens: number | null;
  vram_gb: number | null;
  ollama_default_context: number | null;
}

export interface ProvidersResponse {
  status: string;
  providers: Array<{ provider: string; label: string }>;
}

export interface SkillInfo {
  name: string;
  description: string;
}

export interface ToolInfo {
  name: string;
  description: string;
}

export interface AgentInfo {
  name: string;
  description: string;
}

export interface McpServerStatus {
  label: string;
  status: "connected" | "failed" | "disabled" | "not_configured";
  error?: string;
}

export interface ProviderKeyStatus {
  provider: string;
  configured: boolean;
}

export interface ProviderKeysResponse {
  status: string;
  keys: ProviderKeyStatus[];
}

export interface SetupCompletedResponse {
  status: string;
  completed: boolean;
}

export const configService = {
  /** List available models and the currently selected one. */
  async getModels(provider?: string): Promise<ModelsResponse> {
    const url = provider
      ? `${API_BASE_URL}/api/config/models?provider=${encodeURIComponent(provider)}`
      : `${API_BASE_URL}/api/config/models`;
    const response = await fetch(url, {
      method: "GET",
    });
    if (!response.ok) {
      throw new Error(`HTTP ${response.status}: ${response.statusText}`);
    }
    return response.json();
  },

  /** Select a model for the running agent. */
  async selectModel(model: string, provider: string): Promise<void> {
    const response = await fetch(`${API_BASE_URL}/api/config/models/select`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ model, provider }),
    });
    if (!response.ok) {
      throw new Error(`HTTP ${response.status}: ${response.statusText}`);
    }
    const result = await response.json();
    if (result && result.status === "error") {
      throw new Error(result.message || "Error al seleccionar el modelo");
    }
  },

  /** Get the current context-window turn limit. */
  async getContextWindow(): Promise<ContextWindowResponse> {
    const response = await fetch(`${API_BASE_URL}/api/config/context-window`, {
      method: "GET",
    });
    if (!response.ok) {
      throw new Error(`HTTP ${response.status}: ${response.statusText}`);
    }
    return response.json();
  },

  /** Set the context-window turn limit (-1 = all turns). */
  async setContextWindow(maxTurns: number): Promise<void> {
    const response = await fetch(`${API_BASE_URL}/api/config/context-window`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ max_turns: maxTurns }),
    });
    if (!response.ok) {
      throw new Error(`HTTP ${response.status}: ${response.statusText}`);
    }
    const result = await response.json();
    if (result && result.status === "error") {
      throw new Error(result.message || "Error al guardar el contexto");
    }
  },

  /** Get the current verbose-mode flag. */
  async getVerbose(): Promise<boolean> {
    const response = await fetch(`${API_BASE_URL}/api/config/verbose-mode`, {
      method: "GET",
    });
    if (!response.ok) {
      throw new Error(`HTTP ${response.status}: ${response.statusText}`);
    }
    const result = await response.json();
    return result.verbose_mode === true;
  },

  /** Set the verbose-mode flag. */
  async setVerbose(verboseMode: boolean): Promise<void> {
    const response = await fetch(`${API_BASE_URL}/api/config/verbose-mode`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ verbose_mode: verboseMode }),
    });
    if (!response.ok) {
      throw new Error(`HTTP ${response.status}: ${response.statusText}`);
    }
    const result = await response.json();
    if (result && result.status === "error") {
      throw new Error(result.message || "Error al guardar verbose mode");
    }
  },

  /** List providers that are currently available (Groq, Ollama, …). */
  async getProviders(): Promise<ProvidersResponse> {
    const response = await fetch(`${API_BASE_URL}/api/config/providers`, {
      method: "GET",
    });
    if (!response.ok) {
      throw new Error(`HTTP ${response.status}: ${response.statusText}`);
    }
    return response.json();
  },

  /** List which providers have an API key configured (no key material). */
  async getProviderKeys(): Promise<ProviderKeysResponse> {
    const response = await fetch(`${API_BASE_URL}/api/config/providers/keys`, {
      method: "GET",
    });
    if (!response.ok) {
      throw new Error(`HTTP ${response.status}: ${response.statusText}`);
    }
    return response.json();
  },

  /** Store (encrypted) the API key for a provider. */
  async saveProviderKey(provider: string, apiKey: string): Promise<void> {
    const response = await fetch(
      `${API_BASE_URL}/api/config/providers/${encodeURIComponent(provider)}/key`,
      {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ api_key: apiKey }),
      }
    );
    const result = await response.json();
    if (!response.ok || result.status === "error") {
      throw new Error(result.message || `HTTP ${response.status}`);
    }
  },

  /** Remove the stored API key for a provider. */
  async deleteProviderKey(provider: string): Promise<void> {
    const response = await fetch(
      `${API_BASE_URL}/api/config/providers/${encodeURIComponent(provider)}/key`,
      { method: "DELETE" }
    );
    const result = await response.json();
    if (!response.ok || result.status === "error") {
      throw new Error(result.message || `HTTP ${response.status}`);
    }
  },

  /** Whether the initial provider-setup screen was already completed/skipped. */
  async getSetupCompleted(): Promise<SetupCompletedResponse> {
    const response = await fetch(`${API_BASE_URL}/api/config/setup-completed`, {
      method: "GET",
    });
    if (!response.ok) {
      throw new Error(`HTTP ${response.status}: ${response.statusText}`);
    }
    return response.json();
  },

  /** Mark the initial provider-setup screen as completed (or skipped). */
  async markSetupCompleted(): Promise<void> {
    const response = await fetch(`${API_BASE_URL}/api/config/setup-completed`, {
      method: "POST",
    });
    if (!response.ok) {
      throw new Error(`HTTP ${response.status}: ${response.statusText}`);
    }
  },

  /** List available skills (name + description). */
  async getSkills(): Promise<SkillInfo[]> {
    const response = await fetch(`${API_BASE_URL}/api/config/skills`, {
      method: "GET",
    });
    if (!response.ok) {
      throw new Error(`HTTP ${response.status}: ${response.statusText}`);
    }
    const data = await response.json();
    return data.skills || [];
  },

  /** List all available tools (native + external, no MCP). */
  async getTools(): Promise<ToolInfo[]> {
    const response = await fetch(`${API_BASE_URL}/api/config/tools`, {
      method: "GET",
    });
    if (!response.ok) {
      throw new Error(`HTTP ${response.status}: ${response.statusText}`);
    }
    const data = await response.json();
    return data.tools || [];
  },

  /** Force rebuild of the tools registry and return updated list. */
  async refresh(): Promise<ToolInfo[]> {
    const response = await fetch(`${API_BASE_URL}/api/config/tools/refresh`, {
      method: "POST",
    });
    if (!response.ok) {
      throw new Error(`HTTP ${response.status}: ${response.statusText}`);
    }
    const data = await response.json();
    return data.tools || [];
  },

  /** List available sub-agents. */
  async getAgents(): Promise<AgentInfo[]> {
    const response = await fetch(`${API_BASE_URL}/api/config/agents`, {
      method: "GET",
    });
    if (!response.ok) {
      throw new Error(`HTTP ${response.status}: ${response.statusText}`);
    }
    const data = await response.json();
    return data.agents || [];
  },

  /** List MCP servers with connection status. */
  async getMcp(): Promise<McpServerStatus[]> {
    const response = await fetch(`${API_BASE_URL}/api/config/mcp`, {
      method: "GET",
    });
    if (!response.ok) {
      throw new Error(`HTTP ${response.status}: ${response.statusText}`);
    }
    const data = await response.json();
    return data.servers || [];
  },

  // ── Delete endpoints ─────────────────────────────────────────────

  /** Delete a skill by name. */
  async deleteSkill(name: string): Promise<void> {
    const response = await fetch(
      `${API_BASE_URL}/api/agent/skills/${encodeURIComponent(name)}`,
      { method: "DELETE" }
    );
    if (!response.ok) {
      const data = await response.json();
      throw new Error(data.message || `HTTP ${response.status}`);
    }
  },

  /** Delete an external tool by name. */
  async deleteTool(name: string): Promise<void> {
    const response = await fetch(
      `${API_BASE_URL}/api/agent/tools/${encodeURIComponent(name)}`,
      { method: "DELETE" }
    );
    if (!response.ok) {
      const data = await response.json();
      throw new Error(data.message || `HTTP ${response.status}`);
    }
  },

  /** Delete an agent by name. */
  async deleteAgent(name: string): Promise<void> {
    const response = await fetch(
      `${API_BASE_URL}/api/agent/agents/${encodeURIComponent(name)}`,
      { method: "DELETE" }
    );
    if (!response.ok) {
      const data = await response.json();
      throw new Error(data.message || `HTTP ${response.status}`);
    }
  },

  /** Delete an MCP server by label. */
  async deleteMcp(label: string): Promise<void> {
    const response = await fetch(
      `${API_BASE_URL}/api/agent/mcp/${encodeURIComponent(label)}`,
      { method: "DELETE" }
    );
    if (!response.ok) {
      const data = await response.json();
      throw new Error(data.message || `HTTP ${response.status}`);
    }
  },

  /** List knowledge collections. */
  async listKnowledge(): Promise<string[]> {
    const response = await fetch(`${API_BASE_URL}/api/agent/knowledge`, {
      method: "GET",
    });
    if (!response.ok) {
      return [];
    }
    const data = await response.json();
    return data.collections || [];
  },

  /** Delete a knowledge collection by name. */
  async deleteKnowledge(collection: string): Promise<void> {
    const response = await fetch(
      `${API_BASE_URL}/api/agent/knowledge/${encodeURIComponent(collection)}`,
      { method: "DELETE" }
    );
    if (!response.ok) {
      const data = await response.json();
      throw new Error(data.message || `HTTP ${response.status}`);
    }
  },
};

export default configService;
