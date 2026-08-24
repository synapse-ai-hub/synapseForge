import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from "./ui/dialog";
import { Button } from "./ui/button";
import { useEffect, useState } from "react";
import {
  BarChart3,
  MessageSquare,
  Activity,
  AlertCircle,
  RefreshCw,
  Cpu,
  Wrench,
} from "lucide-react";
import metricsService, {
  type MetricsOverview,
  type SessionMetrics,
  type ToolMetrics,
  type ModelMetrics,
  type ErrorMetrics,
} from "../services/metricsService";

interface MetricsModalProps {
  open: boolean;
  onClose: () => void;
}

type TabId = "overview" | "sessions" | "tools" | "models" | "errors";

interface MetricsData {
  overview: MetricsOverview | null;
  sessions: SessionMetrics | null;
  tools: ToolMetrics | null;
  models: ModelMetrics | null;
  errors: ErrorMetrics | null;
}

const EMPTY_METRICS: MetricsData = {
  overview: null,
  sessions: null,
  tools: null,
  models: null,
  errors: null,
};

/** Format a number using thousands separators (es-AR locale). */
function formatNumber(value: number): string {
  return value.toLocaleString("es-AR");
}

/** KPI summary card. */
function KpiCard({
  title,
  value,
  icon,
  tone = "default",
}: {
  title: string;
  value: string;
  icon: React.ReactNode;
  tone?: "default" | "error";
}) {
  return (
    <div className="rounded-lg border border-app-border bg-white p-4">
      <div className="mb-1 flex items-center gap-2 text-xs text-app-text-secondary">
        {icon}
        {title}
      </div>
      <div
        className={`text-2xl font-bold ${
          tone === "error" ? "text-app-error" : "text-app-text"
        }`}
      >
        {value}
      </div>
    </div>
  );
}

/** Vertical bar chart (pure CSS/Tailwind) for daily series. */
function DailyBarChart({ data }: { data: { date: string; count: number }[] }) {
  if (!data || data.length === 0) {
    return (
      <div className="py-6 text-center text-sm text-app-text-secondary">
        No hay datos
      </div>
    );
  }
  const maxCount = Math.max(...data.map((d) => d.count), 1);

  return (
    <div className="flex h-40 items-end gap-1 overflow-x-auto rounded-lg border border-app-border bg-app-bg-secondary p-3">
      {data.map((d) => {
        const pct = Math.max((d.count / maxCount) * 100, 4);
        return (
          <div
            key={d.date}
            className="flex min-w-[24px] flex-1 flex-col items-center gap-1"
            title={`${d.date}: ${formatNumber(d.count)}`}
          >
            <span className="text-[10px] font-medium text-app-text-secondary">
              {formatNumber(d.count)}
            </span>
            <div
              className="w-full max-w-[32px] rounded-t bg-app-primary"
              style={{ height: `${pct}%` }}
            />
            <span className="text-[10px] text-app-text-secondary">
              {d.date?.slice(5)}
            </span>
          </div>
        );
      })}
    </div>
  );
}

/** Horizontal ranking bars (pure CSS/Tailwind). */
function RankingBars({
  items,
  emptyLabel = "No hay datos",
}: {
  items: { label: string; count: number }[];
  emptyLabel?: string;
}) {
  if (!items || items.length === 0) {
    return (
      <div className="py-6 text-center text-sm text-app-text-secondary">
        {emptyLabel}
      </div>
    );
  }
  const maxCount = Math.max(...items.map((i) => i.count), 1);

  return (
    <div className="space-y-2">
      {items.map((item) => {
        const pct = Math.max((item.count / maxCount) * 100, 2);
        return (
          <div key={item.label} className="flex items-center gap-3 text-xs">
            <div className="w-40 truncate text-app-text" title={item.label}>
              {item.label}
            </div>
            <div className="h-2.5 flex-1 overflow-hidden rounded-full bg-app-bg-tertiary">
              <div
                className="h-full rounded-full bg-app-primary"
                style={{ width: `${pct}%` }}
              />
            </div>
            <div className="w-14 text-right font-medium text-app-text-secondary">
              {formatNumber(item.count)}
            </div>
          </div>
        );
      })}
    </div>
  );
}

/** Section title inside a tab. */
function SectionTitle({ children }: { children: React.ReactNode }) {
  return (
    <h4 className="mb-2 text-xs font-medium text-app-text-secondary">
      {children}
    </h4>
  );
}

