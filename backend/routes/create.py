"""Router para endpoints de creación (tools, skills, agents, RAG).

Endpoints:
- ``POST /api/create/skill`` — Streaming SSE para crear skills, exacto ChatInterface.
  Eventos SSE:
  - ``{"type": "chunk", "content": str}`` — texto generado (interview + agent).
  - ``{"type": "tool_call", "content": {"name": str, "args": dict}}`` — tool call durante creación.
  - ``{"type": "tool_result", "content": {"name": str, "result": any}}`` — resultado de tool.
  - ``{"type": "skill_action", "content": {"action": "question"|"creating"}}`` — acción de skill.
  - ``{"type": "skill_result", "content": {...}}`` — resultado final.
  - ``{"type": "error", "content": str}`` — error.
  - ``{"type": "aborted", "content": str}`` — stream cancelado.
- ``POST /api/create/tool`` — Streaming SSE para crear tools externas, mismo contrato.
  Eventos SSE: idénticos pero con ``tool_action`` y ``tool_result_final`` (terminal).
"""

from __future__ import annotations

import json
import logging
import os
import re
import sys
import time
from datetime import datetime
from typing import Any, AsyncGenerator

from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

# ---------------------------------------------------------------------------
# Ensure project root for absolute imports
# ---------------------------------------------------------------------------
_current_dir = os.path.dirname(os.path.abspath(__file__))
_project_root = os.path.dirname(os.path.dirname(_current_dir))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from backend.agent.utils.config_dir import get_skills_dir, get_tools_dir
from backend.agent.utils.skills_helpers import (
    _copiar_referencias,
    _evaluar_si_existe,
    _listar_skills_locales,
)
from backend.agent.utils.tools_helpers import _listar_tools_locales
from backend.agent.utils.create_helpers import stream_tool_calling_loop, _resolve_create_model_provider
from backend.instances import agent

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/create", tags=["create"])

_SKILLS_DIR = get_skills_dir()
_TOOLS_DIR = get_tools_dir()

# Mensaje user-friendly para errores: el detalle técnico NUNCA llega a la UI.
_FRIENDLY_ERROR = "No se pudo crear la skill. Ocurrió un error durante el proceso. Verificá la configuración e intentá de nuevo."
_FRIENDLY_ERROR_TOOL = "No se pudo crear la tool. Ocurrió un error durante el proceso. Verificá la configuración e intentá de nuevo."


# ── Modelos de request / response ─────────────────────────────────────


class CreateSkillRequest(BaseModel):
    """Request para crear una skill con iteración."""

    descripcion: str
    name: str | None = None
    mensajes: list[dict] | None = None  # [{"role": "user"|"assistant", "content": "..."}]


class CreateToolRequest(BaseModel):
    """Request para crear una tool externa con iteración."""

    descripcion: str
    name: str | None = None
    mensajes: list[dict] | None = None  # [{"role": "user"|"assistant", "content": "..."}]
    parametros: list[dict] | None = None  # [{"name", "type", "description", "required"}]
    datos: list[str] | None = None  # Lista de env vars / datos externos


# ── Tool definition for interview ─────────────────────────────────────

_INTERVIEW_TOOL: dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "responder_interview",
        "description": (
            "Llamar cuando tengas suficiente información para crear la skill "
            "o cuando necesites hacer una pregunta al usuario. "
            "Los parámetros contienen la información estructurada de tu decisión."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["question", "create"],
                    "description": (
                        "'question' cuando necesitás más información del usuario. "
                        "'create' cuando ya tenés suficiente para diseñar la skill."
                    ),
                },
                "question": {
                    "type": "string",
                    "description": "Tu pregunta para el usuario (solo si action='question').",
                },
                "task": {
                    "type": "string",
                    "description": (
                        "Descripción detallada de lo que debe hacer la skill, "
                        "incluyendo señales de activación y pasos (solo si action='create')."
                    ),
                },
                "name": {
                    "type": "string",
                    "description": (
                        "Nombre exacto que dio el usuario para la skill. "
                        "Si no dio nombre, usar nombre corto con guiones (solo si action='create')."
                    ),
                },
                "triggers": {
                    "type": "string",
                    "description": (
                        "Palabras clave separadas por comas que activan la skill "
                        "(solo si action='create')."
                    ),
                },
                "not_triggers": {
                    "type": "string",
                    "description": (
                        "Lo que NO debe hacer la skill, contextos en los que NO activarse "
                        "(solo si action='create', opcional)."
                    ),
                },
                "refs": {
                    "type": "string",
                    "description": (
                        "Referencias, archivos o templates que mencionó el usuario "
                        "(solo si action='create', opcional)."
                    ),
                },
            },
            "required": ["action"],
        },
    },
}

