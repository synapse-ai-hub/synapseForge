"""Metrics endpoints for the agent.

Provides REST endpoints that aggregate usage data from the SQLite
``agent.db`` database to power the frontend metrics panel.
"""

from __future__ import annotations

import json
import logging
import os
import sys
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter

# ---------------------------------------------------------------------------
# Ensure the project root is in sys.path so absolute imports (backend.*)
# resolve correctly regardless of how the file is invoked.
# ---------------------------------------------------------------------------
_current_dir = os.path.dirname(os.path.abspath(__file__))
_project_root = os.path.dirname(os.path.dirname(_current_dir))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from backend.agent.utils.contract import (
    make_error_response,
    make_success_response,
    validate_response,
    zero_usage,
)
from backend.agent.utils.error_logger import log_error
from backend.instances import session_manager

logger = logging.getLogger(__name__)

router = APIRouter(tags=["metrics"])


def _get_db_path() -> str | None:
    """Return the path to agent.db, or None if session_manager is unavailable."""
    if session_manager is None:
        return None
    return session_manager.db_path


def _query_db(query: str, params: tuple = ()) -> list[dict]:
    """Execute a SQL query against agent.db and return rows as dicts.

    Args:
        query: SQL query string.
        params: Tuple of parameters for the query.

    Returns:
        List of dicts (one per row), or empty list on error.
    """
    db_path = _get_db_path()
    if db_path is None:
        return []

    import sqlite3

    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        rows = conn.execute(query, params).fetchall()
        conn.close()
        return [dict(row) for row in rows]
    except Exception as e:
        log_error(str(e), source="backend/routes/metrics.py:_query_db")
        logger.exception("Error querying metrics database")
        return []


@router.get("/metrics/sessions")
async def get_session_metrics():
    """Return session-level metrics aggregated from agent.db.

    Returns:
        A contract response with ``data`` containing session metrics.
    """
    try:
        # Total sessions (excluding sub-agents, which have parent_id)
        total_rows = _query_db(
            "SELECT COUNT(*) AS cnt FROM sessions WHERE parent_id IS NULL"
        )
        total_sessions = total_rows[0]["cnt"] if total_rows else 0

        # Total messages
        msg_rows = _query_db("SELECT COUNT(*) AS cnt FROM messages")
        total_messages = msg_rows[0]["cnt"] if msg_rows else 0

        # Average messages per session
        avg_messages = 0.0
        if total_sessions > 0:
            avg_messages = round(total_messages / total_sessions, 1)

        # Sessions by day (last 30 days)
        day_rows = _query_db(
            """
            SELECT 
                date(created_at) AS day,
                COUNT(*) AS cnt
            FROM sessions 
            WHERE parent_id IS NULL 
                AND created_at >= date('now', '-30 days')
            GROUP BY date(created_at)
            ORDER BY day ASC
            """
        )
        sessions_by_day = [
            {"date": row["day"], "count": row["cnt"]} for row in day_rows
        ]

        return validate_response(
            make_success_response(
                message="Session metrics obtenidas",
                data={
                    "total_sessions": total_sessions,
                    "total_messages": total_messages,
                    "avg_messages_per_session": avg_messages,
                    "sessions_by_day": sessions_by_day,
                },
                usage=zero_usage(),
            )
        )
    except Exception as e:
        log_error(str(e), source="backend/routes/metrics.py:get_session_metrics")
        return make_error_response(message="Error fetching session metrics")


@router.get("/metrics/tools")
async def get_tool_metrics():
    """Return tool usage metrics aggregated from agent.db.

    Returns:
        A contract response with ``data`` containing tool metrics.
    """
    try:
        # Tool usage (from tool_calls JSON in messages)
        tool_rows = _query_db(
            """
            SELECT tool_name, COUNT(*) AS cnt
            FROM messages
            WHERE tool_name IS NOT NULL AND tool_name != ''
            GROUP BY tool_name
            ORDER BY cnt DESC
            """
        )
        tool_usage = [
            {"name": row["tool_name"], "count": row["cnt"]} for row in tool_rows
        ]

        total_tool_calls = sum(t["count"] for t in tool_usage)

        # Sub-agent delegations (tool_calls where name = "task")
        subagent_rows = _query_db(
            """
            SELECT tool_name, COUNT(*) AS cnt
            FROM messages
            WHERE tool_name = 'task'
            GROUP BY tool_name
            """
        )
        top_subagents = [
            {"name": row["tool_name"], "count": row["cnt"]} for row in subagent_rows
        ]

        return validate_response(
            make_success_response(
                message="Tool metrics obtenidas",
                data={
                    "tool_usage": tool_usage,
                    "total_tool_calls": total_tool_calls,
                    "top_subagents": top_subagents,
                },
                usage=zero_usage(),
            )
        )
    except Exception as e:
        log_error(str(e), source="backend/routes/metrics.py:get_tool_metrics")
        return make_error_response(message="Error fetching tool metrics")


