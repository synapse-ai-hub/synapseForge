"""Orquestación principal para la creación de tools externas.

Expone las funciones públicas:
- ``iterar_tool()`` — Itera con el LLM (preguntas → creación).
- ``create_tool()`` — Evalúa tools existentes o crea usando el agente con tools.
"""

from __future__ import annotations

import json
import logging
import os
import re
import sys
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Ensure the project root is in sys.path for absolute imports
# ---------------------------------------------------------------------------
_current_dir = os.path.dirname(os.path.abspath(__file__))
_project_root = os.path.dirname(os.path.dirname(os.path.dirname(_current_dir)))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from backend.agent.utils.config_dir import get_tools_dir
from backend.agent.utils.tool_creator.helpers import (
    _evaluar_si_existe,
    _listar_tools_locales,
    _tool_file_path,
)
from backend.agent.utils.tool_creator.tool_agent import run_tool_agent
from backend.instances import agent

logger = logging.getLogger(__name__)

_TOOLS_DIR = get_tools_dir()


# ═══════════════════════════════════════════════════════════════════════
# Iteración con LLM (preguntas → creación) — SIN TOOLS
# ═══════════════════════════════════════════════════════════════════════


async def iterar_tool(
    descripcion: str,
    nombre: str | None = None,
    mensajes: list[dict] | None = None,
    parametros: list[dict] | None = None,
    datos: list[str] | None = None,
) -> dict[str, Any]:
    """Itera con el LLM para refinar la tool (entrevista).

    El LLM responde con:
    - ``{"action": "question", "question": "..."}`` → sigue preguntando.
    - ``{"action": "create", "task": "...", "name": "...", "parametros": [...],
       "datos": [...]}`` → pasa a crear.

    Args:
        descripcion: Descripción inicial de la tool.
        nombre: Nombre tentativo de la tool.
        mensajes: Historial de la conversación.
        parametros: Lista de parámetros declarados.
        datos: Variables de entorno / datos externos necesarios.

    Returns:
        Dict con ``{status, message, data?, question?}``.
    """
    if not agent._resolved_model:
        return {"status": "error", "message": "No hay modelo configurado."}

    try:
        template = agent.prompt("iterar_tool")
    except FileNotFoundError:
        return {"status": "error", "message": "Prompt iterar_tool.md no encontrado."}

    # Formatear parámetros
    if parametros:
        params_lines = []
        for p in parametros:
            pname = p.get("name", "?")
            ptype = p.get("type", "str")
            pdesc = p.get("description", "")
            preq = "obligatorio" if p.get("required", True) else "opcional"
            params_lines.append(f"  - {pname} ({ptype}, {preq}): {pdesc}")
        parametros_text = "\n".join(params_lines)
    else:
        parametros_text = "(No se declararon parámetros. Inferir los necesarios.)"

    # Formatear datos externos
    if datos:
        datos_text = "\n".join(f"  - {d}" for d in datos)
    else:
        datos_text = "(No se declararon datos externos. Inferir si los necesita.)"

    # Formatear mensajes
    if mensajes:
        partes = []
        for m in mensajes:
            role = m.get("role", "user")
            content = m.get("content", "")
            label = "Usuario" if role == "user" else "Asistente"
            partes.append(f"**{label}**: {content}")
        mensajes_text = "\n\n".join(partes)
    else:
        mensajes_text = "(Sin preguntas aún)"

    prompt = template.format(
        descripcion=descripcion,
        nombre=nombre or "(inferir)",
        parametros=parametros_text,
        datos=datos_text,
        mensajes=mensajes_text,
    )

    result = await agent.llm_process(
        model=agent._resolved_model,
        prompt=prompt,
        temperature=0.3,
        top_p=0.8,
        max_tokens=10000,
        cleaned_output=True,
        json_format=True,
    )

    if result.get("status") != "success" or not result.get("data"):
        return {"status": "error", "message": f"Error del LLM: {result.get('message', 'sin respuesta')}"}

    raw = result["data"].strip()
    m = re.search(r"\{.*\}", raw, re.DOTALL)
    if not m:
        return {"status": "error", "message": "El LLM no devolvió JSON válido."}

    try:
        parsed = json.loads(m.group(0))
    except Exception as e:
        return {"status": "error", "message": f"Error parseando JSON: {e}"}

    action = parsed.get("action")

    if action == "question":
        return {
            "status": "question",
            "message": parsed.get("question", ""),
            "question": parsed.get("question", ""),
        }

    if action == "create":
        return {
            "status": "create",
            "message": "Procediendo a crear la tool.",
            "data": {
                "task": parsed.get("task", descripcion),
                "name": parsed.get("name", nombre),
                "parametros": parsed.get("parametros", parametros or []),
                "datos": parsed.get("datos", datos or []),
            },
        }

    return {"status": "error", "message": f"Acción desconocida: {action}"}


# ═══════════════════════════════════════════════════════════════════════
# Orquestador principal — USA EL AGENTE CON TOOLS
# ═══════════════════════════════════════════════════════════════════════