# ── Tools permitidas para el agente creador ─────────────────────────

_AGENT_TOOLS_PERMS: dict[str, str] = {
    "read": "allow",
    "write": "allow",
    "edit": "allow",
    "shell": "allow",
    "list_dir": "allow",
}


# ── Helper: emitir SSE string ────────────────────────────────────────


def _sse(event: dict) -> str:
    """Serialize dict to SSE ``data: {...}\\n\\n``."""
    return f"data: {json.dumps(event, ensure_ascii=False)}\n\n"


# ── Helper: formatear mensajes ───────────────────────────────────────


def _formatear_mensajes(mensajes: list[dict]) -> str:
    """Convierte la lista de mensajes en texto para el prompt."""
    if not mensajes:
        return "(Sin preguntas aún)"
    partes = []
    for m in mensajes:
        role = m.get("role", "user")
        content = m.get("content", "")
        label = "Usuario" if role == "user" else "Asistente"
        parte = f"**{label}**: {content}"
        files = m.get("files")
        if files and isinstance(files, list):
            for f in files:
                fname = f.get("name", "archivo")
                fcontent = f.get("content", "")
                if fcontent:
                    parte += f"\n\n[Archivo adjunto: {fname}]\n```\n{fcontent}\n```"
        partes.append(parte)
    return "\n\n".join(partes)


# ── Streaming endpoint ───────────────────────────────────────────────


