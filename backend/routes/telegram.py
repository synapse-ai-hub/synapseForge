"""Telegram status and toggle endpoints.

The toggle only controls whether the bot polls Telegram. It is persisted in
``config_kv`` so it survives restarts.
"""

from __future__ import annotations

import logging
import os
import sys

from fastapi import APIRouter
from pydantic import BaseModel

_current_dir = os.path.dirname(os.path.abspath(__file__))
_project_root = os.path.dirname(os.path.dirname(_current_dir))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from backend.instances import session_manager
from backend.telegram.instance import telegram_bot

logger = logging.getLogger(__name__)

router = APIRouter()


class TogglePayload(BaseModel):
    enabled: bool


@router.get("/telegram/status")
async def telegram_status() -> dict:
    """Return whether the Telegram bot is currently enabled."""
    return {"enabled": telegram_bot.enabled}


@router.post("/telegram/toggle")
async def telegram_toggle(payload: TogglePayload) -> dict:
    """Enable/disable the Telegram bot and persist the choice."""
    telegram_bot.set_enabled(payload.enabled)
    session_manager.set_config("telegram_enabled", "true" if payload.enabled else "false")
    logger.info("Telegram toggle -> %s", payload.enabled)
    return {"enabled": payload.enabled}