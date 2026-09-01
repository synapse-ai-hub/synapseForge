"""Configuration endpoints for the agent loop.

Provides endpoints to:
- Get/set the context window (max turns to keep in context).
- Get/set verbose mode and the initial setup flag.
- List available models per provider, select one and manage its advanced
  parameters (temperature, top_p, reasoning) via ``/models/select`` and
  ``/parameters``.
- Manage provider API keys (list status, save encrypted, delete).
- List skills, tools, agents and MCP servers for the settings panel.
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
    get_ollama_models,
    get_ollama_context_window,
    get_vram_gb,
    ollama_default_context,
)
from backend.agent.utils import model_catalog
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

_vram_gb: int | None = None
"""Total VRAM in GB, detected once at startup and read from ``config_kv``."""

_verbose_mode: bool = False
"""Whether verbose mode (show tool / sub-agent cards) is enabled.
Set via ``POST /config/verbose-mode``."""


def _detect_and_persist_context_window(model: str, provider: str) -> int | None:
    """Resolve the model's context window, cache it and persist it in one place.

    Single source of truth for context-window detection. Every code path that
    sets the active model (first-startup default resolution, user model
    selection, background startup fix) calls this so ``selected_model`` and
    ``selected_model_context_window`` are always persisted together.

    Args:
        model: The model name/ID.
        provider: ``"LOCAL"``, ``"GROQ"``, ``"GOOGLE"`` or ``"OPENROUTER"``.

    Returns:
        The context window in tokens, or ``None`` if it cannot be resolved.
    """
    global _context_window_tokens
    cw = None
    try:
        if provider.upper() == "LOCAL":
            cw = get_ollama_context_window(model)
        else:
            # Cloud providers: use model_catalog from models.dev
            cw = model_catalog.get_context_window(provider.strip().lower(), model)
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


def detect_context_window_background() -> None:
    """Detect and persist the context window for the active model, if missing.

    Called once at application startup (like VRAM detection) so the active
    model's context window is resolved without blocking any request.
    """
    if agent is None or agent._resolved_model is None:
        return
    if session_manager is not None and session_manager.get_config("selected_model_context_window"):
        return
    _detect_and_persist_context_window(agent._resolved_model, agent.provider)


@router.get("/context-window")
async def get_context_window() -> JSONResponse:
    """Return the current context-window turn limit (``-1`` = all)."""
    vram = _vram_gb
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


@router.get("/setup-completed")
async def get_setup_completed() -> JSONResponse:
    """Return whether the initial provider-setup screen was completed.

    The flag is persisted in ``config_kv`` and set when the user saves a
    valid API key or skips the initial setup screen, so the screen is only
    shown on first launch (regardless of whether Ollama is available).
    """
    completed = False
    if session_manager is not None:
        try:
            raw = session_manager.get_config("setup_completed")
            completed = (raw or "").strip().lower() == "true"
        except Exception as exc:
            log_error(str(exc), source="backend/routes/config.py")
            logger.warning("No se pudo leer setup_completed: %s", exc)
    return JSONResponse(
        status_code=200,
        content={"status": "success", "completed": completed},
    )


@router.post("/setup-completed")
async def set_setup_completed() -> JSONResponse:
    """Mark the initial provider-setup screen as completed (or skipped)."""
    try:
        if session_manager is not None:
            session_manager.set_config("setup_completed", "true")
    except Exception as exc:
        log_error(str(exc), source="backend/routes/config.py")
        logger.warning("No se pudo persistir setup_completed: %s", exc)
    return JSONResponse(
        status_code=200,
        content={
            "status": "success",
            "message": "Setup marked as completed.",
        },
    )


# ---------------------------------------------------------------------------
# Available providers
# ---------------------------------------------------------------------------


def refresh_providers_cache() -> None:
    """Sync model catalog from models.dev for each provider with an API key.

    Called once at application startup.  For cloud providers (Groq, Google,
    OpenRouter, etc.) the catalog is synced from models.dev into the
    ``model_catalog`` table.  For Ollama (LOCAL) the models are listed
    directly via ``ollama list`` and stored in the ``providers`` table.
    """
    cached: list[dict[str, Any]] = []

    from backend.agent.utils import provider_keys

    # Ollama — try ``ollama list``
    try:
        ollama_models = get_ollama_models()
        if ollama_models:
            cached.append(
                {"provider": "LOCAL", "label": "Ollama (local)", "models": ollama_models}
            )
    except Exception as exc:
        log_error(str(exc), source="backend/routes/config.py:refresh_providers_cache(ollama)")
        logger.warning("No se pudieron listar modelos de Ollama: %s", exc)

    # Cloud providers — sync from models.dev for each configured key.
    _PROVIDER_LABELS = {
        "groq": "Groq",
        "google": "Google Gemini",
        "openrouter": "OpenRouter",
    }
    for provider_id in ["groq", "google", "openrouter"]:
        try:
            api_key = provider_keys.resolve_api_key(provider_id.upper())
            if not api_key:
                continue
            # Sync catalog from models.dev (rate-limited to 24h).
            result = model_catalog.sync_catalog(provider_id)
            # Whether sync ran or was skipped (fresh catalog), get models.
            models = model_catalog.get_models(provider_id)
            if models:
                cached.append({
                    "provider": provider_id.upper(),
                    "label": _PROVIDER_LABELS.get(provider_id, provider_id),
                    "models": models,
                })
        except Exception as exc:
            log_error(str(exc), source=f"backend/routes/config.py:refresh_providers_cache({provider_id})")
            logger.warning("No se pudieron listar modelos de %s: %s", provider_id, exc)

    if session_manager is not None:
        session_manager.save_providers(cached)
    logger.info("Providers cache refreshed: %s", [p["provider"] for p in cached])


@router.get("/providers")
async def list_providers() -> JSONResponse:
    """Return the list of available providers from the startup cache.

    Providers and their model lists are resolved once at application startup
    and persisted in the ``providers`` table, so this endpoint serves them
    from SQLite without per-request network calls.
    """
    providers = session_manager.get_providers() if session_manager is not None else []
    available = [{"provider": p["provider"], "label": p["label"]} for p in providers]
    return JSONResponse(
        status_code=200,
        content={
            "status": "success",
            "providers": available,
        },
    )


# ---------------------------------------------------------------------------
# Provider API keys (encrypted storage in SQLite)
# ---------------------------------------------------------------------------


@router.get("/providers/keys")
async def list_provider_keys() -> JSONResponse:
    """Return which providers have an API key configured.

    Only availability status is exposed — the key material never leaves
    the backend.
    """
    from backend.agent.utils import provider_keys

    try:
        keys = provider_keys.list_configured()
        return JSONResponse(
            status_code=200,
            content={"status": "success", "keys": keys},
        )
    except Exception as exc:
        log_error(str(exc), source="backend/routes/config.py:list_provider_keys")
        return JSONResponse(
            status_code=500,
            content={"status": "error", "message": f"Error consultando API keys: {exc}"},
        )


@router.put("/providers/{provider}/key")
async def save_provider_key(provider: str, data: dict[str, Any]) -> JSONResponse:
    """Validate, store (encrypted) and activate the API key for a provider.

    Body: ``{"api_key": "..."}``. The key is first validated against the
    provider's live API; if invalid it is rejected (400) and nothing is
    stored. On success the key is encrypted with Fernet, persisted in the
    ``provider_api_keys`` table, the provider client is rebuilt and the
    providers cache is refreshed so the new provider becomes selectable
    immediately.
    """
    from backend.agent.utils import provider_keys

    api_key = (data or {}).get("api_key", "")
    validation = await asyncio.to_thread(provider_keys.validate_key, provider, api_key)
    if validation.get("status") != "success":
        return JSONResponse(status_code=400, content=validation)
    result = await asyncio.to_thread(provider_keys.save_key, provider, api_key)
    if result.get("status") != "success":
        return JSONResponse(status_code=400, content=result)
    # Refresh the providers cache FIRST so the new provider becomes
    # selectable immediately even if the client rebuild below fails.
    await asyncio.to_thread(refresh_providers_cache)
    if agent is not None:
        rebuild = await asyncio.to_thread(agent.rebuild_provider_client, provider)
        if rebuild.get("status") != "success":
            return JSONResponse(status_code=500, content=rebuild)
    return JSONResponse(
        status_code=200,
        content={
            "status": "success",
            "message": f"API key de {(provider or '').upper()} validada y guardada.",
        },
    )


@router.delete("/providers/{provider}/key")
async def delete_provider_key(provider: str) -> JSONResponse:
    """Remove the stored API key for a provider and rebuild its client.

    After deletion the client becomes unavailable and the providers cache
    is refreshed so the provider disappears from the selectable list.
    """
    from backend.agent.utils import provider_keys

    result = await asyncio.to_thread(provider_keys.delete_key, provider)
    if result.get("status") != "success":
        return JSONResponse(status_code=400, content=result)
    # Refresh the providers cache FIRST so the removed provider disappears
    # even if the client rebuild below fails.
    await asyncio.to_thread(refresh_providers_cache)
    if agent is not None:
        rebuild = await asyncio.to_thread(agent.rebuild_provider_client, provider)
        if rebuild.get("status") != "success":
            return JSONResponse(status_code=500, content=rebuild)
    return JSONResponse(status_code=200, content=result)


# ---------------------------------------------------------------------------
# Advanced parameters (temperature / top_p / reasoning)
# ---------------------------------------------------------------------------

_PARAM_KEYS = {
    "temperature": "param_temperature",
    "top_p": "param_top_p",
    "reasoning": "param_reasoning",
    "budget_tokens": "param_budget_tokens",
}
"""Mapping of parameter name → ``config_kv`` key. Persisted values use the
literal string ``"null"`` for "default" (no override)."""


def _parse_optional_float(raw: Any, low: float, high: float) -> tuple[float | None, str | None]:
    """Parse an optional float parameter (``None`` = default).

    Args:
        raw: Raw value from the request body (float, int or ``None``).
        low: Minimum accepted value (inclusive).
        high: Maximum accepted value (inclusive).

    Returns:
        Tuple ``(value, error)`` — exactly one of the two is ``None``.
    """
    if raw is None:
        return None, None
    if isinstance(raw, bool):
        return None, f"must be a number between {low} and {high}, or null."
    try:
        value = float(raw)
    except (TypeError, ValueError):
        return None, f"must be a number between {low} and {high}, or null."
    if value < low or value > high:
        return None, f"must be a number between {low} and {high}, or null."
    return value, None


def _persist_param(key: str, value: Any) -> None:
    """Persist one advanced parameter in ``config_kv``.

    Args:
        key: ``config_kv`` key (see ``_PARAM_KEYS``).
        value: Parameter value; ``None`` is stored as the literal string
            ``"null"`` (= default / no override).
    """
    if session_manager is None:
        return
    stored = "null" if value is None else str(value)
    session_manager.set_config(key, stored)


def _read_param(key: str) -> Any:
    """Read one advanced parameter from ``config_kv``.

    Args:
        key: ``config_kv`` key (see ``_PARAM_KEYS``).

    Returns:
        The parsed value (``float`` for temperature/top_p, ``str`` for
        reasoning, ``int`` for budget_tokens) or ``None`` when unset/"null"
        (default).
    """
    if session_manager is None:
        return None
    raw = session_manager.get_config(key)
    if raw is None or raw.strip().lower() == "null":
        return None
    try:
        if key == _PARAM_KEYS["reasoning"]:
            return raw.strip().lower()
        if key == _PARAM_KEYS["budget_tokens"]:
            return int(float(raw))
        return float(raw)
    except (TypeError, ValueError):
        return None


@router.get("/parameters")
async def get_parameters() -> JSONResponse:
    """Return the persisted advanced parameters (``null`` = default).

    Also reports whether the currently selected model declaratively supports
    reasoning (``reasoning_supported``): ``true``/``false`` per the provider
    catalog, or ``null`` when capability is unknown.
    """
    try:
        current_model = agent._resolved_model if agent is not None else None
        current_provider = agent.provider if agent is not None else ""
        reasoning_supported: bool | None = None
        if current_model and current_provider:
            if current_provider.upper() == "LOCAL":
                from backend.agent.utils.model_resolver import model_supports_reasoning
                reasoning_supported = await asyncio.to_thread(
                    model_supports_reasoning, current_provider, current_model
                )
            else:
                caps = await asyncio.to_thread(
                    model_catalog.get_reasoning_options,
                    current_provider.strip().lower(),
                    current_model,
                )
                reasoning_supported = caps.get("reasoning_supported")
        return JSONResponse(
            status_code=200,
            content={
                "status": "success",
                "temperature": _read_param(_PARAM_KEYS["temperature"]),
                "top_p": _read_param(_PARAM_KEYS["top_p"]),
                "reasoning": _read_param(_PARAM_KEYS["reasoning"]),
                "budget_tokens": _read_param(_PARAM_KEYS["budget_tokens"]),
                "model": current_model,
                "provider": current_provider or "",
                "reasoning_supported": reasoning_supported,
            },
        )
    except Exception as exc:
        log_error(str(exc), source="backend/routes/config.py:get_parameters")
        return JSONResponse(
            status_code=500,
            content={"status": "error", "message": f"Error leyendo parámetros: {exc}"},
        )


# ---------------------------------------------------------------------------
# Model selection
# ---------------------------------------------------------------------------


def _effective_provider(provider: str | None = None) -> str:
    """Return the effective provider: query param, else persisted selection.

    No environment/default fallback: when nothing was explicitly selected
    the empty string is returned so callers treat it as "no provider chosen"
    (the UI then shows no provider pre-selected).

    Args:
        provider: Explicit provider from the query param, if any.

    Returns:
        Upper-case provider name, or empty string when none was selected.
    """
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

    return ""


@router.get("/models")
async def list_models(provider: str | None = None) -> JSONResponse:
    """List available models for the current provider.

    Uses the explicit ``provider`` query param if supplied. Otherwise it uses
    the selected provider from persisted config (never environment
    variables).

    - ``LOCAL`` → models from the startup cache (Ollama).
    - ``GROQ`` → models from the startup cache (Groq).

    No model is selected automatically: the user must pick one and apply it
    via ``POST /config/models/select``. The response carries ``model: null``
    until then (a previously persisted selection is still honored).

    Returns the list of model IDs/names and the selected model (or null).
    """
    provider = _effective_provider(provider)

    # Nothing selected yet: return empty lists so the UI shows no provider
    # and no model pre-selected. The user must pick both explicitly.
    if not provider:
        return JSONResponse(
            status_code=200,
            content={
                "status": "success",
                "provider": "",
                "provider_label": None,
                "models": [],
                "model": None,
            },
        )

    # Serve models from the startup cache (providers table) — no network calls.
    cached_providers = session_manager.get_providers() if session_manager is not None else []
    cached = next(
        (p for p in cached_providers if p["provider"].upper() == provider.upper()),
        None,
    )
    if cached is None:
        return JSONResponse(
            status_code=400,
            content={
                "status": "error",
                "message": f"Unknown PROVIDER: '{provider}'. Use 'GROQ', 'LOCAL', 'GOOGLE' or 'OPENROUTER'.",
            },
        )

    models = cached["models"]
    provider_label = cached["label"]

    previous_provider = agent.provider if agent is not None else None
    if agent is not None and agent.provider != provider:
        agent.provider = provider

    selected_model = None
    if agent is not None and previous_provider == provider:
        selected_model = agent._resolved_model

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

        {"model": "llama3.2", "provider": "LOCAL",
         "temperature": 0.7, "top_p": 0.9, "reasoning": true}

    ``temperature``, ``top_p`` and ``reasoning`` are optional advanced
    parameters; ``null`` (or omitted) means "default" (the agent's
    frontmatter value, or the hardcoded fallback). The selection and the
    parameters are stored in the agent singleton / persisted in SQLite
    (``config_kv`` keys ``param_temperature``, ``param_top_p``,
    ``param_reasoning``).

    If ``reasoning=true`` is sent for a model that declaratively does not
    support reasoning (per the provider catalog), the request is rejected
    with a contract error response.
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

    if provider not in {"LOCAL", "GROQ", "GOOGLE", "OPENROUTER"}:
        return JSONResponse(
            status_code=400,
            content={
                "status": "error",
                "message": "provider must be 'LOCAL', 'GROQ', 'GOOGLE' or 'OPENROUTER'.",
            },
        )

    # --- Optional advanced parameters (None = default) ---
    temperature, temp_err = _parse_optional_float(data.get("temperature"), 0.0, 2.0)
    if temp_err:
        return JSONResponse(
            status_code=400,
            content={"status": "error", "message": f"temperature {temp_err}"},
        )
    top_p, top_p_err = _parse_optional_float(data.get("top_p"), 0.0, 1.0)
    if top_p_err:
        return JSONResponse(
            status_code=400,
            content={"status": "error", "message": f"top_p {top_p_err}"},
        )
    reasoning = data.get("reasoning", None)
    if reasoning is not None and not isinstance(reasoning, str):
        return JSONResponse(
            status_code=400,
            content={
                "status": "error",
                "message": "reasoning must be a string or null (default).",
            },
        )
    budget_tokens = data.get("budget_tokens", None)
    if budget_tokens is not None:
        try:
            budget_tokens = int(budget_tokens)
            if budget_tokens < 0:
                raise ValueError
        except (TypeError, ValueError):
            return JSONResponse(
                status_code=400,
                content={
                    "status": "error",
                    "message": "budget_tokens must be a positive integer or null.",
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

    # --- Reasoning capacity validation (declarative catalog check) ---
    if reasoning and reasoning not in ("default", ""):
        try:
            if provider.upper() == "LOCAL":
                from backend.agent.utils.model_resolver import model_supports_reasoning
                supports_reasoning = await asyncio.to_thread(
                    model_supports_reasoning, provider, model
                )
            else:
                caps = await asyncio.to_thread(
                    model_catalog.get_reasoning_options,
                    provider.strip().lower(),
                    model,
                )
                supports_reasoning = caps.get("reasoning_supported")
        except Exception as exc:
            log_error(str(exc), source="backend/routes/config.py:select_model(reasoning_check)")
            supports_reasoning = None
        if supports_reasoning is False:
            return JSONResponse(
                status_code=400,
                content={
                    "status": "error",
                    "message": (
                        f"Model '{model}' does not support reasoning. "
                        "Set reasoning to default/no or pick another model."
                    ),
                },
            )

    # Liberar modelo anterior si es LOCAL (Ollama) y cambió
    modelo_anterior = agent._resolved_model
    if modelo_anterior and modelo_anterior != model and agent.provider.upper() == "LOCAL":
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
            # Persist advanced parameters together with the model
            # ("null" = default / no override).
            _persist_param(_PARAM_KEYS["temperature"], temperature)
            _persist_param(_PARAM_KEYS["top_p"], top_p)
            _persist_param(_PARAM_KEYS["reasoning"], reasoning)
            _persist_param(_PARAM_KEYS["budget_tokens"], budget_tokens)
    except Exception as exc:
        log_error(str(exc), source="backend/routes/config.py")
        logger.warning("No se pudo persistir el modelo o proveedor seleccionado: %s", exc)

    # Detect and persist the model's context window (tokens) — same helper used
    # by the first-startup default resolution, so both are always persisted
    # together.
    await asyncio.to_thread(_detect_and_persist_context_window, model, provider)

    # Broadcast the change so every frontend (and any other subscriber)
    # refreshes — the web UI path already dispatches a local event, but the
    # SSE broadcast makes Telegram↔Frontend bidirectional and keeps multiple
    # browser tabs in sync.
    try:
        from backend.event_bus import event_bus
        await event_bus.emit({
            "type": "model_changed",
            "content": {"model": model, "provider": provider},
        })
    except Exception as exc:
        logger.warning("No se pudo emitir model_changed: %s", exc)

    logger.info("Model selected: %s (%s)", model, provider)
    return JSONResponse(
        status_code=200,
        content={
            "status": "success",
            "message": f"Model '{model}' selected.",
            "model": model,
            "provider": provider,
            "temperature": temperature,
            "top_p": top_p,
            "reasoning": reasoning,
            "budget_tokens": budget_tokens,
        },
    )


@router.get("/models/capabilities")
async def get_model_capabilities(model: str, provider: str) -> JSONResponse:
    """Return reasoning capabilities for a specific model/provider.

    Query params:
        model: Model name/ID
        provider: Provider name (LOCAL, GROQ, GOOGLE, OPENROUTER)

    Returns:
        reasoning_supported: boolean
        reasoning_options: array of {value, label} for the reasoning dropdown
        reasoning_type: "effort_levels" | "budget_tokens" | "boolean"
    """
    if not model or not provider:
        return JSONResponse(
            status_code=400,
            content={
                "status": "error",
                "message": "model and provider query params are required.",
            },
        )

    provider_u = provider.strip().upper()

    try:
        if provider_u == "LOCAL":
            # Ollama: use legacy model_resolver (no models.dev)
            from backend.agent.utils.model_resolver import get_model_reasoning_options

            caps = await asyncio.to_thread(
                get_model_reasoning_options, provider_u, model
            )
        else:
            # Cloud providers: use model_catalog from models.dev
            caps = await asyncio.to_thread(
                model_catalog.get_reasoning_options, provider.strip().lower(), model
            )

        return JSONResponse(
            status_code=200,
            content={
                "status": "success",
                "reasoning_supported": caps.get("reasoning_supported"),
                "reasoning_options": caps.get("reasoning_options", []),
                "reasoning_param": caps.get("reasoning_param"),
                "reasoning_type": caps.get("reasoning_type"),
                "budget_min": caps.get("budget_min"),
                "budget_max": caps.get("budget_max"),
            },
        )
    except Exception as exc:
        log_error(str(exc), source="backend/routes/config.py:get_model_capabilities")
        return JSONResponse(
            status_code=500,
            content={"status": "error", "message": f"Error obteniendo capacidades: {exc}"},
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
    # The result is cached in model_resolver and persisted in config_kv.
    try:
        global _vram_gb
        _vram_gb = get_vram_gb()
        print(f"[DEBUG] VRAM detectada al iniciar: {_vram_gb} GB")
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


@router.post("/tools/refresh")
async def refresh() -> JSONResponse:
    """Full refresh: re-scan external tools, rebuild registry (including MCP).

    Triggered by the ``Actualizar`` button in the agent panel.
    """
    try:
        agent.tools._external_tools = agent.tools._scan_external_tools()
        agent.tools._tools_registry = agent.tools._build_tools_registry()
        tools = get_tools_list()
        return JSONResponse(
            status_code=200,
            content={"status": "success", "tools": tools, "message": "Tools registry refreshed"},
        )
    except Exception as exc:
        log_error(str(exc), source="backend/routes/config.py:refresh")
        return JSONResponse(
            status_code=500,
            content={"status": "error", "message": "Error refreshing tools", "tools": []},
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
