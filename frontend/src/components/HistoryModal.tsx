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

        
      </DialogContent>
    </Dialog>
  );
}

export default HistoryModal;
