import { Wrench, Puzzle, Bot } from "lucide-react";
import { Button } from "./ui/button";

export function CreateTab() {
  return (
    <div className="flex-1 overflow-y-auto p-4 space-y-4">
      <div className="text-xs font-medium text-app-text-secondary">
        Crear herramientas, skills y agentes
      </div>
      <p className="text-[11px] text-app-text-secondary">
        Esta funcionalidad está disponible en modo dev. Selecciona qué tipo de elemento crear y sigue las instrucciones.
      </p>
      <div className="space-y-2">
        <Button className="w-full justify-start gap-2" variant="outline">
          <Wrench size={14} />
          Crear Tool
        </Button>
        <Button className="w-full justify-start gap-2" variant="outline">
          <Puzzle size={14} />
          Crear Skill
        </Button>
        <Button className="w-full justify-start gap-2" variant="outline">
          <Bot size={14} />
          Crear Agente
        </Button>
      </div>
    </div>
  );
}

export default CreateTab;