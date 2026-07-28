"""Servicio de creación de skills.

Flujo:
  1. Lee skills existentes de ``~/.config/synapseForge/skills/``.
  2. Pasa la tarea del usuario + skills locales al LLM (prompt ``evaluar_skills``).
  3. Si el LLM responde "Sí":
     a. Lee el SKILL.md de esa skill.
     b. Pasa el contenido al LLM (prompt ``explicar_skill``) para obtener una
        explicación breve.
     c. Devuelve nombre + explicación.
  4. Si responde "No": pasa al LLM el prompt ``generar_skill`` y crea la skill.
  5. Guarda en ``~/.config/synapseForge/skills/<nombre>/``.
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
# Ensure the project root is in sys.path so absolute imports (backend.*)
# resolve correctly regardless of how the file is invoked.
# ---------------------------------------------------------------------------
_current_dir = os.path.dirname(os.path.abspath(__file__))
_project_root = os.path.dirname(os.path.dirname(os.path.dirname(_current_dir)))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from backend.agent.config_dir import get_skills_dir
from backend.instances import agent

logger = logging.getLogger(__name__)

_SKILLS_DIR = get_skills_dir()


# ═══════════════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════════════


def _parse_frontmatter(content: str) -> dict[str, Any]:
    """Extrae el frontmatter YAML de un SKILL.md."""
    match = re.match(r"^---\s*\n(.*?)\n---", content, re.DOTALL)
    if not match:
        return {}
    try:
        import yaml
        return yaml.safe_load(match.group(1)) or {}
    except Exception as e:
        logger.warning("Error parseando frontmatter: %s", e)
        return {}


# ═══════════════════════════════════════════════════════════════════════
# Skills locales
# ═══════════════════════════════════════════════════════════════════════


def _listar_skills_locales() -> list[dict[str, Any]]:
    """Escanea skills locales y devuelve nombre + descripción."""
    if not _SKILLS_DIR.is_dir():
        return []
    resultados: list[dict[str, Any]] = []
    for d in _SKILLS_DIR.iterdir():
        if not d.is_dir():
            continue
        md = d / "SKILL.md"
        if not md.is_file():
            continue
        fm = _parse_frontmatter(md.read_text(encoding="utf-8"))
        resultados.append({
            "name": d.name,
            "description": fm.get("description", ""),
            "triggers": (fm.get("metadata") or {}).get("triggers", ""),
            "path": str(d),
        })
    return resultados


# ═══════════════════════════════════════════════════════════════════════
# Evaluación con LLM (Sí/No)
# ═══════════════════════════════════════════════════════════════════════


async def _evaluar_si_existe(
    tarea: str,
    skills_locales: list[dict[str, Any]],
) -> dict | None:
    """Pregunta al LLM si alguna skill local sirve.

    Returns:
        ``{"exist": "Sí", "skill": ...}`` o ``{"exist": "No", "skill": None}``.
    """
    if not agent._resolved_model:
        logger.warning("Sin modelo configurado.")
        return None

    try:
        template = agent.prompt("evaluar_skills")
    except FileNotFoundError:
        logger.warning("Prompt evaluar_skills.md no encontrado.")
        return None

    if skills_locales:
        lines = [f"- **{s['name']}**: {s['description'][:200]}" for s in skills_locales]
        skills_text = "\n".join(lines)
    else:
        skills_text = "(No hay skills creadas todavía.)"

    prompt = template.format(tarea=tarea, skills=skills_text)

    print("=" * 60)
    print(">>> EVALUAR SKILLS - PROMPT AL LLM:")
    print(prompt)
    print("=" * 60)

    result = await agent.llm_process(
        model=agent._resolved_model,
        prompt=prompt,
        temperature=0.0,
        top_p=0.6,
        max_tokens=5000,
        cleaned_output=True,
    )

    print(">>> EVALUAR SKILLS - RESPUESTA CRUDA DEL LLM:")
    print("  result brute:", result)
    print("=" * 60)

    if result.get("status") != "success" or not result.get("data"):
        logger.warning("Error del LLM: %s", result.get("message"))
        return None

    raw = result["data"].strip()
    m = re.search(r"\{.*\}", raw, re.DOTALL)
    if not m:
        logger.warning("LLM no devolvió JSON: %s", raw[:150])
        return None
    try:
        parsed = json.loads(m.group(0))
        print(">>> EVALUAR SKILLS - JSON PARSED:", parsed)
        print("=" * 60)
        return parsed
    except Exception as e:
        logger.warning("Error parseando JSON: %s", e)
        return None


# ═══════════════════════════════════════════════════════════════════════
# Explicación de skill existente
# ═══════════════════════════════════════════════════════════════════════


async def _explicar_skill(tarea: str, skill_dir: Path) -> str | None:
    """Pide al LLM una breve explicación de qué hace la skill.

    Args:
        tarea: Lo que el usuario quiere resolver.
        skill_dir: Directorio de la skill.

    Returns:
        Explicación breve, o None si falla.
    """
    if not agent._resolved_model:
        return None

    md_path = skill_dir / "SKILL.md"
    if not md_path.is_file():
        return None

    contenido = md_path.read_text(encoding="utf-8")

    try:
        template = agent.prompt("explicar_skill")
    except FileNotFoundError:
        logger.warning("Prompt explicar_skill.md no encontrado.")
        return None

    prompt = template.format(tarea=tarea, contenido=contenido)

    result = await agent.llm_process(
        model=agent._resolved_model,
        prompt=prompt,
        temperature=0.3,
        top_p=0.8,
        max_tokens=5000,
        cleaned_output=True,
    )

    if result.get("status") != "success" or not result.get("data"):
        return None

    raw = result["data"].strip()
    m = re.search(r"\{.*\}", raw, re.DOTALL)
    if not m:
        return None
    try:
        dec = json.loads(m.group(0))
        return dec.get("explicacion")
    except Exception:
        return None


# ═══════════════════════════════════════════════════════════════════════
# Generación con LLM
# ═══════════════════════════════════════════════════════════════════════


async def _generar_skill(
    conversacion: str,
    nombre: str | None = None,
) -> dict[str, Any]:
    """Genera una skill con el LLM usando el prompt ``generar_skill``.

    Args:
        conversacion: Historial completo de la conversación con el usuario.
        nombre: Nombre sugerido para la skill.

    Returns:
        ``{"name": ..., "content": ...}``.
    """
    if not agent._resolved_model:
        raise RuntimeError("No hay modelo configurado. Seleccioná un modelo en Configuración.")

    try:
        template = agent.prompt("generar_skill")
    except FileNotFoundError:
        raise RuntimeError("Prompt generar_skill.md no encontrado.")

    prompt = template.format(
        nombre=nombre or "(inferir del contexto)",
        conversacion=conversacion,
    )

    logger.info("Generando skill con LLM (%s)...", agent._resolved_model)

    result = await agent.llm_process(
        model=agent._resolved_model,
        prompt=prompt,
        temperature=0.4,
        top_p=0.85,
        max_tokens=15000,
        cleaned_output=True,
    )

    if result.get("status") != "success" or not result.get("data"):
        raise RuntimeError(f"Error del LLM: {result.get('message', 'sin respuesta')}")

    raw = result["data"]
    # Safety: strip markdown code fences (```, ```markdown, ```yaml, etc.)
    raw = re.sub(r"^```\w*\s*", "", raw.strip())
    raw = re.sub(r"\s*```\s*$", "", raw)
    fm = _parse_frontmatter(raw)
    skill_name = (
        nombre
        or fm.get("name")
        or "skill-generada"
    )
    return {"name": skill_name, "content": raw}


# ═══════════════════════════════════════════════════════════════════════
# Iteración con LLM (preguntas → creación)
# ═══════════════════════════════════════════════════════════════════════


async def iterar_skill(
    descripcion: str,
    nombre: str | None = None,
    mensajes: list[dict] | None = None,
) -> dict[str, Any]:
    """Itera con el LLM para refinar la skill.

    El LLM puede responder con:
    - ``{"action": "question", "question": "..."}`` → sigue preguntando.
    - ``{"action": "create", "task": "...", "name": "...", "triggers": "...",
         "not_triggers": "...", "refs": "..."}`` → pasa a crear.

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
            partes.append(f"**{label}**: {content}")
        mensajes_text = "\n\n".join(partes)
    else:
        mensajes_text = "(Sin preguntas aún)"

    prompt = template.format(
        descripcion=descripcion,
        nombre=nombre or "(inferir)",
        mensajes=mensajes_text,
    )

    print("=" * 60)
    print(">>> ITERAR SKILL - PROMPT:")
    print(prompt)
    print("=" * 60)

    result = await agent.llm_process(
        model=agent._resolved_model,
        prompt=prompt,
        temperature=0.3,
        top_p=0.8,
        max_tokens=5000,
        cleaned_output=True,
    )

    print(">>> ITERAR SKILL - RESPUESTA CRUDA:")
    print(" ", result)
    print("=" * 60)

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
        # Tiene suficiente info → crear skill
        return {
            "status": "create",
            "message": "Procediendo a crear la skill.",
            "data": {
                "task": parsed.get("task", descripcion),
                "name": parsed.get("name", nombre),
                "triggers": parsed.get("triggers"),
                "not_triggers": parsed.get("not_triggers"),
                "refs": parsed.get("refs"),
            },
        }

    return {"status": "error", "message": f"Acción desconocida: {action}"}


