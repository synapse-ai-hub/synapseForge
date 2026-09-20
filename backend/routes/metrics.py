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
from backend.utils.db import get_connection
from backend.instances import session_manager

logger = logging.getLogger(__name__)

router = APIRouter(tags=["metrics"])


def _avg_agent_latency(conn) -> float:
    """Return the average per-turn agent latency in seconds (2 decimals).

    Per-turn latency (tf - t0) is reconstructed as: the summed
    ``total_time`` of the turn's non-final assistant steps (sequential LLM
    calls) + per step the MAX ``total_time`` of its tool rows (tools in the
    same step run concurrently, so the slowest one sets the step wall time)
    + the final assistant row's ``time_to_first_token`` (the clock stops at
    the final answer's first chunk, so the final step's full total is NOT
    added). The average is taken over all (session, turn) groups.
    """
    try:
        rows = conn.execute(
            """
            SELECT AVG(lat) AS avg FROM (
                SELECT
                    COALESCE((
                        SELECT SUM(a.total_time) FROM messages a
                        WHERE a.role = 'assistant'
                            AND a.session_id = b.sid
                            AND a.turn_number = b.t
                            AND a.step < b.max_step
                    ), 0)
                    + COALESCE((
                        SELECT SUM(mx) FROM (
                            SELECT MAX(t2.total_time) AS mx FROM messages t2
                            WHERE t2.role = 'tool'
                                AND t2.session_id = b.sid
                                AND t2.turn_number = b.t
                            GROUP BY t2.step
                        )
                    ), 0)
                    + COALESCE((
                        SELECT m2.time_to_first_token FROM messages m2
                        WHERE m2.role = 'assistant'
                            AND m2.session_id = b.sid
                            AND m2.turn_number = b.t
                        ORDER BY m2.step DESC LIMIT 1
                    ), 0) AS lat
                FROM (
                    SELECT session_id AS sid, turn_number AS t, MAX(step) AS max_step
                    FROM messages
                    WHERE role = 'assistant'
                    GROUP BY session_id, turn_number
                ) AS b
            )
            """
        ).fetchall()
        return round(float(rows[0]["avg"] or 0.0), 2)
    except Exception as e:
        log_error(str(e), source="backend/routes/metrics.py:_avg_agent_latency")
        return 0.0


