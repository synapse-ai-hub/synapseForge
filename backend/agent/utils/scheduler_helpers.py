"""Helpers for the scheduler (agenda): CRUD, execution and notifications.

Tasks are stored in the ``scheduled_tasks`` SQLite table and executed by an
async loop started from the application lifespan. Each execution:

1. Creates a dedicated session (metadata ``source: "scheduler"``).
2. Runs the normal agent loop with the task prompt.
3. Records the result in ``task_runs``.
4. Notifies the web UI through the event bus (``scheduler_run`` event) and
   Telegram (one message per allowed chat), so both channels behave exactly
   like a user-triggered run.

All functions are imported by ``backend/routes/scheduler.py``,
``backend/main.py`` and ``backend/telegram/bot.py``.

Timezone: the system local time is used directly (no configuration).
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import sqlite3
import sys
import uuid
from datetime import datetime

# ---------------------------------------------------------------------------
# Ensure the project root is in sys.path for absolute imports
# ---------------------------------------------------------------------------
_current_dir = os.path.dirname(os.path.abspath(__file__))
_project_root = os.path.dirname(os.path.dirname(os.path.dirname(_current_dir)))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from backend.agent.utils.error_logger import log_error

logger = logging.getLogger(__name__)

_DB_PATH = os.path.join(_project_root, "backend", "agent", "agent_db", "agent.db")

CHECK_INTERVAL_SECONDS = 20
"""How often the loop checks for due tasks (must stay below one minute)."""

_TIME_RE_ERROR = "Horario inválido (formato esperado HH:MM)."


# ---------------------------------------------------------------------------
# Database helpers
# ---------------------------------------------------------------------------

def _connect() -> sqlite3.Connection:
    """Open a connection to the agent database with dict rows."""
    conn = sqlite3.connect(_DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _row_to_task(row: sqlite3.Row) -> dict:
    """Convert a ``scheduled_tasks`` row into a public task dict."""
    try:
        days = json.loads(row["days"] or "[]")
    except (json.JSONDecodeError, TypeError):
        days = []
    return {
        "id": row["id"],
        "prompt": row["prompt"],
        "time": row["time"],
        "days": days,
        "enabled": bool(row["enabled"]),
        "last_run_date": row["last_run_date"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


def list_tasks() -> list[dict]:
    """Return all scheduled tasks sorted by time.

    Returns:
        List of task dicts (possibly empty on error).
    """
    try:
        with _connect() as conn:
            rows = conn.execute(
                "SELECT * FROM scheduled_tasks ORDER BY time, created_at"
            ).fetchall()
            return [_row_to_task(row) for row in rows]
    except Exception as exc:
        log_error(str(exc), source="backend/agent/utils/scheduler_helpers.py:list_tasks")
        logger.warning("Failed to list scheduled tasks: %s", exc)
        return []


def get_task(task_id: str) -> dict | None:
    """Return a single scheduled task or ``None`` if it does not exist."""
    try:
        with _connect() as conn:
            row = conn.execute(
                "SELECT * FROM scheduled_tasks WHERE id = ?", (task_id,)
            ).fetchone()
            return _row_to_task(row) if row else None
    except Exception as exc:
        log_error(str(exc), source="backend/agent/utils/scheduler_helpers.py:get_task")
        logger.warning("Failed to get scheduled task %s: %s", task_id, exc)
        return None


def add_task(prompt: str, time_str: str, days: list[int]) -> dict:
    """Create a new scheduled task.

    Args:
        prompt: What the agent should do when the task fires.
        time_str: Local time in ``HH:MM`` (24h).
        days: Selected weekdays, 0=Sunday .. 6=Saturday.

    Returns:
        Contract-style dict with ``status``, ``message`` and ``task``.
    """
    prompt = (prompt or "").strip()
    if not prompt:
        return {"status": "error", "message": "La descripción de la tarea es obligatoria."}
    if not _is_valid_time(time_str):
        return {"status": "error", "message": _TIME_RE_ERROR}
    if not days or any(not isinstance(d, int) or d < 0 or d > 6 for d in days):
        return {"status": "error", "message": "Seleccioná al menos un día válido (0-6)."}

    now = datetime.now().isoformat()
    task_id = uuid.uuid4().hex
    try:
        with _connect() as conn:
            conn.execute(
                "INSERT INTO scheduled_tasks (id, prompt, time, days, enabled, created_at, updated_at) "
                "VALUES (?, ?, ?, ?, 1, ?, ?)",
                (task_id, prompt, time_str, json.dumps(sorted(set(days))), now, now),
            )
            conn.commit()
        return {
            "status": "success",
            "message": "Tarea programada creada.",
            "task": get_task(task_id),
        }
    except Exception as exc:
        log_error(str(exc), source="backend/agent/utils/scheduler_helpers.py:add_task")
        logger.warning("Failed to add scheduled task: %s", exc)
        return {"status": "error", "message": "No se pudo crear la tarea programada."}


def update_task(
    task_id: str,
    prompt: str | None = None,
    time_str: str | None = None,
    days: list[int] | None = None,
    enabled: bool | None = None,
) -> dict:
    """Update the schedule (and optionally the prompt) of a task.

    Args:
        task_id: The task identifier.
        prompt: New prompt, or ``None`` to keep the current one.
        time_str: New local time ``HH:MM``, or ``None`` to keep it.
        days: New weekday list, or ``None`` to keep it.
        enabled: New enabled flag, or ``None`` to keep it.

    Returns:
        Contract-style dict with ``status``, ``message`` and ``task``.
    """
    current = get_task(task_id)
    if current is None:
        return {"status": "error", "message": "La tarea no existe."}

    new_prompt = prompt.strip() if isinstance(prompt, str) else current["prompt"]
    if not new_prompt:
        return {"status": "error", "message": "La descripción de la tarea es obligatoria."}
    new_time = time_str if time_str else current["time"]
    if not _is_valid_time(new_time):
        return {"status": "error", "message": _TIME_RE_ERROR}
    new_days = sorted(set(days)) if days else current["days"]
    if not new_days or any(not isinstance(d, int) or d < 0 or d > 6 for d in new_days):
        return {"status": "error", "message": "Seleccioná al menos un día válido (0-6)."}
    new_enabled = current["enabled"] if enabled is None else bool(enabled)

    try:
        with _connect() as conn:
            conn.execute(
                "UPDATE scheduled_tasks SET prompt = ?, time = ?, days = ?, enabled = ?, "
                "last_run_date = NULL, updated_at = ? WHERE id = ?",
                (
                    new_prompt,
                    new_time,
                    json.dumps(new_days),
                    int(new_enabled),
                    datetime.now().isoformat(),
                    task_id,
                ),
            )
            conn.commit()
        return {
            "status": "success",
            "message": "Tarea actualizada.",
            "task": get_task(task_id),
        }
    except Exception as exc:
        log_error(str(exc), source="backend/agent/utils/scheduler_helpers.py:update_task")
        logger.warning("Failed to update scheduled task %s: %s", task_id, exc)
        return {"status": "error", "message": "No se pudo actualizar la tarea."}


def delete_task(task_id: str) -> dict:
    """Delete a scheduled task together with its recorded runs.

    Args:
        task_id: The task identifier.

    Returns:
        Contract-style dict with ``status`` and ``message``.
    """
    try:
        with _connect() as conn:
            cursor = conn.execute(
                "DELETE FROM task_runs WHERE task_id = ?", (task_id,)
            )
            cursor = conn.execute(
                "DELETE FROM scheduled_tasks WHERE id = ?", (task_id,)
            )
            conn.commit()
        if cursor.rowcount == 0:
            return {"status": "error", "message": "La tarea no existe."}
        return {"status": "success", "message": "Tarea eliminada."}
    except Exception as exc:
        log_error(str(exc), source="backend/agent/utils/scheduler_helpers.py:delete_task")
        logger.warning("Failed to delete scheduled task %s: %s", task_id, exc)
        return {"status": "error", "message": "No se pudo eliminar la tarea."}


def list_runs(limit: int = 50) -> list[dict]:
    """Return the most recent task executions (newest first).

    Args:
        limit: Maximum number of runs to return.

    Returns:
        List of run dicts joined with the task prompt (possibly empty).
    """
    try:
        with _connect() as conn:
            rows = conn.execute(
                "SELECT r.*, t.prompt FROM task_runs r "
                "LEFT JOIN scheduled_tasks t ON t.id = r.task_id "
                "ORDER BY r.started_at DESC LIMIT ?",
                (int(limit),),
            ).fetchall()
            return [
                {
                    "id": row["id"],
                    "task_id": row["task_id"],
                    "prompt": row["prompt"],
                    "session_id": row["session_id"],
                    "status": row["status"],
                    "detail": row["detail"],
                    "started_at": row["started_at"],
                    "finished_at": row["finished_at"],
                }
                for row in rows
            ]
    except Exception as exc:
        log_error(str(exc), source="backend/agent/utils/scheduler_helpers.py:list_runs")
        logger.warning("Failed to list task runs: %s", exc)
        return []


def record_run(
    task_id: str,
    session_id: str | None,
    status: str,
    detail: str,
    started_at: str,
    finished_at: str,
) -> None:
    """Persist a task execution result in ``task_runs``."""
    try:
        with _connect() as conn:
            conn.execute(
                "INSERT INTO task_runs (task_id, session_id, status, detail, started_at, finished_at) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (task_id, session_id, status, detail, started_at, finished_at),
            )
            conn.commit()
    except Exception as exc:
        log_error(str(exc), source="backend/agent/utils/scheduler_helpers.py:record_run")
        logger.warning("Failed to record task run: %s", exc)


def mark_fired(task_id: str, date_str: str) -> None:
    """Mark a task as already fired on the given date (dedup guard)."""
    try:
        with _connect() as conn:
            conn.execute(
                "UPDATE scheduled_tasks SET last_run_date = ? WHERE id = ?",
                (date_str, task_id),
            )
            conn.commit()
    except Exception as exc:
        log_error(str(exc), source="backend/agent/utils/scheduler_helpers.py:mark_fired")
        logger.warning("Failed to mark task fired: %s", exc)


def _is_valid_time(time_str: str) -> bool:
    """Return whether ``time_str`` matches the ``HH:MM`` 24h format."""
    import re

    return bool(isinstance(time_str, str) and re.fullmatch(r"([01]\d|2[0-3]):[0-5]\d", time_str))


# ---------------------------------------------------------------------------
# Execution + notifications
# ---------------------------------------------------------------------------

async def execute_task(task: dict) -> None:
    """Run a scheduled task through the normal agent loop and notify.

    Creates a dedicated session, streams the agent loop (discarding SSE
    chunks but detecting failures), records the run and notifies the web UI
    (event bus) and every allowed Telegram chat.

    Args:
        task: The task dict (as returned by :func:`get_task`).
    """
    from backend.instances import agent, session_manager
    from backend.event_bus import event_bus

    task_id = task["id"]
    prompt = task["prompt"]
    started_at = datetime.now().isoformat()
    session_id = uuid.uuid4().hex

    # Create the session first so messages have a parent row.
    try:
        session_manager.create_session(session_id, metadata={"source": "scheduler"})
    except Exception as exc:
        log_error(str(exc), source="backend/agent/utils/scheduler_helpers.py:execute_task(create_session)")
        logger.warning("Scheduler could not create session: %s", exc)

    status = "success"
    detail = ""
    try:
        from backend.agent.loop import AgentLoop

        agent_loop = AgentLoop(agent=agent, session_manager=session_manager)
        async for event in agent_loop.run(
            session_id=session_id,
            user_message=prompt,
        ):
            # The loop yields dicts; terminal failures arrive as "error"
            # events (real exceptions raise and are caught below).
            etype = event.get("type") if isinstance(event, dict) else None
            if etype == "error":
                status = "error"
                detail = str(event.get("content", ""))
            elif etype == "aborted" and status == "success":
                status = "error"
                detail = "Ejecución cancelada."
    except Exception as exc:
        status = "error"
        detail = str(exc)
        log_error(str(exc), source="backend/agent/utils/scheduler_helpers.py:execute_task")
        logger.warning("Scheduled task failed: %s", exc)

    finished_at = datetime.now().isoformat()

    # Read the final assistant answer from the DB (single source of truth),
    # reusing the same helper the chat route uses for the Telegram reply.
    final_text = ""
    if status == "success":
        try:
            from backend.routes.chat import _get_last_assistant_text

            final_text = _get_last_assistant_text(session_id, turn_number=1)
        except Exception as exc:
            log_error(str(exc), source="backend/agent/utils/scheduler_helpers.py:execute_task(final_text)")
            logger.warning("Could not read scheduler final text: %s", exc)
        if not final_text:
            status = "error"
            detail = "El agente no produjo respuesta."

    if status == "success":
        detail = final_text[:300]

    record_run(task_id, session_id, status, detail, started_at, finished_at)

    finished_local = datetime.now().strftime("%d/%m/%Y %H:%M")
    await event_bus.emit({
        "type": "scheduler_run",
        "status": status,
        "task": prompt,
        "detail": detail,
        "finished_at": finished_local,
        "session_id": session_id,
    })
    await _notify_telegram(status, prompt, detail, finished_local)


async def _notify_telegram(status: str, prompt: str, detail: str, finished_local: str) -> None:
    """Send the execution result to every allowed Telegram chat.

    Sent unconditionally (even when the bot toggle is off): the toggle only
    controls whether Telegram works as a chat channel, but scheduled-task
    notifications must always arrive.

    Args:
        status: ``"success"`` or ``"error"``.
        prompt: The task description.
        detail: Result summary (final answer or error message).
        finished_local: Human-readable local finish timestamp.
    """
    try:
        from backend.telegram.instance import telegram_bot

        if not telegram_bot.token:
            return
        icon = "✅" if status == "success" else "❌"
        header = "Tarea programada ejecutada" if status == "success" else "Tarea programada fallida"
        lines = [
            f"{icon} {header}",
            f"Tarea: {prompt}",
            f"Fecha y hora: {finished_local}",
        ]
        if detail:
            summary = detail if len(detail) <= 500 else f"{detail[:500]}…"
            lines.append(f"Resultado: {summary}")
        text = "\n".join(lines)
        for chat_id in telegram_bot.allowed_chat_ids:
            await telegram_bot.send_message(chat_id, text)
    except Exception as exc:
        log_error(str(exc), source="backend/agent/utils/scheduler_helpers.py:_notify_telegram")
        logger.warning("Failed to notify Telegram about scheduled task: %s", exc)


# ---------------------------------------------------------------------------
# Scheduler loop
# ---------------------------------------------------------------------------

class SchedulerService:
    """Async loop that checks due tasks and executes them."""

    def __init__(self) -> None:
        self._task: asyncio.Task | None = None
        self._running = False
        # Only one scheduled execution at a time.
        self._exec_lock = asyncio.Lock()

    async def start(self) -> None:
        """Start the background check loop (idempotent)."""
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._loop())
        logger.info("Scheduler service started.")

    async def stop(self) -> None:
        """Stop the background loop."""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
        logger.info("Scheduler service stopped.")

    async def _loop(self) -> None:
        """Periodically check tasks and fire the ones due right now."""
        while self._running:
            try:
                await self._check_due_tasks()
            except Exception as exc:
                log_error(str(exc), source="backend/agent/utils/scheduler_helpers.py:_loop")
                logger.warning("Scheduler loop error: %s", exc)
            await asyncio.sleep(CHECK_INTERVAL_SECONDS)

    async def _check_due_tasks(self) -> None:
        """Execute every enabled task whose time matches the current minute."""
        now = datetime.now()
        today = now.strftime("%Y-%m-%d")
        current_time = now.strftime("%H:%M")
        # JS-style weekday (0=Sunday .. 6=Saturday) to match the UI convention.
        js_weekday = (now.weekday() + 1) % 7

        for task in list_tasks():
            if not task["enabled"]:
                continue
            if task["time"] != current_time:
                continue
            if js_weekday not in task["days"]:
                continue
            if task["last_run_date"] == today:
                continue
            if self._exec_lock.locked():
                # Do not mark as fired: retry within the same minute once the
                # current execution finishes.
                logger.info(
                    "Scheduled task deferred (another execution in progress): %s",
                    task["prompt"][:60],
                )
                continue

            # Mark before executing so a restart never double-fires the task.
            mark_fired(task["id"], today)
            async with self._exec_lock:
                logger.info("Executing scheduled task: %s", task["prompt"][:60])
                await execute_task(task)


# Module-level singleton used by the lifespan and the routes.
scheduler_service = SchedulerService()