@router.post("/skill")
async def post_create_skill_stream(req: CreateSkillRequest):
    """Streaming endpoint para crear skills. Retorna SSE events."""
    logger.info(
        "POST /api/create/skill — descripcion='%s' name=%s mensajes=%d",
        req.descripcion, req.name,
        len(req.mensajes) if req.mensajes else 0,
    )

    descripcion = req.descripcion.strip()
    nombre = req.name.strip() if req.name else None
    mensajes = req.mensajes or []

    if not descripcion:
        return StreamingResponse(
            iter([_sse({"type": "error", "content": "El campo 'descripcion' es obligatorio."})]),
            media_type="text/event-stream",
        )

    async def event_stream() -> AsyncGenerator[str, None]:
        """Generate SSE events for the skill creation flow."""
        # ════════════════════════════════════════════════════════════════
        # FASE 1: INTERVIEW — stream texto + tool responder_interview
        # ════════════════════════════════════════════════════════════════
        try:
            template = agent.prompt("iterar_skill")
        except FileNotFoundError:
            logger.exception("Prompt iterar_skill.md no encontrado.")
            yield _sse({"type": "error", "content": _FRIENDLY_ERROR})
            return

        prompt = template.format(
            descripcion=descripcion,
            nombre=nombre or "(inferir)",
            mensajes=_formatear_mensajes(mensajes),
        )

        collected_content = ""
        tool_calls_data = None

        try:
            _create_model, _create_provider = _resolve_create_model_provider()
            async for event in agent.llm_streaming(
                model=_create_model,
                provider=_create_provider,
                prompt=prompt,
                tools=[_INTERVIEW_TOOL],
                temperature=0.3,
                top_p=0.8,
                max_tokens=3000,
                cleaned_output=True,
            ):
                if event["type"] == "chunk":
                    collected_content += event.get("content", "")
                    yield _sse({"type": "chunk", "content": event.get("content", "")})

                elif event["type"] == "reasoning":
                    yield _sse({"type": "reasoning", "content": event.get("content", "")})

                elif event["type"] == "tool_calls_detected":
                    tcs = event["content"]
                    if tcs:
                        tc = tcs[0]
                        tool_calls_data = tc.get("args", {})
                    break

                elif event["type"] == "aborted":
                    yield _sse({"type": "aborted", "content": "Stream cancelado."})
                    return

        except Exception as e:
            logger.exception("Error en streaming interview: %s", e)
            yield _sse({"type": "error", "content": _FRIENDLY_ERROR})
            return

        # ── Fallback: si no hubo tool call, intentar parsear JSON ──
        if not tool_calls_data:
            logger.warning("No tool call recibida. Content: %s", collected_content)
            parsed = _try_parse_json(collected_content)
            if parsed:
                tool_calls_data = parsed
            elif collected_content.strip():
                # El LLM respondió en texto natural sin llamar a la tool: esa es la
                # respuesta de la entrevista (el front ya la mostró). No se envía nada
                # extra al front; finaliza al terminar el stream.
                return
            else:
                yield _sse({"type": "error", "content": "El LLM no devolvió una respuesta válida."})
                return

        action = tool_calls_data.get("action")

        # ── QUESTION ──
        if action == "question":
            question_text = tool_calls_data.get("question", "")
            yield _sse({"type": "skill_action", "content": {"action": "question", "question": question_text}})
            return

        # ── CREATE ──
        if action != "create":
            logger.warning("Acción desconocida del LLM: %s", action)
            yield _sse({"type": "error", "content": _FRIENDLY_ERROR})
            return

        task = tool_calls_data.get("task", descripcion)
        name = nombre or tool_calls_data.get("name")
        refs = tool_calls_data.get("refs")

        # ════════════════════════════════════════════════════════════════
        # FASE 2: EVALUAR si ya existe una skill que cubra la tarea
        # ════════════════════════════════════════════════════════════════
        _SKILLS_DIR.mkdir(parents=True, exist_ok=True)
        skills_locales = _listar_skills_locales()
        decision = await _evaluar_si_existe(task, skills_locales)

        if decision and decision.get("exist") == "Sí":
            skill_name = decision.get("skill")
            yield _sse({"type": "skill_result", "content": {
                "status": "success",
                "message": f"Ya existe la skill '{skill_name}' que cubre esta tarea.",
                "data": {"exist": "Sí", "skill": skill_name},
            }})
            return

        # ════════════════════════════════════════════════════════════════
        # FASE 3: CREAR — ejecutar agente con tools, stremeando events
        # ════════════════════════════════════════════════════════════════
        yield _sse({"type": "skill_action", "content": {"action": "creating"}})

        # Build the generate prompt
        try:
            sys_prompt_template = agent.prompt("generar_skill")
        except FileNotFoundError:
            logger.exception("Prompt generar_skill.md no encontrado.")
            yield _sse({"type": "error", "content": _FRIENDLY_ERROR})
            return

        conversacion = _formatear_mensajes(mensajes)
        carpeta_skill = str(_SKILLS_DIR / (name or "skill"))
        sys_prompt = sys_prompt_template.format(
            nombre=name or "(inferir del contexto)",
            conversacion=conversacion,
            carpeta=carpeta_skill,
        )

        user_msg = "Ejecutá tu tarea. Creá el SKILL.md y los archivos necesarios. Cuando termines, indicame qué creaste."

        # ── 3a. Resolver tools ──
        try:
            tools = list(agent.tools.tools_registry(_AGENT_TOOLS_PERMS))
        except AttributeError as e:
            logger.exception("Error obteniendo tools: %s", e)
            yield _sse({"type": "error", "content": _FRIENDLY_ERROR})
            return

        tool_names = [t.get("function", {}).get("name", "?") for t in tools]

        # ── 3b. Loop de tool calling EXACTO ChatInterface (loop.py) ──
        msgs: list[dict[str, Any]] = [
            {"role": "system", "content": sys_prompt},
            {"role": "user", "content": user_msg},
        ]

        async for event in stream_tool_calling_loop(msgs, tools, _FRIENDLY_ERROR):
            yield _sse(event)
            if event["type"] == "error":
                return

        # ════════════════════════════════════════════════════════════════
        # FASE 4: BUSCAR lo que creó el agente
        # ════════════════════════════════════════════════════════════════
        skills_actualizadas = _listar_skills_locales()
        nuevas = [s for s in skills_actualizadas if s["name"] not in {old["name"] for old in skills_locales}]

        skill_dir = None
        skill_name_creado = None

        if name:
            skill_dir = _SKILLS_DIR / name
            if skill_dir.is_dir() and (skill_dir / "SKILL.md").is_file():
                skill_name_creado = name
        elif nuevas:
            nueva = nuevas[0]
            skill_name_creado = nueva["name"]
            skill_dir = _SKILLS_DIR / skill_name_creado

        # Copiar referencias
        if skill_dir and skill_name_creado:
            _copiar_referencias(skill_dir, mensajes, refs)

        if skill_name_creado and skill_dir:
            yield _sse({"type": "skill_result", "content": {
                "status": "success",
                "message": f"Skill '{skill_name_creado}' creada exitosamente.",
                "data": {"exist": "No", "skill": skill_name_creado, "skill_dir": str(skill_dir)},
            }})
        else:
            # El agente terminó la creación (escribió los archivos). Mostrar el cartel de éxito.
            nombre_creado = skill_name_creado or name or "skill"
            yield _sse({"type": "skill_result", "content": {
                "status": "success",
                "message": f"Skill '{nombre_creado}' creada exitosamente.",
                "data": {"exist": "No", "skill": nombre_creado, "skill_dir": str(skill_dir or _SKILLS_DIR / nombre_creado)},
            }})

    return StreamingResponse(event_stream(), media_type="text/event-stream")


