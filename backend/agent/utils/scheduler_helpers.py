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
import re
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
from backend.utils.db import db_transaction, get_connection

logger = logging.getLogger(__name__)

CHECK_INTERVAL_SECONDS = 20
"""How often the loop checks for due tasks (must stay below one minute)."""

_TIME_RE_ERROR = "Horario inválido (formato esperado HH:MM)."
_NAME_RE = re.compile(r"^[a-z0-9][a-z0-9_-]*$")


# ---------------------------------------------------------------------------
# Serialisation helpers
# ---------------------------------------------------------------------------


def _parse_json_field(value: str | None, default=None):
    """Parse a JSON text column, returning *default* on failure."""
    if value is None:
        return default
    try:
        return json.loads(value)
    except (json.JSONDecodeError, TypeError):
        return default


def _serialize_json(value) -> str | None:
    """Serialise a Python value to a JSON string (or ``None``)."""
    if value is None:
        return None
    return json.dumps(value, ensure_ascii=False)


def _slot_key(time_str: str, days: list[int]) -> str:
    """Generate a unique identifier for a schedule slot.

    Example: ``"09:00_1,2,3,4,5"``.
    """
    return f"{time_str}_{','.join(str(d) for d in sorted(set(days)))}"


def _slugify(text: str) -> str:
    """Convert arbitrary text into a lowercase slug suitable for an agent name.

    Keeps only ``[a-z0-9]``, replacing spaces and special characters with
    hyphens.  Leading/trailing hyphens are stripped.  Falls back to a
    UUID fragment when the input produces nothing usable.
    """
    slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return slug if slug else uuid.uuid4().hex[:8]


# ---------------------------------------------------------------------------
# Row ↔ dict conversion
# ---------------------------------------------------------------------------


def _row_to_task(row: sqlite3.Row) -> dict:
    """Convert a ``scheduled_tasks`` row into a public task dict."""
    return {
        "id": row["id"],
        "name": row["name"],
        "prompt": row["prompt"],
        "time": row["time"],
        "days": _parse_json_field(row["days"], []),
        "enabled": bool(row["enabled"]),
        "repetitions": _parse_json_field(row["repetitions"], []),
        "tool_permissions": _parse_json_field(row["tool_permissions"]),
        "skill_permissions": _parse_json_field(row["skill_permissions"]),
        "parameters": _parse_json_field(row["parameters"]),
        "last_run_date": row["last_run_date"],
        "slot_runs": _parse_json_field(row["slot_runs"], {}),
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


# ---------------------------------------------------------------------------
# CRUD
# ---------------------------------------------------------------------------


def _validate_task_fields(name: str, prompt: str, time_str: str, days: list[int]) -> str | None:
    """Validate the common task fields, returning an error message or ``None``.

    Args:
        name: Task name (already stripped).
        prompt: Task description (already stripped).
        time_str: Local time in ``HH:MM``.
        days: Selected weekdays (0=Sunday .. 6=Saturday).

    Returns:
        An error message string if any field is invalid, otherwise ``None``.
    """
    if not name:
        return "El nombre de la tarea es obligatorio."
    if not _NAME_RE.match(name):
        return "El nombre solo puede contener minúsculas, números, guiones y guiones bajos."
    if not prompt:
        return "La descripción de la tarea es obligatoria."
    if not _is_valid_time(time_str):
        return _TIME_RE_ERROR
    if not days or any(not isinstance(d, int) or d < 0 or d > 6 for d in days):
        return "Seleccioná al menos un día válido (0-6)."
    return None


def list_tasks() -> list[dict]:
    """Return all scheduled tasks sorted by time.

    Returns:
        List of task dicts (possibly empty on error).
    """
    try:
        with get_connection() as conn:
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
        with get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM scheduled_tasks WHERE id = ?", (task_id,)
            ).fetchone()
            return _row_to_task(row) if row else None
    except Exception as exc:
        log_error(str(exc), source="backend/agent/utils/scheduler_helpers.py:get_task")
        logger.warning("Failed to get scheduled task %s: %s", task_id, exc)
        return None


