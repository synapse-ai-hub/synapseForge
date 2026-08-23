/** Service for scheduled tasks (agenda): CRUD + execution history. */

const API_BASE_URL = import.meta.env.VITE_URL_BASE || "http://localhost:8000";

/** Task scheduled to run at a given local time on specific weekdays. */
export interface SchedulerTask {
  id: string;
  /** What the agent should do when the task fires. */
  prompt: string;
  /** Local time in "HH:MM" (24h). */
  time: string;
  /** Selected weekdays (0=Sunday ... 6=Saturday). */
  days: number[];
  enabled: boolean;
}

/** A recorded execution of a scheduled task. */
export interface SchedulerRun {
  id: number;
  task_id: string;
  prompt: string | null;
  session_id: string | null;
  status: "success" | "error";
  detail: string | null;
  started_at: string;
  finished_at: string | null;
}

/** In-app notification shown by the header bell when a task executes. */
export interface SchedulerNotification {
  id: string;
  status: "success" | "error";
  /** Task description. */
  task: string;
  /** Result summary (final answer or error message). */
  detail: string;
  /** Human-readable local finish timestamp (from the backend). */
  finishedAt: string;
}

async function getTasks(): Promise<SchedulerTask[]> {
  const res = await fetch(`${API_BASE_URL}/api/scheduler/tasks`);
  if (!res.ok) throw new Error("Error obteniendo tareas programadas");
  const data = await res.json();
  return (data.tasks || []) as SchedulerTask[];
}

async function createTask(
  prompt: string,
  time: string,
  days: number[],
): Promise<{ message: string; task: SchedulerTask }> {
  const res = await fetch(`${API_BASE_URL}/api/scheduler/tasks`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ prompt, time, days }),
  });
  const data = await res.json();
  if (!res.ok) throw new Error(data.message || "Error creando la tarea programada");
  return data;
}

async function updateTask(
  taskId: string,
  payload: Partial<Pick<SchedulerTask, "prompt" | "time" | "days">>,
): Promise<{ message: string; task: SchedulerTask }> {
  const res = await fetch(`${API_BASE_URL}/api/scheduler/tasks/${taskId}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  const data = await res.json();
  if (!res.ok) throw new Error(data.message || "Error actualizando la tarea programada");
  return data;
}

async function deleteTask(taskId: string): Promise<void> {
  const res = await fetch(`${API_BASE_URL}/api/scheduler/tasks/${taskId}`, {
    method: "DELETE",
  });
  if (!res.ok) {
    const data = await res.json().catch(() => null);
    throw new Error(data?.message || "Error eliminando la tarea programada");
  }
}

async function getRuns(): Promise<SchedulerRun[]> {
  const res = await fetch(`${API_BASE_URL}/api/scheduler/runs`);
  if (!res.ok) throw new Error("Error obteniendo ejecuciones de tareas");
  const data = await res.json();
  return (data.runs || []) as SchedulerRun[];
}

const schedulerService = {
  getTasks,
  createTask,
  updateTask,
  deleteTask,
  getRuns,
};

export default schedulerService;
