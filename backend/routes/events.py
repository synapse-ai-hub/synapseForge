"""SSE endpoint that streams events from the event bus to the frontend.

The Telegram bot emits ``telegram_message`` / ``telegram_command`` events
here; the frontend subscribes to this endpoint and reacts to them exactly
as if the user had typed in the web UI.
"""

from __future__ import annotations

import asyncio
import json
import logging

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse

from backend.event_bus import event_bus

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/events")
async def events_endpoint(request: Request) -> StreamingResponse:
    """Stream events from the event bus as Server-Sent Events."""

    q = await event_bus.subscribe()

    async def event_stream():
        try:
            while True:
                if await request.is_disconnected():
                    break
                try:
                    event = await asyncio.wait_for(q.get(), timeout=15.0)
                except asyncio.TimeoutError:
                    # Keep-alive comment so proxies don't close the connection.
                    yield ": keep-alive\n\n"
                    continue

                yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
        finally:
            await event_bus.unsubscribe(q)

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
