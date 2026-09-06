"""CRUD endpoints for scheduled tasks (agenda) and their execution history.

Thin HTTP layer over :mod:`backend.agent.utils.scheduler_helpers`. The scheduler loop
itself is started from the application lifespan (see ``backend/main.py``).
"""

from __future__ import annotations

import logging
import os
import sys
from typing import Any

from fastapi import APIRouter
from fastapi.responses import JSONResponse

# ---------------------------------------------------------------------------
# Ensure the project root is in sys.path so absolute imports (backend.*)
# resolve correctly regardless of how the file is invoked.
# scheduler.py is at backend/routes/ -> need 3 dirname() calls to reach root.
# ---------------------------------------------------------------------------
_current_dir = os.path.dirname(os.path.abspath(__file__))
_project_root = os.path.dirname(os.path.dirname(_current_dir))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from backend.agent.utils.error_logger import log_error
from backend.agent.utils.contract import (
    make_error_response,
    make_success_response,
    validate_response,
    zero_usage,
)
from backend.agent.utils import scheduler_helpers as scheduler_db
from backend.instances import agent

logger = logging.getLogger(__name__)

router = APIRouter(tags=["scheduler"])


@router.get("/scheduler/tasks")
async def get_scheduled_tasks() -> JSONResponse:
    """List every scheduled task sorted by time."""
    return JSONResponse(
        status_code=200,
        content={"status": "success", "tasks": scheduler_db.list_tasks()},
    )


@router.post("/scheduler/tasks")
async def create_scheduled_task(data: dict[str, Any]) -> JSONResponse:
    """Create a new scheduled task.

    Body: ``{"prompt": str, "time": "HH:MM", "days": [0-6, ...]}``.
    """
    result = scheduler_db.add_task(
        prompt=data.get("prompt"),
        time_str=data.get("time"),
        days=data.get("days") or [],
    )
    if result["status"] == "error":
        log_error(result["message"], source="backend/routes/scheduler.py:create")
        logger.warning("Scheduled task rejected: %s", result["message"])
        return JSONResponse(status_code=400, content=result)
    return JSONResponse(status_code=200, content=result)


@router.put("/scheduler/tasks/{task_id}")
async def update_scheduled_task(task_id: str, data: dict[str, Any]) -> JSONResponse:
    """Update a scheduled task.

    Body (all optional): ``{"prompt": str, "time": "HH:MM", "days": [...],
    "enabled": bool}``. Updating the schedule resets the daily dedup guard.
    """
    result = scheduler_db.update_task(
        task_id,
        prompt=data.get("prompt"),
        time_str=data.get("time"),
        days=data.get("days"),
        enabled=data.get("enabled"),
    )
    if result["status"] == "error":
        log_error(result["message"], source="backend/routes/scheduler.py:update")
        logger.warning("Scheduled task update rejected: %s", result["message"])
        return JSONResponse(status_code=400, content=result)
    return JSONResponse(status_code=200, content=result)


@router.delete("/scheduler/tasks/{task_id}")
async def delete_scheduled_task(task_id: str) -> JSONResponse:
    """Delete a scheduled task and its recorded runs."""
    result = scheduler_db.delete_task(task_id)
    if result["status"] == "error":
        log_error(result["message"], source="backend/routes/scheduler.py:delete")
        logger.warning("Scheduled task delete rejected: %s", result["message"])
        return JSONResponse(status_code=404, content=result)
    return JSONResponse(status_code=200, content=result)


@router.get("/scheduler/runs")
async def get_scheduler_runs() -> JSONResponse:
    """Return the most recent task executions (newest first)."""
    return JSONResponse(
        status_code=200,
        content={"status": "success", "runs": scheduler_db.list_runs()},
    )


@router.post("/scheduler/craft-prompt")
async def craft_scheduled_prompt(data: dict[str, Any]) -> JSONResponse:
    """Refine a user's natural-language task description into a clear agent prompt.

    Body: ``{"prompt": "user text"}``.
    Returns: ``{"status": "success", "message": "...", "data": {"prompt": "refined prompt"}, "usage": ...}``.
    """
    raw = (data.get("prompt") or "").strip()
    if not raw:
        return validate_response(
            make_error_response(message="El prompt no puede estar vacío.")
        )

    if not agent.default_model:
        return validate_response(
            make_error_response(message="No hay modelo seleccionado. Elegí uno en Configuración.")
        )

    system = (
        "You are a prompt engineer for an AI agent. The user will give you a "
        "rough description of what they want the agent to do on a schedule. "
        "Rewrite it as a clear, concise, actionable prompt in the same language "
        "as the input. Do NOT add explanations, greetings, or markdown — return "
        "ONLY the refined prompt text. Keep it under 200 characters."
    )
    try:
        response = await agent.llm_process(
            model=agent.default_model,
            prompt=raw,
            system_content=system,
            max_tokens=256,
            temperature=0.3,
        )
        refined = str(response.data or "").strip()
        if not refined:
            return validate_response(
                make_error_response(message="El modelo no devolvió un prompt.")
            )
        return validate_response(
            make_success_response(
                message="Prompt refinado",
                data={"prompt": refined},
                usage=zero_usage(),
            )
        )
    except Exception as exc:
        logger.exception("craft-prompt LLM call failed")
        log_error(str(exc), source="backend/routes/scheduler.py:craft-prompt")
        return validate_response(
            make_error_response(message="No se pudo mejorar el prompt. Intentá de nuevo.")
        )
