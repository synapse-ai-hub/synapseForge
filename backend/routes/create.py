"""Router para endpoints de creación (tools, skills, agents, RAG).

Endpoints:
- ``POST /api/create/skill`` — Crea una skill con iteración LLM.
"""

import logging

from fastapi import APIRouter
from pydantic import BaseModel

from backend.agent.utils.skill_creator import create_skill, iterar_skill

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/create", tags=["create"])


# ── Modelos de request / response ─────────────────────────────────────


class CreateSkillRequest(BaseModel):
    """Request para crear una skill con iteración."""

    descripcion: str
    name: str | None = None
    mensajes: list[dict] | None = None  # [{"role": "user"|"assistant", "content": "..."}]


class CreateSkillData(BaseModel):
    """Datos de la skill (existente o creada)."""

    exist: str  # "Sí" | "No"
    skill: str  # nombre de la skill
    explicacion: str | None = None
    skill_dir: str | None = None


class CreateSkillResponse(BaseModel):
    """Response siguiendo el contrato ``{status, message, data, usage}``."""

    status: str
    message: str
    data: CreateSkillData | None = None
    question: str | None = None
    usage: dict = {}


# ── Endpoints ─────────────────────────────────────────────────────────


@router.post("/skill", response_model=CreateSkillResponse)
async def post_create_skill(req: CreateSkillRequest) -> CreateSkillResponse:
    """Crea una skill con iteración LLM.

    Flujo:
    1. Si ``mensajes`` está vacío → es la primera llamada.
       El LLM puede responder con una pregunta o con "create".
    2. Si ``mensajes`` tiene historial → el LLM sigue iterando.
    3. Cuando el LLM responde "create" → se evaluan skills existentes
       y si no hay, se genera la skill.
    """
    logger.info(
        "POST /api/create/skill — descripcion='%s' name=%s mensajes=%d",
        req.descripcion[:80], req.name,
        len(req.mensajes) if req.mensajes else 0,
    )

    if not req.descripcion or not req.descripcion.strip():
        return CreateSkillResponse(
            status="error",
            message="El campo 'descripcion' es obligatorio.",
            data=None,
        )

    # ── Iterar con LLM ────────────────────────────────────────────────
    resultado_iter = await iterar_skill(
        descripcion=req.descripcion.strip(),
        nombre=req.name.strip() if req.name else None,
        mensajes=req.mensajes or [],
    )

    # Si el LLM preguntó algo → devolver la pregunta
    if resultado_iter.get("status") == "question":
        logger.info("LLM pregunta: %s", resultado_iter.get("question", "")[:100])
        return CreateSkillResponse(
            status="question",
            message=resultado_iter.get("question", ""),
            question=resultado_iter.get("question", ""),
            data=None,
        )

    # Si el LLM respondió con error
    if resultado_iter.get("status") == "error":
        logger.warning("Error en iteración: %s", resultado_iter.get("message"))
        return CreateSkillResponse(
            status="error",
            message=resultado_iter.get("message", "Error en la iteración."),
            data=None,
        )

    # ── Si el LLM dijo "create" → proceder con evaluación + generación ─
    data_create = (resultado_iter.get("data") or {})
    task = data_create.get("task", req.descripcion)
    # Si el usuario dió nombre, usá ese exacto. Si no, el que el LLM infirió.
    name = req.name or data_create.get("name")
    refs = data_create.get("refs")
    logger.info("LLM decidió crear. task='%s' name=%s", task[:80], name)

    result = await create_skill(
        task=task,
        name=name,
        mensajes=req.mensajes or [],
        refs=refs,
    )

    logger.info(
        "Resultado: status=%s message='%s'",
        result["status"],
        result["message"],
    )

    data = None
    if result.get("data"):
        data = CreateSkillData(**result["data"])

    return CreateSkillResponse(
        status=result["status"],
        message=result["message"],
        data=data,
        question=None,
    )
