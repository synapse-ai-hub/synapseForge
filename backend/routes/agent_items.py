"""List and delete skills, tools, agents, MCP servers and RAG collections.

Endpoints:
- ``GET /api/knowledge`` — List vector collections.
- ``DELETE /api/skills/{name}`` — Delete a skill (whole directory).
- ``DELETE /api/tools/{name}`` — Delete an external tool (.py).
- ``DELETE /api/agents/{name}`` — Delete an agent (.md).
- ``DELETE /api/mcp/{label}`` — Delete an MCP server from the config.
- ``DELETE /api/knowledge/{collection}`` — Delete a vector collection.
"""

from __future__ import annotations

import logging
import os
import shutil
import sys
from pathlib import Path
from typing import Any

from fastapi import APIRouter
from fastapi.responses import JSONResponse

_current_dir = os.path.dirname(os.path.abspath(__file__))
_project_root = os.path.dirname(os.path.dirname(_current_dir))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from backend.agent.utils.config_dir import (
    get_skills_dir,
    get_tools_dir,
    get_agents_dir,
    get_knowledge_dir,
    load_config,
    save_config,
    load_mcp_servers,
    save_mcp_servers,
)
from backend.agent.utils.error_logger import log_error
from backend.agent.utils.vector_db import VectorDB, get_vector_db

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/agent", tags=["agent"])


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_response(
    status: str,
    message: str,
    status_code: int = 200,
) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={"status": status, "message": message},
    )


def _rmtree(path: Path) -> bool:
    """Remove a directory tree."""
    try:
        shutil.rmtree(str(path))
        return True
    except OSError as e:
        log_error(str(e), source="agent_items.py:_rmtree")
        return False


def _unlink(path: Path) -> bool:
    """Remove a single file."""
    try:
        path.unlink()
        return True
    except OSError as e:
        log_error(str(e), source="agent_items.py:_unlink")
        return False


# ---------------------------------------------------------------------------
# GET /agent/knowledge  —  listar colecciones
# ---------------------------------------------------------------------------


@router.get("/knowledge")
async def list_knowledge_collections() -> JSONResponse:
    """List the available vector collections.

    Returns:
        A JSONResponse with ``{status, collections: string[]}``.
    """
    try:
        db = get_vector_db()
        cols = db.list_collections()
        names = [c["name"] for c in cols]
        return JSONResponse(
            status_code=200,
            content={"status": "success", "collections": names},
        )
    except Exception as exc:
        log_error(str(exc), source="agent_items.py:list_knowledge_collections")
        logger.warning("Error listando colecciones: %s", exc)
        return JSONResponse(
            status_code=500,
            content={"status": "error", "message": "Error listando colecciones", "collections": []},
        )


# ---------------------------------------------------------------------------
# DELETE /agent/skills/{name}
# ---------------------------------------------------------------------------


@router.delete("/skills/{name}")
async def delete_skill(name: str) -> JSONResponse:
    """Delete a skill by name.

    Looks up ``<skills_dir>/<name>/`` and removes it recursively.

    Returns:
        A JSONResponse with the operation result.
    """
    if not name or ".." in name or "/" in name:
        return _make_response("error", "Nombre de skill inválido.", 400)

    skill_dir = get_skills_dir() / name
    if not skill_dir.is_dir():
        return _make_response("error", f"Skill '{name}' no encontrada.", 404)

    logger.info("Eliminando skill: %s", skill_dir)
    ok = _rmtree(skill_dir)
    if not ok:
        return _make_response("error", f"No se pudo eliminar la skill '{name}'.", 500)

    return _make_response("success", f"Skill '{name}' eliminada.")


# ---------------------------------------------------------------------------
# DELETE /agent/tools/{name}
# ---------------------------------------------------------------------------


@router.delete("/tools/{name}")
async def delete_tool(name: str) -> JSONResponse:
    """Delete an external tool by name.

    Looks up ``<tools_dir>/<name>.py`` and removes it.

    Returns:
        A JSONResponse with the operation result.
    """
    if not name or ".." in name or "/" in name:
        return _make_response("error", "Nombre de tool inválido.", 400)

    # La tool puede estar como nombre sin extensión
    tool_path = get_tools_dir() / name
    if not tool_path.is_file():
        tool_path = get_tools_dir() / f"{name}.py"
    if not tool_path.is_file():
        return _make_response("error", f"Tool '{name}' no encontrada.", 404)

    logger.info("Eliminando tool externa: %s", tool_path)
    ok = _unlink(tool_path)
    if not ok:
        return _make_response("error", f"No se pudo eliminar la tool '{name}'.", 500)

    return _make_response("success", f"Tool externa '{name}' eliminada.")


# ---------------------------------------------------------------------------
# DELETE /agent/agents/{name}
# ---------------------------------------------------------------------------


@router.delete("/agents/{name}")
async def delete_agent(name: str) -> JSONResponse:
    """Delete an agent by name.

    Looks up ``<agents_dir>/<name>.md`` and removes it.

    Returns:
        A JSONResponse with the operation result.
    """
    if not name or ".." in name or "/" in name:
        return _make_response("error", "Nombre de agente inválido.", 400)

    agent_path = get_agents_dir() / f"{name}.md"
    if not agent_path.is_file():
        return _make_response("error", f"Agente '{name}' no encontrado.", 404)

    logger.info("Eliminando agente: %s", agent_path)
    ok = _unlink(agent_path)
    if not ok:
        return _make_response("error", f"No se pudo eliminar el agente '{name}'.", 500)

    return _make_response("success", f"Agente '{name}' eliminado.")


# ---------------------------------------------------------------------------
# DELETE /agent/mcp/{label}
# ---------------------------------------------------------------------------


@router.delete("/mcp/{label:path}")
async def delete_mcp_server(label: str) -> JSONResponse:
    """Delete an MCP server from mcp.json.

    Returns:
        A JSONResponse with the operation result.
    """
    if not label:
        return _make_response("error", "Label del servidor inválido.", 400)

    servers = load_mcp_servers()

    found = None
    for s in servers:
        if s.get("label") == label:
            found = s
            break

    if found is None:
        return _make_response("error", f"Servidor MCP '{label}' no encontrado.", 404)

    servers.remove(found)
    ok = save_mcp_servers(servers)
    if not ok:
        return _make_response("error", f"No se pudo guardar mcp.json al eliminar '{label}'.", 500)

    logger.info("Servidor MCP eliminado: %s", label)
    return _make_response("success", f"Servidor MCP '{label}' eliminado.")


# ---------------------------------------------------------------------------
# DELETE /agent/knowledge/{collection}
# ---------------------------------------------------------------------------


@router.delete("/knowledge/{collection}")
async def delete_knowledge_collection(collection: str) -> JSONResponse:
    """Delete a vector collection from the knowledge base.

    Looks up ``<knowledge_dir>/<collection>/`` and removes it recursively.

    Returns:
        A JSONResponse with the operation result.
    """
    if not collection or ".." in collection or "/" in collection:
        return _make_response("error", "Nombre de colección inválido.", 400)

    coll_dir = get_knowledge_dir() / collection
    if not coll_dir.is_dir():
        return _make_response("error", f"Colección '{collection}' no encontrada.", 404)

    logger.info("Eliminando colección vectorial: %s", coll_dir)
    ok = _rmtree(coll_dir)
    if not ok:
        return _make_response(
            "error", f"No se pudo eliminar la colección '{collection}'.", 500
        )

    return _make_response("success", f"Colección '{collection}' eliminada.")
