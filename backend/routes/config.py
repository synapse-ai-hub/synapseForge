"""Configuration endpoints for the agent loop.

Provides endpoints to:
- Get/set the context window (max turns to keep in context).
- List available models per provider and select one.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import sys
import traceback
from typing import Any

from fastapi import APIRouter
from fastapi.responses import JSONResponse

# ---------------------------------------------------------------------------
# Ensure the project root is in sys.path so absolute imports (backend.*)
# resolve correctly regardless of how the file is invoked.
# ---------------------------------------------------------------------------
_current_dir = os.path.dirname(os.path.abspath(__file__))
_project_root = os.path.dirname(os.path.dirname(_current_dir))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from backend.instances import agent, session_manager
from backend.agent.utils.model_resolver import (
    get_groq_models,
    get_ollama_models,
    get_groq_context_window,
    get_ollama_context_window,
    get_vram_gb,
    ollama_default_context,
)
from backend.agent.utils.error_logger import log_error
from backend.agent.utils.agent_helpers import get_skills_list, get_tools_list, get_agents_list, get_mcp_list

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/config", tags=["config"])

# ---------------------------------------------------------------------------
# Runtime config — defaults applied if the user never calls POST.
# ---------------------------------------------------------------------------

_context_window_turns: int = -1
"""Number of turns to keep in context.  ``-1`` = all.  Set via
``POST /config/context-window``."""

_context_window_tokens: int | None = None
"""Context window (tokens) of the selected model. Detected at model
selection (Ollama ``/api/show`` / Groq ``/models``) and persisted in
``config_kv`` as ``selected_model_context_window``."""

_verbose_mode: bool = False
"""Whether verbose mode (show tool / sub-agent cards) is enabled.
Set via ``POST /config/verbose-mode``."""


_LOCAL_DEFAULT_MODEL = "qwen3.5:4b"
"""Default model for the LOCAL (Ollama) provider.