async def create_tool(
    task: str,
    name: str | None = None,
    mensajes: list[dict] | None = None,
    parametros: list[dict] | None = None,
    datos: list[str] | None = None,
) -> dict[str, Any]:
    """Busca si existe una tool externa que cubra la tarea. Si no, la crea.

    Args:
        task: Descripción o tarea para evaluar tools existentes.
        name: Nombre exacto para la tool.
        mensajes: Historial de la conversación.
        parametros: Lista de parámetros declarados.
        datos: Variables de entorno / datos externos necesarios.

    Returns:
        Dict con ``{status, message, data: {exist, tool, tool_path?}}``.
    """
    logger.info("=" * 60)
    logger.info("CREATE TOOL: task='%s' name=%s", task, name)
    logger.info("=" * 60)

    _TOOLS_DIR.mkdir(parents=True, exist_ok=True)

    # ── 1. Tools locales ────────────────────────────────────────────
    tools_locales = _listar_tools_locales()
    logger.info("Tools externas: %d", len(tools_locales))

    # ── 2. Evaluar si existe ─────────────────────────────────────────
    decision = await _evaluar_si_existe(task, tools_locales)

    if decision and decision.get("exist") == "Sí":
        tool_name = decision.get("tool")
        logger.info("Tool existente encontrada: '%s'", tool_name)

        tool_path = _tool_file_path(tool_name) if tool_name else None

        return {
            "status": "success",
            "message": (
                f"Ya existe la tool externa '{tool_name}' que cubre esta tarea."
                if tool_path and tool_path.is_file()
                else f"Existe la tool '{tool_name}' que cubre esta tarea."
            ),
            "data": {
                "exist": "Sí",
                "tool": tool_name,
                "tool_path": str(tool_path) if tool_path else None,
            },
        }

    # ── 3. Generar nueva tool con el agente ──────────────────────────
    logger.info("No existe tool. Lanzando agente creador...")

    # Construir system prompt
    try:
        sys_prompt_template = agent.prompt("generar_tool")
    except FileNotFoundError:
        return {"status": "error", "message": "Prompt generar_tool.md no encontrado."}

    carpeta = str(_TOOLS_DIR / (name or "tool"))
    Path(carpeta).mkdir(parents=True, exist_ok=True)
    (Path(carpeta) / "lib").mkdir(exist_ok=True)
    (Path(carpeta) / "lib" / "data").mkdir(exist_ok=True)
    (Path(carpeta) / "lib" / "tests").mkdir(exist_ok=True)

    # Formatear parámetros y datos
    if parametros:
        params_lines = []
        for p in parametros:
            pname = p.get("name", "?")
            ptype = p.get("type", "str")
            pdesc = p.get("description", "")
            preq = "obligatorio" if p.get("required", True) else "opcional"
            params_lines.append(f"- {pname} ({ptype}, {preq}): {pdesc}")
        parametros_text = "\n".join(params_lines)
    else:
        parametros_text = "(Inferir parámetros según la descripción.)"

    if datos:
        datos_text = "\n".join(f"- {d}" for d in datos)
    else:
        datos_text = "(Si la tool necesita credenciales, documentarlas acá.)"

    # Formatear conversación
    if mensajes:
        partes = []
        for m in mensajes:
            role = m.get("role", "user")
            content = m.get("content", "")
            label = "Usuario" if role == "user" else "Asistente"
            partes.append(f"**{label}**: {content}")
        conversacion = "\n\n".join(partes)
    else:
        conversacion = f"**Usuario**: {task}"

    sys_prompt = sys_prompt_template.format(
        nombre=name or "(inferir del contexto)",
        descripcion=task,
        conversacion=conversacion,
        parametros=parametros_text,
        datos=datos_text,
        carpeta=carpeta,
    )

    # ── 4. Lanzar el agente con tools ─────────────────────────────────
    agent_tools_perms: dict[str, str] = {
        "read": "allow",
        "write": "allow",
        "edit": "allow",
        "shell": "allow",
        "list_dir": "allow",
    }
    agent_result = await run_tool_agent(
        system_prompt=sys_prompt,
        user_message=(
            "Creá la tool. Pasos OBLIGATORIOS en orden: "
            "1) Escribí el archivo <nombre>.py con write. "
            "2) Escribí un script de tests en lib/tests/test_<nombre>.py. "
            "3) Ejecutá los tests con shell y mostrame los resultados. "
            "4) Iterá si hay errores. "
            "5) Cuando todo pase, pedime aprobación."
        ),
        tools_permissions=agent_tools_perms,
    )

    logger.info("Agente finalizado. Status: %s", agent_result.get("status"))

    if agent_result.get("status") != "success":
        return {
            "status": "error",
            "message": f"Error del agente: {agent_result.get('message', 'desconocido')}",
            "data": None,
        }

    # ── 5. Buscar la tool creada ─────────────────────────────────────
    if name:
        tool_path = _tool_file_path(name)
        if tool_path.is_file():
            logger.info("Tool encontrada en: %s", tool_path)
            return {
                "status": "success",
                "message": f"Tool '{name}' creada exitosamente.",
                "data": {
                    "exist": "No",
                    "tool": name,
                    "tool_path": str(tool_path),
                },
            }

    # Si no se encontró por nombre, escanear tools recién creadas
    tools_actualizadas = _listar_tools_locales()
    nuevas = [t for t in tools_actualizadas if t["name"] not in {old["name"] for old in tools_locales}]

    if nuevas:
        nueva = nuevas[0]
        tool_path = _tool_file_path(nueva["name"])
        return {
            "status": "success",
            "message": f"Tool '{nueva['name']}' creada exitosamente.",
            "data": {
                "exist": "No",
                "tool": nueva["name"],
                "tool_path": str(tool_path),
            },
        }

    return {
        "status": "error",
        "message": "El agente no creó ninguna tool.",
        "data": None,
    }