@router.get("/metrics/sessions")
async def get_session_metrics():
    """Return session-level metrics aggregated from agent.db.

    Returns:
        A contract response with ``data`` containing session metrics.
    """
    try:
        with get_connection() as conn:
            # Total sessions (excluding sub-agents, which have parent_id)
            total_rows = conn.execute(
                "SELECT COUNT(*) AS cnt FROM sessions WHERE parent_id IS NULL"
            ).fetchall()
            total_sessions = total_rows[0]["cnt"] if total_rows else 0

            # Total messages
            msg_rows = conn.execute("SELECT COUNT(*) AS cnt FROM messages").fetchall()
            total_messages = msg_rows[0]["cnt"] if msg_rows else 0

            # Average messages per session
            avg_messages = 0.0
            if total_sessions > 0:
                avg_messages = round(total_messages / total_sessions, 1)

            # Token consumption metrics
            token_rows = conn.execute(
                "SELECT SUM(total_tokens) AS total FROM messages WHERE total_tokens IS NOT NULL"
            ).fetchall()
            total_tokens = token_rows[0]["total"] or 0

            avg_tokens_per_session = 0.0
            if total_sessions > 0:
                avg_tokens_per_session = round(total_tokens / total_sessions, 1)

            avg_tokens_per_message = 0.0
            if total_messages > 0:
                avg_tokens_per_message = round(total_tokens / total_messages, 1)

            # Average tokens per tool call
            tool_token_rows = conn.execute(
                "SELECT SUM(total_tokens) AS total FROM messages WHERE tool_name IS NOT NULL AND tool_name != '' AND total_tokens IS NOT NULL"
            ).fetchall()
            total_tool_tokens = tool_token_rows[0]["total"] or 0
            tool_call_rows = conn.execute(
                "SELECT COUNT(*) AS cnt FROM messages WHERE tool_name IS NOT NULL AND tool_name != ''"
            ).fetchall()
            total_tool_calls_for_avg = tool_call_rows[0]["cnt"] if tool_call_rows else 0
            avg_tokens_per_tool = 0.0
            if total_tool_calls_for_avg > 0:
                avg_tokens_per_tool = round(total_tool_tokens / total_tool_calls_for_avg, 1)

            # Cost metrics (from messages table — per call cost).
            # All money values use 2 decimals (USD).
            cost_rows = conn.execute(
                "SELECT SUM(cost_total) AS total FROM messages WHERE cost_total IS NOT NULL"
            ).fetchall()
            total_cost = round(float(cost_rows[0]["total"] or 0.0), 2)

            avg_cost_per_session = 0.0
            if total_sessions > 0:
                avg_cost_per_session = round(total_cost / total_sessions, 2)

            avg_cost_per_message = 0.0
            if total_messages > 0:
                avg_cost_per_message = round(total_cost / total_messages, 2)

            # Average cost per tool call
            tool_cost_rows = conn.execute(
                "SELECT SUM(cost_total) AS total FROM messages WHERE tool_name IS NOT NULL AND tool_name != '' AND cost_total IS NOT NULL"
            ).fetchall()
            total_tool_cost = tool_cost_rows[0]["total"] or 0.0
            avg_cost_per_tool = 0.0
            if total_tool_calls_for_avg > 0:
                avg_cost_per_tool = round(total_tool_cost / total_tool_calls_for_avg, 2)

            # Average cost per provider-model (from spend table — aggregated)
            spend_avg_rows = conn.execute(
                "SELECT AVG(cost_total) AS avg FROM spend WHERE cost_total > 0"
            ).fetchall()
            avg_cost_per_provider_model = spend_avg_rows[0]["avg"] or 0.0
            if avg_cost_per_provider_model is not None:
                avg_cost_per_provider_model = round(float(avg_cost_per_provider_model), 2)

            # Time metrics (seconds, 2 decimals). total_time is recorded on
            # assistant rows (LLM latency) and tool rows (execution time).
            time_rows = conn.execute(
                "SELECT SUM(total_time) AS total FROM messages WHERE total_time IS NOT NULL"
            ).fetchall()
            total_time = round(float(time_rows[0]["total"] or 0.0), 2)

            # Average time per turn: mean of per-(session, turn) sums.
            turn_time_rows = conn.execute(
                """
                SELECT AVG(turn_total) AS avg FROM (
                    SELECT SUM(total_time) AS turn_total
                    FROM messages
                    WHERE total_time IS NOT NULL AND turn_number IS NOT NULL
                    GROUP BY session_id, turn_number
                )
                """
            ).fetchall()
            avg_time_per_turn = turn_time_rows[0]["avg"] or 0.0
            avg_time_per_turn = round(float(avg_time_per_turn), 2)

            # Average time per session: total time over root sessions
            # (same methodology as avg_tokens_per_session).
            avg_time_per_session = 0.0
            if total_sessions > 0:
                avg_time_per_session = round(total_time / total_sessions, 2)

            # Average agent latency per turn (tf - t0 reconstruction).
            avg_agent_latency = _avg_agent_latency(conn)

            # Sessions by day (last 30 days)
            day_rows = conn.execute(
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
            ).fetchall()
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
                    "total_tokens": total_tokens,
                    "avg_tokens_per_session": avg_tokens_per_session,
                    "avg_tokens_per_message": avg_tokens_per_message,
                    "avg_tokens_per_tool": avg_tokens_per_tool,
                    "total_cost": total_cost,
                    "avg_cost_per_session": avg_cost_per_session,
                    "avg_cost_per_message": avg_cost_per_message,
                    "avg_cost_per_tool": avg_cost_per_tool,
                    "avg_cost_per_provider_model": avg_cost_per_provider_model,
                    "total_time": total_time,
                    "avg_time_per_turn": avg_time_per_turn,
                    "avg_time_per_session": avg_time_per_session,
                    "avg_agent_latency": avg_agent_latency,
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
        with get_connection() as conn:
            # Tool usage (from tool_calls JSON in messages)
            tool_rows = conn.execute(
                """
                SELECT tool_name, COUNT(*) AS cnt, AVG(total_time) AS avg_time
                FROM messages
                WHERE tool_name IS NOT NULL AND tool_name != ''
                GROUP BY tool_name
                ORDER BY cnt DESC
                """
            ).fetchall()
            tool_usage = [
                {
                    "name": row["tool_name"],
                    "count": row["cnt"],
                    "avg_time": round(float(row["avg_time"] or 0.0), 2),
                }
                for row in tool_rows
            ]

            total_tool_calls = sum(t["count"] for t in tool_usage)

            # Average execution time per tool call (seconds, 2 decimals).
            tool_time_rows = conn.execute(
                """
                SELECT AVG(total_time) AS avg FROM messages
                WHERE tool_name IS NOT NULL AND tool_name != ''
                    AND total_time IS NOT NULL
                """
            ).fetchall()
            avg_time_per_tool_call = tool_time_rows[0]["avg"] or 0.0
            avg_time_per_tool_call = round(float(avg_time_per_tool_call), 2)

            # Sub-agent delegations (tool_calls where name = "task")
            subagent_rows = conn.execute(
                """
                SELECT tool_name, COUNT(*) AS cnt
                FROM messages
                WHERE tool_name = 'task'
                GROUP BY tool_name
                """
            ).fetchall()
        top_subagents = [
            {"name": row["tool_name"], "count": row["cnt"]} for row in subagent_rows
        ]

        return validate_response(
            make_success_response(
                message="Tool metrics obtenidas",
                data={
                    "tool_usage": tool_usage,
                    "total_tool_calls": total_tool_calls,
                    "avg_time_per_tool_call": avg_time_per_tool_call,
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
        with get_connection() as conn:
            # Total errors (excluding provider key errors)
            total_rows = conn.execute(
                "SELECT COUNT(*) AS cnt FROM error_log WHERE exception NOT LIKE '%key%' AND exception NOT LIKE '%api_key%'"
            ).fetchall()
            total_errors = total_rows[0]["cnt"] if total_rows else 0

            # Errors by day (last 30 days, excluding provider key errors)
            day_rows = conn.execute(
                """
                SELECT 
                    date(created_at) AS day,
                    COUNT(*) AS cnt
                FROM error_log
                WHERE created_at >= date('now', '-30 days')
                    AND exception NOT LIKE '%key%'
                    AND exception NOT LIKE '%api_key%'
                GROUP BY date(created_at)
                ORDER BY day ASC
                """
            ).fetchall()
            errors_by_day = [
                {"date": row["day"], "count": row["cnt"]} for row in day_rows
            ]

            # Errors by source (excluding provider key errors — missing API keys are not agent errors)
            source_rows = conn.execute(
                """
                SELECT source, COUNT(*) AS cnt
                FROM error_log
                WHERE source IS NOT NULL AND source != ''
                    AND source NOT LIKE '%provider_keys%'
                    AND exception NOT LIKE '%key%'
                    AND exception NOT LIKE '%api_key%'
                GROUP BY source
                ORDER BY cnt DESC
                LIMIT 10
                """
            ).fetchall()
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
        with get_connection() as conn:
            model_rows = conn.execute(
                """
                SELECT model, COUNT(*) AS cnt
                FROM messages
                WHERE role = 'assistant'
                    AND model IS NOT NULL AND model != ''
                GROUP BY model
                ORDER BY cnt DESC
                """
            ).fetchall()
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
        with get_connection() as conn:
            # Session metrics
            total_rows = conn.execute(
                "SELECT COUNT(*) AS cnt FROM sessions WHERE parent_id IS NULL"
            ).fetchall()
            total_sessions = total_rows[0]["cnt"] if total_rows else 0

            msg_rows = conn.execute("SELECT COUNT(*) AS cnt FROM messages").fetchall()
            total_messages = msg_rows[0]["cnt"] if msg_rows else 0

            avg_messages = 0.0
            if total_sessions > 0:
                avg_messages = round(total_messages / total_sessions, 1)

            # Tool usage
            tool_rows = conn.execute(
                """
                SELECT tool_name, COUNT(*) AS cnt
                FROM messages
                WHERE tool_name IS NOT NULL AND tool_name != ''
                GROUP BY tool_name
                ORDER BY cnt DESC
                LIMIT 5
                """
            ).fetchall()
            top_tools = [
                {"name": row["tool_name"], "count": row["cnt"]} for row in tool_rows
            ]

            # Token consumption metrics
            token_rows = conn.execute(
                "SELECT SUM(total_tokens) AS total FROM messages WHERE total_tokens IS NOT NULL"
            ).fetchall()
            total_tokens = token_rows[0]["total"] or 0
            avg_tokens_per_session = round(total_tokens / total_sessions, 1) if total_sessions > 0 else 0.0
            avg_tokens_per_message = round(total_tokens / total_messages, 1) if total_messages > 0 else 0.0

            # Cost metrics (2 decimals, USD).
            cost_rows = conn.execute(
                "SELECT SUM(cost_total) AS total FROM messages WHERE cost_total IS NOT NULL"
            ).fetchall()
            total_cost = round(float(cost_rows[0]["total"] or 0.0), 2)
            avg_cost_per_session = round(total_cost / total_sessions, 2) if total_sessions > 0 else 0.0
            avg_cost_per_message = round(total_cost / total_messages, 2) if total_messages > 0 else 0.0

            # Average cost per provider-model (from spend table)
            spend_avg_rows = conn.execute(
                "SELECT AVG(cost_total) AS avg FROM spend WHERE cost_total > 0"
            ).fetchall()
            avg_cost_per_provider_model = spend_avg_rows[0]["avg"] or 0.0
            if avg_cost_per_provider_model is not None:
                avg_cost_per_provider_model = round(float(avg_cost_per_provider_model), 2)

            # Time metrics (seconds, 2 decimals).
            time_rows = conn.execute(
                "SELECT SUM(total_time) AS total FROM messages WHERE total_time IS NOT NULL"
            ).fetchall()
            total_time = round(float(time_rows[0]["total"] or 0.0), 2)
            turn_time_rows = conn.execute(
                """
                SELECT AVG(turn_total) AS avg FROM (
                    SELECT SUM(total_time) AS turn_total
                    FROM messages
                    WHERE total_time IS NOT NULL AND turn_number IS NOT NULL
                    GROUP BY session_id, turn_number
                )
                """
            ).fetchall()
            avg_time_per_turn = round(float(turn_time_rows[0]["avg"] or 0.0), 2)
            avg_time_per_session = round(total_time / total_sessions, 2) if total_sessions > 0 else 0.0

            # Average agent latency per turn (tf - t0 reconstruction).
            avg_agent_latency = _avg_agent_latency(conn)

            # Errors (excluding provider key errors)
            err_rows = conn.execute(
                "SELECT COUNT(*) AS cnt FROM error_log WHERE exception NOT LIKE '%key%' AND exception NOT LIKE '%api_key%'"
            ).fetchall()
            total_errors = err_rows[0]["cnt"] if err_rows else 0

            # Sessions by day (last 30 days)
            day_rows = conn.execute(
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
            ).fetchall()
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
                    "total_tokens": total_tokens,
                    "avg_tokens_per_session": avg_tokens_per_session,
                    "avg_tokens_per_message": avg_tokens_per_message,
                    "total_cost": total_cost,
                    "avg_cost_per_session": avg_cost_per_session,
                    "avg_cost_per_message": avg_cost_per_message,
                    "avg_cost_per_provider_model": avg_cost_per_provider_model,
                    "total_time": total_time,
                    "avg_time_per_turn": avg_time_per_turn,
                    "avg_time_per_session": avg_time_per_session,
                    "avg_agent_latency": avg_agent_latency,
                },
                usage=zero_usage(),
            )
        )
    except Exception as e:
        log_error(str(e), source="backend/routes/metrics.py:get_metrics_overview")
        return make_error_response(message="Error fetching metrics overview")
