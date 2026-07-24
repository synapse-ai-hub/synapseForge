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
  json_tool_calls: number;
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

const metricsService = {
  /** Get session-level metrics. */
  async getSessionMetrics(): Promise<SessionMetrics> {
    const response = await fetch(`${API_BASE_URL}/api/metrics/sessions`, {
      method: "GET",
    });
    if (!response.ok) {
      throw new Error(`HTTP ${response.status}: ${response.statusText}`);
    }
    const result = await response.json();
    if (result.status === "error") {
      throw new Error(result.message || "Error fetching session metrics");
    }
    return result.data;
  },

  /** Get tool usage metrics. */
  async getToolMetrics(): Promise<ToolMetrics> {
    const response = await fetch(`${API_BASE_URL}/api/metrics/tools`, {
      method: "GET",
    });
    if (!response.ok) {
      throw new Error(`HTTP ${response.status}: ${response.statusText}`);
    }
    const result = await response.json();
    if (result.status === "error") {
      throw new Error(result.message || "Error fetching tool metrics");
    }
    return result.data;
  },

  /** Get error metrics. */
  async getErrorMetrics(): Promise<ErrorMetrics> {
    const response = await fetch(`${API_BASE_URL}/api/metrics/errors`, {
      method: "GET",
    });
    if (!response.ok) {
      throw new Error(`HTTP ${response.status}: ${response.statusText}`);
    }
    const result = await response.json();
    if (result.status === "error") {
      throw new Error(result.message || "Error fetching error metrics");
    }
    return result.data;
  },

  /** Get a combined overview of all metrics. */
  async getOverview(): Promise<MetricsOverview> {
    const response = await fetch(`${API_BASE_URL}/api/metrics/overview`, {
      method: "GET",
    });
    if (!response.ok) {
      throw new Error(`HTTP ${response.status}: ${response.statusText}`);
    }
    const result = await response.json();
    if (result.status === "error") {
      throw new Error(result.message || "Error fetching metrics overview");
    }
    return result.data;
  },
};

export default metricsService;
