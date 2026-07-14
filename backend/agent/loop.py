"""Agent loop — iterative loop with native tool calling.

Pattern
-------
1. Create/recover session in SQLite.
2. Load conversation history from SQLite.
3. Build system prompt (base + skills).
4. Resolve tools from ``agent.tools.tools_registry``.
5. ``while True``:
   a. Call LLM with ``messages`` + ``tools`` (no streaming).
   b. If response has ``tool_calls`` → execute each tool,
      append results as ``role: "tool"`` messages, continue.
   c. If no ``tool_calls`` → yield content as chunk and break.
6. Persist every message in SQLite.

Both Groq (``client.chat.completions.create``) and Ollama
(``ollama.chat``) support the ``tools`` parameter with JSON Schema
definitions. Tool calls arrive as structured data, not as text to parse.

Sub-agent delegation
--------------------
The ``task`` tool resolves a sub-agent's system prompt and permissions
from its markdown, creates an integrated child session (``parent_id``),
and calls ``run`` again with the resolved arguments. This produces a
``run`` inside ``run`` (recursion) where each level is isolated by its
own session. The parent loop emits ``subagent_call`` / ``subagent_result``
SSE events (collapsible) around the delegation.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import sys
from typing import Any, AsyncGenerator

import urllib.request
from dotenv import load_dotenv

# ---------------------------------------------------------------------------
# Ensure the project root is in sys.path so absolute imports (backend.*)
# resolve correctly regardless of how the file is invoked.
# ---------------------------------------------------------------------------
_current_dir = os.path.dirname(os.path.abspath(__file__))
_project_root = os.path.dirname(os.path.dirname(_current_dir))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from datetime import datetime
from backend.agent.utils.error_logger import log_error, set_error_context, reset_error_context, get_error_context
from backend.agent.utils.skill_loader import format_skills_section
from backend.agent.permissions import list_agents
from backend.agent.utils.clean_memory import liberar_modelo
from backend.instances import agent, session_manager, context_manager
from backend.agent.loop_helpers import (
    build_initial_messages,
    build_system_prompt,
    execute_tool,
    fetch_context_window_turns,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Config endpoint
# ---------------------------------------------------------------------------

_CONFIG_BASE_URL = os.getenv("CONFIG_BASE_URL", "http://127.0.0.1:8000/api/config")

MAX_ITERATIONS = 25
"""Maximum tool-calling iterations before forcing a response (safety net)."""

MAX_SUBAGENT_DEPTH = 3
"""Maximum nesting depth for sub-agent delegation (recursion guard)."""


class AgentLoop:
    """Agent loop with native tool calling.

    The loop iterates calling the LLM with available tools. The LLM
    autonomously decides whether to call a tool or produce the final
    response. The loop only ends when the LLM returns no ``tool_calls``.

    Attributes:
        max_iterations: Max tool-calling iterations before forced response.
    """

    def __init__(
        self,
        agent: Any,
        session_manager: Any,
        context_manager: Any,
        max_iterations: int = MAX_ITERATIONS,
    ) -> None:
        """Initialise the agent loop.

        Args:
            agent: ``Agent`` instance.
            session_manager: ``SessionManager`` for SQLite.
            context_manager: ``ContextManager`` for context control.
            max_iterations: Max tool-calling iterations.
        """
        self.max_iterations = max_iterations

    # ------------------------------------------------------------------
    # Public entry point
    # ------------------------------------------------------------------

    async def run(
        self,
        session_id: str,
        user_message: str,
        file_contents: list[tuple[str, str]] | None = None,
        stream_cancel_event: asyncio.Event | None = None,
        system_prompt: str | None = None,
        tool_permissions: dict | None = None,
        skill_permissions: dict | None = None,
        parameters: dict | None = None,
        agent_name: str | None = None,
        depth: int = 0,
        parent_id: str | None = None,
    ) -> AsyncGenerator[dict[str, Any], None]:
        """Run the agent loop for a single user message.

        Args:
            session_id: Unique session identifier.
            user_message: User message text.
            file_contents: Optional list of (filename, text) attachments.
            stream_cancel_event: Event to cancel streaming mid-response.
            system_prompt: Pre-resolved system prompt. If ``None``, it is
                built for the router (or for *agent_name* if provided).
            tool_permissions: Tool permission dict (from an agent's
                frontmatter). ``None`` → all tools.
            skill_permissions: Skill permission dict. ``None`` → all skills.
            parameters: Model/agent parameters (TODO: from frontmatter).
            agent_name: Sub-agent name being executed (``None`` = router).
            depth: Current sub-agent nesting depth (recursion guard).
            parent_id: Parent session identifier (for sub-agents).

        Yields:
            SSE events (raw ``"data: {...}\\n\\n"`` strings):
            - ``{"type": "chunk", "content": str}`` — text fragment.
            - ``{"type": "tool_call", "content": {"name", "args"}}`` — tool.
            - ``{"type": "tool_result", "content": {"name", "result"}}``.
            - ``{"type": "subagent_call", "content": {"agent_name", "prompt"}}``.
            - ``{"type": "subagent_result", "content": {"agent_name", "result"}}``.
            - ``"data: [DONE]\\n\\n"`` — stream end.

            On error, the stream yields a chunk SSE event followed by
            the raw ``[DONE]`` marker.
        """
        # --- 0.5. Set error logging context FIRST (covers recursion guard and all early errors) ---
        error_ctx_token = set_error_context(
            session_id=session_id,
            turn_number=0,  # Will be updated after getting actual turn_number
            agent_name=agent_name,
            depth=depth,
            parent_id=parent_id,
        )

        # --- Recursion guard for sub-agent delegation ---
        if depth >= MAX_SUBAGENT_DEPTH:
            log_error("Max sub-agent depth reached", source="loop.py:recursion_guard")
            yield f"data: {json.dumps({'type': 'chunk', 'content': 'No se puede delegar: se alcanzó la profundidad máxima de sub-agentes.'}, ensure_ascii=False)}\n\n"
            yield "data: [DONE]\n\n"
            await asyncio.to_thread(liberar_modelo, agent._resolved_model, session_id, 0, parent_id)
            reset_error_context(error_ctx_token)
            return

        # --- Track current session/depth on the Tools instance so that the
        #     `task` tool can create an integrated child session. ---
        agent.tools._current_session_id = session_id
        agent.tools._current_depth = depth

        # --- 0. Model (resuelto por el endpoint /api/config/models) ---
        model = agent._resolved_model

        # --- 0a. Resolve model parameters (temperature, top_p, model override) ---
        # parameters dict comes from agent frontmatter (via task tool or router)
        temperature = 0.0
        top_p = 0.5
        max_tokens = 3000
        if parameters:
            temperature = parameters.get("temperature", temperature)
            top_p = parameters.get("top_p", top_p)
            # model override from frontmatter (optional)
            if parameters.get("model"):
                model = parameters["model"]
            max_tokens = parameters.get("max_tokens", max_tokens)

        logger.info(
            "Agent loop started — model: %s, session: %s, agent: %s, depth: %d, temp: %s, top_p: %s",
            model, session_id, agent_name, depth, temperature, top_p,
        )

        # --- 0b. Free model at the start of the cycle ---
        try:
            # Capture context for thread pool
            ctx = get_error_context()
            await asyncio.to_thread(
                liberar_modelo, model,
                ctx.get("session_id") if ctx else None,
                ctx.get("turn_number") if ctx else None,
                ctx.get("parent_id") if ctx else None,
            )
        except Exception as exc:
            logger.warning("Error liberando modelo al inicio del ciclo: %s", exc)
            log_error(str(exc), source="loop.py:run")

        # --- 1. Ensure session exists ---
        result = session_manager.create_session(session_id)
        if result.get("status") == "error" and "already exists" not in result.get("message", ""):
            msg = result.get("message", "Error al crear sesión")
            yield f"data: {json.dumps({'type': 'chunk', 'content': msg}, ensure_ascii=False)}\n\n"
            yield "data: [DONE]\n\n"
            ctx = get_error_context()
            await asyncio.to_thread(
                liberar_modelo, model,
                ctx.get("session_id") if ctx else None,
                ctx.get("turn_number") if ctx else None,
                ctx.get("parent_id") if ctx else None,
            )
            reset_error_context(error_ctx_token)
            return

        # --- 1b. Get turn_number for this message ---
        turn_number = session_manager.get_last_turn_number(session_id) + 1

        # --- 1c. Update error logging context with actual turn_number ---
        reset_error_context(error_ctx_token)
        error_ctx_token = set_error_context(
            session_id=session_id,
            turn_number=turn_number,
            agent_name=agent_name,
            depth=depth,
            parent_id=parent_id,
        )

        # --- 2. Build system prompt ---
        if system_prompt is None:
            system_prompt = build_system_prompt(agent_name)

        # Sub-agents get their skills/agents appended (router prompt already
        # includes them via system_prompt.md placeholders).
        if agent_name is not None:
            skills_section = format_skills_section(skill_permissions=skill_permissions)
            agents_result = list_agents()
            agents = (
                json.loads(agents_result["data"])
                if agents_result.get("status") == "success"
                else []
            )
            system_prompt = (
                f"{system_prompt}\n\n"
                f"## Skills Disponibles\n{skills_section}\n\n"
                f"## Agentes Disponibles\n{agents}"
            )

        # --- 3. Resolve tools ---
        try:
            tools = list(agent.tools.tools_registry(tool_permissions))
        except AttributeError as e:
            log_error(str(e), source="loop.py:run(tools)")
            tools = []
        logger.info("Tools available: %d", len(tools))

        # --- 4. Build initial messages array (history does NOT include current message) ---
        # Append attached files (if any) to the user message
        effective_message = user_message
        if file_contents:
            try:
                parts: list[str] = []
                for fn, text in file_contents:
                    parts.append(f"**Archivo: {fn}**\n{text}")
                attachments_section = (
                    "<inicio_adjuntos>\n"
                    + "\n".join(parts)
                    + "\n<fin_adjuntos>"
                )
                effective_message = f"{user_message}\n\n{attachments_section}"
            except Exception as exc:
                logger.warning("Error building attachments section: %s", exc)
                log_error(str(exc), source="loop.py:run")

        messages = build_initial_messages(
            session_manager,
            session_id,
            system_prompt,
            effective_message,
            max_turns=await asyncio.to_thread(fetch_context_window_turns),
        )

        # --- 5. Save user message to DB (after building messages so history is clean) ---
        session_manager.save_message(
            session_id, "user", content=user_message, turn_number=turn_number,
        )

        # --- 5b. Generate title on first turn ---
        if turn_number == 1:
            try:
                existing_titles = session_manager.get_all_titles()
                if existing_titles:
                    titles_formatted = "\n".join(
                        [f"{i+1}. {t}" for i, t in enumerate(existing_titles)]
                    )
                else:
                    titles_formatted = "Sin restricciones (primera conversación)"
                title_prompt = agent.prompt("title").format(
                    message=user_message,
                    titles=titles_formatted,
                )
                title_result = await asyncio.to_thread(
                    agent.llm_process,
                    model=model,
                    prompt=title_prompt,
                    max_tokens=300,
                    temperature=temperature,
                    top_p=top_p,
                )
                raw_title = title_result.get("data", "") if isinstance(title_result, dict) else ""
                title = (raw_title or "").strip().replace('"', "").replace("'", "")
                if title:
                    try:
                        session_manager.update_session_title(session_id, title)
                    except Exception as exc:
                        logger.warning("No se pudo guardar el título: %s", exc)
                        log_error(str(exc), source="loop.py:run")
                    yield f"data: {json.dumps({'type': 'session_title', 'content': title}, ensure_ascii=False)}\n\n"
            except Exception as exc:
                logger.warning("No se pudo generar el título: %s", exc)
                log_error(str(exc), source="loop.py:run")

        # --- 6. Agent loop (while True) ---
        iteration = 0
        while iteration < self.max_iterations:
            iteration += 1
            logger.info(
                "Iteration %d / %d — messages in context: %d, tools: %d",
                iteration, self.max_iterations, len(messages), len(tools),
            )

            # ---- 6a. Call LLM with streaming (single API call, detects tool_calls) ----
            collected_content = ""
            tool_calls = None

            try:
                async for event in agent.llm_streaming(
                    model=model, messages=messages, tools=tools,
                    stream_cancel_event=stream_cancel_event,
                    temperature=temperature, top_p=top_p, max_tokens=max_tokens,
                ):
                    if event["type"] == "chunk":
                        collected_content += event.get("content", "")
                        yield f"data: {json.dumps({'type': 'chunk', 'content': event.get('content', '')}, ensure_ascii=False)}\n\n"
                    elif event["type"] == "tool_calls_detected":
                        tool_calls = event["content"]
                        break
                    elif event["type"] == "aborted":
                        yield "data: [DONE]\n\n"
                        ctx = get_error_context()
                        await asyncio.to_thread(
                            liberar_modelo, model,
                            ctx.get("session_id") if ctx else None,
                            ctx.get("turn_number") if ctx else None,
                            ctx.get("parent_id") if ctx else None,
                        )
                        reset_error_context(error_ctx_token)
                        return
            except Exception as e:
                logger.exception("Error in agent streaming: %s", e)
                log_error(str(e), source="loop.py:run(llm_stream)")
                session_manager.save_message(session_id, "assistant", content="Ocurrió un error al procesar la solicitud. Por favor, intentá de nuevo.", turn_number=turn_number)
                yield f"data: {json.dumps({'type': 'chunk', 'content': 'Ocurrió un error al procesar la solicitud. Por favor, intentá de nuevo.'}, ensure_ascii=False)}\n\n"
                yield "data: [DONE]\n\n"
                ctx = get_error_context()
                await asyncio.to_thread(
                    liberar_modelo, model,
                    ctx.get("session_id") if ctx else None,
                    ctx.get("turn_number") if ctx else None,
                    ctx.get("parent_id") if ctx else None,
                )
                reset_error_context(error_ctx_token)
                return

            logger.debug(
                "LLM response — tool_calls: %s, content_length: %d",
                len(tool_calls) if tool_calls else 0, len(collected_content),
            )

            # ---- 6b. Process tool_calls (LLM wants to continue) ----
            if tool_calls:
                # Save assistant message with tool_calls (collected_content may be empty)
                assistant_msg: dict[str, Any] = {
                    "role": "assistant",
                    "content": collected_content,
                    "tool_calls": tool_calls,
                }
                messages.append(assistant_msg)

                session_manager.save_message(
                    session_id, "assistant",
                    content=collected_content,
                    tool_calls=tool_calls,
                    turn_number=turn_number,
                )

                # Collect tool results to update assistant message after all tools execute
                tool_results: list[dict[str, Any]] = []

                for tc in tool_calls:
                    is_subagent = tc.get("name") == "task"

                    if is_subagent:
                        yield f"data: {json.dumps({'type': 'subagent_call', 'content': {'agent_name': tc.get('args', {}).get('agent_name', ''), 'prompt': tc.get('args', {}).get('prompt', '')}}, ensure_ascii=False)}\n\n"
                    else:
                        yield f"data: {json.dumps({'type': 'tool_call', 'content': {'name': tc['name'], 'args': tc['args']}}, ensure_ascii=False)}\n\n"

                    result_data = await execute_tool(agent, tc)

                    # Restore parent session/depth state: a nested run (sub-agent)
                    # may have overwritten these on the shared Tools instance.
                    agent.tools._current_session_id = session_id
                    agent.tools._current_depth = depth

                    if is_subagent:
                        yield f"data: {json.dumps({'type': 'subagent_result', 'content': {'agent_name': tc.get('args', {}).get('agent_name', ''), 'result': result_data}}, ensure_ascii=False)}\n\n"
                    else:
                        yield f"data: {json.dumps({'type': 'tool_result', 'content': {'name': tc['name'], 'result': result_data}}, ensure_ascii=False)}\n\n"

                    # Build tool result message (provider-dependent format)
                    tool_content = (
                        json.dumps(result_data, ensure_ascii=False)
                        if isinstance(result_data, (dict, list))
                        else str(result_data)
                    )
                    is_groq = agent.provider.upper() == "API"
                    if is_groq:
                        tool_msg = {
                            "role": "tool",
                            "tool_call_id": tc.get("id", ""),
                            "content": tool_content,
                        }
                    else:
                        tool_msg = {
                            "role": "tool",
                            "tool_name": tc["name"],
                            "content": tool_content,
                        }

                    messages.append(tool_msg)

                    session_manager.save_message(
                        session_id, "tool",
                        content=tool_msg.get("content", ""),
                        tool_call_id=tool_msg.get("tool_call_id"),
                        tool_name=tool_msg.get("tool_name"),
                        turn_number=turn_number,
                    )

                    # Collect result for assistant message's tool_results field
                    tool_results.append({
                        "tool_call_id": tc.get("id", ""),
                        "tool_name": tc["name"],
                        "result": result_data,
                    })

                # Update assistant message with tool_results so frontend can display them on history load
                session_manager.update_message_tool_results(session_id, turn_number, tool_results)

                continue  # back to while loop

            # ---- 6c. No tool_calls → final response ----
            cleaned = agent.clean(collected_content) if collected_content else None
            session_manager.save_message(
                session_id, "assistant", content=cleaned, turn_number=turn_number,
            )
            yield "data: [DONE]\n\n"
            logger.info("Agent loop completed in %d iterations", iteration)
            ctx = get_error_context()
            await asyncio.to_thread(
                liberar_modelo, model,
                ctx.get("session_id") if ctx else None,
                ctx.get("turn_number") if ctx else None,
                ctx.get("parent_id") if ctx else None,
            )
            reset_error_context(error_ctx_token)
            return

        # ---- Max iterations ----
        logger.warning("Agent loop reached max_iterations (%d)", self.max_iterations)
        yield f"data: {json.dumps({'type': 'chunk', 'content': '\n\n*El agente alcanzó el límite de iteraciones.*'})}\n\n"
        yield "data: [DONE]\n\n"
        ctx = get_error_context()
        await asyncio.to_thread(
            liberar_modelo, model,
            ctx.get("session_id") if ctx else None,
            ctx.get("turn_number") if ctx else None,
            ctx.get("parent_id") if ctx else None,
        )
        reset_error_context(error_ctx_token)


# ------------------------------------------------------------------
# Access point (entry point for direct testing)
# ------------------------------------------------------------------

if __name__ == "__main__":
    async def _main() -> None:
        from backend.instances import agent, session_manager, context_manager

        session_id = sys.argv[1] if len(sys.argv) > 1 else "test-session"
        message = sys.argv[2] if len(sys.argv) > 2 else "Hola, ¿qué podés hacer?"

        loop = AgentLoop(
            agent=agent,
            session_manager=session_manager,
            context_manager=context_manager,
        )
        async for event in loop.run(session_id=session_id, user_message=message):
            print(event, flush=True)

    asyncio.run(_main())