def add_task(
    name: str,
    prompt: str,
    time_str: str,
    days: list[int],
    tool_permissions: dict | None = None,
    skill_permissions: dict | None = None,
    parameters: dict | None = None,
    repetitions: list[dict] | None = None,
) -> dict:
    """Create a new scheduled task.

    Args:
        name: Task name (also used as sub-agent identifier).
        prompt: What the agent should do when the task fires.
        time_str: Local time in ``HH:MM`` (24h).
        days: Selected weekdays, 0=Sunday .. 6=Saturday.
        tool_permissions: Tool permissions dict for the sub-agent.
        skill_permissions: Skill permissions dict for the sub-agent.
        parameters: Model parameters dict (temperature, top_p, etc.).
        repetitions: Additional schedule slots ``[{"time": "HH:MM", "days": [0..6]}]``.

    Returns:
        Contract-style dict with ``status``, ``message`` and ``task``.
    """
    name = (name or "").strip()
    prompt = (prompt or "").strip()
    error = _validate_task_fields(name, prompt, time_str, days)
    if error:
        return {"status": "error", "message": error}

    now = datetime.now().isoformat()
    task_id = uuid.uuid4().hex
    try:
        with db_transaction() as conn:
            conn.execute(
                "INSERT INTO scheduled_tasks "
                "(id, name, prompt, time, days, enabled, repetitions, "
                "tool_permissions, skill_permissions, parameters, "
                "slot_runs, created_at, updated_at) "
                "VALUES (?, ?, ?, ?, ?, 1, ?, ?, ?, ?, '{}', ?, ?)",
                (
                    task_id,
                    name,
                    prompt,
                    time_str,
                    json.dumps(sorted(set(days))),
                    _serialize_json(repetitions),
                    _serialize_json(tool_permissions),
                    _serialize_json(skill_permissions),
                    _serialize_json(parameters),
                    now,
                    now,
                ),
            )
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
    name: str | None = None,
    prompt: str | None = None,
    time_str: str | None = None,
    days: list[int] | None = None,
    enabled: bool | None = None,
    tool_permissions: dict | None = None,
    skill_permissions: dict | None = None,
    parameters: dict | None = None,
    repetitions: list[dict] | None = None,
) -> dict:
    """Update a scheduled task.

    Args:
        task_id: The task identifier.
        name: New name, or ``None`` to keep the current one.
        prompt: New prompt, or ``None`` to keep the current one.
        time_str: New local time ``HH:MM``, or ``None`` to keep it.
        days: New weekday list, or ``None`` to keep it.
        enabled: New enabled flag, or ``None`` to keep it.
        tool_permissions: New tool permissions, or ``None`` to keep current.
        skill_permissions: New skill permissions, or ``None`` to keep current.
        parameters: New model parameters, or ``None`` to keep current.
        repetitions: New additional slots, or ``None`` to keep current.

    Returns:
        Contract-style dict with ``status``, ``message`` and ``task``.
    """
    current = get_task(task_id)
    if current is None:
        return {"status": "error", "message": "La tarea no existe."}

    new_name = name.strip() if isinstance(name, str) else current["name"]
    new_prompt = prompt.strip() if isinstance(prompt, str) else current["prompt"]
    new_time = time_str if time_str else current["time"]
    new_days = sorted(set(days)) if days else current["days"]
    error = _validate_task_fields(new_name, new_prompt, new_time, new_days)
    if error:
        return {"status": "error", "message": error}
    new_enabled = current["enabled"] if enabled is None else bool(enabled)
    # For permissions/params: a dict (even empty) means "clear", None means "keep".
    new_tool_perms = tool_permissions if isinstance(tool_permissions, dict) or tool_permissions is None else current.get("tool_permissions")
    new_skill_perms = skill_permissions if isinstance(skill_permissions, dict) or skill_permissions is None else current.get("skill_permissions")
    new_params = parameters if isinstance(parameters, dict) or parameters is None else current.get("parameters")
    new_reps = repetitions if isinstance(repetitions, list) or repetitions is None else current.get("repetitions")

    try:
        with db_transaction() as conn:
            conn.execute(
                "UPDATE scheduled_tasks SET "
                "name = ?, prompt = ?, time = ?, days = ?, enabled = ?, "
                "repetitions = ?, tool_permissions = ?, skill_permissions = ?, "
                "parameters = ?, last_run_date = NULL, updated_at = ? WHERE id = ?",
                (
                    new_name,
                    new_prompt,
                    new_time,
                    json.dumps(new_days),
                    int(new_enabled),
                    _serialize_json(new_reps),
                    _serialize_json(new_tool_perms),
                    _serialize_json(new_skill_perms),
                    _serialize_json(new_params),
                    datetime.now().isoformat(),
                    task_id,
                ),
            )
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
    """Delete a scheduled task together with its recorded runs and sub-agent.

    Args:
        task_id: The task identifier.

    Returns:
        Contract-style dict with ``status`` and ``message``.
    """
    # Read the task before deleting so we can clean up the sub-agent.
    task = get_task(task_id)
    try:
        with db_transaction() as conn:
            cursor = conn.execute(
                "DELETE FROM task_runs WHERE task_id = ?", (task_id,)
            )
            cursor = conn.execute(
                "DELETE FROM scheduled_tasks WHERE id = ?", (task_id,)
            )
        if cursor.rowcount == 0:
            return {"status": "error", "message": "La tarea no existe."}
        # Remove the sub-agent .md if it exists.
        if task and task.get("name"):
            _cleanup_scheduler_agent(task["name"])
        return {"status": "success", "message": "Tarea eliminada."}
    except Exception as exc:
        log_error(str(exc), source="backend/agent/utils/scheduler_helpers.py:delete_task")
        logger.warning("Failed to delete scheduled task %s: %s", task_id, exc)
        return {"status": "error", "message": "No se pudo eliminar la tarea."}