# ── Fallback: intentar extraer JSON del texto ────────────────────────


def _try_parse_json(text: str) -> dict | None:
    """Intenta extraer un JSON del texto generado por el LLM."""
    m = re.search(r"\{.*\}", text, re.DOTALL)
    if not m:
        return None
    try:
        return json.loads(m.group(0))
    except Exception:
        return None


# ═══════════════════════════════════════════════════════════════════════
# POST /api/create/tool — crear tools externas (mismo contrato que /skill)
# ═══════════════════════════════════════════════════════════════════════


# Tool schema para la entrevista (idéntico patrón que skills)
_TOOL_INTERVIEW_TOOL: dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "responder_interview_tool",
        "description": (
            "Llamar cuando tengas suficiente información para crear la tool "
            "o cuando necesites hacer una pregunta al usuario. "
            "Los parámetros contienen la información estructurada de tu decisión."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["question", "create"],
                    "description": (
                        "'question' cuando necesitás más información del usuario. "
                        "'create' cuando ya tenés suficiente para diseñar la tool."
                    ),
                },
                "question": {
                    "type": "string",
                    "description": "Tu pregunta para el usuario (solo si action='question').",
                },
                "task": {
                    "type": "string",
                    "description": (
                        "Descripción detallada de lo que debe hacer la tool, "
                        "incluyendo señales de activación y pasos (solo si action='create')."
                    ),
                },
                "name": {
                    "type": "string",
                    "description": (
                        "Nombre exacto del archivo de la tool (sin extensión, "
                        "snake_case). Si no dio nombre, inferir del contexto "
                        "(solo si action='create')."
                    ),
                },
                "parametros": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "name": {"type": "string"},
                            "type": {"type": "string"},
                            "description": {"type": "string"},
                            "required": {"type": "boolean"},
                        },
                    },
                    "description": (
                        "Lista de parámetros que la tool recibe del LLM "
                        "(solo si action='create')."
                    ),
                },
                "datos": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": (
                        "Variables de entorno o datos externos que la tool necesita "
                        "(solo si action='create', opcional)."
                    ),
                },
            },
            "required": ["action"],
        },
    },
}


