"""Helpers for skill creation.

Low-level internal functions:
- ``_parse_frontmatter``
- ``_listar_skills_locales``
- ``_evaluar_si_existe``
- ``_explicar_skill``
- ``_generar_skill``
- ``_copiar_referencias``

All are imported by ``backend/routes/create.py``.
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

from backend.agent.utils.config_dir import get_skills_dir
from backend.agent.utils.create_helpers import resolve_create_model_provider
from backend.instances import agent

logger = logging.getLogger(__name__)

_SKILLS_DIR = get_skills_dir()


# ═══════════════════════════════════════════════════════════════════════
# Frontmatter
# ═══════════════════════════════════════════════════════════════════════


def _parse_frontmatter(content: str) -> dict[str, Any]:
    """Extrae el frontmatter YAML de un SKILL.md.

    Args:
        content: Contenido completo del archivo.

    Returns:
        Diccionario con los campos del frontmatter, o dict vacío.
    """
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
    model: str | None = None,
    provider: str | None = None,
) -> dict | None:
    """Pregunta al LLM si alguna skill local sirve.

    Args:
        tarea: Lo que el usuario quiere hacer.
        skills_locales: Lista de skills existentes.
        model: Modelo elegido por el usuario (opcional).
        provider: Provider elegido por el usuario (opcional).

    Returns:
        ``{"exist": "Sí", "skill": ...}`` o ``{"exist": "No", "skill": None}``.
    """
    eval_model, eval_provider = resolve_create_model_provider(model, provider)
    if not eval_model:
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

    # print("=" * 60)
    # print(">>> EVALUAR SKILLS - PROMPT AL LLM:")
    # print(prompt)
    # print("=" * 60)

    result = await agent.llm_process(
        model=eval_model,
        provider=eval_provider,
        prompt=prompt,
        temperature=0.0,
        top_p=0.6,
        max_tokens=5000,
        cleaned_output=True,
    )

    # print(">>> EVALUAR SKILLS - RESPUESTA CRUDA DEL LLM:")
    # print("  result brute:", result)
    # print("=" * 60)

    if result.get("status") != "success" or not result.get("data"):
        logger.warning("Error del LLM: %s", result.get("message"))
        return None

    raw = result["data"].strip()
    m = re.search(r"\{.*?\}", raw, re.DOTALL)
    if not m:
        logger.warning("LLM no devolvió JSON: %s", raw[:150])
        return None
    try:
        parsed = json.loads(m.group(0))
        # print(">>> EVALUAR SKILLS - JSON PARSED:", parsed)
        # print("=" * 60)
        return parsed
    except Exception as e:
        logger.warning("Error parseando JSON: %s", e)
        return None


# ═══════════════════════════════════════════════════════════════════════
# Explicación de skill existente
# ═══════════════════════════════════════════════════════════════════════


async def _explicar_skill(
    tarea: str,
    skill_dir: Path,
    model: str | None = None,
    provider: str | None = None,
) -> str | None:
    """Pide al LLM una breve explicación de qué hace la skill.

    Args:
        tarea: Lo que el usuario quiere resolver.
        skill_dir: Directorio de la skill.
        model: Modelo elegido por el usuario (opcional).
        provider: Provider elegido por el usuario (opcional).

    Returns:
        Explicación breve, o None si falla.
    """
    eval_model, eval_provider = resolve_create_model_provider(model, provider)
    if not eval_model:
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
        model=eval_model,
        provider=eval_provider,
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
    model: str | None = None,
    provider: str | None = None,
) -> dict[str, Any]:
    """Genera una skill con el LLM usando el prompt ``generar_skill``.

    Args:
        conversacion: Historial completo de la conversación con el usuario.
        nombre: Nombre sugerido para la skill.
        model: Modelo elegido por el usuario (opcional).
        provider: Provider elegido por el usuario (opcional).

    Returns:
        ``{"name": ..., "content": ...}``.

    Raises:
        RuntimeError: Si el LLM falla o no hay modelo.
    """
    eval_model, eval_provider = resolve_create_model_provider(model, provider)
    if not eval_model:
        raise RuntimeError("No hay modelo configurado. Seleccioná un modelo en Configuración.")

    try:
        template = agent.prompt("generar_skill")
    except FileNotFoundError:
        raise RuntimeError("Prompt generar_skill.md no encontrado.")

    prompt = template.format(
        nombre=nombre or "(inferir del contexto)",
        conversacion=conversacion,
    )

    logger.info("Generando skill con LLM (%s)...", eval_model)

    result = await agent.llm_process(
        model=eval_model,
        provider=eval_provider,
        prompt=prompt,
        temperature=0.4,
        top_p=0.85,
        max_tokens=15000,
        cleaned_output=True,
    )

    if result.get("status") != "success" or not result.get("data"):
        raise RuntimeError(f"Error del LLM: {result.get('message', 'sin respuesta')}")

    raw = result["data"]
    # Safety: strip markdown code fences
    raw = re.sub(r"^```\w*\s*", "", raw.strip())
    raw = re.sub(r"\s*```\s*$", "", raw)
    fm = _parse_frontmatter(raw)
    skill_name = nombre or fm.get("name") or "skill-generada"
    return {"name": skill_name, "content": raw}


# ═══════════════════════════════════════════════════════════════════════
# Post-creación: referencias
# ═══════════════════════════════════════════════════════════════════════


def _copiar_referencias(
    skill_dir: Path,
    mensajes: list[dict] | None = None,
    refs: str | None = None,
) -> None:
    """Copia los archivos adjuntos del usuario a ``references/``.

    Paso separado de la creación de la skill. Solo copia archivos
    por código. El LLM ya referenció estos archivos en el SKILL.md
    con rutas relativas (``references/``).

    No se crean subdirectorios anidados. Solo archivos sueltos
    dentro de ``references/``.

    Args:
        skill_dir: Directorio de la skill.
        mensajes: Historial de mensajes (pueden contener ``files``).
        refs: Texto de referencia del LLM (opcional, legacy).
    """
    refs_dir = skill_dir / "references"
    refs_dir.mkdir(exist_ok=True)

    # 5a. Si el LLM devolvió refs de texto (legacy)
    if refs and refs.strip():
        (refs_dir / "referencias_usuario.md").write_text(refs, encoding="utf-8")
        logger.info("Refs de texto guardadas en references/")

    # 5b. Copiar archivos adjuntos del usuario con nombre original
    #     Solo archivos sueltos, sin subdirectorios anidados.
    if mensajes:
        contadas = 0
        for m in mensajes:
            files = m.get("files")
            if files and isinstance(files, list):
                for f in files:
                    fname = f.get("name", "archivo")
                    fcontent = f.get("content", "")
                    if fname and fcontent:
                        safe_name = Path(fname).name
                        if not safe_name:
                            continue
                        ref_path = refs_dir / safe_name
                        ref_path.write_text(fcontent, encoding="utf-8")
                        contadas += 1
                        logger.info("Referencia copiada: %s", ref_path)
        if contadas:
            logger.info("%d archivos copiados a references/", contadas)
