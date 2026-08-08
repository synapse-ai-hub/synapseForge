"""In-process async event bus that fans out events to SSE subscribers.

The Telegram bot publishes events (e.g. ``telegram_message``,
``telegram_command``) here and the frontend consumes them through the
``/api/events`` SSE endpoint. This keeps the bot decoupled from the HTTP
layer: it only emits, it never renders or re-streams agent events.
"""

from __future__ import annotations

import asyncio
import logging

logger = logging.getLogger(__name__)


class EventBus:
    """Simple fan-out bus backed by one ``asyncio.Queue`` per subscriber."""

    def __init__(self) -> None:
        self._subscribers: set[asyncio.Queue] = set()
        self._lock = asyncio.Lock()

    async def subscribe(self) -> asyncio.Queue:
        """Register a new subscriber and return its queue."""
        q: asyncio.Queue = asyncio.Queue(maxsize=200)
        async with self._lock:
            self._subscribers.add(q)
        return q

    async def unsubscribe(self, q: asyncio.Queue) -> None:
        """Remove a subscriber queue (client disconnected)."""
        async with self._lock:
            self._subscribers.discard(q)

    async def emit(self, event: dict) -> None:
        """Publish an event to every subscriber (non-blocking, drop-oldest)."""
        async with self._lock:
            subs = list(self._subscribers)
        print(f"[DEBUG fantasma] event_bus.emit type={event.get('type')} n_subs={len(subs)} event={event}")
        for q in subs:
            try:
                q.put_nowait(event)
            except asyncio.QueueFull:
                # Keep the stream alive: drop the oldest event for this client.
                try:
                    q.get_nowait()
                    q.put_nowait(event)
                except Exception:
                    pass


# Module-level singleton used by the bot and the SSE endpoint.
event_bus = EventBus()
