"""Chat SSE streaming endpoint for the <descripcion>nombre_proyecto</descripcion>."""

from __future__ import annotations

import asyncio
import json
import logging
import os
import sys
import uuid
from typing import Optional

from fastapi import APIRouter, File, Form, Request, UploadFile
from fastapi.responses import JSONResponse, StreamingResponse

# ---------------------------------------------------------------------------
# Ensure the project root is in sys.path so absolute imports (backend.*)
# resolve correctly regardless of how the file is invoked.
# chat.py is at backend/routes/ -> need 3 dirname() calls to reach root.
# ---------------------------------------------------------------------------
_current_dir = os.path.dirname(os.path.abspath(__file__))
_project_root = os.path.dirname(os.path.dirname(_current_dir))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from backend.agent.loop import AgentLoop
from backend.agent.utils.error_logger import log_error, set_error_context, reset_error_context
from backend.routes.file_text_extractor import (
    ExtractionResult,
    extract_text_from_bytes,
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["chat"])


@router.post("/chat")
async def chat_endpoint(
    request: Request,
    message: str = Form(...),
    session_id: str | None = Form(None),
    stream_id: str | None = Form(None),
    files: Optional[list[UploadFile]] = File(None),
):
    """Stream a conversation turn via Server-Sent Events.

    Accepts the user's message as ``FormData``, optionally with attached
    files, and returns a ``StreamingResponse`` with ``text/event-stream``
    content type.
    """
    # Ensure session_id exists (generate one if not provided)
    if session_id is None or not session_id.strip():
        session_id = uuid.uuid4().hex

    # Process uploaded files (prospectingAgent pattern)
    file_contents: list[tuple[str, str]] = []
    if files:
        for i, file in enumerate(files):
            filename = file.filename or f"archivo_{i + 1}"
            try:
                content = await file.read()
            except Exception as exc:
                log_error(str(exc), source="backend/routes/chat.py:file_read")
                logger.warning("Error reading file %s: %s", filename, exc)
                content = b""
            result: ExtractionResult = extract_text_from_bytes(filename, content)
            if not result.success:
                if result.error_code in ("file_too_large", "unsupported_type", "missing_dependency"):
                    logger.warning(
                        "Skipping file %s (error_code=%s): %s",
                        filename,
                        result.error_code,
                        result.error_detail or "unknown",
                    )
                    continue
                file_contents.append((filename, result.text or f"[Error al procesar {filename}]"))
                continue
            text = (result.text or "").strip()
            if not text:
                file_contents.append(
                    (filename, f"[Error al procesar {filename}: no se encontró texto legible en el archivo.]")
                )
                continue
            file_contents.append((filename, text))

    logger.info("Processing chat request for session_id=%s", session_id)

    # Create a cancellation event tied to the client disconnection
    stream_cancel_event = asyncio.Event()

    async def event_stream():
        # Set error context for this request (inside event_stream so set/reset share same async context)
        error_ctx_token = set_error_context(session_id=session_id, turn_number=0)
        try:
            from backend.instances import agent, session_manager, context_manager

            agent_loop = AgentLoop(
                agent=agent,
                session_manager=session_manager,
                context_manager=context_manager,
            )
            async for sse_event in agent_loop.run(
                session_id=session_id,
                user_message=message,
                file_contents=file_contents,
                stream_cancel_event=stream_cancel_event,
            ):
                # If client disconnected, stop
                if await request.is_disconnected():
                    stream_cancel_event.set()
                    break
                yield sse_event
        except Exception as exc:
            log_error(str(exc), source="backend/routes/chat.py")
            logger.exception("Error in agent loop stream: %s", exc)
            # Yield a terminal error event so the client sees something
            yield f"data: {json.dumps({'type': 'chunk', 'content': 'En este momento no se puede ejecutar la solicitud. Por favor, intentá más tarde.'})}\n\n"
            yield "data: [DONE]\n\n"
        finally:
            reset_error_context(error_ctx_token)

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
