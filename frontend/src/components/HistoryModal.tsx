import { useState, useEffect, useCallback, useRef } from "react";
import { Search } from "lucide-react";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from "./ui/dialog";
import { Button } from "./ui/button";
import { Input } from "./ui/input";
import quoteHistoryService from "../services/quoteHistoryService";
import type { Quote } from "../services/quoteHistoryService";

interface HistoryModalProps {
  open: boolean;
  onClose: () => void;
}

// Module-level helpers to avoid recreation on every render
function formatCurrency(value: number): string {
  return new Intl.NumberFormat("es-AR", {
    style: "currency",
    currency: "ARS",
    minimumFractionDigits: 2,
  }).format(value);
}

function formatDate(dateStr: string): string {
  try {
    const d = new Date(dateStr);
    if (isNaN(d.getTime())) return dateStr;
    return d.toLocaleDateString("es-AR", {
      day: "2-digit",
      month: "2-digit",
      year: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  } catch {
    return dateStr;
  }
}

export function HistoryModal({ open, onClose }: HistoryModalProps) {
  const [quotes, setQuotes] = useState<Quote[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [cliente, setCliente] = useState("");
  const [producto, setProducto] = useState("");
  const [desde, setDesde] = useState("");
  const [hasta, setHasta] = useState("");
  const abortRef = useRef<AbortController | null>(null);

  const fetchHistory = useCallback(async () => {
    // Cancel any in-flight request
    if (abortRef.current) {
      abortRef.current.abort();
    }
    abortRef.current = new AbortController();

    setLoading(true);
    setError(null);

    const signal = abortRef.current?.signal;

    try {
      const result = await quoteHistoryService.getHistory({
        cliente: cliente || undefined,
        producto: producto || undefined,
        desde: desde || undefined,
        hasta: hasta || undefined,
      }, signal);
      setQuotes(result);
    } catch (err: unknown) {
      // Ignore aborted requests
      if (err instanceof DOMException && err.name === "AbortError") return;
      const message =
        err instanceof Error
          ? err.message
          : "Error al obtener el historial.";
      setError(message);
      setQuotes([]);
    } finally {
      setLoading(false);
    }
  }, [cliente, producto, desde, hasta]);

  // Load history when modal opens (only on open toggle, not on every filter change)
  useEffect(() => {
    if (open) {
      fetchHistory();
    }
    // Cleanup: abort any in-flight request on unmount or modal close
    return () => {
      if (abortRef.current) {
        abortRef.current.abort();
      }
    };
    // Only trigger on open/close, not when fetchHistory reference changes
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open]);

  return (
    <Dialog open={open} onOpenChange={(o) => !o && onClose()}>
      <DialogContent className="max-w-4xl max-h-[80vh] flex flex-col">
        <DialogHeader>
          <DialogTitle>Historial de Cotizaciones</DialogTitle>
          <DialogDescription>
            Consultá las cotizaciones realizadas. Usá los filtros para
            encontrar resultados específicos.
          </DialogDescription>
        </DialogHeader>

        {/* Filters */}
        <div className="flex flex-wrap gap-2 py-4">
          <Input
            placeholder="Cliente"
            value={cliente}
            onChange={(e) => setCliente(e.target.value)}
            className="w-40"
          />
          <Input
            placeholder="Producto"
            value={producto}
            onChange={(e) => setProducto(e.target.value)}
            className="w-40"
          />
          <Input
            type="date"
            placeholder="Desde"
            value={desde}
            onChange={(e) => setDesde(e.target.value)}
            className="w-36"
          />
          <Input
            type="date"
            placeholder="Hasta"
            value={hasta}
            onChange={(e) => setHasta(e.target.value)}
            className="w-36"
          />
          <Button onClick={fetchHistory} disabled={loading} className="gap-2">
            <Search className="h-4 w-4" />
            Buscar
          </Button>
        </div>

        {/* Error state */}
        {error && (
          <div className="mb-4 px-3 py-2 rounded-md text-xs bg-app-error text-white">
            {error}
          </div>
        )}

        {/* Results table */}
        <div className="flex-1 overflow-y-auto">
          {loading ? (
            <div className="text-center py-8 text-app-text-secondary">
              Cargando...
            </div>
          ) : quotes.length === 0 && !error ? (
            <div className="text-center py-8 text-app-text-secondary">
              No hay cotizaciones registradas.
            </div>
          ) : quotes.length > 0 ? (
            <table className="w-full text-sm">
              <thead className="sticky top-0 bg-white">
                <tr className="border-b border-app-border">
                  <th className="text-left py-2 px-3 font-medium text-app-text-secondary">
                    Fecha
                  </th>
                  <th className="text-left py-2 px-3 font-medium text-app-text-secondary">
                    Cliente
                  </th>
                  <th className="text-left py-2 px-3 font-medium text-app-text-secondary">
                    Producto
                  </th>
                  <th className="text-right py-2 px-3 font-medium text-app-text-secondary">
                    Cant.
                  </th>
                  <th className="text-right py-2 px-3 font-medium text-app-text-secondary">
                    P. Unit.
                  </th>
                  <th className="text-right py-2 px-3 font-medium text-app-text-secondary">
                    Desc.
                  </th>
                  <th className="text-right py-2 px-3 font-medium text-app-text-secondary">
                    Total
                  </th>
                </tr>
              </thead>
              <tbody>
                {quotes.map((q, idx) => (
                  <tr
                    key={q.id || `quote-${idx}`}
                    className="border-b border-app-border hover:bg-app-bg-secondary transition-colors"
                  >
                    <td className="py-2 px-3 text-app-text-secondary">
                      {formatDate(q.fecha)}
                    </td>
                    <td className="py-2 px-3">{q.cliente}</td>
                    <td className="py-2 px-3 max-w-[200px] truncate">
                      {q.producto}
                    </td>
                    <td className="py-2 px-3 text-right">{q.cantidad}</td>
                    <td className="py-2 px-3 text-right">
                      {formatCurrency(q.precio_unitario)}
                    </td>
                    <td className="py-2 px-3 text-right">{q.descuento}%</td>
                    <td className="py-2 px-3 text-right font-semibold">
                      {formatCurrency(q.total)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          ) : null}
        </div>
      </DialogContent>
    </Dialog>
  );
}

export default HistoryModal;
