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
}

export interface ProvidersResponse {
  status: string;
  providers: Array<{ provider: string; label: string }>;
}

export interface McpServer {
  label: string;
  description: string;
  transport: string;
  command: string;
  args: string[];
  disabled: boolean;
}

export interface McpServerHealth {
  label: string;
  status: "connected" | "failed" | "disabled" | "not_configured";
  error?: string;
  tools_count?: number;
  tools?: string[];
  note?: string;
}

export interface McpServersResponse {
  status: string;
  servers: McpServer[];
}

export interface McpHealthResponse {
  status: string;
  servers: McpServerHealth[];
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

  /** List configured MCP servers. */
  async getMcpServers(): Promise<McpServersResponse> {
    const response = await fetch(`${API_BASE_URL}/api/config/mcp/servers`, {
      method: "GET",
    });
    if (!response.ok) {
      throw new Error(`HTTP ${response.status}: ${response.statusText}`);
    }
    return response.json();
  },

  /** Check health of all configured MCP servers. */
  async getMcpHealth(): Promise<McpHealthResponse> {
    const response = await fetch(`${API_BASE_URL}/api/config/mcp/health`, {
      method: "GET",
    });
    if (!response.ok) {
      throw new Error(`HTTP ${response.status}: ${response.statusText}`);
    }
    return response.json();
  },
};

export default configService;
