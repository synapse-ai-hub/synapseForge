const API_BASE_URL = import.meta.env.VITE_URL_BASE || "http://localhost:8000";

export interface SessionMetrics {
  total_sessions: number;
  total_messages: number;
  avg_messages_per_session: number;
  sessions_by_day: { date: string; count: number }[];
}

export interface ToolMetrics {
  tool_usage: { name: string; count: number }[];
  total_tool_calls: number;
  top_subagents: { name: string; count: number }[];
}

export interface ModelMetrics {
  models: { model: string; count: number }[];
  total_model_calls: number;
}

export interface ErrorMetrics {
  total_errors: number;
  errors_by_day: { date: string; count: number }[];
  errors_by_source: { source: string; count: number }[];
}

export interface MetricsOverview {
  total_sessions: number;
  total_messages: number;
  avg_messages_per_session: number;
  total_errors: number;
  top_tools: { name: string; count: number }[];
  sessions_by_day: { date: string; count: number }[];
}

/**
 * Fetch a metrics endpoint and unwrap the unified contract response.
 *
 * Args:
 *   path: API path relative to the base URL (e.g. "/api/metrics/sessions").
 *   errorMessage: Message used when the backend reports an error status.
 *
 * Returns:
 *   The ``data`` payload of the contract response.
 *
 * Throws:
 *   Error: When the HTTP request fails or the backend returns
 *     ``status: "error"``.
 */
async function fetchMetric<T>(path: string, errorMessage: string): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    method: "GET",
  });
  if (!response.ok) {
    throw new Error(`HTTP ${response.status}: ${response.statusText}`);
  }
  const result = await response.json();
  if (result.status === "error") {
    throw new Error(result.message || errorMessage);
  }
  return result.data as T;
}

const metricsService = {
  /** Get session-level metrics. */
  async getSessionMetrics(): Promise<SessionMetrics> {
    return fetchMetric<SessionMetrics>(
      "/api/metrics/sessions",
      "Error fetching session metrics",
    );
  },

  /** Get tool usage metrics. */
  async getToolMetrics(): Promise<ToolMetrics> {
    return fetchMetric<ToolMetrics>(
      "/api/metrics/tools",
      "Error fetching tool metrics",
    );
  },

  /** Get LLM usage metrics grouped by model. */
  async getModelMetrics(): Promise<ModelMetrics> {
    return fetchMetric<ModelMetrics>(
      "/api/metrics/models",
      "Error fetching model metrics",
    );
  },

  /** Get error metrics. */
  async getErrorMetrics(): Promise<ErrorMetrics> {
    return fetchMetric<ErrorMetrics>(
      "/api/metrics/errors",
      "Error fetching error metrics",
    );
  },

  /** Get a combined overview of all metrics. */
  async getOverview(): Promise<MetricsOverview> {
    return fetchMetric<MetricsOverview>(
      "/api/metrics/overview",
      "Error fetching metrics overview",
    );
  },
};

export default metricsService;
