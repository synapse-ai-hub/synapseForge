"""Orquestación principal para la creación de skills.

Expone las funciones públicas:
- ``iterar_skill()`` — Itera con el LLM (preguntas → creación).
- ``create_skill()`` — Evalúa skills existentes o crea usando el agente con tools.
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

from backend.agent.utils.skill_creator.helpers import (
    _copiar_referencias,
    _evaluar_si_existe,
    _explicar_skill,
    _generar_skill,
    _listar_skills_locales,
)
from backend.agent.utils.skill_creator.skill_agent import run_skill_agent
from backend.agent.agent import Agent
from backend.agent.utils.config_dir import get_skills_dir
from backend.instances import agent

logger = logging.getLogger(__name__)

_SKILLS_DIR = get_skills_dir()


# ═══════════════════════════════════════════════════════════════════════
# Iteración con LLM (preguntas → creación) — SIN TOOLS
# ═══════════════════════════════════════════════════════════════════════


async def iterar_skill(
    descripcion: str,
    nombre: str | None = None,
    mensajes: list[dict] | None = None,
) -> dict[str, Any]:
    """Itera con el LLM para refinar la skill (entrevista).

    El LLM puede responder con:
    - ``{"action": "question", "question": "..."}`` → sigue preguntando.
    - ``{"action": "create", "task": "...", "name": "...", "triggers": "...",
         "not_triggers": "...", "refs": "...", "files": [...]}`` → pasa a crear.

    Returns:
        Dict con ``{status, message, data?, question?}``.
    """
    if not agent._resolved_model:
        return {"status": "error", "message": "No hay modelo configurado."}

    try:
        template = agent.prompt("iterar_skill")
    except FileNotFoundError:
        return {"status": "error", "message": "Prompt iterar_skill.md no encontrado."}

    # Formatear mensajes para el prompt
    mensajes_text = ""
    if mensajes:
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
        mensajes_text = "\n\n".join(partes)
    else:
        mensajes_text = "(Sin preguntas aún)"

    prompt = template.format(
        descripcion=descripcion,
        nombre=nombre or "(inferir)",
        mensajes=mensajes_text,
    )

    # print("=" * 60)
    # print(">>> ITERAR SKILL - PROMPT:")
    # print(prompt)
    # print("=" * 60)

    result = await agent.llm_process(
        model=agent._resolved_model,
        prompt=prompt,
        temperature=0.3,
        top_p=0.8,
        max_tokens=10000,
        cleaned_output=True,
        json_format=True,
    )

    # print(">>> ITERAR SKILL - RESPUESTA CRUDA:")
    # print(" ", result)
    # print("=" * 60)

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
            "message": "Procediendo a crear la skill.",
            "data": {
                "task": parsed.get("task", descripcion),
                "name": parsed.get("name", nombre),
                "triggers": parsed.get("triggers"),
                "not_triggers": parsed.get("not_triggers"),
                "refs": parsed.get("refs"),
                "files": parsed.get("files"),
            },
        }

    return {"status": "error", "message": f"Acción desconocida: {action}"}


# ═══════════════════════════════════════════════════════════════════════
# Orquestador principal — USA EL AGENTE CON TOOLS
# ═══════════════════════════════════════════════════════════════════════


async def create_skill(
    task: str,
    name: str | None = None,
    mensajes: list[dict] | None = None,
    refs: str | None = None,
    files: list[dict] | None = None,
) -> dict[str, Any]:
    """Busca si existe una skill que ya haga esto. Si no, la crea usando el agente.

    Args:
        task: Descripción o tarea para evaluar skills existentes.
        name: Nombre exacto para la skill.
        mensajes: Historial completo de la conversación con el usuario.
        refs: Material de referencia del usuario (texto legado).
        files: Archivos que el LLM decidió crear durante la entrevista.

    Returns:
        Dict con ``{status, message, data: {exist, skill, skill_dir?}}``.
    """
    logger.info("=" * 60)
    logger.info("CREATE SKILL: task='%s' name=%s", task, name)
    logger.info("=" * 60)

    _SKILLS_DIR.mkdir(parents=True, exist_ok=True)

    # ── 1. Skills locales ────────────────────────────────────────────
    skills_locales = _listar_skills_locales()
    logger.info("Skills locales: %d", len(skills_locales))

    # ── 2. Evaluar si existe ─────────────────────────────────────────
    decision = await _evaluar_si_existe(task, skills_locales)

    if decision and decision.get("exist") == "Sí":
        skill_name = decision.get("skill")
        logger.info("Skill existente encontrada: '%s'", skill_name)

        skill_dir = _SKILLS_DIR / skill_name if skill_name else None
        explicacion = None
        if skill_dir and skill_dir.is_dir():
            explicacion = await _explicar_skill(task, skill_dir)

        return {
            "status": "success",
            "message": f"Ya existe la skill '{skill_name}' que cubre esta tarea."
            if not explicacion
            else explicacion,
            "data": {
                "exist": "Sí",
                "skill": skill_name,
                "explicacion": explicacion,
            },
        }

    # ── 3. Generar nueva skill con el agente ──────────────────────────
    logger.info("No existe skill. Lanzando agente creador...")

    # Formatear la conversación completa como mensaje de usuario
    if mensajes:
        partes = []
        for m in mensajes:
            role = m.get("role", "user")
            content = m.get("content", "")
            label = "Usuario" if role == "user" else "Asistente"
            parte = f"**{label}**: {content}"
            files_in_msg = m.get("files")
            if files_in_msg and isinstance(files_in_msg, list):
                for f in files_in_msg:
                    fname = f.get("name", "archivo")
                    fcontent = f.get("content", "")
                    if fcontent:
                        parte += f"\n\n[Archivo adjunto: {fname}]\n```\n{fcontent}\n```"
            partes.append(parte)
        conversacion = "\n\n".join(partes)
    else:
        conversacion = f"**Usuario**: {task}"

    # Si el LLM ya decidió crear archivos durante la entrevista, agregarlos
    if files:
        for f in files:
            fname = f.get("filename", "archivo.md")
            fcontent = f.get("content", "")
            if fcontent:
                conversacion += f"\n\n[Archivo a crear: {fname}]\n```\n{fcontent}\n```"

    # Construir system prompt para el agente
    try:
        sys_prompt = agent.prompt("generar_skill")
    except FileNotFoundError:
        return {"status": "error", "message": "Prompt generar_skill.md no encontrado."}

    # Inyectar los datos en el system prompt
    sys_prompt = sys_prompt.format(
        nombre=name or "(inferir del contexto)",
        conversacion=conversacion,
    )

    # ── 4. Lanzar el agente con tools ─────────────────────────────────
    agent_tools_perms: dict[str, str] = {
        "read": "allow",
        "write": "allow",
        "edit": "allow",
        "shell": "allow",
        "list_dir": "allow",
    }
    agent_result = await run_skill_agent(
        system_prompt=sys_prompt,
        user_message="Ejecutá tu tarea. Creá el SKILL.md y los archivos necesarios. Cuando termines, indicame qué creaste.",
        tools_permissions=agent_tools_perms,
    )

    logger.info("Agente finalizado. Status: %s", agent_result.get("status"))

    if agent_result.get("status") != "success":
        return {
            "status": "error",
            "message": f"Error del agente: {agent_result.get('message', 'desconocido')}",
            "data": None,
        }

    # ── 5. Buscar la skill creada ─────────────────────────────────────
    # El agente ya escribió los archivos. Buscamos si se creó.
    if name:
        skill_dir = _SKILLS_DIR / name
        if skill_dir.is_dir() and (skill_dir / "SKILL.md").is_file():
            logger.info("Skill encontrada en: %s", skill_dir)

            # Copiar referencias del usuario si hay
            _copiar_referencias(skill_dir, mensajes, refs)

            return {
                "status": "success",
                "message": f"Skill '{name}' creada exitosamente.",
                "data": {
                    "exist": "No",
                    "skill": name,
                    "skill_dir": str(skill_dir),
                },
            }

    # Si no se encontró por nombre, escanear skills recién creadas
    skills_actualizadas = _listar_skills_locales()
    nuevas = [s for s in skills_actualizadas if s["name"] not in {old["name"] for old in skills_locales}]

    if nuevas:
        nueva = nuevas[0]
        skill_dir = _SKILLS_DIR / nueva["name"]
        _copiar_referencias(skill_dir, mensajes, refs)
        return {
            "status": "success",
            "message": f"Skill '{nueva['name']}' creada exitosamente.",
            "data": {
                "exist": "No",
                "skill": nueva["name"],
                "skill_dir": str(skill_dir),
            },
        }

    # El agente generó contenido pero no encontramos skill. Guardar igual.
    data_content = agent_result.get("data", "")
    if data_content and name:
        skill_dir = _SKILLS_DIR / name
        skill_dir.mkdir(parents=True, exist_ok=True)
        (skill_dir / "SKILL.md").write_text(data_content, encoding="utf-8")
        _copiar_referencias(skill_dir, mensajes, refs)
        logger.info("Skill guardada (fallback) en: %s", skill_dir)
        return {
            "status": "success",
            "message": f"Skill '{name}' creada exitosamente.",
            "data": {
                "exist": "No",
                "skill": name,
                "skill_dir": str(skill_dir),
            },
        }

    return {
        "status": "error",
        "message": "El agente no creó ningún skill.",
        "data": None,
    }