# ---------------------------------------------------------------------------
# Sub-agent helpers
# ---------------------------------------------------------------------------


def _get_agents_dir() -> str:
    """Return the agents config directory, creating it if needed."""
    from backend.agent.utils.config_dir import get_agents_dir
    agents_dir = get_agents_dir()
    agents_dir.mkdir(parents=True, exist_ok=True)
    return str(agents_dir)


def _ensure_scheduler_agent(task: dict) -> str | None:
    """Create the sub-agent ``.md`` for a scheduled task with permissions.

    If the task has no tool/skill permissions configured, returns ``None``
    (fallback to router).

    Args:
        task: Task dict from :func:`get_task`.

    Returns:
        The agent name to pass to ``AgentLoop.run()``, or ``None``.
    """
    tool_perms = task.get("tool_permissions")
    skill_perms = task.get("skill_permissions")
    # If neither is set, run as router (no custom sub-agent).
    if tool_perms is None and skill_perms is None:
        return None

    task_name = task["name"]
    params = task.get("parameters") or {}
    prompt = task.get("prompt", "")

    # Build frontmatter YAML.
    lines = ["---"]
    lines.append(f"name: {task_name}")
    lines.append(f'description: "Sub-agente programado: {task_name}"')
    lines.append("permission:")

    if tool_perms:
        lines.append("  tool:")
        for k, v in tool_perms.items():
            lines.append(f"    {k}: {v}")
    else:
        lines.append("  tool: {}")

    if skill_perms:
        lines.append("  skill:")
        for k, v in skill_perms.items():
            lines.append(f"    {k}: {v}")
    else:
        lines.append("  skill: {}")

    # Parameters section.
    if params:
        lines.append("parameters:")
        for k, v in params.items():
            if v is None:
                lines.append(f"  {k}: null")
            elif isinstance(v, str):
                lines.append(f"  {k}: \"{v}\"")
            else:
                lines.append(f"  {k}: {v}")

    lines.append("---")
    lines.append("")
    lines.append(prompt)

    content = "\n".join(lines) + "\n"

    # Avoid overwriting a user-created agent with the same name.
    agents_dir = _get_agents_dir()
    target = os.path.join(agents_dir, f"{task_name}.md")
    if os.path.isfile(target):
        logger.warning(
            "Agent '%s' already exists; skipping scheduler agent creation.",
            task_name,
        )
        # Still return the name — the existing agent will be used.
        return task_name

    try:
        with open(target, "w", encoding="utf-8") as f:
            f.write(content)
        logger.info("Scheduler agent created: %s", target)
    except OSError as exc:
        log_error(str(exc), source="backend/agent/utils/scheduler_helpers.py:_ensure_scheduler_agent")
        logger.warning("Failed to create scheduler agent %s: %s", task_name, exc)
        return None

    return task_name


def _cleanup_scheduler_agent(task_name: str) -> None:
    """Remove the sub-agent ``.md`` created by the scheduler for a task.

    Args:
        task_name: The task/agent name (filename without ``.md``).
    """
    agents_dir = _get_agents_dir()
    target = os.path.join(agents_dir, f"{task_name}.md")
    try:
        if os.path.isfile(target):
            os.remove(target)
            logger.info("Scheduler agent removed: %s", target)
    except OSError as exc:
        log_error(str(exc), source="backend/agent/utils/scheduler_helpers.py:_cleanup_scheduler_agent")
        logger.warning("Failed to remove scheduler agent %s: %s", task_name, exc)


# ---------------------------------------------------------------------------
# Slot dedup helpers
# ---------------------------------------------------------------------------


