"""Context files endpoints for the agent loop.

Provides endpoints to upload, list, and delete context files.
Context files are stored in SQLite and their content is injected
into the system prompt for both the main agent and sub-agents.
"""

from __future__ import annotations

import logging
import os
import sqlite3
import sys
from datetime import datetime, timezone

from fastapi import APIRouter, File, Form, UploadFile

# ---------------------------------------------------------------------------
# Ensure the project root is in sys.path so absolute imports (backend.*)
# resolve correctly regardless of how the file is invoked.
# ---------------------------------------------------------------------------
_current_dir = os.path.dirname(os.path.abspath(__file__))
_project_root = os.path.dirname(os.path.dirname(_current_dir))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from backend.agent.contract import (
    make_error_response,
    make_success_response,
    validate_response,
    zero_usage,
)
from backend.routes.file_text_extractor import (
    ExtractionResult,
    extract_text_from_bytes,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/context-files", tags=["context-files"])

_DB_PATH = os.path.join(_project_root, "backend", "agent", "agent_db", "agent.db")


def _get_connection() -> sqlite3.Connection:
    """Open a connection to the SQLite database and ensure the table exists.

    Returns:
        A ``sqlite3.Connection`` instance.
    """
    db_dir = os.path.dirname(_DB_PATH)
    if db_dir:
        os.makedirs(db_dir, exist_ok=True)
    conn = sqlite3.connect(_DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS context_files (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            filename TEXT NOT NULL,
            content TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
        """
    )
    return conn


@router.post("")
async def upload_context_file(
    file: UploadFile = File(...),
):
    """Upload a context file, extract its text, and store it in SQLite.

    The endpoint receives an uploaded file, extracts its text content
    using ``extract_text_from_bytes``, and stores it in the ``context_files``
    table.

    Args:
        file: The uploaded file object.

    Returns:
        A contract response with ``data`` containing ``id`` and ``filename``.
    """
    try:
        filename = file.filename or "sin_nombre"
        content_bytes = await file.read()

        # Validate size (50 MB limit)
        max_bytes = 50 * 1024 * 1024
        if len(content_bytes) > max_bytes:
            return make_error_response(
                message=f"{filename} excede el tamaño máximo de 50 MB.",
            )

        result: ExtractionResult = extract_text_from_bytes(filename, content_bytes)
        if not result.success:
            detail = result.error_detail or f"No se pudo procesar {filename}."
            return make_error_response(message=detail)

        text = (result.text or "").strip()
        if not text:
            return make_error_response(
                message=f"No se encontró texto legible en {filename}.",
            )

        now = datetime.now(timezone.utc).isoformat()
        conn = _get_connection()
        try:
            cursor = conn.execute(
                "INSERT INTO context_files (filename, content, created_at) VALUES (?, ?, ?)",
                (filename, text, now),
            )
            conn.commit()
            file_id = cursor.lastrowid
        finally:
            conn.close()

        return validate_response(
            make_success_response(
                message="Archivo subido exitosamente",
                data={"id": file_id, "filename": filename},
                usage=zero_usage(),
            )
        )
    except Exception as exc:
        logger.exception("Error subiendo archivo de contexto")
        return make_error_response(message=str(exc))


@router.get("")
async def list_context_files():
    """List all uploaded context files.

    Returns basic info (id, filename, created_at) without the full content
    to keep the response lightweight.

    Returns:
        A contract response with ``data`` containing a ``files`` array.
    """
    try:
        conn = _get_connection()
        try:
            rows = conn.execute(
                "SELECT id, filename, created_at FROM context_files ORDER BY created_at DESC"
            ).fetchall()
        finally:
            conn.close()

        files = [
            {
                "id": row["id"],
                "filename": row["filename"],
                "created_at": row["created_at"],
            }
            for row in rows
        ]

        return validate_response(
            make_success_response(
                message="Archivos listados",
                data={"files": files},
                usage=zero_usage(),
            )
        )
    except Exception as exc:
        logger.exception("Error listando archivos de contexto")
        return make_error_response(message=str(exc))


@router.delete("/{file_id}")
async def delete_context_file(file_id: int):
    """Delete a context file from SQLite.

    Args:
        file_id: The ID of the file to delete.

    Returns:
        A contract response confirming deletion.
    """
    try:
        conn = _get_connection()
        try:
            cursor = conn.execute(
                "DELETE FROM context_files WHERE id = ?", (file_id,)
            )
            conn.commit()
            deleted = cursor.rowcount
        finally:
            conn.close()

        if deleted == 0:
            return make_error_response(
                message=f"Archivo con id {file_id} no encontrado.",
            )

        return validate_response(
            make_success_response(
                message="Archivo eliminado",
                data={"id": file_id},
                usage=zero_usage(),
            )
        )
    except Exception as exc:
        logger.exception("Error eliminando archivo de contexto")
        return make_error_response(message=str(exc))
