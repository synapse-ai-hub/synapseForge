import { useState, useEffect, useCallback, useRef } from "react";
import { Settings, Server, Cpu, Database, Globe, Trash2, Upload } from "lucide-react";
import { Button } from "./ui/button";
import { Input } from "./ui/input";
import configService from "../services/configService";
import contextFilesService, { type ContextFile } from "../services/contextFilesService";

interface ConfigTabProps {
  verboseMode: boolean;
  onVerboseModeChange: (val: boolean) => void;
}

export function ConfigTab({ verboseMode, onVerboseModeChange }: ConfigTabProps) {
  const [providers, setProviders] = useState<Array<{ provider: string; label: string }>>([]);
  const [models, setModels] = useState<string[]>([]);
  const [currentModel, setCurrentModel] = useState<string | null>(null);
  const [selectedProvider, setSelectedProvider] = useState<string>("");
  const [maxTurns, setMaxTurns] = useState<number>(-1);
  const [loading, setLoading] = useState(true);
  const [savingModel, setSavingModel] = useState(false);
  const [savingContext, setSavingContext] = useState(false);
  const [contextFiles, setContextFiles] = useState<ContextFile[]>([]);
  const [uploadingContext, setUploadingContext] = useState(false);
  const contextFileInputRef = useRef<HTMLInputElement>(null);

  const load = useCallback(async (prov?: string) => {
    let label: string | undefined;
    try {
      setLoading(true);
      label = "[ConfigTab] load " + Date.now();
      console.time(label);
      const tProv = "[ConfigTab] getProviders " + Date.now();
      const tModels = "[ConfigTab] getModels " + Date.now();
      const tCW = "[ConfigTab] getContextWindow " + Date.now();
      console.time(tProv);
      console.time(tModels);
      console.time(tCW);
      const [provResp, m, cw] = await Promise.all([
        configService.getProviders().finally(() => console.timeEnd(tProv)),
        configService.getModels(prov).finally(() => console.timeEnd(tModels)),
        configService.getContextWindow().finally(() => console.timeEnd(tCW)),
      ]);
      setProviders(provResp.providers || []);
      setModels(m.models || []);
      setCurrentModel(m.model);
      const effective = prov || m.provider || (provResp.providers?.[0]?.provider ?? "");
      setSelectedProvider(effective);
      setMaxTurns(typeof cw.max_turns === "number" ? cw.max_turns : -1);
    } catch (err) {
      console.error("Error cargando configuración:", err);
    } finally {
      setLoading(false);
      if (label) console.timeEnd(label);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  useEffect(() => {
    contextFilesService.list()
      .then((files) => setContextFiles(files || []))
      .catch((err) => console.error("Error cargando archivos de contexto:", err));
  }, []);

  const handleProviderChange = (value: string) => {
    setSelectedProvider(value);
    load(value);
  };

  const handleSelectModel = async (model: string) => {
    try {
      setSavingModel(true);
      await configService.selectModel(model, selectedProvider);
      setCurrentModel(model);
    } catch (err) {
      console.error("Error seleccionando modelo:", err);
    } finally {
      setSavingModel(false);
    }
  };

  const handleSaveContext = async () => {
    try {
      setSavingContext(true);
      await configService.setContextWindow(maxTurns);
    } catch (err) {
      console.error("Error guardando contexto:", err);
    } finally {
      setSavingContext(false);
    }
  };

  const handleUploadContextFile = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    try {
      setUploadingContext(true);
      await contextFilesService.upload(file);
      const files = await contextFilesService.list();
      setContextFiles(files || []);
    } catch (err) {
      console.error("Error subiendo archivo de contexto:", err);
    } finally {
      setUploadingContext(false);
      if (e.target) e.target.value = "";
    }
  };

  const handleDeleteContextFile = async (id: number) => {
    try {
      await contextFilesService.delete(id);
      setContextFiles((prev) => prev.filter((f) => f.id !== id));
    } catch (err) {
      console.error("Error eliminando archivo de contexto:", err);
    }
  };

  if (loading) {
    return (
      <div className="p-4 text-sm text-app-text-secondary">Cargando...</div>
    );
  }

  return (
    <div className="flex-1 overflow-y-auto p-4 space-y-5">
      <div>
        <div className="text-xs font-medium text-app-text-secondary">
          Proveedor
        </div>
        <select
          value={selectedProvider}
          onChange={(e) => handleProviderChange(e.target.value)}
          className="mt-1 w-full rounded-lg border border-app-border bg-white px-3 py-2 text-sm text-app-text focus:outline-none focus:ring-2 focus:ring-app-primary-light"
        >
          {providers.length === 0 ? (
            <option value="">No hay proveedores disponibles</option>
          ) : (
            providers.map((p) => (
              <option key={p.provider} value={p.provider}>
                {p.label}
              </option>
            ))
          )}
        </select>
      </div>

      <div>
        <div className="text-xs font-medium text-app-text-secondary">
          Modelo
        </div>
        <select
          value={currentModel || ""}
          onChange={(e) => handleSelectModel(e.target.value)}
          disabled={savingModel || models.length === 0}
          className="mt-1 w-full rounded-lg border border-app-border bg-white px-3 py-2 text-sm text-app-text focus:outline-none focus:ring-2 focus:ring-app-primary-light"
        >
          {models.length === 0 ? (
            <option value="">No hay modelos disponibles</option>
          ) : (
            models.map((m) => (
              <option key={m} value={m}>
                {m}
              </option>
            ))
          )}
        </select>
      </div>

      <div>
        <div className="text-xs font-medium text-app-text-secondary">
          Ventana de contexto
        </div>
        <p className="text-[11px] text-app-text-secondary mt-1">
          Controla cuántos turnos de la conversación se recuerdan al responder. -1 = todo el historial.
        </p>
        <div className="flex gap-2 mt-2">
          <Input
            type="number"
            min={-1}
            value={maxTurns}
            onChange={(e) => {
              const v = Number(e.target.value);
              setMaxTurns(Number.isNaN(v) ? -1 : v < -1 ? -1 : v);
            }}
            className="flex-1"
          />
          <Button onClick={handleSaveContext} disabled={savingContext} variant="gradient">
            Guardar
          </Button>
        </div>
      </div>

      <div className="flex items-center justify-between py-2">
        <div>
          <div className="text-xs font-medium text-app-text-secondary">
            Modo verbose
          </div>
          <p className="text-[11px] text-app-text-secondary mt-1">
            Muestra herramientas y sub-agentes en la conversación.
          </p>
        </div>
        <button
          type="button"
          role="switch"
          aria-checked={verboseMode}
          onClick={() => onVerboseModeChange(!verboseMode)}
          className={`relative inline-flex h-5 w-9 shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors focus:outline-none focus:ring-2 focus:ring-app-primary-light ${
            verboseMode ? "bg-app-primary" : "bg-app-bg-tertiary"
          }`}
        >
          <span
            className={`pointer-events-none inline-block h-4 w-4 rounded-full bg-white shadow transition-transform ${
              verboseMode ? "translate-x-4" : "translate-x-0"
            }`}
          />
        </button>
      </div>

      {/* Instrucciones y documentos */}
      <div className="pt-2">
        <div className="text-xs font-medium text-app-text-secondary">
          Instrucciones y documentos
        </div>
        <p className="text-[11px] text-app-text-secondary mt-1">
          Archivos con instrucciones, reglas de comportamiento, reglas de negocio o información que el agente debe conocer al responder.
        </p>
        <div className="mt-2">
          <button
            type="button"
            onClick={() => contextFileInputRef.current?.click()}
            disabled={uploadingContext}
            className="flex w-full cursor-pointer items-center justify-center gap-2 rounded-lg border border-dashed border-app-border bg-white px-3 py-4 text-xs text-app-text-secondary hover:border-app-primary/50 hover:text-app-primary transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
          >
            <Upload size={16} />
            <span>{uploadingContext ? "Subiendo..." : "Subir archivos (PDF, Word, TXT)"}</span>
          </button>
          <input
            ref={contextFileInputRef}
            type="file"
            accept=".pdf,.docx,.doc,.txt,.md,.csv,.json,.yaml,.yml,.xml,.py"
            className="hidden"
            onChange={handleUploadContextFile}
          />
        </div>

        {contextFiles.length > 0 && (
          <div className="mt-3 space-y-1">
            {contextFiles.map((f) => (
              <div
                key={f.id}
                className="flex items-center justify-between rounded-md bg-white px-2 py-1.5 text-xs"
              >
                <span className="truncate text-app-text flex-1 min-w-0">{f.filename}</span>
                <button
                  type="button"
                  onClick={() => handleDeleteContextFile(f.id)}
                  className="ml-2 shrink-0 rounded p-0.5 text-app-text-secondary hover:text-red-500 hover:bg-red-50 transition-colors"
                  aria-label="Eliminar archivo de contexto"
                >
                  <Trash2 size={14} />
                </button>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

export default ConfigTab;