"""Model resolver — discovers available models per provider.

The provider is resolved at runtime from the persisted configuration
(``config_kv`` / ``providers`` tables) rather than from environment
variables. Environment variables (``PROVIDER``, ``MODEL_NAME_2``,
``MODEL_NAME_3``) are only used as a legacy fallback when no persisted
selection exists.

- ``LOCAL`` → runs ``ollama list`` and lists the available models.
- ``GROQ`` → queries the Groq API (``https://api.groq.com/openai/v1/models``)
  and lists the available models.

The user selects a model from a numbered list. The selected model is returned
as a string to be used by the ``Agent`` and the loop.
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
    key (or falls back to the ``GROQ_API_KEY`` env var) and extracts model
    IDs from the response.

    Args:
        api_key: Groq API key. If ``None``, reads ``GROQ_API_KEY`` from env.

    Returns:
        A list of model ID strings. Empty if the API call fails.
    """
    import requests

    key = api_key or os.getenv("GROQ_API_KEY")
    if not key:
        logger.error("No GROQ_API_KEY found in env")
        return []

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
# User model selection (CLI)
# ---------------------------------------------------------------------------

def _prompt_user_selection(models: List[str], provider_label: str) -> str | None:
    """Show a numbered list of models and let the user pick one.

    Args:
        models: List of model name strings.
        provider_label: Human-readable provider label (e.g. ``"Ollama"``).

    Returns:
        The selected model name, or ``None`` if the user cancels.
    """
    if not models:
        print(f"\n[model_resolver] No hay modelos disponibles para {provider_label}.")
        return None

    print(f"\n{'='*60}")
    print(f"  Modelos disponibles ({provider_label})")
    print(f"{'='*60}")
    for i, m in enumerate(models, 1):
        print(f"  {i:3d}. {m}")

    while True:
        try:
            choice = input(f"\nSeleccioná un modelo (1-{len(models)}) o 'q' para cancelar: ").strip()
        except (EOFError, KeyboardInterrupt) as e:
            log_error(str(e), source="model_resolver.py:_prompt_user_selection")
            print()
            return None

        if choice.lower() in ("q", "quit", "exit"):
            return None

        try:
            idx = int(choice) - 1
            if 0 <= idx < len(models):
                selected = models[idx]
                print(f"\n  -> Modelo seleccionado: {selected}\n")
                return selected
            else:
                print(f"  Número inválido. Elegí entre 1 y {len(models)}.")
        except ValueError as e:
            log_error(str(e), source="model_resolver.py:_prompt_user_selection(value)")
            print("  Ingresá un número válido.")


# ---------------------------------------------------------------------------
# Main resolver
# ---------------------------------------------------------------------------

def resolve_model() -> str:
    """Resolve the model name based on the configured provider.

    Reads ``PROVIDER`` from the environment (``.env`` file). If the
    corresponding env var for the model is already set (e.g. ``MODEL_NAME_2``
    for LOCAL, ``MODEL_NAME_3`` for GROQ), returns it directly (legacy
    behaviour). Otherwise, discovers available models and prompts the user
    to select one.

    Returns:
        The selected model name as a string, or an empty string if
        resolution fails.
    """
    from dotenv import load_dotenv
    load_dotenv()

    provider = os.getenv("PROVIDER", "GROQ").strip().upper()
    logger.info("Resolving model for provider: %s", provider)

    if provider.upper() == "LOCAL":
        # Legacy: check if MODEL_NAME_2 is already set
        legacy = os.getenv("MODEL_NAME_2", "").strip()
        if legacy:
            logger.info("Using legacy MODEL_NAME_2: %s", legacy)
            return legacy

        models = get_ollama_models()
        selected = _prompt_user_selection(models, "Ollama (local)")
        return selected or ""

    elif provider.upper() == 'GROQ':
        # Legacy: check if MODEL_NAME_3 is already set
        legacy = os.getenv("MODEL_NAME_3", "").strip()
        if legacy:
            logger.info("Using legacy MODEL_NAME_3: %s", legacy)
            return legacy

        api_key = os.getenv("GROQ_API_KEY", "").strip()
        models = get_groq_models(api_key)
        selected = _prompt_user_selection(models, "Groq (API)")
        return selected or ""

    else:
        logger.error("Unknown PROVIDER: %s", provider)
        return ""


# ---------------------------------------------------------------------------
# Context window detection
# ---------------------------------------------------------------------------

def get_groq_context_window(model: str, api_key: str | None = None) -> int | None:
    """Return the context window (tokens) for a Groq model.

    Calls ``GET https://api.groq.com/openai/v1/models/{model}`` and reads the
    ``context_window`` field.

    Args:
        model: The Groq model ID.
        api_key: Groq API key. If ``None``, reads ``GROQ_API_KEY`` from env.

    Returns:
        The context window in tokens, or ``None`` if it cannot be resolved.
    """
    import requests

    key = api_key or os.getenv("GROQ_API_KEY")
    if not key:
        return None
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
        else:
            cw = get_groq_context_window(model, os.getenv("GROQ_API_KEY", "").strip())
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


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    model = resolve_model()
    if model:
        print(f"\nModelo final: {model}")
    else:
        print("\nNo se seleccionó ningún modelo.")
        sys.exit(1)
