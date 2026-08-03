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
"""

from __future__ import annotations

import json
import logging
import os
import re
import sys
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

from backend.agent.utils.skill_creator.helpers import _listar_skills_locales, _evaluar_si_existe, _copiar_referencias
from backend.agent.utils.skill_creator.skill_agent import run_skill_agent
from backend.instances import agent
from backend.agent.config_dir import get_skills_dir

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/create", tags=["create"])

_SKILLS_DIR = get_skills_dir()

# Mensaje user-friendly para errores: el detalle técnico NUNCA llega a la UI.
_FRIENDLY_ERROR = "No se pudo crear la skill. Ocurrió un error durante el proceso. Verificá la configuración e intentá de nuevo."


# ── Modelos de request / response ─────────────────────────────────────


class CreateSkillRequest(BaseModel):
    """Request para crear una skill con iteración."""

    descripcion: str
    name: str | None = None
    mensajes: list[dict] | None = None  # [{"role": "user"|"assistant", "content": "..."}]


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
            async for event in agent.llm_streaming(
                model=agent._resolved_model,
                prompt=prompt,
                tools=[_INTERVIEW_TOOL],
                temperature=0.3,
                top_p=0.8,
                max_tokens=5000,
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
                        print(">>> CREATE SKILL - Tool call interview:")
                        print(f"  name: {tc.get('name')}")
                        print(f"  args: {json.dumps(tool_calls_data, ensure_ascii=False)}")
                    break

                elif event["type"] == "aborted":
                    yield _sse({"type": "aborted", "content": "Stream cancelado."})
                    return

        except Exception as e:
            logger.exception("Error en streaming interview: %s", e)
            print(f">>> CREATE SKILL - Error técnico (interview): {e}")
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
                print(">>> CREATE SKILL - Sin tool call: el texto plano es la respuesta de la entrevista.")
                return
            else:
                yield _sse({"type": "error", "content": "El LLM no devolvió una respuesta válida."})
                return

        action = tool_calls_data.get("action")

        # ── QUESTION ──
        if action == "question":
            question_text = tool_calls_data.get("question", "")
            print(">>> CREATE SKILL - Acción: question")
            print(f"  Pregunta: {question_text}")
            yield _sse({"type": "skill_action", "content": {"action": "question", "question": question_text}})
            return

        # ── CREATE ──
        if action != "create":
            logger.warning("Acción desconocida del LLM: %s", action)
            yield _sse({"type": "error", "content": _FRIENDLY_ERROR})
            return

        print(">>> CREATE SKILL - Acción: create")
        task = tool_calls_data.get("task", descripcion)
        name = nombre or tool_calls_data.get("name")
        refs = tool_calls_data.get("refs")
        print(f"  Task: {task}")
        print(f"  Name: {name}")

        # ════════════════════════════════════════════════════════════════
        # FASE 2: EVALUAR si ya existe una skill que cubra la tarea
        # ════════════════════════════════════════════════════════════════
        _SKILLS_DIR.mkdir(parents=True, exist_ok=True)
        skills_locales = _listar_skills_locales()
        decision = await _evaluar_si_existe(task, skills_locales)

        if decision and decision.get("exist") == "Sí":
            skill_name = decision.get("skill")
            print(f">>> CREATE SKILL - Ya existe: {skill_name}")
            yield _sse({"type": "skill_result", "content": {
                "status": "success",
                "message": f"Ya existe la skill '{skill_name}' que cubre esta tarea.",
                "data": {"exist": "Sí", "skill": skill_name},
            }})
            return

        # ════════════════════════════════════════════════════════════════
        # FASE 3: CREAR — ejecutar agente con tools, stremeando events
        # ════════════════════════════════════════════════════════════════
        print(">>> CREATE SKILL - No existe. Lanzando agente creador...")
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
            print(f">>> CREATE SKILL - Error técnico (tools): {e}")
            yield _sse({"type": "error", "content": _FRIENDLY_ERROR})
            return

        tool_names = [t.get("function", {}).get("name", "?") for t in tools]
        print(f">>> CREATE SKILL - Tools: {tool_names}")

        # ── 3b. Loop de tool calling EXACTO ChatInterface (loop.py) ──
        msgs: list[dict[str, Any]] = [
            {"role": "system", "content": sys_prompt},
            {"role": "user", "content": user_msg},
        ]

        max_iter = 25
        iteration = 0
        while iteration < max_iter:
            iteration += 1
            print(f">>> CREATE SKILL - Iteración {iteration}/{max_iter}")

            collected_content = ""
            tool_calls = None

            try:
                async for event in agent.llm_streaming(
                    model=agent._resolved_model,
                    messages=msgs,
                    tools=tools,
                    temperature=0.3,
                    top_p=0.8,
                    max_tokens=10000,
                    cleaned_output=True,
                ):
                    if event["type"] == "chunk":
                        collected_content += event.get("content", "")
                        yield _sse({"type": "chunk", "content": event.get("content", "")})

                    elif event["type"] == "reasoning":
                        yield _sse({"type": "reasoning", "content": event.get("content", "")})

                    elif event["type"] == "tool_calls_detected":
                        tool_calls = event["content"]
                        break

                    elif event["type"] == "aborted":
                        yield _sse({"type": "aborted", "content": "Stream cancelado."})
                        return

            except Exception as e:
                logger.exception("Error en streaming create agent: %s", e)
                print(f">>>> CREATE SKILL - Error técnico (create): {e}")
                yield _sse({"type": "error", "content": _FRIENDLY_ERROR})
                return

            print(f">>> CREATE SKILL - LLM: content_len={len(collected_content)}, tool_calls={len(tool_calls) if tool_calls else 0}")

            # ── Procesar tool_calls ──
            if tool_calls:
                # Guardar mensaje assistant con tool_calls
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

                    print(f">>> CREATE SKILL - Tool call: {tc_name}")
                    yield _sse({"type": "tool_call", "content": {"name": tc_name, "args": tc_args}})

                    # Ejecutar tool
                    try:
                        result = await agent.tools._execute_tool(tc_name, **tc_args)
                    except Exception as e:
                        logger.exception("Tool '%s' failed", tc_name)
                        result = {"status": "error", "message": str(e)}

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

                    print(f">>> CREATE SKILL - Tool result: {tc_name} -> {str(result_content)}")
                    yield _sse({"type": "tool_result", "content": {"name": tc_name, "result": result_content}})

                    msgs.append({
                        "role": "tool",
                        "tool_call_id": tc_id,
                        "content": result_content,
                    })

                # Continuar loop → siguiente iteración stremea la respuesta con tools results
            else:
                # Sin tool calls → terminó
                print(">>> CREATE SKILL - Sin tool calls, finalizando.")
                break

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
            print(f">>> CREATE SKILL - Skill creada: {skill_name_creado}")
            yield _sse({"type": "skill_result", "content": {
                "status": "success",
                "message": f"Skill '{skill_name_creado}' creada exitosamente.",
                "data": {"exist": "No", "skill": skill_name_creado, "skill_dir": str(skill_dir)},
            }})
        else:
            # El agente terminó la creación (escribió los archivos). Mostrar el cartel de éxito.
            nombre_creado = skill_name_creado or name or "skill"
            print(f">>> CREATE SKILL - Skill creada: {nombre_creado}")
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
