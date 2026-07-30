"""Runner del agente con tools para la creación de skills.

Implementa un loop de ejecución similar a ``loop.py`` pero sin SSE:
- El agente tiene acceso a tools (read, write, edit, shell, etc.)
- Corre en el backend, solo visible en modo dev
- No transmite eventos SSE, solo logs internos
- Retorna el resultado al finalizar
"""

from __future__ import annotations

import json
import logging
import os
import sys
from typing import Any

# ---------------------------------------------------------------------------
# Ensure the project root is in sys.path for absolute imports
# ---------------------------------------------------------------------------
_current_dir = os.path.dirname(os.path.abspath(__file__))
_project_root = os.path.dirname(os.path.dirname(os.path.dirname(_current_dir)))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from backend.instances import agent

logger = logging.getLogger(__name__)

_MAX_ITERATIONS = 25


async def run_skill_agent(
    system_prompt: str,
    user_message: str,
    tools_permissions: dict | None = None,
) -> dict[str, Any]:
    """Ejecuta el agente creador con tools.

    Args:
        system_prompt: Prompt de sistema que define el rol y tarea del agente.
        user_message: Mensaje inicial del usuario.
        tools_permissions: Permisos de tools (``None`` = todas permitidas).

    Returns:
        Dict con ``{status, message, data}``.
    """
    if not agent._resolved_model:
        return {"status": "error", "message": "No hay modelo configurado."}

    # ── 1. Resolver tools ─────────────────────────────────────────────
    try:
        tools = list(agent.tools.tools_registry(tools_permissions))
    except AttributeError as e:
        logger.error("Error obteniendo tools: %s", e)
        return {"status": "error", "message": f"Error obteniendo tools: {e}"}

    tool_names = [t.get("function", {}).get("name", "?") for t in tools]
    print("=" * 60)
    print(">>> SKILL AGENT - Tools disponibles:", tool_names)
    print("=" * 60)
    logger.info("Tools: %s", ", ".join(tool_names))

    # ── 2. Construir mensajes ─────────────────────────────────────────
    messages: list[dict[str, Any]] = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_message},
    ]

    # ── 3. Loop de tool calling ───────────────────────────────────────
    for iteration in range(_MAX_ITERATIONS):
        print(f"\n--- SKILL AGENT - Iteración {iteration + 1}/{_MAX_ITERATIONS} ---")
        logger.info("Iteración %d / %d", iteration + 1, _MAX_ITERATIONS)

        llama_result = await agent.llm_process(
            model=agent._resolved_model,
            messages=messages,
            tools=tools,
            temperature=0.3,
            top_p=0.8,
            max_tokens=10000,
            cleaned_output=True,
        )

        if llama_result.get("status") != "success":
            logger.error("Error del LLM: %s", llama_result.get("message"))
            return {"status": "error", "message": f"Error del LLM: {llama_result.get('message')}"}

        content = llama_result.get("data", "")
        tool_calls = llama_result.get("tool_calls")

        print(">>> SKILL AGENT - Respuesta del LLM:")
        print("  content:", content[:500] if content else "(vacío)")
        if tool_calls:
            for tc in tool_calls:
                print(f"  tool_call: {tc.get('name')}({json.dumps(tc.get('args', {}), ensure_ascii=False)[:200]})")
        else:
            print("  tool_calls: ninguna")
        print("=" * 60)

        # ── 3a. Sin tool calls → fin del loop ─────────────────────────
        if not tool_calls:
            print(">>> SKILL AGENT - Sin tool calls, finalizando.")
            logger.info("Sin tool calls, finalizando.")
            print(">>> SKILL AGENT - Contenido completo devuelto:")
            print(content)
            print("=" * 60)
            return {
                "status": "success",
                "message": "Agente finalizado.",
                "data": content,
            }

        # ── 3b. Agregar mensaje del asistente CON tool_calls ──────────
        assistant_msg: dict[str, Any] = {
            "role": "assistant",
            "content": content,
            "tool_calls": tool_calls,
        }
        messages.append(assistant_msg)

        # ── 3c. Ejecutar cada tool y agregar resultado ────────────────
        for tc in tool_calls:
            tc_id = tc.get("id", "")
            tc_name = tc.get("name", "")
            tc_args = tc.get("args", {})

            print(f">>> SKILL AGENT - Ejecutando tool: {tc_name}")
            print(f"  args: {json.dumps(tc_args, ensure_ascii=False)[:300]}")
            logger.info("Ejecutando tool: %s (id=%s)", tc_name, tc_id)

            try:
                t0 = __import__('time').time()
                result = await agent.tools._execute_tool(tc_name, **tc_args)
                elapsed = __import__('time').time() - t0
            except Exception as e:
                logger.exception("Tool '%s' failed", tc_name)
                result = {"status": "error", "message": str(e)}
                elapsed = 0

            # Extraer contenido del resultado
            if isinstance(result, dict):
                if result.get("status") == "error":
                    result_content = result.get("message", "Error desconocido")
                else:
                    result_content = result.get("data", json.dumps(result))
            else:
                result_content = str(result)

            if not isinstance(result_content, str):
                result_content = json.dumps(result_content)

            print(f">>> SKILL AGENT - Resultado de {tc_name} ({elapsed:.2f}s):")
            print(f"  {str(result_content)[:300]}")
            print("-" * 40)

            messages.append({
                "role": "tool",
                "tool_call_id": tc_id,
                "content": result_content,
            })

    # ── 4. Safety net: superó el máximo de iteraciones ────────────────
    print(f">>> SKILL AGENT - Máximo de iteraciones alcanzado ({_MAX_ITERATIONS})")
    logger.warning("Máximo de iteraciones alcanzado (%d)", _MAX_ITERATIONS)
    return {
        "status": "success",
        "message": f"Máximo de iteraciones alcanzado ({_MAX_ITERATIONS}).",
        "data": messages[-1].get("content", "") if messages else "",
    }
