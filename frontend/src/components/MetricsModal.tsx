import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from "./ui/dialog";
import { Button } from "./ui/button";
import { useEffect, useState } from "react";
import { BarChart3, MessageSquare, Activity, AlertCircle, RefreshCw } from "lucide-react";
import metricsService, {
  type MetricsOverview,
  type SessionMetrics,
  type ToolMetrics,
  type ErrorMetrics,
} from "../services/metricsService";

interface MetricsModalProps {
  open: boolean;
  onClose: () => void;
}

export function MetricsModal({ open, onClose }: MetricsModalProps) {
  const [activeTab, setActiveTab] = useState<"overview" | "sessions" | "tools" | "errors">("overview");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Overview data
  const [overview, setOverview] = useState<MetricsOverview | null>(null);
  const [sessionMetrics, setSessionMetrics] = useState<SessionMetrics | null>(null);
  const [toolMetrics, setToolMetrics] = useState<ToolMetrics | null>(null);
  const [errorMetrics, setErrorMetrics] = useState<ErrorMetrics | null>(null);

  const loadAll = async () => {
    setLoading(true);
    setError(null);
    try {
      const [ov, sm, tm, em] = await Promise.all([
        metricsService.getOverview().catch(() => null),
        metricsService.getSessionMetrics().catch(() => null),
        metricsService.getToolMetrics().catch(() => null),
        metricsService.getErrorMetrics().catch(() => null),
      ]);
      setOverview(ov);
      setSessionMetrics(sm);
      setToolMetrics(tm);
      setErrorMetrics(em);
    } catch (err) {
      setError("Error al cargar métricas");
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (open) {
      loadAll();
    }
  }, [open]);

  // Simple bar chart component using CSS
  const BarChart = ({ data, maxValue, labelKey, valueKey }: {
    data: { [key: string]: string | number }[];
    maxValue: number;
    labelKey: string;
    valueKey: string;
  }) => {
    if (!data || data.length === 0) {
      return <div className="text-center py-4 text-sm text-app-text-secondary">No hay datos</div>;
    }
    const barHeight = 8; // min height in rem units for scale
    return (
      <div className="space-y-2">
        {data.map((item, i) => {
          const val = Number(item[valueKey]) || 0;
          const pct = maxValue > 0 ? (val / maxValue) * 100 : 0;
          return (
            <div key={i} className="flex items-center gap-2 text-xs">
              <div className="w-24 truncate text-app-text-secondary">
                {String(item[labelKey])}
              </div>
               <div className="flex-1 flex items-end">
                 <div
                   className="h-2 rounded transition-all"
                   style={{ width: `${Math.max(pct, 2)}%`, backgroundColor: "#2a23d6" }}
                 />
              </div>
              <div className="w-8 text-right text-app-text-secondary">{val}</div>
            </div>
          );
        })}
      </div>
    );
  };

  // Line chart for sessions by day
  const LineChart = ({ data }: { data: { date: string; count: number }[] }) => {
    if (!data || data.length === 0) {
      return <div className="text-center py-4 text-sm text-app-text-secondary">No hay datos</div>;
    }
    const maxCount = Math.max(...data.map(d => d.count), 1);
    const chartHeight = 80;
    const chartWidth = Math.max(data.length * 20, 200);

    const points = data.map((d, i) => {
      const x = (i / Math.max(data.length - 1, 1)) * chartWidth;
      const y = chartHeight - (d.count / maxCount) * chartHeight;
      return `${x},${y}`;
    }).join(" ");

    return (
      <div className="overflow-x-auto">
        <svg width={chartWidth} height={chartHeight + 20} className="w-full h-auto">
          {/* Grid lines */}
          {[0, 25, 50, 75, 100].map(pct => {
            const y = chartHeight - (pct / 100) * chartHeight;
            return (
              <line
                key={pct}
                x1="0"
                y1={y}
                x2={chartWidth}
                y2={y}
                stroke="#e5e7eb"
                strokeWidth="1"
              />
            );
          })}
          {/* Line */}
          <polyline
            points={points}
            fill="none"
            stroke="#2563eb"
            strokeWidth="2"
            strokeLinejoin="round"
          />
          {/* Points */}
          {data.map((d, i) => {
            const x = (i / Math.max(data.length - 1, 1)) * chartWidth;
            const y = chartHeight - (d.count / maxCount) * chartHeight;
            return (
              <circle key={i} cx={x} cy={y} r="3" fill="#2563eb" />
            );
          })}
          {/* X axis labels */}
          {data.map((d, i) => {
            if (i % Math.ceil(data.length / 6) !== 0 && i !== data.length - 1) return null;
            const x = (i / Math.max(data.length - 1, 1)) * chartWidth;
            return (
              <text key={i} x={x} y={chartHeight + 15} textAnchor="middle" fontSize="9" fill="#9ca3af">
                {d.date}
              </text>
            );
          })}
        </svg>
      </div>
    );
  };

  const StatCard = ({
    title,
    value,
    icon,
    color = "text-app-primary",
  }: {
    title: string;
    value: string | number;
    icon: React.ReactNode;
    color?: string;
  }) => (
    <div className="bg-white rounded-lg border border-app-border p-3">
      <div className="flex items-center gap-2 text-xs text-app-text-secondary mb-1">
        {icon}
        {title}
      </div>
      <div className={`text-2xl font-bold ${color}`}>{value}</div>
    </div>
  );

  if (!open) return null;

  return (
    <Dialog open={open} onOpenChange={(o) => !o && onClose()}>
      <DialogContent className="max-w-4xl w-[640px] h-[600px] flex flex-col p-0 gap-0">
        <DialogHeader className="px-6 pt-6 pb-4">
          <DialogTitle className="flex items-center gap-2">
            <BarChart3 size={20} />
            Métricas del agente
          </DialogTitle>
          <DialogDescription>
            Estadísticas de uso, herramientas y errores.
          </DialogDescription>
                </DialogHeader>

        {/* Tabs */}
        <div className="flex border-b" style={{ borderColor: "#ded7e1" }}>          <button
            onClick={() => setActiveTab("overview")}
            className="px-4 py-2 text-sm font-medium"
            style={{
              borderBottomWidth: activeTab === "overview" ? "2px" : "0px",
              borderBottomStyle: "solid",
              borderBottomColor: activeTab === "overview" ? "#8c3f9b" : "transparent",
              color: activeTab === "overview" ? "#8c3f9b" : "#6b7280",
              cursor: "pointer",
            }}
            onMouseEnter={(e) => {
              if (activeTab !== "overview") {
                e.currentTarget.style.color = "#8c3f9b";
              }
            }}
            onMouseLeave={(e) => {
              if (activeTab !== "overview") {
                e.currentTarget.style.color = "#6b7280";
              }
            }}
          >
            Overview
          </button>
          <button
            onClick={() => setActiveTab("sessions")}
            className="px-4 py-2 text-sm font-medium"
            style={{
              borderBottomWidth: activeTab === "sessions" ? "2px" : "0px",
              borderBottomStyle: "solid",
              borderBottomColor: activeTab === "sessions" ? "#8c3f9b" : "transparent",
              color: activeTab === "sessions" ? "#8c3f9b" : "#6b7280",
              cursor: "pointer",
            }}
            onMouseEnter={(e) => {
              if (activeTab !== "sessions") {
                e.currentTarget.style.color = "#8c3f9b";
              }
            }}
            onMouseLeave={(e) => {
              if (activeTab !== "sessions") {
                e.currentTarget.style.color = "#6b7280";
              }
            }}
          >
            Conversaciones
          </button>
          <button
            onClick={() => setActiveTab("tools")}
            className="px-4 py-2 text-sm font-medium"
            style={{
              borderBottomWidth: activeTab === "tools" ? "2px" : "0px",
              borderBottomStyle: "solid",
              borderBottomColor: activeTab === "tools" ? "#8c3f9b" : "transparent",
              color: activeTab === "tools" ? "#8c3f9b" : "#6b7280",
              cursor: "pointer",
            }}
            onMouseEnter={(e) => {
              if (activeTab !== "tools") {
                e.currentTarget.style.color = "#8c3f9b";
              }
            }}
            onMouseLeave={(e) => {
              if (activeTab !== "tools") {
                e.currentTarget.style.color = "#6b7280";
              }
            }}
          >
            Herramientas
          </button>
          <button
            onClick={() => setActiveTab("errors")}
            className="px-4 py-2 text-sm font-medium"
            style={{
              borderBottomWidth: activeTab === "errors" ? "2px" : "0px",
              borderBottomStyle: "solid",
              borderBottomColor: activeTab === "errors" ? "#8c3f9b" : "transparent",
              color: activeTab === "errors" ? "#8c3f9b" : "#6b7280",
              cursor: "pointer",
            }}
            onMouseEnter={(e) => {
              if (activeTab !== "errors") {
                e.currentTarget.style.color = "#8c3f9b";
              }
            }}
            onMouseLeave={(e) => {
              if (activeTab !== "errors") {
                e.currentTarget.style.color = "#6b7280";
              }
            }}
          >
            Errores
          </button>
        </div>

        {/* Content - fixed height with scroll */}
        <div className="flex-1 overflow-y-auto py-4 pr-6 min-h-0 space-y-4" style={{ paddingLeft: "40px" }}>
        {loading ? (
          <div className="text-center py-8 text-sm text-app-text-secondary">
            Cargando métricas...
          </div>
        ) : error ? (
          <div className="text-center py-8 text-sm text-app-error">
            {error}
          </div>
        ) : (
          <>
            {/* Overview Tab */}
              {activeTab === "overview" && overview && (
                <div className="space-y-4">
                  <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                    <StatCard
                      title="Sesiones"
                      value={overview.total_sessions}
                      icon={<MessageSquare size={14} />}
                    />
                    <StatCard
                      title="Mensajes"
                      value={overview.total_messages}
                      icon={<Activity size={14} />}
                    />
                    <StatCard
                      title="Prom. mensajes/sesión"
                      value={overview.avg_messages_per_session}
                      icon={<BarChart3 size={14} />}
                    />
                    <StatCard
                      title="Errores"
                      value={overview.total_errors}
                      icon={<AlertCircle size={14} />}
                      color="text-app-error"
                    />
                  </div>

                  <div>
                    <h4 className="text-xs font-medium text-app-text-secondary mb-2">
                      Herramientas más usadas
                    </h4>
                    <BarChart
                      data={overview.top_tools || []}
                      maxValue={Math.max(...(overview.top_tools || [{ count: 1 }]).map(t => t.count), 1)}
                      labelKey="name"
                      valueKey="count"
                    />
                  </div>

                  <div>
                    <h4 className="text-xs font-medium text-app-text-secondary mb-2">
                      Conversaciones por día (últimos 30 días)
                    </h4>
                    <LineChart data={overview.sessions_by_day || []} />
                  </div>
                </div>
              )}

              {/* Sessions Tab */}
              {activeTab === "sessions" && sessionMetrics && (
                <div className="space-y-4">
                  <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
                    <StatCard
                      title="Total sesiones"
                      value={sessionMetrics.total_sessions}
                      icon={<MessageSquare size={14} />}
                    />
                    <StatCard
                      title="Total mensajes"
                      value={sessionMetrics.total_messages}
                      icon={<Activity size={14} />}
                    />
                    <StatCard
                      title="Prom. mensajes/sesión"
                      value={sessionMetrics.avg_messages_per_session}
                      icon={<BarChart3 size={14} />}
                    />
                  </div>

                  <div>
                    <h4 className="text-xs font-medium text-app-text-secondary mb-2">
                      Conversaciones por día (últimos 30 días)
                    </h4>
                    <LineChart data={sessionMetrics.sessions_by_day || []} />
                  </div>
                </div>
              )}

              {/* Tools Tab */}
              {activeTab === "tools" && toolMetrics && (
                <div className="space-y-4">
                  <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
                    <StatCard
                      title="Total tool calls"
                      value={toolMetrics.total_tool_calls}
                      icon={<Activity size={14} />}
                    />
                    <StatCard
                      title="JSON tool calls"
                      value={toolMetrics.json_tool_calls}
                      icon={<BarChart3 size={14} />}
                    />
                    <StatCard
                      title="Delegaciones (task)"
                      value={toolMetrics.top_subagents?.[0]?.count || 0}
                      icon={<MessageSquare size={14} />}
                    />
                  </div>

                  <div>
                    <h4 className="text-xs font-medium text-app-text-secondary mb-2">
                      Herramientas más usadas
                    </h4>
                    <BarChart
                      data={toolMetrics.tool_usage || []}
                      maxValue={Math.max(...(toolMetrics.tool_usage || [{ count: 1 }]).map(t => t.count), 1)}
                      labelKey="name"
                      valueKey="count"
                    />
                  </div>
                </div>
              )}

              {/* Errors Tab */}
              {activeTab === "errors" && errorMetrics && (
                <div className="space-y-4">
                  <StatCard
                    title="Total errores"
                    value={errorMetrics.total_errors}
                    icon={<AlertCircle size={14} />}
                    color="text-app-error"
                  />

                  <div>
                    <h4 className="text-xs font-medium text-app-text-secondary mb-2">
                      Errores por día (últimos 30 días)
                    </h4>
                    <LineChart data={errorMetrics.errors_by_day || []} />
                  </div>

                  <div>
                    <h4 className="text-xs font-medium text-app-text-secondary mb-2">
                      Errores por origen
                    </h4>
                    <BarChart
                      data={errorMetrics.errors_by_source || []}
                      maxValue={Math.max(...(errorMetrics.errors_by_source || [{ count: 1 }]).map(e => e.count), 1)}
                      labelKey="source"
                      valueKey="count"
                    />
                  </div>
                </div>
              )}
            </>
          )}
        </div>

        {/* Footer */}
        <div className="flex justify-between items-center pt-3 pb-4 pr-6" style={{ borderTopColor: "#ded7e1" }}>
          <button
            onClick={loadAll}
            disabled={loading}
            className="flex items-center gap-2 px-3 py-2 text-sm font-medium"
            style={{
              backgroundColor: loading ? "#f3f4f6" : "#dcfce7",
              color: loading ? "#6b7280" : "#166534",
              borderRadius: "4px",
              cursor: loading ? "not-allowed" : "pointer",
              border: "1px solid transparent",
              marginLeft: "24px",
            }}
            onMouseEnter={(e) => {
              if (!loading) {
                e.currentTarget.style.backgroundColor = "#bbf7d0";
              }
            }}
            onMouseLeave={(e) => {
              if (!loading) {
                e.currentTarget.style.backgroundColor = "#dcfce7";
              }
            }}
          >
            <RefreshCw size={12} className={loading ? "animate-spin" : ""} />
            Actualizar
          </button>
          <button
            onClick={onClose}
            size="sm"
            className="flex items-center gap-2 px-3 py-2 text-sm font-medium"
            style={{
              backgroundColor: "#fef2f2",
              color: "#991b1b",
              borderRadius: "4px",
              cursor: "pointer",
              border: "1px solid transparent",
            }}
            onMouseEnter={(e) => {
              e.currentTarget.style.backgroundColor = "#fee2e2";
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.backgroundColor = "#fef2f2";
            }}
          >
            Cerrar
          </button>
        </div>
      </DialogContent>
    </Dialog>
  );
}

export default MetricsModal;
