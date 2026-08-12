"""Telegram bot: polling bridge that emits events to the event bus.

The bot does NOT run the agent loop. When a message arrives it publishes a
``telegram_message`` event (with the resolved ``session_id``) to the event
bus; the frontend receives it through ``/api/events`` and runs the normal
chat flow (``chatService.sendMessage`` -> ``POST /api/chat``). When the
backend finishes that request it calls ``send_message`` to deliver the final
answer back to Telegram.

The bot also handles a set of commands directly (``/sesiones``, ``/usar``,
``/actual``, ``/contexto``, ``/borrar``, ``/proveedor``, ``/modelo``,
``/skills``, ``/tools``, ``/agentes``, ``/ayuda``, ``/cancelar``). Commands
that need a user reply (``/usar``, ``/borrar``, ``/proveedor``, ``/modelo``)
use a per-chat "awaiting" state: the bot asks a question and the next plain
message is treated as the answer. ``/cancelar`` (or the word "cancelar")
aborts any pending question.
"""

from __future__ import annotations

import asyncio
import io
import json
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
        allowed_chat_ids: set[int] | None = None,
    ) -> None:
        self.token = token
        self.session_manager = session_manager
        self.allowed_chat_ids = allowed_chat_ids if allowed_chat_ids is not None else set()
        # chat_id -> current session_id (set via /nueva, /usar, /borrar)
        self._session: dict[int, str | None] = {}
        # chat_id -> command awaiting a user reply ("usar", "borrar", ...)
        self._awaiting: dict[int, str] = {}
        self._offset = 0
        self._running = False
        self._task: asyncio.Task | None = None
        self._enabled = False
        self._client = httpx.AsyncClient(timeout=30.0)
        self._whisper_model = None
        self.mode = os.getenv("MODE", os.getenv("VITE_MODE", "dev")).strip().lower()
        self.is_dev = self.mode == "dev"
        # Mode state for skill/RAG creation via Telegram (remote control).
        # chat_id -> "skill" | "rag"
        self._mode: dict[int, str] = {}
        # Per-chat mode data (skill: descripcion/name/mensajes; rag: collection).
        self._mode_data: dict[int, dict] = {}
        # Session to restore after the mode ends.
        self._prev_session: dict[int, str | None] = {}

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

        if updates:
            for u in updates:
                msg = u.get("message") or u.get("edited_message") or {}
                chat = msg.get("chat", {})

            self._offset = updates[-1]["update_id"] + 1

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


        # Whitelist: only allow configured chat ids.
        if chat_id not in self.allowed_chat_ids:
            logger.warning("Telegram update from unauthorized chat_id=%s ignored", chat_id)
            return

        # File attachment (document / photo) -> process like the backend does.
        if message.get("document") or message.get("photo"):
            await self._handle_attachment(chat_id, message)
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

        # "cancelar" aborts any pending question or exits a skill/RAG mode.
        if text.strip().lower() == "cancelar":
            if chat_id in self._mode:
                await self._exit_mode(chat_id, "Cancelado.")
                return
            if chat_id in self._awaiting:
                self._awaiting.pop(chat_id, None)
                await self.send_message(chat_id, "Cancelado.")
            return

        # "terminar" closes the current skill/RAG creation window.
        if text.strip().lower() == "terminar":
            if chat_id in self._mode:
                await self._exit_mode(chat_id, "Listo. Ventana cerrada.")
            else:
                await self.send_message(chat_id, "No hay ninguna creación en curso.")
            return

        # If in a skill/RAG mode, route the message to the mode handler.
        if chat_id in self._mode:
            await self._handle_mode_message(chat_id, text)
            return

        # If a command is awaiting a reply, treat this message as the answer.
        if chat_id in self._awaiting:
            await self._process_awaiting(chat_id, text)
            return

        if text.startswith("/"):
            await self._handle_command(chat_id, text)
            return

        # Detect skill/RAG creation intent (Telegram as remote control).
        intent = self._detect_intent(text)
        if intent:
            await self._enter_mode(chat_id, intent, text)
            return

        # Normal message -> emit to the frontend. The frontend decides the
        # session: it continues the currently active session (the one the user
        # has open in the web UI) instead of creating a new one. Only the
        # /nueva command starts a fresh conversation.

        await event_bus.emit({
            "type": "telegram_message",
            "content": text,
            "session_id": self._active_session(chat_id),
            "chat_id": chat_id,
        })

    # ------------------------------------------------------------------
    # Commands
    # ------------------------------------------------------------------

    async def _handle_command(self, chat_id: int, text: str) -> None:
        parts = text.split()
        cmd = parts[0].lower()
        arg = " ".join(parts[1:]) if len(parts) > 1 else ""


        if cmd == "/nueva":
            self._session[chat_id] = None
            try:
                self.session_manager.set_config("active_session", "")
            except Exception as exc:
                logger.warning("No se pudo limpiar la sesión activa: %s", exc)

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
        elif cmd == "/sesiones":
            await self._cmd_sesiones(chat_id)
        elif cmd == "/usar":
            await self._cmd_usar(chat_id)
        elif cmd == "/cancelar":
            self._awaiting.pop(chat_id, None)
            await self.send_message(chat_id, "Cancelado.")
        elif cmd == "/actual":
            await self._cmd_actual(chat_id)
        elif cmd == "/contexto":
            await self._cmd_contexto(chat_id)
        elif cmd == "/borrar":
            await self._cmd_borrar(chat_id)
        elif cmd == "/proveedor":
            await self._cmd_proveedor(chat_id)
        elif cmd == "/modelo":
            await self._cmd_modelo(chat_id)
        elif cmd == "/skills":
            await self._cmd_skills(chat_id)
        elif cmd == "/tools":
            await self._cmd_tools(chat_id)
        elif cmd == "/agentes":
            await self._cmd_agentes(chat_id)
        elif cmd == "/crear":
            await self._cmd_crear(chat_id, arg)
        elif cmd in ("/ayuda", "/help"):
            await self._cmd_ayuda(chat_id)
        else:
            await self.send_message(chat_id, f"Comando desconocido: {cmd}")

    async def _process_awaiting(self, chat_id: int, text: str) -> None:
        """Process a reply given while a command is awaiting an argument."""
        cmd = self._awaiting.pop(chat_id, None)
        if not cmd:
            return

        if text.strip().lower() == "cancelar":
            await self.send_message(chat_id, "Cancelado.")
            return
        if cmd == "usar":
            await self._cmd_usar(chat_id, text)
        elif cmd == "borrar":
            await self._cmd_borrar(chat_id, text)
        elif cmd == "proveedor":
            await self._cmd_proveedor(chat_id, text)
        elif cmd == "modelo":
            await self._cmd_modelo(chat_id, text)
        elif cmd == "crear":
            await self._cmd_crear(chat_id, text)

    # ------------------------------------------------------------------
    # Skill / RAG creation modes (Telegram as remote control)
    # ------------------------------------------------------------------

    def _detect_intent(self, text: str) -> str | None:
        """Detect whether a message asks to create a skill or a RAG collection.

        Args:
            text: The incoming message text.

        Returns:
            ``"skill"``, ``"rag"`` or ``None`` if no creation intent is found.
        """
        t = text.strip().lower()
        if "crear skill" in t or "crear una skill" in t or "crear la skill" in t:
            return "skill"
        if (
            "crear rag" in t
            or "crear un rag" in t
            or "crear colección" in t
            or "crear coleccion" in t
            or "crear una colección" in t
            or "crear una coleccion" in t
        ):
            return "rag"
        return None

    def _extract_skill_descripcion(self, text: str) -> str | None:
        """Extract the skill description that follows 'crear skill'.

        Args:
            text: The full message text.

        Returns:
            The description, or ``None`` if nothing follows the trigger.
        """
        t = text.strip()
        lower = t.lower()
        for marker in ("crear skill", "crear una skill", "crear la skill"):
            idx = lower.find(marker)
            if idx != -1:
                desc = t[idx + len(marker):].strip()
                return desc or None
        return None

    async def _enter_mode(self, chat_id: int, intent: str, text: str) -> None:
        """Enter a skill or RAG creation mode for a chat.

        Saves the current session so it can be restored when the mode ends.

        Args:
            chat_id: The Telegram chat id.
            intent: ``"skill"`` or ``"rag"``.
            text: The triggering message text.
        """
        self._prev_session[chat_id] = self._active_session(chat_id)
        if intent == "skill":
            descripcion = self._extract_skill_descripcion(text)
            self._mode[chat_id] = "skill"
            self._mode_data[chat_id] = {
                "descripcion": descripcion,
                "name": None,
                "mensajes": [],
            }
            await self._emit_create_window(chat_id, intent, "open")
            if not descripcion:
                await self.send_message(
                    chat_id, "¿Qué skill querés crear? Describí la tarea (o /cancelar)."
                )
                return
            await self._run_skill_iteration(chat_id)
        elif intent == "rag":
            self._mode[chat_id] = "rag"
            self._mode_data[chat_id] = {"collection": None}
            await self._emit_create_window(chat_id, intent, "open")
            await self.send_message(
                chat_id, "¿Nombre de la colección? (o /cancelar)"
            )

    async def _handle_mode_message(self, chat_id: int, text: str) -> None:
        """Route a message while a skill/RAG mode is active.

        Args:
            chat_id: The Telegram chat id.
            text: The message text.
        """
        mode = self._mode.get(chat_id)
        data = self._mode_data.get(chat_id, {})
        if mode == "skill":
            if not data.get("descripcion"):
                data["descripcion"] = text.strip()
                await self._run_skill_iteration(chat_id)
                return
            data["mensajes"] = data.get("mensajes", []) + [
                {"role": "user", "content": text}
            ]
            await self._run_skill_iteration(chat_id)
        elif mode == "rag":
            if data.get("awaiting_finish"):
                await self._handle_rag_finish(chat_id, text.strip())
            elif not data.get("collection"):
                await self._create_rag_collection(chat_id, text.strip())
            else:
                await self._handle_rag_url(chat_id, text.strip())

    async def _run_skill_iteration(self, chat_id: int) -> None:
        """Run one skill-creation iteration against the /api/create/skill route.

        Streams the SSE response and either asks the next question (staying in
        the mode) or finishes the skill (exiting the mode).

        Args:
            chat_id: The Telegram chat id.
        """
        data = self._mode_data.get(chat_id, {})
        descripcion = data.get("descripcion")
        if not descripcion:
            return
        mensajes = data.get("mensajes", [])
        try:
            from backend.routes.create import CreateSkillRequest, post_create_skill_stream

            resp = await post_create_skill_stream(
                CreateSkillRequest(
                    descripcion=descripcion,
                    name=data.get("name"),
                    mensajes=mensajes,
                )
            )
            accumulated = ""
            async for raw in resp.body_iterator:
                for event in self._parse_sse(raw):
                    etype = event.get("type")
                    if etype == "chunk":
                        accumulated += event.get("content", "")
                    elif etype == "skill_action":
                        action = (event.get("content") or {}).get("action")
                        if action == "question":
                            question = (event.get("content") or {}).get("question", "")
                            if accumulated.strip():
                                mensajes.append(
                                    {"role": "assistant", "content": accumulated}
                                )
                            data["mensajes"] = mensajes
                            await self.send_message(
                                chat_id, question or accumulated or "Continuá."
                            )
                            return
                    elif etype == "skill_result":
                        content = event.get("content") or {}
                        if content.get("status") == "success":
                            await self.send_message(
                                chat_id,
                                content.get("message", "Skill creada exitosamente."),
                            )
                        else:
                            await self.send_message(
                                chat_id,
                                "Error: "
                                + (content.get("message") or "Error desconocido"),
                            )
                        await self._exit_mode(chat_id)
                        return
                    elif etype == "error":
                        await self.send_message(
                            chat_id, event.get("content") or "Error al crear la skill."
                        )
                        await self._exit_mode(chat_id)
                        return
        except Exception as exc:
            logger.warning("Error en skill iteration: %s", exc)
            await self.send_message(chat_id, "Error al comunicarse con el backend.")
            await self._exit_mode(chat_id)

    async def _create_rag_collection(self, chat_id: int, name: str) -> None:
        """Create a RAG collection via the /api/rag/collections route.

        Args:
            chat_id: The Telegram chat id.
            name: The collection name.
        """
        try:
            from backend.routes.rag import CreateCollectionRequest, create_collection

            result = await create_collection(
                CreateCollectionRequest(name=name, description="")
            )
            if result.get("status") == "success":
                self._mode_data[chat_id]["collection"] = name
                self._mode_data[chat_id]["awaiting_finish"] = True
                await self.send_message(
                    chat_id,
                    f"Colección '{name}' creada. ¿Querés terminar? (sí/no)",
                )
            else:
                await self.send_message(
                    chat_id, result.get("message") or "No se pudo crear la colección."
                )
                # Stay in mode: the next message is another name attempt (or
                # /cancelar) instead of going to the general session.
        except Exception as exc:
            logger.warning("Error creando colección: %s", exc)
            await self.send_message(chat_id, "Error al crear la colección.")
            await self._exit_mode(chat_id)

    async def _handle_rag_url(self, chat_id: int, url: str) -> None:
        """Add a URL to the active RAG collection via the /api/rag route.

        Args:
            chat_id: The Telegram chat id.
            url: The URL to add.
        """
        name = self._mode_data.get(chat_id, {}).get("collection")
        if not name:
            return
        try:
            from backend.routes.rag import AddUrlRequest, add_url

            result = await add_url(name, AddUrlRequest(url=url))
            if result.get("status") == "success":
                self._mode_data[chat_id]["awaiting_finish"] = True
                await self.send_message(
                    chat_id,
                    f"{result.get('message') or f'Página agregada a {name!r}.'} ¿Querés terminar? (sí/no)",
                )
            else:
                await self.send_message(
                    chat_id, result.get("message") or "No se pudo agregar la URL."
                )
        except Exception as exc:
            logger.warning("Error agregando URL: %s", exc)
            await self.send_message(chat_id, "Error al agregar la URL.")

    async def _handle_rag_upload(
        self, chat_id: int, filename: str, content: bytes
    ) -> None:
        """Upload a file to the active RAG collection via the /api/rag route.

        Args:
            chat_id: The Telegram chat id.
            filename: The file name.
            content: The file bytes.
        """
        name = self._mode_data.get(chat_id, {}).get("collection")
        if not name:
            return
        try:
            from fastapi import UploadFile
            from backend.routes.rag import upload_files

            result = await upload_files(
                name, [UploadFile(filename=filename, file=io.BytesIO(content))]
            )
            if result.get("status") == "success":
                self._mode_data[chat_id]["awaiting_finish"] = True
                await self.send_message(
                    chat_id,
                    f"{result.get('message') or f'Archivo procesado en {name!r}.'} ¿Querés terminar? (sí/no)",
                )
            else:
                await self.send_message(
                    chat_id, result.get("message") or "No se pudo procesar el archivo."
                )
        except Exception as exc:
            logger.warning("Error subiendo archivo: %s", exc)
            await self.send_message(chat_id, "Error al subir el archivo.")

    async def _handle_rag_finish(self, chat_id: int, text: str) -> None:
        """Handle the "¿Querés terminar?" reply in RAG mode.

        Args:
            chat_id: The Telegram chat id.
            text: The user reply (sí/no).
        """
        t = text.strip().lower()
        if t in ("si", "sí", "yes", "y"):
            await self._exit_mode(chat_id, "Listo. Ventana de RAG cerrada.")
        elif t in ("no", "n"):
            self._mode_data[chat_id]["awaiting_finish"] = False
            await self.send_message(chat_id, "Subí archivos o URLs, o /cancelar.")
        else:
            await self.send_message(chat_id, "Respondé sí o no, o /cancelar.")

    async def _exit_mode(self, chat_id: int, message: str | None = None) -> None:
        """Exit a skill/RAG mode and restore the previous session.

        Args:
            chat_id: The Telegram chat id.
            message: Optional message to send after exiting.
        """
        kind = self._mode.get(chat_id)
        self._mode.pop(chat_id, None)
        self._mode_data.pop(chat_id, None)
        prev = self._prev_session.pop(chat_id, None)
        if prev:
            try:
                self.session_manager.set_config("active_session", prev)
            except Exception as exc:
                logger.warning("No se pudo restaurar la sesión: %s", exc)
        if kind:
            await self._emit_create_window(chat_id, kind, "close")
        if message:
            await self.send_message(chat_id, message)

    async def _emit_create_window(self, chat_id: int, kind: str, action: str) -> None:
        """Emit an event to the frontend to open/close the create window.

        Telegram acts as a remote control ("or"): the same window the user
        would open in the web UI is opened/closed in the frontend.

        Args:
            chat_id: The Telegram chat id.
            kind: ``"skill"`` or ``"rag"``.
            action: ``"open"`` or ``"close"``.
        """
        await event_bus.emit({
            "type": "telegram_create",
            "kind": kind,
            "action": action,
            "chat_id": chat_id,
        })

    @staticmethod
    def _parse_sse(raw: bytes) -> list[dict]:
        """Parse SSE ``data:`` lines from a raw chunk into event dicts.

        Args:
            raw: Raw bytes from the streaming response.

        Returns:
            A list of parsed event dicts.
        """
        events: list[dict] = []
        text = raw.decode("utf-8", errors="ignore")
        for line in text.splitlines():
            if not line.startswith("data: "):
                continue
            payload = line[6:]
            if payload == "[DONE]":
                continue
            try:
                events.append(json.loads(payload))
            except Exception:
                continue
        return events

    # ------------------------------------------------------------------
    # Command handlers
    # ------------------------------------------------------------------

    def _list_sessions(self) -> list[dict]:
        """Return the list of root sessions (most recent first)."""
        try:
            return self.session_manager.list_sessions() or []
        except Exception as exc:
            logger.warning("No se pudieron listar sesiones: %s", exc)
            return []

    def _session_title(self, session_id: str) -> str | None:
        for s in self._list_sessions():
            if s.get("session_id") == session_id:
                return s.get("title") or session_id
        return None

    def _active_session(self, chat_id: int) -> str | None:
        """Return the active session for a chat.

        Prefers the in-memory per-chat session (set via ``/usar``, ``/nueva``,
        ``/borrar``). Falls back to the DB-persisted ``active_session`` so a
        session selected in the frontend is also active in Telegram.
        """
        sid = self._session.get(chat_id)
        if sid:
            return sid
        try:
            return self.session_manager.get_config("active_session")
        except Exception as exc:
            logger.warning("No se pudo leer la sesión activa de la DB: %s", exc)
            return None

    async def _cmd_sesiones(self, chat_id: int) -> None:
        sessions = self._list_sessions()
        if not sessions:
            await self.send_message(chat_id, "No hay sesiones.")
            return
        lines = ["Sesiones:"]
        for s in sessions:
            title = s.get("title") or "Sin título"
            lines.append(f"- {title}")
        await self.send_message(chat_id, "\n".join(lines))

    async def _cmd_usar(self, chat_id: int, title: str | None = None) -> None:
        sessions = self._list_sessions()
        if not sessions:
            await self.send_message(chat_id, "No hay sesiones.")
            return
        if not title:
            self._awaiting[chat_id] = "usar"
            lines = ["¿Qué sesión querés usar? (respondé con el título o 'cancelar')"]
            for s in sessions:
                lines.append(f"- {s.get('title') or 'Sin título'}")
            await self.send_message(chat_id, "\n".join(lines))
            return
        target = next((s for s in sessions if (s.get("title") or "Sin título") == title), None)
        if not target:
            await self.send_message(chat_id, f"No encontré la sesión '{title}'.")
            return
        self._session[chat_id] = target["session_id"]
        try:
            self.session_manager.set_config("active_session", target["session_id"])
        except Exception as exc:
            logger.warning("No se pudo persistir la sesión activa: %s", exc)
        # Notify the frontend so it switches to the selected session.
        await event_bus.emit({
            "type": "telegram_command",
            "command": "usar",
            "session_id": target["session_id"],
            "chat_id": chat_id,
        })
        await self.send_message(chat_id, f"Sesión cambiada a '{target.get('title') or target['session_id']}'.")

    async def _cmd_actual(self, chat_id: int) -> None:
        sid = self._active_session(chat_id)
        if not sid:
            await self.send_message(chat_id, "No hay sesión activa.")
            return
        title = self._session_title(sid)
        await self.send_message(chat_id, f"Sesión actual: {title or sid}")

    async def _cmd_contexto(self, chat_id: int) -> None:
        """Report the context usage of the active session.

        Shows session title, model, model context window, tokens used
        (cumulative ``prompt_tokens`` of the latest assistant message) and
        the percentage of the context window consumed.
        """
        sid = self._active_session(chat_id)
        if not sid:
            await self.send_message(chat_id, "No hay sesión activa.")
            return

        model = None
        context_window = None
        try:
            from backend.instances import agent
            model = agent._resolved_model if agent is not None else None
            context_window = agent._context_window if agent is not None else None
        except Exception as exc:
            logger.warning("No se pudo leer modelo/context window: %s", exc)

        title = self._session_title(sid) or sid

        prompt_tokens = None
        try:
            msgs = self.session_manager.load_messages(sid) or []
            for m in reversed(msgs):
                if m.get("role") == "assistant" and m.get("prompt_tokens"):
                    prompt_tokens = m["prompt_tokens"]
                    break
        except Exception as exc:
            logger.warning("No se pudieron leer los tokens de la sesión: %s", exc)

        percent = (
            round((prompt_tokens / context_window) * 100, 2)
            if (prompt_tokens and context_window)
            else None
        )

        lines = [
            f"Título: {title}",
            f"Modelo: {model or 'desconocido'}",
            f"Ventana de contexto: {context_window if context_window else 'desconocida'} tokens",
            f"Tokens utilizados: {prompt_tokens if prompt_tokens is not None else 'desconocido'}",
            f"Porcentaje: {percent if percent is not None else 'desconocido'}%",
        ]
        await self.send_message(chat_id, "\n".join(lines))

    async def _cmd_borrar(self, chat_id: int, title: str | None = None) -> None:
        sessions = self._list_sessions()
        if not sessions:
            await self.send_message(chat_id, "No hay sesiones.")
            return
        if not title:
            self._awaiting[chat_id] = "borrar"
            lines = ["¿Qué sesión querés borrar? (respondé con el título o 'cancelar')"]
            for s in sessions:
                lines.append(f"- {s.get('title') or 'Sin título'}")
            await self.send_message(chat_id, "\n".join(lines))
            return
        target = next((s for s in sessions if (s.get("title") or "Sin título") == title), None)
        if not target:
            await self.send_message(chat_id, f"No encontré la sesión '{title}'.")
            return
        try:
            self.session_manager.delete_session(target["session_id"])
        except Exception as exc:
            logger.warning("No se pudo borrar la sesión: %s", exc)
            await self.send_message(chat_id, f"No se pudo borrar la sesión '{title}'.")
            return
        if self._session.get(chat_id) == target["session_id"]:
            self._session[chat_id] = None
        # Notify the frontend so the sidebar refreshes after the deletion.
        await event_bus.emit({
            "type": "telegram_command",
            "command": "borrar",
            "chat_id": chat_id,
        })
        await self.send_message(chat_id, f"Sesión '{title}' borrada.")

    async def _cmd_proveedor(self, chat_id: int, provider: str | None = None) -> None:
        if not provider:
            self._awaiting[chat_id] = "proveedor"
            await self.send_message(chat_id, "¿Qué proveedor? (LOCAL o API, o 'cancelar')")
            return
        provider = provider.strip().upper()
        if provider not in ("LOCAL", "API"):
            await self.send_message(chat_id, "Proveedor inválido. Usá LOCAL o API.")
            return
        try:
            from backend.instances import agent
            agent.provider = provider
            self.session_manager.set_config("selected_provider", provider)
        except Exception as exc:
            logger.warning("No se pudo cambiar el proveedor: %s", exc)
            await self.send_message(chat_id, f"No se pudo cambiar el proveedor: {exc}")
            return
        await self.send_message(chat_id, f"Proveedor cambiado a {provider}.")

    async def _cmd_modelo(self, chat_id: int, model: str | None = None) -> None:
        from backend.agent.utils.model_resolver import get_ollama_models, get_groq_models
        try:
            from backend.instances import agent
            provider = (agent.provider or "LOCAL").strip().upper()
        except Exception:
            provider = "LOCAL"
        if provider == "API":
            import os as _os
            models = get_groq_models(_os.getenv("GROQ_API_KEY", "").strip())
        else:
            models = get_ollama_models()
        if not models:
            await self.send_message(chat_id, "No hay modelos disponibles.")
            return
        if not model:
            self._awaiting[chat_id] = "modelo"
            lines = ["¿Qué modelo? (respondé con el número o 'cancelar')"]
            for i, m in enumerate(models, 1):
                lines.append(f"{i}. {m}")
            await self.send_message(chat_id, "\n".join(lines))
            return
        try:
            idx = int(model) - 1
            selected = models[idx] if 0 <= idx < len(models) else None
        except (ValueError, TypeError):
            selected = model if model in models else None
        if not selected:
            await self.send_message(chat_id, f"No encontré el modelo '{model}'.")
            return
        try:
            from backend.instances import agent
            agent._resolved_model = selected
            self.session_manager.set_config("selected_model", selected)
            # Persist the model's context window at the same moment (same
            # helper used by the web UI model selection).
            from backend.routes.config import _detect_and_persist_context_window
            provider = (agent.provider or "LOCAL").strip().upper()
            await asyncio.to_thread(_detect_and_persist_context_window, selected, provider)
        except Exception as exc:
            logger.warning("No se pudo cambiar el modelo: %s", exc)
            await self.send_message(chat_id, f"No se pudo cambiar el modelo: {exc}")
            return
        # Broadcast the model change so the frontend refreshes (Telegram is
        # bidirectional: any persistence path must push the update).
        try:
            await event_bus.emit({
                "type": "model_changed",
                "content": {"model": selected, "provider": provider},
            })
        except Exception as exc:
            logger.warning("No se pudo emitir model_changed: %s", exc)
        await self.send_message(chat_id, f"Modelo cambiado a {selected}.")

    async def _cmd_skills(self, chat_id: int) -> None:
        if not self.is_dev:
            await self.send_message(chat_id, "Disponible solo en modo dev.")
            return
        from backend.agent.utils.agent_helpers import get_skills_list
        skills = get_skills_list()
        if not skills:
            await self.send_message(chat_id, "No hay skills.")
            return
        lines = ["Skills:"]
        for s in skills:
            lines.append(f"- {s.get('name')}: {s.get('description')}")
        await self.send_message(chat_id, "\n".join(lines))

    async def _cmd_tools(self, chat_id: int) -> None:
        if not self.is_dev:
            await self.send_message(chat_id, "Disponible solo en modo dev.")
            return
        from backend.agent.utils.agent_helpers import get_tools_list
        tools = get_tools_list()
        if not tools:
            await self.send_message(chat_id, "No hay tools.")
            return
        lines = ["Tools:"]
        for t in tools:
            lines.append(f"- {t.get('name')}: {t.get('description')}")
        await self.send_message(chat_id, "\n".join(lines))

    async def _cmd_agentes(self, chat_id: int) -> None:
        if not self.is_dev:
            await self.send_message(chat_id, "Disponible solo en modo dev.")
            return
        from backend.agent.utils.agent_helpers import get_agents_list
        agents = get_agents_list()
        if not agents:
            await self.send_message(chat_id, "No hay agentes.")
            return
        lines = ["Agentes:"]
        for a in agents:
            lines.append(f"- {a.get('name')}: {a.get('description')}")
        await self.send_message(chat_id, "\n".join(lines))

    async def _cmd_crear(self, chat_id: int, arg: str) -> None:
        """Handle ``/crear``.

        With an argument (``/crear skill <desc>`` or ``/crear rag``) it enters
        the mode directly. Without arguments it asks what to create and routes
        the reply (or /cancelar).

        Args:
            chat_id: The Telegram chat id.
            arg: The argument after ``/crear``.
        """
        sub = arg.strip().lower()
        if sub.startswith("skill"):
            desc = arg.strip()[5:].strip()
            await self._enter_mode(chat_id, "skill", f"crear skill {desc}")
        elif sub.startswith("rag") or sub.startswith("coleccion") or sub.startswith("colección"):
            await self._enter_mode(chat_id, "rag", "crear rag")
        else:
            self._awaiting[chat_id] = "crear"
            await self.send_message(
                chat_id, "¿Qué querés crear? (skill o rag, o /cancelar)"
            )

    async def _cmd_ayuda(self, chat_id: int) -> None:
        help_text = (
            "Comandos:\n"
            "/sesiones - Listar sesiones\n"
            "/usar - Cambiar a una sesión\n"
            "/cancelar - Cancelar comando en espera\n"
            "/nueva - Crear chat nuevo\n"
            "/actual - Mostrar sesión actual\n"
            "/contexto - Ver uso de ventana de contexto\n"
            "/borrar - Borrar un chat\n"
            "/detener - Detener tarea en curso\n"
            "/proveedor - Cambiar proveedor\n"
            "/modelo - Cambiar modelo\n"
            "/skills - Ver skills (dev)\n"
            "/tools - Ver tools (dev)\n"
            "/agentes - Ver agentes (dev)\n"
            "/crear - Crear skill o colección RAG (dev)\n"
            "/ayuda - Mostrar ayuda"
        )
        await self.send_message(chat_id, help_text)

    # ------------------------------------------------------------------
    # Attachments
    # ------------------------------------------------------------------

    async def _handle_attachment(self, chat_id: int, message: dict) -> None:
        """Download a document/photo and process it like the backend does.

        The file is downloaded, its text is extracted with the same
        ``extract_text_from_bytes`` used by the backend, and the result is
        emitted to the frontend as a normal message so the agent processes it.
        """
        document = message.get("document")
        photo = message.get("photo")
        caption = message.get("caption") or ""
        file_id = None
        filename = None
        if document:
            file_id = document.get("file_id")
            filename = document.get("file_name") or "archivo"
        elif photo:
            largest = photo[-1] if isinstance(photo, list) and photo else photo
            file_id = largest.get("file_id")
            filename = "foto.jpg"
        if not file_id:
            return
        try:
            content = await self._download_file(file_id)
        except Exception as exc:
            logger.warning("No se pudo descargar el archivo: %s", exc)
            await self.send_message(chat_id, f"No pude descargar el archivo: {exc}")
            return

        # If in RAG mode, upload the file to the collection instead of
        # emitting it to the frontend.
        if chat_id in self._mode and self._mode[chat_id] == "rag":
            await self._handle_rag_upload(chat_id, filename, content)
            return

        from backend.routes.file_text_extractor import extract_text_from_bytes
        result = extract_text_from_bytes(filename, content)
        if not result.success:
            await self.send_message(chat_id, result.text or "No se pudo procesar el archivo.")
            return
        text = result.text.strip()
        if not text:
            await self.send_message(chat_id, "No se encontró texto en el archivo.")
            return

        full = f"{caption}\n\n**Archivo: {filename}**\n{text}".strip()

        await event_bus.emit({
            "type": "telegram_message",
            "content": full,
            "session_id": self._session.get(chat_id),
            "chat_id": chat_id,
        })

    # ------------------------------------------------------------------
    # Telegram API helpers
    # ------------------------------------------------------------------

    async def send_message(self, chat_id: int, text: str) -> None:
        """Send a text message to a chat (used for the final answer)."""
        if not text:
            return

        url = _TELEGRAM_API.format(token=self.token) + "/sendMessage"
        try:
            resp = await self._client.post(url, json={"chat_id": chat_id, "text": text})
            

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