Used only on first initialization (when no model is persisted yet). Once a
model is selected it is stored in the SQLite config and used from there.
"""


def _default_model_for_provider(provider: str, models: list[str]) -> str | None:
    """Return the default model for the given provider.

    - ``LOCAL`` (Ollama): ``qwen3.5:4b`` if present in the ``ollama list``
      output (it accepts tools); otherwise falls back to the first model.
    - ``API`` (Groq): first available model from the Groq model list,
      avoiding a hard-coded model if the API returns real choices.

    Args:
        provider: ``"LOCAL"`` or ``"API"``.
        models: The list of models already resolved for that provider.

    Returns:
        The default model string, or ``None`` if no models are available.
    """
    if not models:
        return None
    if provider == "LOCAL" and _LOCAL_DEFAULT_MODEL in models:
        return _LOCAL_DEFAULT_MODEL
    return models[0]


def _detect_and_persist_context_window(model: str, provider: str) -> int | None:
    """Resolve the model's context window, cache it and persist it in one place.

    Single source of truth for context-window detection. Every code path that
    sets the active model (first-startup default resolution, user model
    selection, background startup fix) calls this so ``selected_model`` and
    ``selected_model_context_window`` are always persisted together.

    Args:
        model: The model name/ID.
        provider: ``"LOCAL"`` or ``"API"``.

    Returns:
        The context window in tokens, or ``None`` if it cannot be resolved.
    """
    global _context_window_tokens
    cw = None
    try:
        if provider == "LOCAL":
            cw = get_ollama_context_window(model)
        else:
            cw = get_groq_context_window(model, os.getenv("GROQ_API_KEY", "").strip())
    except Exception as exc:
        log_error(str(exc), source="backend/routes/config.py:_detect_and_persist_context_window")
        logger.warning("No se pudo detectar la context window de %s: %s", model, exc)
        return None
    if cw:
        _context_window_tokens = cw
        if agent is not None:
            agent._context_window = cw
        if session_manager is not None:
            session_manager.set_config("selected_model_context_window", str(cw))
        logger.info("Context window for %s: %d tokens", model, cw)
    else:
        logger.warning("No se pudo detectar la context window de %s", model)
    return cw


@router.get("/context-window")
async def get_context_window() -> JSONResponse:
    """Return the current context-window turn limit (``-1`` = all)."""
    vram = get_vram_gb()
    print(f"[DEBUG] get_context_window: max_turns={_context_window_turns}, context_window_tokens={_context_window_tokens}, vram_gb={vram}")
    return JSONResponse(
        status_code=200,
        content={
            "status": "success",
            "max_turns": _context_window_turns,
            "context_window_tokens": _context_window_tokens,
            "vram_gb": vram,
            "ollama_default_context": ollama_default_context(vram),
        },
    )


@router.post("/context-window")
async def set_context_window(data: dict[str, Any]) -> JSONResponse:
    """Set the context-window turn limit.

    Request body::

        {"max_turns": 10}

    ``-1`` means *all turns*. The value must be ``-1`` or a positive integer.
    """
    try:
        value = int(data.get("max_turns", -1))
    except (ValueError, TypeError) as e:
        log_error(str(e), source="backend/routes/config.py")
        return JSONResponse(
            status_code=400,
            content={
                "status": "error",
                "message": "max_turns must be an integer (-1 = all turns).",
            },
        )

    if value < -1 or value == 0:
        return JSONResponse(
            status_code=400,
            content={
                "status": "error",
                "message": "max_turns must be -1 (all) or a positive integer.",
            },
        )

    global _context_window_turns
    _context_window_turns = value

    try:
        if session_manager is not None:
            session_manager.set_config("context_window_turns", str(value))
    except Exception as exc:
        log_error(str(exc), source="backend/routes/config.py")
        logger.warning("No se pudo persistir la ventana de contexto: %s", exc)

    logger.info("Context window set to %d turns", value)
    return JSONResponse(
        status_code=200,
        content={
            "status": "success",
            "message": f"Context window set to {value} turn(s).",
            "max_turns": value,
        },
    )


# ---------------------------------------------------------------------------
# Verbose mode
# ---------------------------------------------------------------------------


@router.get("/verbose-mode")
async def get_verbose_mode() -> JSONResponse:
    """Return the current verbose-mode flag."""
    return JSONResponse(
        status_code=200,
        content={
            "status": "success",
            "verbose_mode": _verbose_mode,
        },
    )


@router.post("/verbose-mode")
async def set_verbose_mode(data: dict[str, Any]) -> JSONResponse:
    """Set the verbose-mode flag.

    Request body::

        {"verbose_mode": true}
    """
    raw = data.get("verbose_mode", False)
    if not isinstance(raw, bool):
        return JSONResponse(
            status_code=400,
            content={
                "status": "error",
                "message": "verbose_mode must be a boolean.",
            },
        )
    value = raw

    global _verbose_mode
    _verbose_mode = value

    try:
        if session_manager is not None:
            session_manager.set_config("verbose_mode", str(value))
    except Exception as exc:
        log_error(str(exc), source="backend/routes/config.py")
        logger.warning("No se pudo persistir verbose_mode: %s", exc)

    logger.info("Verbose mode set to %s", value)
    return JSONResponse(
        status_code=200,
        content={
            "status": "success",
            "message": f"Verbose mode set to {value}.",
            "verbose_mode": value,
        },
    )


# ---------------------------------------------------------------------------
# Available providers
# ---------------------------------------------------------------------------


@router.get("/providers")
async def list_providers() -> JSONResponse:
    """Return the list of available providers.

    Checks each provider by attempting to list models via the existing
    ``get_groq_models`` / ``get_ollama_models`` functions. Providers whose
    model list returns empty are excluded so the frontend knows not to show
    them in the dropdown.

    This endpoint is intended to be called **once** when the frontend app
    starts.  If a provider becomes available later (e.g. Ollama is restarted),
    the user must restart the app — no live polling is performed.
    """
    from dotenv import load_dotenv
    load_dotenv()

    available: list[dict[str, str]] = []

    # Ollama — try ``ollama list``
    ollama_models = await asyncio.to_thread(get_ollama_models)
    if ollama_models:
        available.append({"provider": "LOCAL", "label": "Ollama (local)"})

    # Groq — try the API
    api_key = os.getenv("GROQ_API_KEY", "").strip()
    if api_key:
        groq_models = await asyncio.to_thread(get_groq_models, api_key)
        if groq_models:
            available.append({"provider": "API", "label": "Groq (API)"})

    return JSONResponse(
        status_code=200,
        content={
            "status": "success",
            "providers": available,
        },
    )


# ---------------------------------------------------------------------------
# Model selection
# ---------------------------------------------------------------------------


def _effective_provider(provider: str | None = None) -> str:
    """Return the effective provider, using query param, persisted config, or env default."""
    from dotenv import load_dotenv

    load_dotenv()
    if provider:
        return provider.strip().upper()

    if session_manager is not None:
        try:
            persisted = session_manager.get_config("selected_provider")
            if persisted:
                return persisted.strip().upper()
        except Exception as exc:
            log_error(str(exc), source="backend/routes/config.py")
            logger.warning("No se pudo leer el proveedor persistido: %s", exc)

    return (os.getenv("PROVIDER", "LOCAL") or "LOCAL").strip().upper()


@router.get("/models")
async def list_models(provider: str | None = None) -> JSONResponse:
    """List available models for the current provider.

    Uses the explicit ``provider`` query param if supplied. Otherwise it uses
    the selected provider from persisted config or the ``PROVIDER`` env
    variable.

    - ``LOCAL`` → runs ``ollama list``.
    - ``API`` → queries the Groq API.

    If no model has been selected yet, resolves and stores the provider-
    appropriate default from the available model list.

    Returns the list of model IDs/names and the selected (or default) model.
    """
    from dotenv import load_dotenv

    provider = _effective_provider(provider)
    load_dotenv()

    if provider == "LOCAL":
        models = await asyncio.to_thread(get_ollama_models)
        provider_label = "Ollama (local)"
    elif provider == "API":
        api_key = os.getenv("GROQ_API_KEY", "").strip()
        models = await asyncio.to_thread(get_groq_models, api_key)
        provider_label = "Groq (API)"
    else:
        return JSONResponse(
            status_code=400,
            content={
                "status": "error",
                "message": f"Unknown PROVIDER: '{provider}'. Use 'API' or 'LOCAL'.",
            },
        )

    previous_provider = agent.provider if agent is not None else None
    if agent is not None and agent.provider != provider:
        agent.provider = provider

    selected_model = None
    if agent is not None and previous_provider == provider:
        selected_model = agent._resolved_model

    if selected_model is None:
        default = _default_model_for_provider(provider, models)
        if default is not None and agent is not None:
            agent._resolved_model = default
            selected_model = default
            try:
                if session_manager is not None:
                    session_manager.set_config("selected_model", default)
                    session_manager.set_config("selected_provider", provider)
            except Exception as exc:
                log_error(str(exc), source="backend/routes/config.py")
                logger.warning("No se pudo persistir modelo/proveedor por defecto: %s", exc)
            # Persist the model's context window at the same moment the model is
            # persisted (first startup with no DB).
            await asyncio.to_thread(_detect_and_persist_context_window, default, provider)

    if agent is not None and session_manager is not None:
        try:
            session_manager.set_config("selected_provider", provider)
        except Exception as exc:
            log_error(str(exc), source="backend/routes/config.py")
            logger.warning("No se pudo persistir proveedor seleccionado: %s", exc)

    return JSONResponse(
        status_code=200,
        content={
            "status": "success",
            "provider": provider,
            "provider_label": provider_label,
            "models": models,
            "model": agent._resolved_model if agent is not None else None,
        },
    )


@router.post("/models/select")
async def select_model(data: dict[str, Any]) -> JSONResponse:
    """Select a model and provider for the current session.

    Request body::

        {"model": "llama3.2", "provider": "LOCAL"}

    The selection is stored in the agent singleton and persisted in SQLite.
    """
    model = data.get("model", "").strip()
    provider = data.get("provider", "").strip().upper()

    if not model:
        return JSONResponse(
            status_code=400,
            content={
                "status": "error",
                "message": "model is required.",
            },
        )

    if provider not in {"LOCAL", "API"}:
        return JSONResponse(
            status_code=400,
            content={
                "status": "error",
                "message": "provider must be 'LOCAL' or 'API'.",
            },
        )

    if agent is None:
        return JSONResponse(
            status_code=503,
            content={
                "status": "error",
                "message": "Agent not initialised.",
            },
        )

    # Liberar modelo anterior si es LOCAL (Ollama) y cambió
    modelo_anterior = agent._resolved_model
    if modelo_anterior and modelo_anterior != model and agent.provider == "LOCAL":
        try:
            from backend.agent.utils.clean_memory import liberar_modelo
            await asyncio.to_thread(liberar_modelo, modelo_anterior)
            logger.info("Modelo anterior liberado: %s", modelo_anterior)
        except Exception as exc:
            log_error(str(exc), source="backend/routes/config.py:select_model")
            logger.warning("No se pudo liberar modelo anterior %s: %s", modelo_anterior, exc)

    agent._resolved_model = model
    agent.provider = provider

    try:
        if session_manager is not None:
            session_manager.set_config("selected_model", model)
            session_manager.set_config("selected_provider", provider)
    except Exception as exc:
        log_error(str(exc), source="backend/routes/config.py")
        logger.warning("No se pudo persistir el modelo o proveedor seleccionado: %s", exc)

    # Detect and persist the model's context window (tokens) — same helper used
    # by the first-startup default resolution, so both are always persisted
    # together.
    await asyncio.to_thread(_detect_and_persist_context_window, model, provider)

    logger.info("Model selected: %s (%s)", model, provider)
    return JSONResponse(
        status_code=200,
        content={
            "status": "success",
            "message": f"Model '{model}' selected.",
            "model": model,
            "provider": provider,
        },
    )


# ---------------------------------------------------------------------------
# Persisted config loading (SQLite -> in-memory state)
# ---------------------------------------------------------------------------


def load_persisted_config() -> None:
    """Load persisted model and context-window config from SQLite.

    Reads the ``selected_model`` and ``selected_provider`` and
    ``context_window_turns`` keys from the session manager's key-value store
    and applies them to the in-memory state (``agent._resolved_model``, the
    runtime provider, and the module-level ``_context_window_turns`` global).
    Each load is guarded so a failure in one does not prevent the other from
    being applied.
    """
    if session_manager is None:
        return

    try:
        model = session_manager.get_config("selected_model")
        provider = session_manager.get_config("selected_provider")
        if provider and agent is not None:
            agent.provider = provider.strip().upper()
            logger.info("Proveedor persistido cargado desde SQLite: %s", provider)
        if model and agent is not None:
            agent._resolved_model = model
            logger.info("Modelo persistido cargado desde SQLite: %s", model)
    except Exception as exc:
        log_error(str(exc), source="backend/routes/config.py")
        logger.warning("No se pudo cargar el modelo o proveedor persistidos: %s", exc)

    try:
        cw = session_manager.get_config("context_window_turns")
        if cw is not None:
            global _context_window_turns
            _context_window_turns = int(cw)
            logger.info("Ventana de contexto persistida cargada: %s", cw)
    except Exception as exc:
        log_error(str(exc), source="backend/routes/config.py")
        logger.warning("No se pudo cargar la ventana de contexto: %s", exc)

    try:
        cwt = session_manager.get_config("selected_model_context_window")
        if cwt is not None:
            global _context_window_tokens
            _context_window_tokens = int(cwt)
            if agent is not None:
                agent._context_window = _context_window_tokens
            logger.info("Context window de modelo persistida cargada: %s", cwt)
    except Exception as exc:
        log_error(str(exc), source="backend/routes/config.py")
        logger.warning("No se pudo cargar la context window de modelo: %s", exc)

    try:
        vm = session_manager.get_config("verbose_mode")
        if vm is not None:
            global _verbose_mode
            _verbose_mode = vm.lower() == "true"
            logger.info("Verbose mode persistido cargado: %s", _verbose_mode)
    except Exception as exc:
        log_error(str(exc), source="backend/routes/config.py")
        logger.warning("No se pudo cargar verbose_mode: %s", exc)

# Detect VRAM once at startup (it does not change while the app runs).
    # The result is cached in model_resolver, so this is a single query.
    try:
        vram = get_vram_gb()
        print(f"[DEBUG] VRAM detectada al iniciar: {vram} GB")
    except Exception as exc:
        log_error(str(exc), source="backend/routes/config.py:load_persisted_config(vram)")
        print(f"[DEBUG] VRAM no detectada al iniciar: {exc}")


# ---------------------------------------------------------------------------
# AgentInfo endpoints
# ---------------------------------------------------------------------------


@router.get("/skills")
async def list_skills() -> JSONResponse:
    """List available skills (name + description)."""
    try:
        skills = get_skills_list()
        return JSONResponse(
            status_code=200,
            content={"status": "success", "skills": skills},
        )
    except Exception as exc:
        log_error(str(exc), source="backend/routes/config.py:list_skills")
        return JSONResponse(
            status_code=500,
            content={"status": "error", "message": "Error listing skills", "skills": []},
        )


@router.get("/tools")
async def list_tools() -> JSONResponse:
    """List all available tools (native + external) without permission filtering."""
    try:
        tools = get_tools_list()
        return JSONResponse(
            status_code=200,
            content={"status": "success", "tools": tools},
        )
    except Exception as exc:
        log_error(str(exc), source="backend/routes/config.py:list_tools")
        return JSONResponse(
            status_code=500,
            content={"status": "error", "message": "Error listing tools", "tools": []},
        )


@router.get("/agents")
async def list_agents() -> JSONResponse:
    """List available sub-agents (excluding AGENT.md and ROUTER.md)."""
    try:
        agents = get_agents_list()
        return JSONResponse(
            status_code=200,
            content={"status": "success", "agents": agents},
        )
    except Exception as exc:
        log_error(str(exc), source="backend/routes/config.py:list_agents")
        return JSONResponse(
            status_code=500,
            content={"status": "error", "message": "Error listing agents", "agents": []},
        )


@router.get("/mcp")
async def list_mcp_servers() -> JSONResponse:
    """List MCP servers with connection status."""
    try:
        servers = await get_mcp_list()
        return JSONResponse(
            status_code=200,
            content={"status": "success", "servers": servers},
        )
    except Exception as exc:
        log_error(str(exc), source="backend/routes/config.py:list_mcp_servers")
        return JSONResponse(
            status_code=500,
            content={"status": "error", "message": "Error checking MCP servers", "servers": []},
        )
