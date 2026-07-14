import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from "./ui/dialog";
import { Button } from "./ui/button";

interface MetricsModalProps {
  open: boolean;
  onClose: () => void;
}

export function MetricsModal({ open, onClose }: MetricsModalProps) {
  return (
    <Dialog open={open} onOpenChange={(o) => !o && onClose()}>
      <DialogContent className="max-w-lg">
        <DialogHeader>
          <DialogTitle>Métricas</DialogTitle>
          <DialogDescription>
            Estadísticas de uso del agente.
          </DialogDescription>
        </DialogHeader>

        <div className="py-10 text-center text-sm text-app-text-secondary">
          Próximamente. La definición de métricas se definirá más adelante.
        </div>

        <div className="flex justify-end">
          <Button onClick={onClose}>Cerrar</Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}

export default MetricsModal;
