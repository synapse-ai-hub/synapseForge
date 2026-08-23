import { useCallback, useEffect, useState } from "react";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from "./ui/dialog";
import {
  AlarmClock,
  Plus,
  Trash2,
  Pencil,
  Clock,
  Check,
  X,
} from "lucide-react";
import schedulerService, { SchedulerTask } from "../services/schedulerService";

interface SchedulerModalProps {
  open: boolean;
  onClose: () => void;
}

const WEEKDAY_LABELS = ["D", "L", "M", "X", "J", "V", "S"];
const ALL_DAYS = [0, 1, 2, 3, 4, 5, 6];

/** Read the system timezone (no configuration needed). */
function getSystemTimezone(): string {
  try {
    return Intl.DateTimeFormat().resolvedOptions().timeZone || "—";
  } catch {
    return "—";
  }
}

/** Format "HH:MM" plus the selected days as a human-readable schedule. */
function formatSchedule(time: string, days: number[]): string {
  const sorted = [...days].sort((a, b) => a - b);
  if (sorted.length === 7) return `Todos los días a las ${time}`;
  const labels = sorted.map((d) => WEEKDAY_LABELS[d]).join(" ");
  return `${labels} · ${time}`;
}

export function SchedulerModal({ open, onClose }: SchedulerModalProps) {
  const [tasks, setTasks] = useState<SchedulerTask[]>([]);
  const [timezone] = useState<string>(getSystemTimezone);

  /* ---- add-task form ---- */
  const [newPrompt, setNewPrompt] = useState("");
  const [newTime, setNewTime] = useState("09:00");
  const [newDays, setNewDays] = useState<number[]>(ALL_DAYS);
  const [formError, setFormError] = useState<string | null>(null);

  /* ---- inline schedule editing ---- */
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editTime, setEditTime] = useState("09:00");
  const [editDays, setEditDays] = useState<number[]>(ALL_DAYS);
  const [editError, setEditError] = useState<string | null>(null);

  /* ---- save feedback ---- */
  const [savedMsg, setSavedMsg] = useState<string | null>(null);
  const [saveError, setSaveError] = useState<string | null>(null);

  /* ---- reload tasks from the backend ---- */
  const reloadTasks = useCallback(async () => {
    try {
      setTasks(await schedulerService.getTasks());
    } catch (err) {
      setSaveError(err instanceof Error ? err.message : "Error cargando las tareas.");
    }
  }, []);

  /* Load persisted tasks each time the modal opens */
  useEffect(() => {
    if (open) {
      setSavedMsg(null);
      setSaveError(null);
      setFormError(null);
      setEditingId(null);
      reloadTasks();
    }
  }, [open, reloadTasks]);

  /* Auto-dismiss the saved confirmation */
  useEffect(() => {
    if (!savedMsg) return;
    const timer = setTimeout(() => setSavedMsg(null), 4000);
    return () => clearTimeout(timer);
  }, [savedMsg]);

  /* ---- global save: validate every task, then confirm ---- */
  const handleSaveAll = useCallback(() => {
    setSaveError(null);
    for (const task of tasks) {
      if (!task.prompt.trim()) {
        setSaveError("Hay tareas sin descripción.");
        return;
      }
      if (!/^([01]\d|2[0-3]):[0-5]\d$/.test(task.time)) {
        setSaveError(`Horario inválido en: "${task.prompt.slice(0, 40)}".`);
        return;
      }
      if (task.days.length === 0) {
        setSaveError(`La tarea "${task.prompt.slice(0, 40)}" no tiene días seleccionados.`);
        return;
      }
    }
    setSavedMsg("Tareas guardadas correctamente.");
  }, [tasks]);

  /* ---- add task ---- */
  const handleAdd = useCallback(async () => {
    setFormError(null);
    const prompt = newPrompt.trim();
    if (!prompt) {
      setFormError("La tarea es obligatoria.");
      return;
    }
    if (!/^([01]\d|2[0-3]):[0-5]\d$/.test(newTime)) {
      setFormError("Horario inválido.");
      return;
    }
    if (newDays.length === 0) {
      setFormError("Seleccioná al menos un día.");
      return;
    }
    try {
      await schedulerService.createTask(prompt, newTime, [...newDays].sort((a, b) => a - b));
      setNewPrompt("");
      setNewTime("09:00");
      setNewDays(ALL_DAYS);
      await reloadTasks();
    } catch (err) {
      setFormError(err instanceof Error ? err.message : "No se pudo crear la tarea.");
    }
  }, [newPrompt, newTime, newDays, reloadTasks]);

  /* ---- delete task ---- */
  const handleDelete = useCallback(
    async (id: string) => {
      try {
        await schedulerService.deleteTask(id);
        if (editingId === id) setEditingId(null);
        await reloadTasks();
      } catch (err) {
        setSaveError(err instanceof Error ? err.message : "No se pudo eliminar la tarea.");
      }
    },
    [editingId, reloadTasks],
  );

  /* ---- edit schedule (inline) ---- */
  const startEdit = useCallback((task: SchedulerTask) => {
    setEditingId(task.id);
    setEditTime(task.time);
    setEditDays(task.days);
    setEditError(null);
  }, []);

  const cancelEdit = useCallback(() => {
    setEditingId(null);
    setEditError(null);
  }, []);

  const saveEdit = useCallback(async () => {
    setEditError(null);
    if (!/^([01]\d|2[0-3]):[0-5]\d$/.test(editTime)) {
      setEditError("Horario inválido.");
      return;
    }
    if (editDays.length === 0) {
      setEditError("Seleccioná al menos un día.");
      return;
    }
    if (!editingId) return;
    try {
      await schedulerService.updateTask(editingId, {
        time: editTime,
        days: [...editDays].sort((a, b) => a - b),
      });
      setEditingId(null);
      await reloadTasks();
    } catch (err) {
      setEditError(err instanceof Error ? err.message : "No se pudo actualizar la tarea.");
    }
  }, [editTime, editDays, editingId, reloadTasks]);

  const toggleDay = useCallback(
    (list: number[], day: number, setter: (days: number[]) => void) => {
      setter(
        list.includes(day)
          ? list.filter((d) => d !== day)
          : [...list, day],
      );
    },
    [],
  );

  if (!open) return null;

  return (
    <Dialog open={open} onOpenChange={(o) => !o && onClose()}>
      <DialogContent className="max-w-4xl w-[640px] h-[600px] flex flex-col p-0 gap-0">
        <DialogHeader className="px-6 pt-6 pb-4">
          <DialogTitle className="flex items-center gap-2">
            <AlarmClock size={20} />
            Tareas programadas
          </DialogTitle>
          <DialogDescription>
            Configurá tareas y horarios para el agente. Zona horaria:{" "}
            <span className="font-medium text-app-text">{timezone}</span>{" "}
            (tomada del sistema).
          </DialogDescription>
        </DialogHeader>

        {/* Body */}
        <div className="flex-1 min-h-0 overflow-y-auto px-6 pb-4 space-y-4">
          {savedMsg && (
            <div className="text-sm rounded-lg px-4 py-2.5 border text-green-800 bg-green-50 border-green-200">
              {savedMsg}
            </div>
          )}

          {saveError && (
            <div className="text-sm text-red-600 bg-red-50 border border-red-200 rounded-lg px-4 py-2.5">
              {saveError}
            </div>
          )}

          {/* Task list */}
          {tasks.length === 0 ? (
            <p className="text-sm text-app-text-secondary">
              No hay tareas programadas todavía.
            </p>
          ) : (
            <ul className="space-y-2">
              {tasks.map((task) => (
                <li
                  key={task.id}
                  className="bg-white border border-gray-200 rounded-lg px-4 py-3"
                >
                  {editingId === task.id ? (
                    /* ---- inline schedule editor ---- */
                    <div className="space-y-2">
                      <p className="text-sm font-medium text-app-text">
                        {task.prompt}
                      </p>
                      <div className="flex items-center gap-3 flex-wrap">
                        <label className="flex items-center gap-2 text-sm text-app-text-secondary">
                          <Clock size={14} className="text-app-primary" />
                          Hora
                          <input
                            type="time"
                            value={editTime}
                            onChange={(e) => setEditTime(e.target.value)}
                            className="border border-gray-300 rounded-lg px-2 py-1 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-400 focus:border-transparent"
                          />
                        </label>
                        <div className="flex items-center gap-1">
                          {WEEKDAY_LABELS.map((label, day) => (
                            <button
                              key={day}
                              type="button"
                              onClick={() => toggleDay(editDays, day, setEditDays)}
                              title="Día de la semana"
                              className={`w-7 h-7 rounded-full text-xs font-medium border transition-colors ${
                                editDays.includes(day)
                                  ? "bg-app-primary text-white border-app-primary"
                                  : "bg-white text-gray-500 border-gray-300 hover:border-indigo-400"
                              }`}
                            >
                              {label}
                            </button>
                          ))}
                        </div>
                      </div>
                      {editError && (
                        <div className="text-xs text-red-600 bg-red-50 border border-red-200 rounded-lg px-3 py-1.5">
                          {editError}
                        </div>
                      )}
                      <div className="flex items-center gap-2">
                        <button
                          type="button"
                          onClick={saveEdit}
                          className="flex items-center gap-1.5 bg-gradient-to-r from-[#4f46e5] to-[#8b5cf6] text-white text-xs font-medium px-3 py-1.5 rounded-lg hover:opacity-90"
                        >
                          <Check size={13} />
                          Guardar horario
                        </button>
                        <button
                          type="button"
                          onClick={cancelEdit}
                          className="flex items-center gap-1.5 bg-gray-100 hover:bg-gray-200 text-gray-700 text-xs font-medium px-3 py-1.5 rounded-lg transition-colors border border-gray-300"
                        >
                          <X size={13} />
                          Cancelar
                        </button>
                      </div>
                    </div>
                  ) : (
                    /* ---- task row ---- */
                    <div className="flex items-center gap-3">
                      <Clock size={15} className="shrink-0 text-app-primary" />
                      <div className="flex-1 min-w-0">
                        <p className="text-sm font-medium text-app-text truncate">
                          {task.prompt}
                        </p>
                        <p className="text-xs text-app-text-secondary">
                          {formatSchedule(task.time, task.days)}
                        </p>
                      </div>
                      <button
                        type="button"
                        onClick={() => startEdit(task)}
                        className="text-gray-400 hover:text-app-primary shrink-0"
                        title="Editar horario"
                      >
                        <Pencil size={14} />
                      </button>
                      <button
                        type="button"
                        onClick={() => handleDelete(task.id)}
                        className="text-red-500 hover:text-red-700 shrink-0"
                        title="Eliminar tarea"
                      >
                        <Trash2 size={14} />
                      </button>
                    </div>
                  )}
                </li>
              ))}
            </ul>
          )}

          {/* Add task */}
          <section className="space-y-2 pt-2 border-t border-gray-200">
            <h3 className="text-sm font-medium text-app-text flex items-center gap-2">
              <Plus size={14} className="text-app-primary" />
              Nueva tarea
            </h3>
            <textarea
              value={newPrompt}
              onChange={(e) => setNewPrompt(e.target.value)}
              placeholder="¿Qué tiene que hacer el agente? (ej.: Resumime los mails pendientes)"
              rows={2}
              className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm resize-none focus:outline-none focus:ring-2 focus:ring-indigo-400 focus:border-transparent"
            />
            <div className="flex items-center gap-3 flex-wrap">
              <label className="flex items-center gap-2 text-sm text-app-text-secondary">
                <Clock size={14} className="text-app-primary" />
                Hora
                <input
                  type="time"
                  value={newTime}
                  onChange={(e) => setNewTime(e.target.value)}
                  className="border border-gray-300 rounded-lg px-2 py-1 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-400 focus:border-transparent"
                />
              </label>
              <div className="flex items-center gap-1">
                {WEEKDAY_LABELS.map((label, day) => (
                  <button
                    key={day}
                    type="button"
                    onClick={() => toggleDay(newDays, day, setNewDays)}
                    title="Día de la semana"
                    className={`w-7 h-7 rounded-full text-xs font-medium border transition-colors ${
                      newDays.includes(day)
                        ? "bg-app-primary text-white border-app-primary"
                        : "bg-white text-gray-500 border-gray-300 hover:border-indigo-400"
                    }`}
                  >
                    {label}
                  </button>
                ))}
              </div>
            </div>
            {formError && (
              <div className="text-xs text-red-600 bg-red-50 border border-red-200 rounded-lg px-3 py-1.5">
                {formError}
              </div>
            )}
            <button
              type="button"
              onClick={handleAdd}
              className="w-full flex items-center justify-center gap-2 bg-gradient-to-r from-[#4f46e5] to-[#8b5cf6] text-white text-sm font-medium px-4 py-2 rounded-lg hover:opacity-90 disabled:opacity-50"
            >
              <Plus size={14} />
              Agregar tarea
            </button>
          </section>
        </div>

        {/* Footer: global save + close */}
        <div className="flex items-center justify-end gap-2 px-6 py-4 border-t border-gray-200">
          <button
            type="button"
            onClick={handleSaveAll}
            className="flex items-center justify-center gap-2 bg-gradient-to-r from-[#4f46e5] to-[#8b5cf6] text-white text-sm font-medium px-5 py-2 rounded-lg hover:opacity-90"
          >
            <Check size={15} />
            Guardar
          </button>
          <button
            type="button"
            onClick={onClose}
            className="bg-gray-100 hover:bg-gray-200 text-gray-700 text-sm font-medium px-5 py-2 rounded-lg transition-colors border border-gray-300"
          >
            Cerrar
          </button>
        </div>
      </DialogContent>
    </Dialog>
  );
}

export default SchedulerModal;
