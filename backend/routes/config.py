"""Configuration endpoints for the agent loop.

Provides endpoints to:
- Get/set the context window (max turns to keep in context).
- List available models per provider and select one.
"""

from __future__ import annotations

import logging
import os
import sys
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
from backend.agent.utils.model_resolver import get_groq_models, get_ollama_models
from backend.agent.utils.error_logger import log_error
from backend.agent.config_dir import get_mcp_config
from backend.agent.utils.mcp_helper import check_all_mcp_servers_health

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/config", tags=["config"])

# ---------------------------------------------------------------------------
# Runtime config — defaults applied if the user never calls POST.
# ---------------------------------------------------------------------------

_context_window_turns: int = -1
"""Number of turns to keep in context.  ``-1`` = all.  Set via
``POST /config/context-window``."""


def _default_model_for_provider(provider: str, models: list[str]) -> str | None:
    """Return the default model for the given provider.

    - ``LOCAL`` (Ollama): first model from the dynamic ``ollama list``
      output.
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
    return models[0]


@router.get("/context-window")
async def get_context_window() -> JSONResponse:
    """Return the current context-window turn limit (``-1`` = all)."""
    return JSONResponse(
        status_code=200,
        content={
            "status": "success",
            "max_turns": _context_window_turns,
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
    except (ValueError, TypeError):
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
    ollama_models = get_ollama_models()
    if ollama_models:
        available.append({"provider": "LOCAL", "label": "Ollama (local)"})

    # Groq — try the API
    api_key = os.getenv("GROQ_API_KEY", "").strip()
    if api_key:
        groq_models = get_groq_models(api_key)
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
        models = get_ollama_models()
        provider_label = "Ollama (local)"
    elif provider == "API":
        api_key = os.getenv("GROQ_API_KEY", "").strip()
        models = get_groq_models(api_key)
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

    agent._resolved_model = model
    agent.provider = provider

    try:
        if session_manager is not None:
            session_manager.set_config("selected_model", model)
            session_manager.set_config("selected_provider", provider)
    except Exception as exc:
        log_error(str(exc), source="backend/routes/config.py")
        logger.warning("No se pudo persistir el modelo o proveedor seleccionado: %s", exc)

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


# ---------------------------------------------------------------------------
# MCP servers
# ---------------------------------------------------------------------------


@router.get("/mcp/servers")
async def list_mcp_servers() -> JSONResponse:
    """List configured MCP servers from config.json."""
    try:
        mcp_config = get_mcp_config()
        servers = mcp_config.get("servers", {})
        # Convert dict of servers to list, adding label to each
        server_list = []
        for label, config in servers.items():
            if config.get("disabled"):
                continue
            server_config = dict(config)
            server_config["label"] = label
            server_list.append(server_config)
        
        # Return only safe fields for the frontend
        safe_servers = [
            {
                "label": s.get("label", ""),
                "description": s.get("description", ""),
                "transport": s.get("transport", "stdio"),
                "command": s.get("command", ""),
                "args": s.get("args", []),
                "disabled": s.get("disabled", False),
            }
            for s in server_list
        ]
        return JSONResponse(
            status_code=200,
            content={"status": "success", "servers": safe_servers},
        )
    except Exception as exc:
        log_error(str(exc), source="backend/routes/config.py:list_mcp_servers")
        return JSONResponse(
            status_code=500,
            content={"status": "error", "message": "Error cargando servidores MCP", "servers": []},
        )


# ---------------------------------------------------------------------------
# MCP health check
# ---------------------------------------------------------------------------


@router.get("/mcp/health")
async def mcp_health_check() -> JSONResponse:
    """Check health of all configured MCP servers.

    Attempts to connect to each server and list tools to verify it's functional.
    Returns status for each server: connected, failed, disabled, or not_configured.
    """
    try:
        results = await check_all_mcp_servers_health(timeout=10.0)
        return JSONResponse(
            status_code=200,
            content={"status": "success", "servers": results},
        )
    except Exception as exc:
        log_error(str(exc), source="backend/routes/config.py:mcp_health_check")
        return JSONResponse(
            status_code=500,
            content={"status": "error", "message": "Error verificando salud MCP", "servers": []},
        )