@router.post("/tool")
async def post_create_tool_stream(req: CreateToolRequest):
    """Streaming endpoint para crear tools externas. Retorna SSE events.

    Contrato idéntico a ``POST /api/create/skill`` pero emite eventos
    ``tool_action`` y ``tool_result`` en lugar de ``skill_action`` /
    ``skill_result``.
    """
    logger.info(
        "POST /api/create/tool — descripcion='%s' name=%s mensajes=%d",
        req.descripcion, req.name,
        len(req.mensajes) if req.mensajes else 0,
    )

    descripcion = req.descripcion.strip()
    nombre = req.name.strip() if req.name else None
    mensajes = req.mensajes or []
    parametros = req.parametros or []
    datos = req.datos or []

    if not descripcion:
        return StreamingResponse(
            iter([_sse({"type": "error", "content": "El campo 'descripcion' es obligatorio."})]),
            media_type="text/event-stream",
        )

    async def event_stream() -> AsyncGenerator[str, None]:
        """Generate SSE events for the tool creation flow."""
        # ════════════════════════════════════════════════════════════════
        # FASE 1: EVALUAR — ¿ya existe una tool que cubra esto?
        # (antes de iterar para no gastar tokens si ya hay una)
        # ════════════════════════════════════════════════════════════════
        try:
            tools_locales = _listar_tools_locales()
            decision = await _evaluar_si_existe_tool_inline(descripcion, tools_locales, agent)

            if decision and decision.get("exist") == "Sí":
                tool_name = decision.get("tool")
                yield _sse({"type": "tool_result", "content": {
                    "status": "success",
                    "message": f"Ya existe la tool '{tool_name}' que cubre esta tarea.",
                    "data": {"exist": "Sí", "tool": tool_name},
                }})
                return
        except Exception as e:
            logger.exception("Error en evaluación inicial: %s", e)
            # No es bloqueante: seguimos a la fase de entrevista

        # ════════════════════════════════════════════════════════════════
        # FASE 2: ENTREVISTA — stream texto + tool responder_interview_tool
        # ════════════════════════════════════════════════════════════════
        try:
            template = agent.prompt("iterar_tool")
        except FileNotFoundError:
            logger.exception("Prompt iterar_tool.md no encontrado.")
            yield _sse({"type": "error", "content": _FRIENDLY_ERROR_TOOL})
            return

        # Formatear parámetros y datos
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

        datos_text = "\n".join(f"  - {d}" for d in datos) if datos else "(No se declararon datos externos. Inferir si los necesita.)"

        prompt = template.format(
            descripcion=descripcion,
            nombre=nombre or "(inferir)",
            parametros=parametros_text,
            datos=datos_text,
            mensajes=_formatear_mensajes(mensajes),
        )

        collected_content = ""
        tool_calls_data = None

        try:
            _create_model, _create_provider = _resolve_create_model_provider()
            async for event in agent.llm_streaming(
                model=_create_model,
                provider=_create_provider,
                prompt=prompt,
                tools=[_TOOL_INTERVIEW_TOOL],
                temperature=0.3,
                top_p=0.8,
                max_tokens=3000,
                cleaned_output=True,
            ):
                if event["type"] == "chunk":
                    collected_content += event.get("content", "")
                    yield _sse({"type": "chunk", "content": event.get("content", "")})

                elif event["type"] == "reasoning":
                    yield _sse({"type": "reasoning", "content": event.get("content", "")})

                elif event["type"] == "tool_calls_detected":
                    tcs = event["content"]
                    if tcs:
                        tc = tcs[0]
                        tool_calls_data = tc.get("args", {})
                    break

                elif event["type"] == "aborted":
                    yield _sse({"type": "aborted", "content": "Stream cancelado."})
                    return

        except Exception as e:
            logger.exception("Error en streaming interview: %s", e)
            yield _sse({"type": "error", "content": _FRIENDLY_ERROR_TOOL})
            return

        # ── Fallback: si no hubo tool call, intentar parsear JSON ──
        if not tool_calls_data:
            logger.warning("No tool call recibida. Content: %s", collected_content)
            parsed = _try_parse_json(collected_content)
            if parsed:
                tool_calls_data = parsed
            elif collected_content.strip():
                return
            else:
                yield _sse({"type": "error", "content": "El LLM no devolvió una respuesta válida."})
                return

        action = tool_calls_data.get("action")

        # ── QUESTION ──
        if action == "question":
            question_text = tool_calls_data.get("question", "")
            yield _sse({"type": "tool_action", "content": {"action": "question", "question": question_text}})
            return

        # ── CREATE ──
        if action != "create":
            logger.warning("Acción desconocida del LLM: %s", action)
            yield _sse({"type": "error", "content": _FRIENDLY_ERROR_TOOL})
            return

        task = tool_calls_data.get("task", descripcion)
        name = nombre or tool_calls_data.get("name")
        llm_parametros = tool_calls_data.get("parametros") or parametros
        llm_datos = tool_calls_data.get("datos") or datos

        # ════════════════════════════════════════════════════════════════
        # FASE 3: CREAR — ejecutar agente con tools (mismo loop que /skill)
        # ════════════════════════════════════════════════════════════════
        yield _sse({"type": "tool_action", "content": {"action": "creating"}})

        try:
            sys_prompt_template = agent.prompt("generar_tool")
        except FileNotFoundError:
            logger.exception("Prompt generar_tool.md no encontrado.")
            yield _sse({"type": "error", "content": _FRIENDLY_ERROR_TOOL})
            return

        # Formatear params/datos/conversación para el prompt de generación
        if llm_parametros:
            params_lines = []
            for p in llm_parametros:
                pname = p.get("name", "?")
                ptype = p.get("type", "str")
                pdesc = p.get("description", "")
                preq = "obligatorio" if p.get("required", True) else "opcional"
                params_lines.append(f"- {pname} ({ptype}, {preq}): {pdesc}")
            params_text = "\n".join(params_lines)
        else:
            params_text = "(Inferir parámetros según la descripción.)"

        datos_text = "\n".join(f"- {d}" for d in llm_datos) if llm_datos else "(Si la tool necesita credenciales, documentarlas acá.)"

        conversacion = _formatear_mensajes(mensajes) if mensajes else f"**Usuario**: {task}"

        carpeta = str(_TOOLS_DIR / (name or "tool"))
        sys_prompt = sys_prompt_template.format(
            nombre=name or "(inferir del contexto)",
            descripcion=task,
            conversacion=conversacion,
            parametros=params_text,
            datos=datos_text,
            carpeta=carpeta,
        )

        user_msg = (
            "Creá la tool. Pasos OBLIGATORIOS en orden: "
            "1) Escribí el archivo <nombre>.py con write. "
            "2) Escribí un script de tests en lib/tests/test_<nombre>.py. "
            "3) Ejecutá los tests con shell y mostrame los resultados. "
            "4) Iterá si hay errores. "
            "5) Cuando todo pase, pedime aprobación."
        )

        # ── 3a. Resolver tools ──
        try:
            tools = list(agent.tools.tools_registry(_AGENT_TOOLS_PERMS))
        except AttributeError as e:
            logger.exception("Error obteniendo tools: %s", e)
            yield _sse({"type": "error", "content": _FRIENDLY_ERROR_TOOL})
            return

        # ── 3b. Loop de tool calling EXACTO ChatInterface (loop.py) ──
        msgs: list[dict[str, Any]] = [
            {"role": "system", "content": sys_prompt},
            {"role": "user", "content": user_msg},
        ]

        async for event in stream_tool_calling_loop(msgs, tools, _FRIENDLY_ERROR_TOOL):
            yield _sse(event)
            if event["type"] == "error":
                return

        # ════════════════════════════════════════════════════════════════
        # FASE 4: BUSCAR lo que creó el agente
        # ════════════════════════════════════════════════════════════════
        if name:
            tool_path = _TOOLS_DIR / f"{name}.py"
            if tool_path.is_file():
                yield _sse({"type": "tool_result_final", "content": {
                    "status": "success",
                    "message": f"Tool '{name}' creada exitosamente.",
                    "data": {"exist": "No", "tool": name, "tool_path": str(tool_path)},
                }})
                return

        # Fallback: escanear tools recién creadas
        tools_actualizadas = _listar_tools_locales()
        herramientas_previas = _listar_tools_locales()  # Recompute; ya vimos las nuevas
        # Comparar contra las que ya existían al inicio de esta request
        # (re-leer del disco por si la última escritura las cambió)
        tools_actuales_nombres = {t["name"] for t in tools_actualizadas}
        # Recompute "previas": las que NO fueron creadas por este agente.
        # (el race condition se evita porque tools_locales ya se listó al inicio
        # pero acá lo volvemos a leer para tener el estado más fresco)
        tools_locales_reload = _listar_tools_locales()
        # Las "nuevas" son las que aparecieron desde el inicio
        # Para simplificar: si no encontramos la pedida por nombre,
        # igual emitimos un mensaje de éxito si hay archivo nuevo.
        nombres_actuales = {t["name"] for t in tools_locales_reload}
        # Buscar cualquier .py que haya sido creado en los últimos 60 segundos
        import time as _time
        cutoff = _time.time() - 300  # 5 min
        candidatos = []
        if _TOOLS_DIR.is_dir():
            for entry in _TOOLS_DIR.iterdir():
                if not entry.is_file() or not entry.name.endswith(".py") or entry.name.startswith("_"):
                    continue
                try:
                    mtime = entry.stat().st_mtime
                    if mtime >= cutoff:
                        candidatos.append(entry.stem)
                except Exception:
                    continue
        if candidatos:
            nueva_nombre = candidatos[0]
            tool_path = _TOOLS_DIR / f"{nueva_nombre}.py"
            yield _sse({"type": "tool_result_final", "content": {
                "status": "success",
                "message": f"Tool '{nueva_nombre}' creada exitosamente.",
                "data": {"exist": "No", "tool": nueva_nombre, "tool_path": str(tool_path)},
            }})
            return

        yield _sse({"type": "tool_result_final", "content": {
            "status": "success",
            "message": f"Tool '{name or 'tool'}' creada exitosamente.",
            "data": {"exist": "No", "tool": name or "tool", "tool_path": str(_TOOLS_DIR / f"{name or 'tool'}.py")},
        }})

    return StreamingResponse(event_stream(), media_type="text/event-stream")


# Helper para evaluar inline sin reimportar todo el módulo
async def _evaluar_si_existe_tool_inline(tarea, tools_locales, agent):
    """Wrapper sobre el helper compartido."""
    from backend.agent.utils.tools_helpers import _evaluar_si_existe
    return await _evaluar_si_existe(tarea, tools_locales)