export function MetricsModal({ open, onClose }: MetricsModalProps) {
  const [activeTab, setActiveTab] = useState<TabId>("overview");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [metrics, setMetrics] = useState<MetricsData>(EMPTY_METRICS);

  const loadAll = async () => {
    setLoading(true);
    setError(null);
    try {
      const [overviewRes, sessionsRes, toolsRes, modelsRes, errorsRes] =
        await Promise.allSettled([
          metricsService.getOverview(),
          metricsService.getSessionMetrics(),
          metricsService.getToolMetrics(),
          metricsService.getModelMetrics(),
          metricsService.getErrorMetrics(),
        ]);

      const next: MetricsData = {
        overview: overviewRes.status === "fulfilled" ? overviewRes.value : null,
        sessions: sessionsRes.status === "fulfilled" ? sessionsRes.value : null,
        tools: toolsRes.status === "fulfilled" ? toolsRes.value : null,
        models: modelsRes.status === "fulfilled" ? modelsRes.value : null,
        errors: errorsRes.status === "fulfilled" ? errorsRes.value : null,
      };
      setMetrics(next);

      const allFailed =
        overviewRes.status === "rejected" &&
        sessionsRes.status === "rejected" &&
        toolsRes.status === "rejected" &&
        modelsRes.status === "rejected" &&
        errorsRes.status === "rejected";
      if (allFailed) {
        setError(
          "No se pudieron cargar las métricas. Verificá que el backend esté corriendo e intentá de nuevo.",
        );
      }
    } catch (err) {
      setError("Error inesperado al cargar métricas.");
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

  const tabs: { id: TabId; label: string }[] = [
    { id: "overview", label: "Resumen" },
    { id: "sessions", label: "Conversaciones" },
    { id: "tools", label: "Herramientas" },
    { id: "models", label: "Modelos" },
    { id: "errors", label: "Errores" },
  ];

  return (
    <Dialog open={open} onOpenChange={(o) => !o && onClose()}>
      <DialogContent className="flex h-[620px] max-w-4xl w-[720px] flex-col gap-0 p-0">
        <DialogHeader className="px-6 pt-6 pb-4">
          <DialogTitle className="flex items-center gap-2">
            <BarChart3 size={20} />
            Métricas del agente
          </DialogTitle>
          <DialogDescription>
            Estadísticas de uso, herramientas, modelos y errores.
          </DialogDescription>
        </DialogHeader>

        {/* Tabs */}
        <div className="flex border-b border-app-border">
          {tabs.map((tab) => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={`px-4 py-2 text-sm font-medium transition-colors ${
                activeTab === tab.id
                  ? "border-b-2 border-app-primary text-app-primary"
                  : "border-b-2 border-transparent text-app-text-secondary hover:text-app-primary"
              }`}
            >
              {tab.label}
            </button>
          ))}
        </div>

        {/* Content — fixed height with scroll */}
        <div className="min-h-0 flex-1 space-y-4 overflow-y-auto px-6 py-4">
          {loading ? (
            <div className="flex h-full flex-col items-center justify-center gap-3 text-sm text-app-text-secondary">
              <RefreshCw size={24} className="animate-spin text-app-primary" />
              Cargando métricas...
            </div>
          ) : error ? (
            <div className="flex h-full flex-col items-center justify-center gap-4 text-sm">
              <AlertCircle size={28} className="text-app-error" />
              <p className="text-app-error">{error}</p>
              <Button variant="outline" size="sm" onClick={loadAll}>
                <RefreshCw size={14} className="mr-2" />
                Reintentar
              </Button>
            </div>
          ) : (
            <>
              {/* Overview tab */}
              {activeTab === "overview" && metrics.overview && (
                <div className="space-y-4">
                  <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
                    <KpiCard
                      title="Sesiones"
                      value={formatNumber(metrics.overview.total_sessions)}
                      icon={<MessageSquare size={14} />}
                    />
                    <KpiCard
                      title="Mensajes"
                      value={formatNumber(metrics.overview.total_messages)}
                      icon={<Activity size={14} />}
                    />
                    <KpiCard
                      title="Prom. mensajes/sesión"
                      value={formatNumber(metrics.overview.avg_messages_per_session)}
                      icon={<BarChart3 size={14} />}
                    />
                    <KpiCard
                      title="Errores"
                      value={formatNumber(metrics.overview.total_errors)}
                      icon={<AlertCircle size={14} />}
                      tone="error"
                    />
                  </div>

                  <div>
                    <SectionTitle>Sesiones por día (últimos 30 días)</SectionTitle>
                    <DailyBarChart data={metrics.overview.sessions_by_day || []} />
                  </div>

                  <div>
                    <SectionTitle>Herramientas más usadas</SectionTitle>
                    <RankingBars
                      items={(metrics.overview.top_tools || []).map((t) => ({
                        label: t.name,
                        count: t.count,
                      }))}
                    />
                  </div>
                </div>
              )}

              {/* Sessions tab */}
              {activeTab === "sessions" && metrics.sessions && (
                <div className="space-y-4">
                  <div className="grid grid-cols-2 gap-3 md:grid-cols-3">
                    <KpiCard
                      title="Total sesiones"
                      value={formatNumber(metrics.sessions.total_sessions)}
                      icon={<MessageSquare size={14} />}
                    />
                    <KpiCard
                      title="Total mensajes"
                      value={formatNumber(metrics.sessions.total_messages)}
                      icon={<Activity size={14} />}
                    />
                    <KpiCard
                      title="Prom. mensajes/sesión"
                      value={formatNumber(metrics.sessions.avg_messages_per_session)}
                      icon={<BarChart3 size={14} />}
                    />
                  </div>

                  <div>
                    <SectionTitle>Sesiones por día (últimos 30 días)</SectionTitle>
                    <DailyBarChart data={metrics.sessions.sessions_by_day || []} />
                  </div>
                </div>
              )}

              {/* Tools tab */}
              {activeTab === "tools" && metrics.tools && (
                <div className="space-y-4">
                  <div className="grid grid-cols-2 gap-3 md:grid-cols-3">
                    <KpiCard
                      title="Total tool calls"
                      value={formatNumber(metrics.tools.total_tool_calls)}
                      icon={<Wrench size={14} />}
                    />
                    <KpiCard
                      title="Herramientas distintas"
                      value={formatNumber(metrics.tools.tool_usage?.length ?? 0)}
                      icon={<BarChart3 size={14} />}
                    />
                    <KpiCard
                      title="Delegaciones (task)"
                      value={formatNumber(metrics.tools.top_subagents?.[0]?.count ?? 0)}
                      icon={<MessageSquare size={14} />}
                    />
                  </div>

                  <div>
                    <SectionTitle>Ranking de herramientas</SectionTitle>
                    <RankingBars
                      items={(metrics.tools.tool_usage || []).map((t) => ({
                        label: t.name,
                        count: t.count,
                      }))}
                    />
                  </div>
                </div>
              )}

              {/* Models tab */}
              {activeTab === "models" && metrics.models && (
                <div className="space-y-4">
                  <div className="grid grid-cols-2 gap-3 md:grid-cols-3">
                    <KpiCard
                      title="Llamadas con modelo registrado"
                      value={formatNumber(metrics.models.total_model_calls)}
                      icon={<Cpu size={14} />}
                    />
                    <KpiCard
                      title="Modelos distintos"
                      value={formatNumber(metrics.models.models?.length ?? 0)}
                      icon={<BarChart3 size={14} />}
                    />
                  </div>

                  <div>
                    <SectionTitle>Ranking de modelos</SectionTitle>
                    <RankingBars
                      items={(metrics.models.models || []).map((m) => ({
                        label: m.model,
                        count: m.count,
                      }))}
                      emptyLabel="Sin registros aún: el uso por modelo se registra desde mensajes nuevos."
                    />
                  </div>
                </div>
              )}

              {/* Errors tab */}
              {activeTab === "errors" && metrics.errors && (
                <div className="space-y-4">
                  <div className="grid grid-cols-2 gap-3 md:grid-cols-3">
                    <KpiCard
                      title="Total errores"
                      value={formatNumber(metrics.errors.total_errors)}
                      icon={<AlertCircle size={14} />}
                      tone="error"
                    />
                  </div>

                  <div>
                    <SectionTitle>Errores por día (últimos 30 días)</SectionTitle>
                    <DailyBarChart data={metrics.errors.errors_by_day || []} />
                  </div>

                  <div>
                    <SectionTitle>Errores por origen</SectionTitle>
                    <RankingBars
                      items={(metrics.errors.errors_by_source || []).map((e) => ({
                        label: e.source,
                        count: e.count,
                      }))}
                    />
                  </div>
                </div>
              )}
            </>
          )}
        </div>

        {/* Footer */}
        <div
          className="flex items-center justify-between border-t border-app-border px-6 py-3"
        >
          <Button variant="secondary" size="sm" onClick={loadAll} disabled={loading}>
            <RefreshCw size={12} className={`mr-2 ${loading ? "animate-spin" : ""}`} />
            Actualizar
          </Button>
          <Button variant="outline" size="sm" onClick={onClose}>
            Cerrar
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}

export default MetricsModal;
