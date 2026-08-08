"""Helper functions for the agent loop.

Extracted from ``loop.py`` so the loop module stays focused on the
iteration logic. Each helper is a plain module-level function that
receives its dependencies as arguments (no hidden shared state).
"""

from __future__ import annotations

import json
import logging
import os
import sqlite3
import sys
import time
import urllib.request
from datetime import datetime
from typing import Any

# ---------------------------------------------------------------------------
# Ensure the project root is in sys.path so absolute imports (backend.*)
# resolve correctly regardless of how the file is invoked.
# loop_helpers.py is at backend/agent/ -> need 2 dirname() calls to reach root.
# ---------------------------------------------------------------------------
_current_dir = os.path.dirname(os.path.abspath(__file__))
_project_root = os.path.dirname(os.path.dirname(_current_dir))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from backend.agent.permissions import get_agent_prompt, list_agents
from backend.agent.utils.error_logger import log_error
from backend.agent.utils.skill_loader import format_skills_section
from backend.instances import agent
from backend.agent.utils.config_dir import get_agents_dir

logger = logging.getLogger(__name__)

_CONFIG_BASE_URL = os.getenv("CONFIG_BASE_URL", "http://127.0.0.1:8000/api/config")
_SESSION_DB_PATH = os.path.join(os.path.dirname(os.path.dirname(_current_dir)), "backend", "agent", "agent_db", "agent.db")


def _mandatory_block() -> str:
    """Load the MANDATORY rules block from ``prompts/mandatory.md``.

    Returns:
        The block content, or ``""`` if the prompt file is missing.
    """
    try:
        return agent.prompt("mandatory")
    except FileNotFoundError:
        logger.warning("Prompt mandatory.md no encontrado; no se inyecta MANDATORY.")
        return ""


def load_context_text() -> str:
    """Load all context files from SQLite and return their content joined.

    Reads every row from the ``context_files`` table and joins the file name
    and extracted text with a visible separator.  Returns an empty string if
    no context files exist or the table cannot be read.

    Returns:
        A formatted string ready to be appended to the system prompt.
    """
    db_dir = os.path.dirname(_SESSION_DB_PATH)
    if db_dir:
        os.makedirs(db_dir, exist_ok=True)
    try:
        conn = sqlite3.connect(_SESSION_DB_PATH)
        conn.row_factory = sqlite3.Row
        try:
            rows = conn.execute(
                "SELECT filename, content FROM context_files ORDER BY id"
            ).fetchall()
        finally:
            conn.close()
        if not rows:
            return ""
        parts: list[str] = []
        for row in rows:
            parts.append(f"--- {row['filename']} ---\n{row['content']}")
        return "==================================\n".join(parts)
    except Exception as exc:
        logger.warning("No se pudieron cargar archivos de contexto: %s", exc)
        return ""


def fetch_context_window_turns() -> int:
    """Query the config endpoint for the current context-window setting.

    Returns the ``max_turns`` value reported by
    ``GET /api/config/context-window``.  Falls back to ``-1`` (all
    turns) if the endpoint is unreachable.
    """
    try:
        url = f"{_CONFIG_BASE_URL}/context-window"
        with urllib.request.urlopen(url, timeout=5) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        return int(data.get("max_turns", -1))
    except Exception as exc:
        logger.warning("Failed to fetch context window from endpoint: %s", exc)
        log_error(str(exc), source="loop_helpers.py:fetch_context_window_turns")
        return -1


def build_system_prompt(agent_name: str | None = None) -> str:
    """Build the system prompt for an agent.

    - If *agent_name* is ``None`` (router): ``system_prompt.md`` is always the
      base prompt. If ``AGENT.md`` exists in the agents config directory, it is
      injected as a ``## Behavior`` section before ``## MANDATORY:``.
      In both cases, append the current date and the list of available
      agents (from the agents folder). No placeholders, no ``.format()``.
    - If *agent_name* is provided (sub-agent): resolve the system prompt
      from the agent's markdown via ``get_agent_prompt``.

    Args:
        agent_name: Optional sub-agent name. ``None`` means the router.

    Returns:
        The system prompt string.
    """

    # Date
    fecha = datetime.now().strftime("%d/%m/%Y %H:%M")
    print(f"[DEBUG de la verga que hice] loop_helpers.build_system_prompt.INICIO agent={agent_name} ts={time.time()}")
    
    if agent_name is not None:
        result = get_agent_prompt(agent_name)
        if result.get("status") == "success":
            base = result.get("data", "") or ""
            mandatory = _mandatory_block()

            # AGENT.md (comportamiento general) se inyecta antes de MANDATORY
            behavior_text = ""
            agent_md_path = get_agents_dir() / "AGENT.md"
            if agent_md_path.is_file():
                try:
                    with open(agent_md_path, encoding="utf-8") as f:
                        behavior_text = f.read()
                except (OSError, UnicodeDecodeError) as exc:
                    logger.warning("Error al leer AGENT.md: %s; no se inyecta Behavior.", exc)
                    log_error(str(exc), source="loop_helpers.py:build_system_prompt")

            if behavior_text or mandatory:
                parts = [base] if base else []
                if behavior_text:
                    parts.append(f"## Behavior\n{behavior_text}")
                if mandatory:
                    parts.append(f"## MANDATORY:\n{mandatory}")
                parts.append(f"## Fecha\n{fecha}")
                system_prompt = "\n\n---\n\n".join(parts)
                # print(f'\n\n\n{"#"*80}\nSystem prompt:\n\n{system_prompt}\n{"#"*80}\n\n\n')
                return system_prompt

            # print(f'\n\n\n{"#"*80}\nSystem prompt:\n\n{base}\n{"#"*80}\n\n\n')
            return base
        logger.warning(
            "Agent '%s' no encontrado; usando system prompt del router.", agent_name
        )

