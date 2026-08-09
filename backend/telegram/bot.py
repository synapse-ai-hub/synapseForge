"""Telegram bot: polling bridge that emits events to the event bus.

The bot does NOT run the agent loop. When a message arrives it publishes a
``telegram_message`` event (with the resolved ``session_id``) to the event
bus; the frontend receives it through ``/api/events`` and runs the normal
chat flow (``chatService.sendMessage`` -> ``POST /api/chat``). When the
backend finishes that request it calls ``send_message`` to deliver the final
answer back to Telegram.

The bot also handles a set of commands directly (``/sesiones``, ``/usar``,
``/actual``, ``/borrar``, ``/proveedor``, ``/modelo``, ``/skills``,
``/tools``, ``/agentes``, ``/ayuda``, ``/cancelar``). Commands that need a
user reply (``/usar``, ``/borrar``, ``/proveedor``, ``/modelo``) use a
per-chat "awaiting" state: the bot asks a question and the next plain message
is treated as the answer. ``/cancelar`` (or the word "cancelar") aborts any
pending question.
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

        # "cancelar" aborts any pending question.
        if text.strip().lower() == "cancelar":
            if chat_id in self._awaiting:
                self._awaiting.pop(chat_id, None)
                await self.send_message(chat_id, "Cancelado.")
            return

        # If a command is awaiting a reply, treat this message as the answer.
        if chat_id in self._awaiting:
            await self._process_awaiting(chat_id, text)
            return

        if text.startswith("/"):
            await self._handle_command(chat_id, text)
            return

        # Normal message -> emit to the frontend. The frontend decides the
        # session: it continues the currently active session (the one the user
        # has open in the web UI) instead of creating a new one. Only the
        # /nueva command starts a fresh conversation.

        await event_bus.emit({
            "type": "telegram_message",
            "content": text,
            "session_id": self._session.get(chat_id),
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
            await self.send_message(chat_id, "El comando /crear no está implementado todavía.")
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
        # Notify the frontend so it switches to the selected session.
        await event_bus.emit({
            "type": "telegram_command",
            "command": "usar",
            "session_id": target["session_id"],
            "chat_id": chat_id,
        })
        await self.send_message(chat_id, f"Sesión cambiada a '{target.get('title') or target['session_id']}'.")

    async def _cmd_actual(self, chat_id: int) -> None:
        sid = self._session.get(chat_id)
        if not sid:
            await self.send_message(chat_id, "No hay sesión activa.")
            return
        title = self._session_title(sid)
        await self.send_message(chat_id, f"Sesión actual: {title or sid}")

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
        except Exception as exc:
            logger.warning("No se pudo cambiar el modelo: %s", exc)
            await self.send_message(chat_id, f"No se pudo cambiar el modelo: {exc}")
            return
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

    async def _cmd_ayuda(self, chat_id: int) -> None:
        help_text = (
            "Comandos:\n"
            "/sesiones - Listar sesiones\n"
            "/usar - Cambiar a una sesión\n"
            "/cancelar - Cancelar comando en espera\n"
            "/nueva - Crear chat nuevo\n"
            "/actual - Mostrar sesión actual\n"
            "/borrar - Borrar un chat\n"
            "/detener - Detener tarea en curso\n"
            "/proveedor - Cambiar proveedor\n"
            "/modelo - Cambiar modelo\n"
            "/skills - Ver skills (dev)\n"
            "/tools - Ver tools (dev)\n"
            "/agentes - Ver agentes (dev)\n"
            "/crear - Crear skill/tool/agente (dev)\n"
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