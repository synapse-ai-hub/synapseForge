"""Telegram bot: polling bridge that emits events to the event bus.

The bot does NOT run the agent loop. When a message arrives it publishes a
``telegram_message`` event (with the resolved ``session_id``) to the event
bus; the frontend receives it through ``/api/events`` and runs the normal
chat flow (``chatService.sendMessage`` -> ``POST /api/chat``). When the
backend finishes that request it calls ``send_message`` to deliver the final
answer back to Telegram.
"""

from __future__ import annotations

import asyncio
import io
import logging
import os
import uuid

import httpx

from faster_whisper import WhisperModel

from backend.event_bus import event_bus

logger = logging.getLogger(__name__)

_TELEGRAM_API = "https://api.telegram.org/bot{token}"


class TelegramBot:
    """Minimal Telegram bot using long-polling against the Bot API."""

    def __init__(
        self,
        token: str,
        session_manager,
        chat_id: int | None = None,
        password: str | None = None,
        allowed_chat_ids: set[int] | None = None,
    ) -> None:
        self.token = token
        self.session_manager = session_manager
        self.chat_id = chat_id  # optional authorized chat id
        self.password = password
        self.allowed_chat_ids = allowed_chat_ids if allowed_chat_ids is not None else set()
        self._session: dict[int, str | None] = {}
        self._offset = 0
        self._running = False
        self._task: asyncio.Task | None = None
        self._enabled = False
        self._client = httpx.AsyncClient(timeout=30.0)
        self._whisper_model = None

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    @property
    def enabled(self) -> bool:
        return self._enabled

    def set_enabled(self, value: bool) -> None:
        self._enabled = bool(value)
        logger.info("Telegram enabled=%s", self._enabled)

    async def start(self) -> None:
        self._running = True
        self._task = asyncio.create_task(self._poll_loop())
        logger.info("Telegram bot polling started (enabled=%s).", self._enabled)

    async def stop(self) -> None:
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        await self._client.aclose()

    # ------------------------------------------------------------------
    # Polling
    # ------------------------------------------------------------------

    async def _poll_loop(self) -> None:
        was_enabled = False  # force a sync when the bot becomes enabled (startup or re-enable)
        while self._running:
            if not self._enabled:
                was_enabled = False
                await asyncio.sleep(1)
                continue
            if not was_enabled:
                # Telegram was just enabled (or started enabled): discard any
                # messages that arrived while it was disabled/offline so they
                # are NOT processed. Only messages from the moment of enabling
                # are handled.
                await self._skip_queued_updates()
                was_enabled = True
            try:
                updates = await self._get_updates()
                for update in updates:
                    await self._handle_update(update)
            except Exception as exc:
                logger.warning("Telegram poll error: %s", exc)
            await asyncio.sleep(0.5)

    async def _skip_queued_updates(self) -> None:
        """Advance the poll offset past queued updates without processing them.

        Called when the bot transitions to enabled (startup or re-enable) so
        messages that arrived while Telegram was disabled/offline are discarded
        instead of being replayed. Only updates received after this point are
        handled by the normal polling loop.
        """
        try:
            url = _TELEGRAM_API.format(token=self.token) + "/getUpdates"
            for _ in range(100):  # safety cap (100 rounds * 100 updates)
                resp = await self._client.post(
                    url, json={"timeout": 0, "offset": self._offset}
                )
                data = resp.json()
                if not data.get("ok"):
                    return
                updates = data.get("result", [])
                if not updates:
                    return
                self._offset = updates[-1]["update_id"] + 1
                print(f"[DEBUG fantasma] bot._skip_queued_updates descartados={len(updates)} new_offset={self._offset}")
                if len(updates) < 100:
                    return
        except Exception as exc:
            logger.warning("Failed to skip queued Telegram updates: %s", exc)

    async def _get_updates(self) -> list[dict]:
        url = _TELEGRAM_API.format(token=self.token) + "/getUpdates"
        resp = await self._client.post(url, json={"timeout": 0, "offset": self._offset})
        data = resp.json()
        if not data.get("ok"):
            return []
        updates = data.get("result", [])
        print(f"[DEBUG fantasma] bot._get_updates offset={self._offset} -> {len(updates)} updates")
        if updates:
            for u in updates:
                msg = u.get("message") or u.get("edited_message") or {}
                chat = msg.get("chat", {})
                print(f"[DEBUG fantasma] bot._get_updates update_id={u.get('update_id')} chat_id={chat.get('id')} text={(msg.get('text') or '')[:60]!r}")
            self._offset = updates[-1]["update_id"] + 1
            print(f"[DEBUG fantasma] bot._get_updates new_offset={self._offset}")
        return updates

    # ------------------------------------------------------------------
    # Update handling
    # ------------------------------------------------------------------

    async def _handle_update(self, update: dict) -> None:
        message = update.get("message") or update.get("edited_message")
        if not message:
            return
        chat_id = message["chat"]["id"]
        text = message.get("text") or ""
        voice = message.get("voice")
        audio = message.get("audio")
        caption = message.get("caption") or ""
        print(f"[DEBUG fantasma] bot._handle_update update_id={update.get('update_id')} chat_id={chat_id} text={text[:60]!r}")

        # Whitelist: only allow configured chat ids.
        if chat_id not in self.allowed_chat_ids:
            logger.warning("Telegram update from unauthorized chat_id=%s ignored", chat_id)
            return

        # Voice / audio note -> transcribe locally and use as the message.
        voice_file_id = (voice or {}).get("file_id") or (audio or {}).get("file_id")
        if voice_file_id:
            try:
                content = await self._download_file(voice_file_id)
                transcript = await self._transcribe(content)
                text = f"{caption}\n{transcript}".strip() if caption else transcript
                logger.info("Voice transcribed: %d chars", len(transcript))
            except Exception as exc:
                logger.warning("Failed to transcribe voice: %s", exc)
                await self.send_message(chat_id, "No pude transcribir la nota de voz.")
                return

        if not text:
            return

        if text.startswith("/"):
            await self._handle_command(chat_id, text)
            return

        # Normal message -> emit to the frontend. The frontend decides the
        # session: it continues the currently active session (the one the user
        # has open in the web UI) instead of creating a new one. Only the
        # /nueva command starts a fresh conversation.
        print(f"[DEBUG fantasma] bot._handle_update EMIT telegram_message chat_id={chat_id} session_id=None text={text[:60]!r}")
        await event_bus.emit({
            "type": "telegram_message",
            "content": text,
            "session_id": None,
            "chat_id": chat_id,
        })

    async def _handle_command(self, chat_id: int, text: str) -> None:
        parts = text.split()
        cmd = parts[0].lower()
        arg = " ".join(parts[1:]) if len(parts) > 1 else ""
        print(f"[DEBUG fantasma] bot._handle_command chat_id={chat_id} cmd={cmd} arg={arg[:40]!r}")
        if cmd == "/nueva":
            self._session[chat_id] = None
            print(f"[DEBUG fantasma] bot._handle_command EMIT telegram_command nueva chat_id={chat_id}")
            await event_bus.emit({
                "type": "telegram_command",
                "command": "nueva",
                "chat_id": chat_id,
            })
        elif cmd == "/detener":
            await event_bus.emit({
                "type": "telegram_command",
                "command": "detener",
                "chat_id": chat_id,
            })
        elif cmd == "/help":
            await self.send_message(
                chat_id,
                "Comandos disponibles:\n/nueva — nueva conversación\n/detener — detener la generación\n/help — esta ayuda",
            )
        else:
            await self.send_message(chat_id, f"Comando desconocido: {cmd}")

    # ------------------------------------------------------------------
    # Telegram API helpers
    # ------------------------------------------------------------------

    async def send_message(self, chat_id: int, text: str) -> None:
        """Send a text message to a chat (used for the final answer)."""
        if not text:
            return
        print(f"[DEBUG fantasma] bot.send_message chat_id={chat_id} text={text[:80]!r}")
        url = _TELEGRAM_API.format(token=self.token) + "/sendMessage"
        try:
            await self._client.post(url, json={"chat_id": chat_id, "text": text})
        except Exception as exc:
            logger.warning("Failed to send Telegram message: %s", exc)

    async def _download_file(self, file_id: str) -> bytes:
        url = _TELEGRAM_API.format(token=self.token) + "/getFile"
        resp = await self._client.post(url, json={"file_id": file_id})
        data = resp.json()
        if not data.get("ok"):
            raise RuntimeError("getFile failed")
        file_path = data["result"]["file_path"]
        file_url = f"https://api.telegram.org/file/bot{self.token}/{file_path}"
        resp = await self._client.get(file_url)
        return resp.content

    async def _transcribe(self, content: bytes) -> str:
        """Transcribe audio bytes with faster-whisper (model cached)."""
        if self._whisper_model is None:
            self._whisper_model = WhisperModel("base", device="cpu", compute_type="int8")
        segments, _ = self._whisper_model.transcribe(io.BytesIO(content))
        return "".join(s.text for s in segments).strip()