def mark_slot_fired(task_id: str, slot_key: str, date_str: str) -> None:
    """Mark a specific slot as fired on the given date (dedup per slot).

    Updates the ``slot_runs`` JSON dict on the ``scheduled_tasks`` row.

    Args:
        task_id: The task identifier.
        slot_key: Unique slot identifier from :func:`_slot_key`.
        date_str: Today's date (``YYYY-MM-DD``).
    """
    try:
        with get_connection() as conn:
            row = conn.execute(
                "SELECT slot_runs FROM scheduled_tasks WHERE id = ?", (task_id,)
            ).fetchone()
            slot_runs = _parse_json_field(row["slot_runs"] if row else None, {})
            slot_runs[slot_key] = date_str
        with db_transaction() as conn:
            conn.execute(
                "UPDATE scheduled_tasks SET slot_runs = ? WHERE id = ?",
                (json.dumps(slot_runs, ensure_ascii=False), task_id),
            )
    except Exception as exc:
        log_error(str(exc), source="backend/agent/utils/scheduler_helpers.py:mark_slot_fired")
        logger.warning("Failed to mark slot fired: %s", exc)


# ---------------------------------------------------------------------------
# Runs log
# ---------------------------------------------------------------------------


def list_runs(limit: int = 50) -> list[dict]:
    """Return the most recent task executions (newest first).

    Args:
        limit: Maximum number of runs to return.

    Returns:
        List of run dicts joined with the task name and prompt (possibly empty).
    """
    try:
        with get_connection() as conn:
            rows = conn.execute(
                "SELECT r.*, t.prompt, t.name FROM task_runs r "
                "LEFT JOIN scheduled_tasks t ON t.id = r.task_id "
                "ORDER BY r.started_at DESC LIMIT ?",
                (int(limit),),
            ).fetchall()
            return [
                {
                    "id": row["id"],
                    "task_id": row["task_id"],
                    "prompt": row["prompt"],
                    "name": row["name"],
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
        with db_transaction() as conn:
            conn.execute(
                "INSERT INTO task_runs (task_id, session_id, status, detail, started_at, finished_at) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (task_id, session_id, status, detail, started_at, finished_at),
            )
    except Exception as exc:
        log_error(str(exc), source="backend/agent/utils/scheduler_helpers.py:record_run")
        logger.warning("Failed to record task run: %s", exc)


def _is_valid_time(time_str: str) -> bool:
    """Return whether ``time_str`` matches the ``HH:MM`` 24h format."""
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

    # Ensure sub-agent .md exists if the task has permissions.
    agent_name = _ensure_scheduler_agent(task)

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
        run_kwargs: dict = {"session_id": session_id, "user_message": prompt}
        if agent_name:
            run_kwargs["agent_name"] = agent_name
        async for event in agent_loop.run(**run_kwargs):
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
        """Execute every enabled task whose time matches the current minute.

        Supports multiple slots per task: the primary slot (``time``/``days``)
        plus any additional slots in ``repetitions``.  Each slot is deduped
        independently via ``slot_runs``.
        """
        now = datetime.now()
        today = now.strftime("%Y-%m-%d")
        current_time = now.strftime("%H:%M")
        # JS-style weekday (0=Sunday .. 6=Saturday) to match the UI convention.
        js_weekday = (now.weekday() + 1) % 7

        for task in list_tasks():
            if not task["enabled"]:
                continue

            # Build the full list of slots to evaluate.
            slots = [{"time": task["time"], "days": task["days"]}]
            for rep in (task.get("repetitions") or []):
                if isinstance(rep, dict) and rep.get("time") and rep.get("days"):
                    slots.append({"time": rep["time"], "days": rep["days"]})

            for slot in slots:
                if slot["time"] != current_time:
                    continue
                if js_weekday not in slot["days"]:
                    continue

                slot_key = _slot_key(slot["time"], slot["days"])
                slot_runs = task.get("slot_runs") or {}
                if slot_runs.get(slot_key) == today:
                    continue

                if self._exec_lock.locked():
                    logger.info(
                        "Scheduled task deferred (another execution in progress): %s",
                        task["prompt"][:60],
                    )
                    continue

                # Mark before executing so a restart never double-fires the task.
                mark_slot_fired(task["id"], slot_key, today)
                async with self._exec_lock:
                    logger.info("Executing scheduled task: %s", task["prompt"][:60])
                    await execute_task(task)
                # Break after first slot match per task to avoid double-execution
                # in the same check cycle.
                break


# Module-level singleton used by the lifespan and the routes.
scheduler_service = SchedulerService()
