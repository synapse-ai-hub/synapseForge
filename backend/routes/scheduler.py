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
from backend.agent.utils import scheduler_helpers as scheduler_db

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
