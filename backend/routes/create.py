"""Router para endpoints de creación (tools, skills, agents, RAG).

Actualmente implementa:
- ``POST /api/create/skill`` — Busca o crea una skill.
"""

import logging

from fastapi import APIRouter
from pydantic import BaseModel

from backend.agent.utils.skill_creator import create_skill

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/create", tags=["create"])


# ── Modelos de request / response ─────────────────────────────────────


class CreateSkillRequest(BaseModel):
    """Request para crear una skill."""

    task: str
    name: str | None = None
    triggers: str | None = None
    not_triggers: str | None = None
    refs: str | None = None


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
    usage: dict = {}


# ── Endpoints ─────────────────────────────────────────────────────────


@router.post("/skill", response_model=CreateSkillResponse)
async def post_create_skill(req: CreateSkillRequest) -> CreateSkillResponse:
    """Crea una skill, buscando primero entre las existentes.

    Flujo:
    1. Lee skills locales y pregunta al LLM si alguna sirve.
    2. Si Sí → la devuelve con explicación.
    3. Si No → la genera con el LLM y la guarda.
    """
    logger.info("POST /api/create/skill — task='%s' name=%s", req.task, req.name)

    if not req.task or not req.task.strip():
        return CreateSkillResponse(
            status="error",
            message="El campo 'task' es obligatorio.",
            data=None,
        )

    result = await create_skill(
        task=req.task.strip(),
        name=req.name.strip() if req.name else None,
        triggers=req.triggers.strip() if req.triggers else None,
        not_triggers=req.not_triggers.strip() if req.not_triggers else None,
        refs=req.refs.strip() if req.refs else None,
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
    )
