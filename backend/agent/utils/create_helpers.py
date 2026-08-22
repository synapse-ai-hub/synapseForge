"""Shared tool-calling loop for the creation flows (skills and tools).

This module implements the agent tool-calling loop used by the creation
endpoints in ``backend/routes/create.py``. It is the single source of
truth for the loop so the same behaviour (streaming events, tool
execution, message accumulation) is shared between the skill and tool
creation flows instead of being duplicated inline in the routes.

The loop streams LLM events (chunks, reasoning, tool calls), executes
each requested tool through ``agent.tools._execute_tool`` and appends the
assistant/tool messages to the provided ``msgs`` list in place.

Imported by ``backend/routes/create.py``.
"""

from __future__ import annotations

import json
import logging
import os
import sys
import time
from datetime import datetime
from typing import Any, AsyncGenerator

# ---------------------------------------------------------------------------
# Ensure the project root is in sys.path for absolute imports
# ---------------------------------------------------------------------------
_current_dir = os.path.dirname(os.path.abspath(__file__))
_project_root = os.path.dirname(os.path.dirname(os.path.dirname(_current_dir)))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from backend.instances import agent

logger = logging.getLogger(__name__)

_DEFAULT_MODEL = "qwen/qwen3.6-27b"
_DEFAULT_PROVIDER = "Groq"
_DEFAULT_MAX_ITERATIONS = 25
_DEFAULT_TEMPERATURE = 0.3
_DEFAULT_TOP_P = 0.8
_DEFAULT_MAX_TOKENS = 3000


def _resolve_create_model_provider() -> tuple[str, str]:
    """Resolve the (model, provider) used by the creation flows.

    When the Groq client is available the flows keep using Groq with
    ``qwen/qwen3.6-27b``. If Groq could not be instantiated at startup
    (missing/invalid API key), fall back to the provider and model saved
    in the DB (``agent.provider`` / ``agent._resolved_model``).

    Returns:
        Tuple of ``(model, provider)``.
    """
    if agent.groq_client is not None:
        return _DEFAULT_MODEL, _DEFAULT_PROVIDER
    return (
        getattr(agent, "_resolved_model", None) or _DEFAULT_MODEL,
        getattr(agent, "provider", None) or "LOCAL",
    )


async def stream_tool_calling_loop(
    msgs: list[dict[str, Any]],
    tools: list[dict[str, Any]],
    friendly_error: str,
    model: str | None = None,
    provider: str | None = None,
    max_iter: int = _DEFAULT_MAX_ITERATIONS,
    temperature: float = _DEFAULT_TEMPERATURE,
    top_p: float = _DEFAULT_TOP_P,
    max_tokens: int = _DEFAULT_MAX_TOKENS,
) -> AsyncGenerator[dict[str, Any], None]:
    """Run the agent tool-calling loop and yield SSE event dicts.

    Streams the LLM response with the given ``tools`` and executes every
    tool call through ``agent.tools._execute_tool``. ``msgs`` is mutated in
    place (assistant message with tool calls + tool result messages are
    appended) so callers can inspect the full conversation afterwards.

    Args:
        msgs: Mutable conversation list; system and user messages are
            expected to already be present.
        tools: Tool definitions passed to the provider for function calling.
        friendly_error: User-friendly error message yielded on failure.
        model: Model identifier sent to the provider. If ``None``,
            resolved via ``_resolve_create_model_provider``.
        provider: Provider name (``"Groq"`` or ``"LOCAL"``). If ``None``,
            resolved via ``_resolve_create_model_provider``.
        max_iter: Maximum number of loop iterations.
        temperature: Sampling temperature.
        top_p: Nucleus sampling parameter.
        max_tokens: Maximum output tokens per request.

    Yields:
        SSE event dicts: ``chunk``, ``reasoning``, ``tool_call``,
        ``tool_result``, ``aborted`` or ``error``.
    """
    if model is None or provider is None:
        model, provider = _resolve_create_model_provider()
    iteration = 0
    while iteration < max_iter:
        iteration += 1

        collected_content = ""
        tool_calls = None

        try:
            async for event in agent.llm_streaming(
                model=model,
                provider=provider,
                messages=msgs,
                tools=tools,
                temperature=temperature,
                top_p=top_p,
                max_tokens=max_tokens,
                cleaned_output=True,
            ):
                if event["type"] == "chunk":
                    collected_content += event.get("content", "")
                    yield {"type": "chunk", "content": event.get("content", "")}

                elif event["type"] == "reasoning":
                    yield {"type": "reasoning", "content": event.get("content", "")}

                elif event["type"] == "tool_calls_detected":
                    tool_calls = event["content"]
                    break

                elif event["type"] == "aborted":
                    yield {"type": "aborted", "content": "Stream cancelado."}
                    return

        except Exception as e:
            logger.exception("Error en streaming create agent: %s", e)
            yield {"type": "error", "content": friendly_error}
            return

        # ── Process tool calls ──────────────────────────────────────────
        if tool_calls:
            assistant_msg: dict[str, Any] = {
                "role": "assistant",
                "content": collected_content,
                "tool_calls": tool_calls,
            }
            msgs.append(assistant_msg)

            for tc in tool_calls:
                tc_id = tc.get("id", "")
                tc_name = tc.get("name", "")
                tc_args = tc.get("args", {})

                yield {"type": "tool_call", "content": {"name": tc_name, "args": tc_args}}

                try:
                    result = await agent.tools._execute_tool(tc_name, **tc_args)
                except Exception as e:
                    logger.exception("Tool '%s' failed", tc_name)
                    result = {"status": "error", "message": str(e)}

                # Extract the result content
                if isinstance(result, dict):
                    if result.get("status") == "error":
                        result_content = result.get("message", "Error desconocido")
                    else:
                        result_content = result.get("data", json.dumps(result))
                else:
                    result_content = str(result)

                if not isinstance(result_content, str):
                    result_content = json.dumps(result_content)

                yield {
                    "type": "tool_result",
                    "content": {"name": tc_name, "result": result_content},
                }

                msgs.append({
                    "role": "tool",
                    "tool_call_id": tc_id,
                    "content": result_content,
                })

            # Continue loop → next iteration streams the response with tool results
        else:
            # No tool calls → finished
            break