# ═══════════════════════════════════════════════════════════════════════
# Orquestador principal
# ═══════════════════════════════════════════════════════════════════════


async def create_skill(
    task: str,
    name: str | None = None,
    mensajes: list[dict] | None = None,
    refs: str | None = None,
) -> dict[str, Any]:
    """Busca si existe una skill que ya haga esto. Si no, la crea.

    Args:
        task: Descripción o tarea para evaluar skills existentes.
        name: Nombre exacto para la skill.
        mensajes: Historial completo de la conversación con el usuario.
        refs: Material de referencia del usuario.

    Returns:
        Dict con ``{status, message, data: {exist, skill, explication?,
        skill_dir?}}``.
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

        # Buscar el directorio de la skill
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

    # ── 3. Generar nueva skill ───────────────────────────────────────
    logger.info("No existe skill. Generando...")

    # Formatear la conversación completa para el prompt
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

    try:
        gen = await _generar_skill(
            conversacion=conversacion,
            nombre=name,
        )
    except RuntimeError as e:
        return {"status": "error", "message": f"Error del LLM: {e}", "data": None}

    # ── 4. Guardar ────────────────────────────────────────────────────
    skill_dir = _SKILLS_DIR / gen["name"]
    skill_dir.mkdir(parents=True, exist_ok=True)
    (skill_dir / "SKILL.md").write_text(gen["content"], encoding="utf-8")

    # Siempre crear carpeta references (vacía si no hay refs)
    refs_dir = skill_dir / "references"
    refs_dir.mkdir(exist_ok=True)
    if refs and refs.strip():
        (refs_dir / "referencias_usuario.md").write_text(refs, encoding="utf-8")

    logger.info(">>> SKILL GUARDADA EN: %s", skill_dir)

    return {
        "status": "success",
        "message": f"Skill '{gen['name']}' creada exitosamente.",
        "data": {
            "exist": "No",
            "skill": gen["name"],
            "skill_dir": str(skill_dir),
        },
    }