# Router: system_prompt.md es SIEMPRE la base; AGENT.md se inyecta como ## Behavior.
    base_prompt = agent.prompt("system_prompt")

    

    

    # Agents from the agents folder
    agents_result = list_agents()
    agents = (
        json.loads(agents_result["data"])
        if agents_result.get("status") == "success"
        else []
    )
    agents_str = ""
    if agents:
        agents_str = "\n".join(
            f"- {a['name']}: {a['description']}" for a in agents
        )

    # Concatenate: base + date + agents + context (no .format())
    parts = []
    if base_prompt:
        parts.append(base_prompt)
    
    if agents_str:
        parts.append(f"## Agentes\n{agents_str}")

    # Append context files content 
    context_text = load_context_text()
    if context_text:
        parts.append(f"## Contexto\n{context_text}")

    # AGENT.md (comportamiento general) se inyecta antes de MANDATORY
    agent_md_path = get_agents_dir() / "AGENT.md"
    if agent_md_path.is_file():
        try:
            with open(agent_md_path, encoding="utf-8") as f:
                behavior_text = f.read()
            parts.append(f"## Behavior\n{behavior_text}")
        except (OSError, UnicodeDecodeError) as exc:
            logger.warning("Error al leer AGENT.md: %s; no se inyecta Behavior.", exc)
            log_error(str(exc), source="loop_helpers.py:build_system_prompt")

    # Reglas obligatorias inyectadas al final del prompt de todos los agentes
    mandatory = _mandatory_block()
    if mandatory:
        parts.append(f"## MANDATORY:\n{mandatory}")

    parts.append(f"## Fecha\n{fecha}")

    final_prompt = "\n\n---\n\n".join(parts)

    # print(f'\n\n\n{"#"*80}\nSystem prompt:\n\n{final_prompt}\n{"#"*80}\n\n\n')
    return final_prompt


def build_initial_messages(
    session_manager,
    session_id: str,
    system_prompt: str,
    user_message: str,
    max_turns: int = -1,
) -> list[dict[str, Any]]:
    """Build the initial messages array.

    Structure::

        [{"role": "system", "content": ...},
         ...session history (filtered by max_turns)...,
         {"role": "user", "content": current_message}]

    Args:
        session_manager: The ``SessionManager`` instance.
        session_id: Session ID to load history.
        system_prompt: Built system prompt.
        user_message: Current user message.
        max_turns: Number of recent turns to load (``-1`` = all).

    Returns:
        Messages array ready for the API.
    """
    messages: list[dict[str, Any]] = [
        {"role": "system", "content": system_prompt},
    ]
    print(f"[DEBUG de la verga que hice] loop_helpers.build_initial_messages.INICIO session={session_id} ts={time.time()}")

    history = session_manager.load_messages(session_id, max_turns=max_turns)
    for msg in history:
        role = msg.get("role", "")
        if role == "system":
            continue  # Use our system prompt, not the saved one

        entry: dict[str, Any] = {"role": role}

        content = msg.get("content")
        if content is not None:
            entry["content"] = content

        tool_calls = msg.get("tool_calls")
        if tool_calls:
            entry["tool_calls"] = tool_calls

        if role == "tool":
            tool_call_id = msg.get("tool_call_id")
            if tool_call_id:
                entry["tool_call_id"] = tool_call_id
            tool_name = msg.get("tool_name")
            if tool_name:
                entry["tool_name"] = tool_name

        messages.append(entry)

    messages.append({"role": "user", "content": user_message})

    return messages


async def execute_tool(agent, tc: dict[str, Any]) -> Any:
    """Execute a tool call by name.

    Delegates to ``agent.tools._execute_tool`` which handles both native
    and external tools and returns the unified contract
    ``{status, message, data, usage}``.

    Args:
        agent: The ``Agent`` instance (provides ``tools``).
        tc: Normalized tool call with ``name`` and ``args``.

    Returns:
        Result data (``data`` from contract), or dict with
        ``{"error": message}`` on failure.
    """
    tool_name = tc["name"]
    tool_args = tc.get("args", {})

    print(f"[DEBUG de la verga que hice] loop_helpers.execute_tool.INICIO tool={tool_name} ts={time.time()}")
    try:
        result = await agent.tools._execute_tool(tool_name, **tool_args)
    except Exception as e:
        logger.exception("Tool '%s' failed", tool_name)
        log_error(str(e), source="loop_helpers.py:execute_tool")
        return {"error": str(e)}
    print(f"[DEBUG de la verga que hice] loop_helpers.execute_tool.FIN tool={tool_name} ts={time.time()}")

    if isinstance(result, dict) and result.get("status") == "error":
        error_msg = result.get("message", f"Tool '{tool_name}' failed")
        logger.error("Tool '%s' error: %s", tool_name, error_msg)
        return {"error": error_msg}

    if isinstance(result, dict) and "data" in result:
        return result["data"]
    return result
