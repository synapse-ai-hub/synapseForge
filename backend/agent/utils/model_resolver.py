"""Model resolver — discovers available models per provider.

The provider/model selection lives entirely in the persisted configuration
(``config_kv`` / ``providers`` tables): nothing is read from environment
variables. This module only exposes discovery helpers:

- ``LOCAL`` → runs ``ollama list`` and lists the available models.
- ``GROQ`` → queries the Groq API (``https://api.groq.com/openai/v1/models``)
  and lists the available models.
- ``GOOGLE`` / ``OPENROUTER`` → query their respective APIs/catalogs.

The user selects a model from the UI; the selection is persisted by
``backend/routes/config.py``.
"""

import json
import logging
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import List

# ---------------------------------------------------------------------------
# Ensure the project root is in sys.path so absolute imports (backend.*)
# resolve correctly regardless of how the file is invoked.
# ---------------------------------------------------------------------------
_current_dir = os.path.dirname(os.path.abspath(__file__))
_project_root = os.path.dirname(os.path.dirname(_current_dir))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from backend.agent.utils.error_logger import log_error

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Ollama model listing
# ---------------------------------------------------------------------------

def get_ollama_models() -> List[str]:
    """List available models via ``ollama list``.

    Runs ``ollama list`` in a subprocess and parses the output to extract
    model names (first column, excluding the header line).

    Returns:
        A list of model name strings. Empty if ``ollama`` is not installed
        or returns no output.

    Raises:
        FileNotFoundError: If the ``ollama`` binary is not found.
        subprocess.CalledProcessError: If ``ollama list`` fails.
    """
    try:
        result = subprocess.run(
            ["ollama", "list"],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode != 0:
            logger.error("ollama list failed: %s", result.stderr.strip())
            return []
    except FileNotFoundError as e:
        log_error(str(e), source="model_resolver.py:get_ollama_models")
        logger.error("ollama binary not found. Is Ollama installed?")
        return []
    except subprocess.TimeoutExpired as e:
        log_error(str(e), source="model_resolver.py:get_ollama_models(timeout)")
        logger.error("ollama list timed out")
        return []

    lines = result.stdout.strip().splitlines()
    if not lines:
        return []

    # Skip header line ("NAME\tID\tSIZE\tMODIFIED")
    models = []
    for line in lines[1:]:
        parts = line.split()
        if parts:
            models.append(parts[0])

    return models


# ---------------------------------------------------------------------------
# Groq model listing
# ---------------------------------------------------------------------------

def get_groq_models(api_key: str | None = None) -> List[str]:
    """List available models via the Groq API.

    Calls ``GET https://api.groq.com/openai/v1/models`` with the given API
    key and extracts model IDs from the response.

    Args:
        api_key: Groq API key (resolved from the encrypted DB storage by
            the caller).

    Returns:
        A list of model ID strings. Empty if the API call fails.
    """
    import requests

    if not api_key:
        logger.error("No Groq API key provided")
        return []
    key = api_key

    url = "https://api.groq.com/openai/v1/models"
    headers = {
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
    }

    try:
        resp = requests.get(url, headers=headers, timeout=30)
        resp.raise_for_status()
        data = resp.json()
    except requests.RequestException as e:
        log_error(str(e), source="model_resolver.py:get_groq_models(request)")
        logger.error("Groq API request failed: %s", e)
        return []
    except json.JSONDecodeError as e:
        log_error(str(e), source="model_resolver.py:get_groq_models(json)")
        logger.error("Groq API returned invalid JSON: %s", e)
        return []

    models_raw = data.get("data", []) if isinstance(data, dict) else []
    models = [m["id"] for m in models_raw if isinstance(m, dict) and m.get("id")]
    return models


# ---------------------------------------------------------------------------
# Google Gemini model listing / context window
# ---------------------------------------------------------------------------

def get_google_models(api_key: str | None = None) -> List[str]:
    """List chat-capable Gemini models via the Google GenAI API.

    Filters the full model list to models that support ``generateContent``
    and excludes non-chat variants (TTS, image, embedding, live/audio,
    robotics, computer-use) so only text-generation chat models are shown.

    Args:
        api_key: Google API key (resolved from the encrypted DB storage by
            the caller).

    Returns:
        A list of model name strings (with the ``models/`` prefix).
        Empty if the API call fails or no key is available.
    """
    key = (api_key or "").strip()
    if not key:
        logger.error("No Google API key provided")
        return []

    try:
        from google import genai
        client = genai.Client(api_key=key)
        models: List[str] = []
        for m in client.models.list():
            name = m.name or ""
            actions = getattr(m, "supported_actions", None) or []
            if "generateContent" not in actions:
                continue
            # Exclude non-text-generation variants (TTS, image gen, embeddings,
            # live audio, robotics, computer use) — they are listed by the API
            # but are not usable as chat models.
            lowered = name.lower()
            if any(tag in lowered for tag in (
                "-tts", "image", "embedding", "native-audio",
                "live", "robotics", "computer-use",
            )):
                continue
            models.append(name)
        return models
    except Exception as e:
        log_error(str(e), source="model_resolver.py:get_google_models")
        logger.error("Google API request failed: %s", e)
        return []


def get_google_context_window(model: str, api_key: str | None = None) -> int | None:
    """Return the context window (tokens) for a Gemini model.

    Calls ``client.models.get(model=...)`` and reads the
    ``input_token_limit`` field.

    Args:
        model: The Gemini model name (e.g. ``models/gemini-3.5-flash``).
        api_key: Google API key (resolved from the encrypted DB storage by
            the caller).

    Returns:
        The context window in tokens, or ``None`` if it cannot be resolved.
    """
    key = (api_key or "").strip()
    if not key:
        return None

    try:
        from google import genai
        client = genai.Client(api_key=key)
        m = client.models.get(model=model)
        limit = getattr(m, "input_token_limit", None)
        return int(limit) if limit else None
    except Exception as e:
        log_error(str(e), source="model_resolver.py:get_google_context_window")
        return None


# ---------------------------------------------------------------------------
# OpenRouter model listing / details
# ---------------------------------------------------------------------------

_OPENROUTER_MODELS_URL = "https://openrouter.ai/api/v1/models"
"""Public OpenRouter catalog endpoint (no API key required)."""

_NON_CHAT_ID_TAGS = (
    "embedding", "whisper", "tts", "moderation", "guard",
    "rerank", "voice", "transcri", "speech", "video", "image-gen",
)
"""Catalog ID substrings that identify non-chat models."""


def _fetch_openrouter_catalog() -> list[dict]:
    """Fetch and return the raw OpenRouter model catalog entries.

    Returns:
        List of catalog entry dicts, or an empty list on failure.
    """
    import requests

    try:
        resp = requests.get(_OPENROUTER_MODELS_URL, timeout=30)
        resp.raise_for_status()
        data = resp.json()
    except requests.RequestException as e:
        log_error(str(e), source="model_resolver.py:_fetch_openrouter_catalog(request)")
        logger.error("OpenRouter catalog request failed: %s", e)
        return []
    except json.JSONDecodeError as e:
        log_error(str(e), source="model_resolver.py:_fetch_openrouter_catalog(json)")
        logger.error("OpenRouter catalog returned invalid JSON: %s", e)
        return []

    entries = data.get("data", []) if isinstance(data, dict) else []
    return [m for m in entries if isinstance(m, dict) and m.get("id")]


def _is_chat_model(entry: dict) -> bool:
    """Return whether a catalog entry is a text-generation chat model.

    Prefers the ``architecture.output_modalities`` field when present;
    otherwise falls back to excluding known non-chat ID tags.

    Args:
        entry: A raw OpenRouter catalog entry.

    Returns:
        ``True`` if the model can be used for chat completions.
    """
    arch = entry.get("architecture") or {}
    modalities = arch.get("output_modalities")
    if isinstance(modalities, list) and modalities:
        return "text" in modalities
    model_id = str(entry.get("id", "")).lower()
    return not any(tag in model_id for tag in _NON_CHAT_ID_TAGS)


def get_openrouter_models(api_key: str | None = None) -> List[str]:
    """List chat-capable models from the public OpenRouter catalog.

    Args:
        api_key: Unused (the catalog is public); kept for signature
            consistency with the other provider resolvers.

    Returns:
        Sorted list of model ID strings (e.g. ``openai/gpt-4o``).
        Empty if the catalog cannot be fetched.
    """
    entries = _fetch_openrouter_catalog()
    models = sorted(
        entry["id"] for entry in entries if _is_chat_model(entry)
    )
    return models


def get_openrouter_model_details(model: str) -> dict | None:
    """Return catalog details for an OpenRouter model.

    Args:
        model: The OpenRouter model ID (e.g. ``openai/gpt-4o``).

    Returns:
        Dict with ``context_length``, ``reasoning`` (bool),
        ``reasoning_levels`` (list or None) and ``pricing`` (dict or None),
        or ``None`` if the model is not found.
    """
    for entry in _fetch_openrouter_catalog():
        if entry.get("id") == model:
            supported = entry.get("supported_parameters") or []
            has_reasoning = "reasoning" in supported
            levels = None
            if has_reasoning:
                # Some models expose enabled_reasoning_levels in the catalog.
                levels = entry.get("enabled_reasoning_levels") or None
            return {
                "context_length": entry.get("context_length"),
                "reasoning": has_reasoning,
                "reasoning_levels": levels,
                "pricing": entry.get("pricing"),
            }
    return None


def get_openrouter_context_window(model: str, api_key: str | None = None) -> int | None:
    """Return the context window (tokens) for an OpenRouter model.

    Reads ``context_length`` from the public catalog.

    Args:
        model: The OpenRouter model ID.
        api_key: Unused (the catalog is public).

    Returns:
        The context window in tokens, or ``None`` if it cannot be resolved.
    """
    try:
        details = get_openrouter_model_details(model)
        cw = (details or {}).get("context_length")
        return int(cw) if cw else None
    except Exception as e:
        log_error(str(e), source="model_resolver.py:get_openrouter_context_window")
        return None


# ---------------------------------------------------------------------------
# Context window detection
# ---------------------------------------------------------------------------

def get_groq_context_window(model: str, api_key: str | None = None) -> int | None:
    """Return the context window (tokens) for a Groq model.

    Calls ``GET https://api.groq.com/openai/v1/models/{model}`` and reads the
    ``context_window`` field.

    Args:
        model: The Groq model ID.
        api_key: Groq API key (resolved from the encrypted DB storage by
            the caller).

    Returns:
        The context window in tokens, or ``None`` if it cannot be resolved.
    """
    import requests

    if not api_key:
        return None
    key = api_key
    url = f"https://api.groq.com/openai/v1/models/{model}"
    headers = {
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
    }
    try:
        resp = requests.get(url, headers=headers, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        cw = data.get("context_window")
        return int(cw) if cw else None
    except Exception as e:
        log_error(str(e), source="model_resolver.py:get_groq_context_window")
        return None


def get_ollama_context_window(model: str) -> int | None:
    """Return the effective runtime context length (tokens) for an Ollama model.

    Calls ``POST /api/show`` and reads, in order of preference:
    1. the top-level ``context_length`` (context for the running model),
    2. ``model_info["<family>.context_length"]`` (model max context),
    3. ``num_ctx`` parsed from the ``parameters`` string.

    Args:
        model: The Ollama model name.

    Returns:
        The context length in tokens, or ``None`` if it cannot be resolved.
    """
    import requests

    try:
        resp = requests.post(
            "http://localhost:11434/api/show",
            json={"model": model},
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()

        cl = data.get("context_length")
        if cl:
            return int(cl)

        model_info = data.get("model_info") or {}
        for k, v in model_info.items():
            if k.endswith(".context_length") and v:
                return int(v)

        params = data.get("parameters") or ""
        m = re.search(r"num_ctx\s+(\d+)", params)
        if m:
            return int(m.group(1))

        return None
    except Exception as e:
        log_error(str(e), source="model_resolver.py:get_ollama_context_window")
        return None


def ensure_context_window(agent, model: str) -> int | None:
    """Return the model's context window, detecting and caching it if needed.

    If ``agent._context_window`` is already set, returns it. Otherwise it
    detects the context window for the given model (Ollama ``/api/show`` or
    Groq ``/models``) and caches it on the agent instance.

    Args:
        agent: The ``Agent`` instance (may be ``None``).
        model: The model name.

    Returns:
        The context window in tokens, or ``None`` if it cannot be resolved.
    """
    if agent is not None and getattr(agent, "_context_window", None):
        return agent._context_window

    provider = (getattr(agent, "provider", None) or "LOCAL").strip().upper()
    cw = None
    try:
        if provider.upper() == "LOCAL":
            cw = get_ollama_context_window(model)
        elif provider.upper() == "GOOGLE":
            cw = get_google_context_window(model)
        elif provider.upper() == "OPENROUTER":
            cw = get_openrouter_context_window(model)
        else:
            from backend.agent.utils import provider_keys

            cw = get_groq_context_window(model, provider_keys.get_key("GROQ"))
    except Exception as e:
        log_error(str(e), source="model_resolver.py:ensure_context_window")
        cw = None

    if cw and agent is not None:
        agent._context_window = cw
    return cw


# ---------------------------------------------------------------------------
# VRAM detection (for the context-window recommendation)
# ---------------------------------------------------------------------------

_vram_cache: int | None | object = None
"""Cache for ``get_vram_gb`` (``None`` = not computed yet)."""


def get_vram_gb() -> int | None:
    """Return the total VRAM in GB of the primary GPU, or ``None`` if unknown.

    Resolution order:
    1. In-memory cache (``_vram_cache``).
    2. Value persisted in ``config_kv`` (``vram_gb``), set at application
       startup.
    3. Detect via ``nvidia-smi`` then ``wmic`` (Windows), persisting the
       result to ``config_kv`` so it is only queried once per process.

    Returns:
        Total VRAM in GB, or ``None`` if it cannot be determined.
    """
    global _vram_cache
    if _vram_cache is not None:
        return _vram_cache if isinstance(_vram_cache, int) else None

    # Prefer the value persisted at startup so we never re-run nvidia-smi/wmic
    # on every request.
    try:
        from backend.instances import session_manager

        persisted = (
            session_manager.get_config("vram_gb")
            if session_manager is not None
            else None
        )
        if persisted is not None:
            vram = int(persisted)
            _vram_cache = vram
            return vram
    except Exception:
        pass

    import subprocess

    vram = None
    # nvidia-smi (NVIDIA GPUs)
    try:
        result = subprocess.run(
            ["nvidia-smi", "--query-gpu=memory.total", "--format=csv,noheader,nounits"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode == 0 and result.stdout.strip():
            first = result.stdout.strip().splitlines()[0].strip()
            vram = int(float(first) / 1024)
    except Exception:
        vram = None

    # wmic (Windows fallback)
    if vram is None:
        try:
            result = subprocess.run(
                ["wmic", "path", "win32_VideoController", "get", "AdapterRAM"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            if result.returncode == 0:
                for line in result.stdout.splitlines():
                    line = line.strip()
                    if line.isdigit():
                        vram = int(int(line) / (1024**3))
                        break
        except Exception:
            vram = None

    # Persist so future processes/requests read from config_kv.
    if vram is not None:
        try:
            from backend.instances import session_manager

            if session_manager is not None:
                session_manager.set_config("vram_gb", str(vram))
        except Exception:
            pass

    _vram_cache = vram if vram is not None else -1
    print(f"[DEBUG] get_vram_gb: {vram}")
    return vram


def ollama_default_context(vram_gb: int | None) -> int | None:
    """Return the default context length Ollama configures for a given VRAM.

    Based on Ollama's documented VRAM-based defaults:
    - < 24 GiB VRAM: 4,096 context
    - 24-48 GiB VRAM: 32,768 context
    - >= 48 GiB VRAM: 262,144 context

    Args:
        vram_gb: Total VRAM in GB, or ``None`` if unknown.

    Returns:
        The default context length in tokens, or ``None`` if VRAM is unknown.
    """
    if vram_gb is None:
        return None
    if vram_gb < 24:
        return 4096
    if vram_gb < 48:
        return 32768
    return 262144
