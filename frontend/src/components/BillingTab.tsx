import { useState, useEffect, useCallback } from "react";
import { DollarSign, RefreshCw, AlertCircle, ChevronDown } from "lucide-react";

const API_BASE_URL = import.meta.env.VITE_URL_BASE || "http://localhost:8000";

interface SpendRecord {
  provider: string;
  model: string;
  prompt_tokens: number;
  completion_tokens: number;
  total_tokens: number;
  cost_input: number;
  cost_output: number;
  cost_total: number;
  updated_at: string;
}

export function BillingTab() {
  const [providerFilter, setProviderFilter] = useState<string>("");
  const [modelFilter, setModelFilter] = useState<string>("");
  const [spend, setSpend] = useState<SpendRecord[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [configProvider, setConfigProvider] = useState<string>("");
  const [configModel, setConfigModel] = useState<string>("");
  const [limitAmount, setLimitAmount] = useState<string>("");
  const [saving, setSaving] = useState(false);
  const [saveMsg, setSaveMsg] = useState<string | null>(null);

  const providers = Array.from(new Set(spend.map((s) => s.provider))).sort();
  const models = Array.from(
    new Set(spend.filter((s) => s.provider === providerFilter).map((s) => s.model)),
  ).sort();

  const fetchSpend = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const url = new URL(`${API_BASE_URL}/api/spend`);
      if (providerFilter) url.searchParams.set("provider", providerFilter);
      const res = await fetch(url.toString());
      if (!res.ok) throw new Error("Error fetching spend");
      const json = await res.json();
      if (json.status === "error") throw new Error(json.message);
      const records: SpendRecord[] = (json.data?.spend || []).filter(
        (r: SpendRecord) => r.cost_total > 0,
      );
      setSpend(records);
    } catch (err: any) {
      setError(err.message || "Error inesperado");
    } finally {
      setLoading(false);
    }
  }, [providerFilter]);

  useEffect(() => {
    fetchSpend();
  }, [fetchSpend]);

  const handleApply = async () => {
    if (!configProvider || limitAmount === "") return;
    setSaving(true);
    setSaveMsg(null);
    try {
      const url = new URL(`${API_BASE_URL}/api/billing-config`);
      url.searchParams.set("provider", configProvider);
      if (configModel) url.searchParams.set("model", configModel);
      url.searchParams.set("limit_amount", limitAmount);
      const res = await fetch(url.toString(), { method: "POST" });
      const json = await res.json();
      if (!res.ok || json.status === "error") throw new Error(json.message || "Error al guardar");
      setSaveMsg(`Límite configurado: ${configProvider}${configModel ? ` / ${configModel}` : ""} = $${limitAmount}`);
      setLimitAmount("");
    } catch (err: any) {
      setSaveMsg(err.message || "Error al guardar");
    } finally {
      setSaving(false);
    }
  };

  const filteredSpend = spend.filter((s) => {
    const matchProvider = providerFilter ? s.provider === providerFilter : true;
    const matchModel = modelFilter ? s.model === modelFilter : true;
    return matchProvider && matchModel;
  });

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h3 className="text-base font-semibold text-app-text">Facturación</h3>
        <button
          onClick={fetchSpend}
          disabled={loading}
          className="inline-flex items-center gap-1.5 rounded-md px-2.5 py-1.5 text-xs font-medium text-app-text-secondary hover:text-app-primary hover:bg-app-bg-tertiary transition-colors disabled:opacity-50"
          title="Actualizar"
        >
          <RefreshCw size={14} className={loading ? "animate-spin" : ""} />
          Actualizar
        </button>
      </div>

      {error && (
        <div className="flex items-center gap-2 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-app-error">
          <AlertCircle size={16} />
          <span>{error}</span>
        </div>
      )}

      {/* View spend dropdowns */}
      <div className="rounded-lg border border-app-border bg-white p-4">
        <h4 className="mb-3 text-sm font-medium text-app-text">Ver gasto</h4>
        <div className="flex gap-3 mb-4">
          <div className="relative">
            <select
              value={providerFilter}
              onChange={(e) => {
                setProviderFilter(e.target.value);
                setModelFilter("");
              }}
              className="appearance-none rounded-md border border-app-border bg-white px-3 py-2 pr-8 text-sm text-app-text focus:outline-none focus:ring-2 focus:ring-app-primary/20"
            >
              <option value="">Todos los proveedores</option>
              {providers.map((p) => (
                <option key={p} value={p}>
                  {p}
                </option>
              ))}
            </select>
            <ChevronDown size={14} className="pointer-events-none absolute right-2.5 top-2.5 text-app-text-secondary" />
          </div>
          <div className="relative">
            <select
              value={modelFilter}
              onChange={(e) => setModelFilter(e.target.value)}
              disabled={!providerFilter}
              className="appearance-none rounded-md border border-app-border bg-white px-3 py-2 pr-8 text-sm text-app-text focus:outline-none focus:ring-2 focus:ring-app-primary/20 disabled:opacity-50"
            >
              <option value="">Todos los modelos</option>
              {models.map((m) => (
                <option key={m} value={m}>
                  {m}
                </option>
              ))}
            </select>
            <ChevronDown size={14} className="pointer-events-none absolute right-2.5 top-2.5 text-app-text-secondary" />
          </div>
        </div>
        <div className="divide-y divide-app-border">
          {filteredSpend.map((s) => (
            <div key={`${s.provider}-${s.model}`} className="flex items-center justify-between py-2.5 text-sm">
              <div className="flex items-center gap-2">
                <DollarSign size={14} className="text-app-primary" />
                <span className="font-medium text-app-text">
                  {s.provider} / {s.model}
                </span>
              </div>
              <div className="flex gap-4 text-xs text-app-text-secondary">
                <span>Tokens: {s.total_tokens}</span>
                <span>USD: {s.cost_total.toFixed(4)}</span>
              </div>
            </div>
          ))}
          {filteredSpend.length === 0 && (
            <div className="py-3 text-xs text-app-text-secondary">Sin registros de gasto (solo se muestran valores &gt; 0)</div>
          )}
        </div>
      </div>

      {/* Configuration section */}
      <div className="rounded-lg border border-app-border bg-white p-4">
        <h4 className="mb-3 text-sm font-medium text-app-text">Configurar límite</h4>
        <div className="flex flex-wrap gap-3 items-end">
          <div className="flex-1 min-w-[140px]">
            <label htmlFor="provider-select" className="mb-1 block text-xs text-app-text-secondary">Proveedor</label>
            <select
              id="provider-select"
              value={configProvider}
              onChange={(e) => setConfigProvider(e.target.value)}
              className="w-full rounded-md border border-app-border bg-white px-3 py-2 text-sm text-app-text focus:outline-none focus:ring-2 focus:ring-app-primary/20"
            >
              <option value="">Seleccionar</option>
              {providers.map((p) => (
                <option key={p} value={p}>
                  {p}
                </option>
              ))}
            </select>
          </div>
          <div className="flex-1 min-w-[140px]">
            <label htmlFor="model-select" className="mb-1 block text-xs text-app-text-secondary">Modelo (opcional)</label>
            <select
              id="model-select"
              value={configModel}
              onChange={(e) => setConfigModel(e.target.value)}
              disabled={!configProvider}
              className="w-full rounded-md border border-app-border bg-white px-3 py-2 text-sm text-app-text focus:outline-none focus:ring-2 focus:ring-app-primary/20 disabled:opacity-50"
            >
              <option value="">Nivel proveedor</option>
              {Array.from(
                new Set(spend.filter((s) => s.provider === configProvider).map((s) => s.model)),
              ).map((m) => (
                <option key={m} value={m}>
                  {m}
                </option>
              ))}
            </select>
          </div>
          <div className="flex-1 min-w-[140px]">
            <label htmlFor="limit-input" className="mb-1 block text-xs text-app-text-secondary">Monto (USD)</label>
            <input
              id="limit-input"
              type="number"
              min={0}
              step={0.01}
              value={limitAmount}
              onChange={(e) => setLimitAmount(e.target.value)}
              placeholder="0.00"
              className="w-full rounded-md border border-app-border bg-white px-3 py-2 text-sm text-app-text focus:outline-none focus:ring-2 focus:ring-app-primary/20"
            />
          </div>
          <button
            onClick={handleApply}
            disabled={saving || !configProvider || limitAmount === ""}
            className="rounded-md bg-app-primary px-4 py-2 text-sm font-medium text-white hover:bg-app-primary/90 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {saving ? "Aplicando..." : "Aplicar"}
          </button>
        </div>
        {saveMsg && (
          <div className={`mt-3 rounded-md px-3 py-2 text-xs ${saveMsg.startsWith("Límite") ? "bg-green-50 text-green-700" : "bg-red-50 text-red-700"}`}>
            {saveMsg}
          </div>
        )}
      </div>
    </div>
  );
}

export default BillingTab;
