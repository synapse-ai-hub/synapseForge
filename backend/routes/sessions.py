"""Session listing and retrieval endpoints for the chat.

Provides REST endpoints to list chat sessions, load the full message
history of a session, and delete a session. These back the frontend
sidebar that shows the conversation history.
"""

from __future__ import annotations

import logging
import os
import sys

from backend.agent.utils.error_logger import log_error

from fastapi import APIRouter

# ---------------------------------------------------------------------------
# Ensure the project root is in sys.path so absolute imports (backend.*)
# resolve correctly regardless of how the file is invoked.
# sessions.py is at backend/routes/ -> need 3 dirname() calls to reach root.
# ---------------------------------------------------------------------------
_current_dir = os.path.dirname(os.path.abspath(__file__))
_project_root = os.path.dirname(os.path.dirname(_current_dir))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from backend.instances import session_manager
from backend.agent.contract import (
    make_error_response,
    make_success_response,
    validate_response,
    zero_usage,
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["sessions"])


@router.get("/sessions/titles")
async def list_titles():
    """Return all existing session titles.

    Returns:
        A contract response with ``data`` containing the list of titles.
    """
    if session_manager is None:
        return make_error_response(message="Session manager no disponible")
    try:
        titles = session_manager.get_all_titles()
        return validate_response(
            make_success_response(
                message="Títulos obtenidos",
                data=titles,
                usage=zero_usage(),
            )
        )
    except Exception as exc:
        log_error(str(exc), source="sessions.py:list_titles")
        logger.exception("Error listing titles: %s", exc)
        return make_error_response(message="Error al obtener los títulos")


@router.get("/sessions")
async def list_sessions():
    """Return all chat sessions ordered by most recent activity.

    Returns:
        A contract response with ``data`` containing the list of sessions.
    """
    if session_manager is None:
        return make_error_response(message="Session manager no disponible")
    try:
        sessions = session_manager.list_sessions()
        return validate_response(
            make_success_response(
                message="Sesiones obtenidas",
                data=sessions,
                usage=zero_usage(),
            )
        )
    except Exception as exc:
        log_error(str(exc), source="sessions.py:list_sessions")
        logger.exception("Error listing sessions: %s", exc)
        return make_error_response(message="Error al obtener las sesiones")


@router.get("/sessions/{session_id}")
async def get_session(session_id: str):
    """Return the full message history of a session.

    Only ``user`` and ``assistant`` messages are returned, mapped to the
    frontend-friendly shape (``id``, ``type``, ``content``, ``toolCalls``, ``toolResults``).

    Args:
        session_id: The session identifier.

    Returns:
        A contract response with ``data`` containing the session id and
        the list of messages.
    """
    if session_manager is None:
        return make_error_response(message="Session manager no disponible")
    try:
        raw_messages = session_manager.load_messages(session_id)
        mapped: list[dict] = []
        for msg in raw_messages:
            role = msg.get("role")
            if role not in ("user", "assistant"):
                continue
            tool_calls = msg.get("tool_calls") or None
            tool_results = msg.get("tool_results") or None
            mapped.append(
                {
                    "id": f"msg-{msg.get('id')}",
                    "type": role,
                    "content": msg.get("content") or "",
                    "toolCalls": tool_calls,
                    "toolResults": tool_results,
                }
            )
        return validate_response(
            make_success_response(
                message="Mensajes obtenidos",
                data={"session_id": session_id, "messages": mapped},
                usage=zero_usage(),
            )
        )
    except Exception as exc:
        log_error(str(exc), source="sessions.py:get_session")
        logger.exception("Error loading session %s: %s", session_id, exc)
        return make_error_response(message="Error al obtener la sesión")


@router.delete("/sessions/{session_id}")
async def delete_session(session_id: str):
    """Delete a session and all its messages.

    Args:
        session_id: The session identifier to remove.

    Returns:
        A contract response indicating success or failure.
    """
    if session_manager is None:
        return make_error_response(message="Session manager no disponible")
    try:
        result = session_manager.delete_session(session_id)
        return validate_response(result)
    except Exception as exc:
        log_error(str(exc), source="sessions.py:delete_session")
        logger.exception("Error deleting session %s: %s", session_id, exc)
        return make_error_response(message="Error al eliminar la sesión")


@router.delete("/conversations")
async def delete_all_conversations():
    """Delete ALL conversations (entire conversaciones table).

    This is a destructive operation that removes all conversation documents.
    Use with caution.

    Returns:
        A contract response indicating success or failure.
    """
    if session_manager is None:
        return make_error_response(message="Session manager no disponible")
    try:
        from backend.agent.session import SessionManager
        # Use the same DB path as SessionManager
        db = SessionManager()
        conn = db._get_connection()
        conn.execute("DELETE FROM conversaciones")
        conn.commit()
        return validate_response(
            make_success_response(
                message="Todas las conversaciones eliminadas",
                usage=zero_usage(),
            )
        )
    except Exception as exc:
        log_error(str(exc), source="sessions.py:delete_all_conversations")
        logger.exception("Error deleting all conversations: %s", exc)
        return make_error_response(message="Error al eliminar conversaciones")
