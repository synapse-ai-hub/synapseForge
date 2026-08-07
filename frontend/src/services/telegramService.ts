/** Service for the Telegram toggle (status + enable/disable). */

const API_BASE_URL = import.meta.env.VITE_URL_BASE || "http://localhost:8000";

export interface TelegramStatus {
  enabled: boolean;
}

async function getStatus(): Promise<boolean> {
  const res = await fetch(`${API_BASE_URL}/api/telegram/status`);
  if (!res.ok) throw new Error("Error obteniendo estado de Telegram");
  const data = (await res.json()) as TelegramStatus;
  return data.enabled;
}

async function toggle(enabled: boolean): Promise<boolean> {
  const res = await fetch(`${API_BASE_URL}/api/telegram/toggle`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ enabled }),
  });
  if (!res.ok) throw new Error("Error actualizando estado de Telegram");
  const data = (await res.json()) as TelegramStatus;
  return data.enabled;
}

const telegramService = { getStatus, toggle };

export default telegramService;