@router.get("/metrics/errors")
async def get_error_metrics():
    """Return error metrics from the error_log table.

    Returns:
        A contract response with ``data`` containing error metrics.
    """
    try:
        # Total errors
        total_rows = _query_db("SELECT COUNT(*) AS cnt FROM error_log")
        total_errors = total_rows[0]["cnt"] if total_rows else 0

        # Errors by day (last 30 days)
        day_rows = _query_db(
            """
            SELECT 
                date(created_at) AS day,
                COUNT(*) AS cnt
            FROM error_log
            WHERE created_at >= date('now', '-30 days')
            GROUP BY date(created_at)
            ORDER BY day ASC
            """
        )
        errors_by_day = [
            {"date": row["day"], "count": row["cnt"]} for row in day_rows
        ]

        # Errors by source
        source_rows = _query_db(
            """
            SELECT source, COUNT(*) AS cnt
            FROM error_log
            WHERE source IS NOT NULL AND source != ''
            GROUP BY source
            ORDER BY cnt DESC
            LIMIT 10
            """
        )
        errors_by_source = [
            {"source": row["source"], "count": row["cnt"]} for row in source_rows
        ]

        return validate_response(
            make_success_response(
                message="Error metrics obtenidas",
                data={
                    "total_errors": total_errors,
                    "errors_by_day": errors_by_day,
                    "errors_by_source": errors_by_source,
                },
                usage=zero_usage(),
            )
        )
    except Exception as e:
        log_error(str(e), source="backend/routes/metrics.py:get_error_metrics")
        return make_error_response(message="Error fetching error metrics")


@router.get("/metrics/models")
async def get_model_metrics():
    """Return LLM usage metrics grouped by model from agent.db.

    Counts assistant messages that recorded the model that produced
    them. Historical messages without a model are excluded.

    Returns:
        A contract response with ``data`` containing the per-model
        call counts, ordered from most to least used.
    """
    try:
        model_rows = _query_db(
            """
            SELECT model, COUNT(*) AS cnt
            FROM messages
            WHERE role = 'assistant'
                AND model IS NOT NULL AND model != ''
            GROUP BY model
            ORDER BY cnt DESC
            """
        )
        models = [
            {"model": row["model"], "count": row["cnt"]} for row in model_rows
        ]
        total_model_calls = sum(m["count"] for m in models)

        return validate_response(
            make_success_response(
                message="Model metrics obtenidas",
                data={
                    "models": models,
                    "total_model_calls": total_model_calls,
                },
                usage=zero_usage(),
            )
        )
    except Exception as e:
        log_error(str(e), source="backend/routes/metrics.py:get_model_metrics")
        return make_error_response(message="Error fetching model metrics")


@router.get("/metrics/overview")
async def get_metrics_overview():
    """Return an overview combining all metrics in a single response.

    Returns:
        A contract response with ``data`` containing combined metrics.
    """
    try:
        # Session metrics
        total_rows = _query_db(
            "SELECT COUNT(*) AS cnt FROM sessions WHERE parent_id IS NULL"
        )
        total_sessions = total_rows[0]["cnt"] if total_rows else 0

        msg_rows = _query_db("SELECT COUNT(*) AS cnt FROM messages")
        total_messages = msg_rows[0]["cnt"] if msg_rows else 0

        avg_messages = 0.0
        if total_sessions > 0:
            avg_messages = round(total_messages / total_sessions, 1)

        # Tool usage
        tool_rows = _query_db(
            """
            SELECT tool_name, COUNT(*) AS cnt
            FROM messages
            WHERE tool_name IS NOT NULL AND tool_name != ''
            GROUP BY tool_name
            ORDER BY cnt DESC
            LIMIT 5
            """
        )
        top_tools = [
            {"name": row["tool_name"], "count": row["cnt"]} for row in tool_rows
        ]

        # Errors
        err_rows = _query_db("SELECT COUNT(*) AS cnt FROM error_log")
        total_errors = err_rows[0]["cnt"] if err_rows else 0

        # Sessions by day (last 30 days)
        day_rows = _query_db(
            """
            SELECT 
                date(created_at) AS day,
                COUNT(*) AS cnt
            FROM sessions 
            WHERE parent_id IS NULL 
                AND created_at >= date('now', '-30 days')
            GROUP BY date(created_at)
            ORDER BY day ASC
            """
        )
        sessions_by_day = [
            {"date": row["day"], "count": row["cnt"]} for row in day_rows
        ]

        return validate_response(
            make_success_response(
                message="Overview obtenida",
                data={
                    "total_sessions": total_sessions,
                    "total_messages": total_messages,
                    "avg_messages_per_session": avg_messages,
                    "total_errors": total_errors,
                    "top_tools": top_tools,
                    "sessions_by_day": sessions_by_day,
                },
                usage=zero_usage(),
            )
        )
    except Exception as e:
        log_error(str(e), source="backend/routes/metrics.py:get_metrics_overview")
        return make_error_response(message="Error fetching metrics overview")
