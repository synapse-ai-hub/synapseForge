"""Model catalog — fetches and caches model data from models.dev.

Replaces the hardcoded provider-specific model discovery logic with a
single source of truth from ``https://models.dev/api.json``.  The catalog
is persisted in the agent's SQLite database (``agent.db``) so queries are
fast (indexed B-tree) and the data survives process restarts.

Sync strategy:

- A sync is triggered automatically when the user saves an API key for a
  provider (see ``provider_keys.save_key``).
- Each provider sync is rate-limited to once every 24 hours.
- Only providers with a configured API key are synced (except Ollama,
  which is handled separately in ``model_resolver``).
"""

from __future__ import annotations

import json
import logging
import os
import sqlite3
import sys
import time
from datetime import datetime, timezone
from typing import Any

# ---------------------------------------------------------------------------
# Ensure project root is in sys.path for absolute imports
# ---------------------------------------------------------------------------
_current_dir = os.path.dirname(os.path.abspath(__file__))
_project_root = os.path.dirname(os.path.dirname(_current_dir))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from backend.agent.utils.error_logger import log_error

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_MODELS_DEV_URL = "https://models.dev/api.json"
_SYNC_TTL_SECONDS = 86400  # 24 hours
_TIMEOUT_SECONDS = 30


# ---------------------------------------------------------------------------
# Database helpers
# ---------------------------------------------------------------------------

def _db_path() -> str:
    """Return the agent SQLite database path.

    Returns:
        Absolute path to ``agent.db``.
    """
    from backend.agent.session import _DB_PATH

    return _DB_PATH


def _connect() -> sqlite3.Connection | None:
    """Open a short-lived connection to the agent DB.

    Returns:
        A new ``sqlite3.Connection``, or ``None`` on failure.
    """
    try:
        conn = sqlite3.connect(_db_path(), check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=5000")
        from backend.agent.ddl_setup import setup_database

        setup_database(conn)
        return conn
    except Exception as e:
        log_error(str(e), source="model_catalog.py:_connect")
        logger.error("Could not open agent DB for model catalog: %s", e)
        return None


# ---------------------------------------------------------------------------
# TTL check
# ---------------------------------------------------------------------------

def should_sync(provider: str) -> bool:
    """Check whether the catalog for a provider needs refreshing.

    Uses the ``config_kv`` table to store the last sync timestamp per
    provider (key: ``catalog_sync_{provider}``).

    Args:
        provider: Provider name (e.g. ``"groq"``).

    Returns:
        ``True`` if the catalog is stale or missing.
    """
    conn = _connect()
    if conn is None:
        return True
    try:
        row = conn.execute(
            "SELECT value FROM config_kv WHERE key = ?",
            (f"catalog_sync_{provider.lower()}",),
        ).fetchone()
        if row is None:
            return True
        last_sync = float(row["value"])
        return (time.time() - last_sync) > _SYNC_TTL_SECONDS
    except Exception:
        return True
    finally:
        conn.close()


def _set_sync_timestamp(provider: str) -> None:
    """Record the current time as last sync for a provider.

    Args:
        provider: Provider name.
    """
    conn = _connect()
    if conn is None:
        return
    try:
        with conn:
            conn.execute(
                """INSERT INTO config_kv (key, value)
                   VALUES (?, ?)
                   ON CONFLICT(key) DO UPDATE SET value = excluded.value""",
                (f"catalog_sync_{provider.lower()}", str(time.time())),
            )
    except Exception as e:
        log_error(str(e), source="model_catalog.py:_set_sync_timestamp")
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Fetch from models.dev
# ---------------------------------------------------------------------------

def _fetch_models_dev() -> dict[str, Any]:
    """Download the full catalog from models.dev.

    Returns:
        The parsed JSON dict (provider → data).
    """
    import requests

    resp = requests.get(
        _MODELS_DEV_URL,
        headers={"User-Agent": "synapseForge/1.0"},
        timeout=_TIMEOUT_SECONDS,
    )
    resp.raise_for_status()
    return resp.json()


def _extract_provider_models(catalog: dict, provider: str) -> list[dict]:
    """Extract model entries for a specific provider from the catalog.

    Args:
        catalog: The full models.dev catalog.
        provider: Provider ID (e.g. ``"groq"``).

    Returns:
        List of model dicts ready for DB insertion.
    """
    provider_data = catalog.get(provider)
    if not provider_data:
        return []

    provider_api = provider_data.get("api")
    provider_npm = provider_data.get("npm")
    models_raw = provider_data.get("models") or {}
    now = datetime.now(timezone.utc).isoformat()
    rows: list[dict] = []

    for model_id, model_data in models_raw.items():
        if not isinstance(model_data, dict):
            continue

        limit = model_data.get("limit") or {}
        cost = model_data.get("cost")
        modalities = model_data.get("modalities") or {}
        reasoning_opts = model_data.get("reasoning_options") or []

        rows.append({
            "provider": provider,
            "model_id": model_id,
            "name": model_data.get("name"),
            "description": model_data.get("description"),
            "family": model_data.get("family"),
            "context_window": limit.get("context"),
            "input_limit": limit.get("input"),
            "output_limit": limit.get("output"),
            "reasoning": 1 if model_data.get("reasoning") else 0,
            "reasoning_options": json.dumps(reasoning_opts) if reasoning_opts else None,
            "tool_call": 1 if model_data.get("tool_call") else 0,
            "attachment": 1 if model_data.get("attachment") else 0,
            "temperature": 1 if model_data.get("temperature") else 0,
            "structured_output": 1 if model_data.get("structured_output") else 0,
            "modalities_input": json.dumps(modalities.get("input")) if modalities.get("input") else None,
            "modalities_output": json.dumps(modalities.get("output")) if modalities.get("output") else None,
            "cost_input": cost.get("input") if cost else None,
            "cost_output": cost.get("output") if cost else None,
            "cost_cache_read": cost.get("cache_read") if cost else None,
            "cost_cache_write": cost.get("cache_write") if cost else None,
            "open_weights": 1 if model_data.get("open_weights") else 0,
            "status": model_data.get("status"),
            "api": provider_api,
            "npm": provider_npm,
            "updated_at": now,
        })

    return rows


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def sync_catalog(provider: str) -> dict:
    """Fetch models.dev and upsert models for a provider into the DB.

    Rate-limited to once every 24 hours per provider.

    Args:
        provider: Provider ID (e.g. ``"groq"``, ``"google"``, ``"openrouter"``).

    Returns:
        ``{"status": "success", "models": count}`` or
        ``{"status": "error", "message": ...}``.
    """
    provider = (provider or "").strip().lower()
    if not provider:
        return {"status": "error", "message": "Provider is empty."}

    if not should_sync(provider):
        logger.debug("Catalog for '%s' is fresh, skipping sync.", provider)
        return {"status": "success", "message": "Catalog is fresh.", "models": 0}

    try:
        catalog = _fetch_models_dev()
    except Exception as e:
        log_error(str(e), source="model_catalog.py:sync_catalog(fetch)")
        return {"status": "error", "message": f"Could not fetch models.dev: {e}"}

    rows = _extract_provider_models(catalog, provider)
    if not rows:
        return {
            "status": "error",
            "message": f"Provider '{provider}' not found in models.dev or has no models.",
        }

    conn = _connect()
    if conn is None:
        return {"status": "error", "message": "Could not open database."}

    try:
        with conn:
            conn.executemany(
                """INSERT INTO model_catalog
                   (provider, model_id, name, description, family,
                    context_window, input_limit, output_limit,
                    reasoning, reasoning_options,
                    tool_call, attachment, temperature, structured_output,
                    modalities_input, modalities_output,
                    cost_input, cost_output, cost_cache_read, cost_cache_write,
                    open_weights, status, api, npm, updated_at)
                   VALUES
                   (:provider, :model_id, :name, :description, :family,
                    :context_window, :input_limit, :output_limit,
                    :reasoning, :reasoning_options,
                    :tool_call, :attachment, :temperature, :structured_output,
                    :modalities_input, :modalities_output,
                    :cost_input, :cost_output, :cost_cache_read, :cost_cache_write,
                    :open_weights, :status, :api, :npm, :updated_at)
                   ON CONFLICT(provider, model_id) DO UPDATE SET
                       name = excluded.name,
                       description = excluded.description,
                       family = excluded.family,
                       context_window = excluded.context_window,
                       input_limit = excluded.input_limit,
                       output_limit = excluded.output_limit,
                       reasoning = excluded.reasoning,
                       reasoning_options = excluded.reasoning_options,
                       tool_call = excluded.tool_call,
                       attachment = excluded.attachment,
                       temperature = excluded.temperature,
                       structured_output = excluded.structured_output,
                       modalities_input = excluded.modalities_input,
                       modalities_output = excluded.modalities_output,
                       cost_input = excluded.cost_input,
                       cost_output = excluded.cost_output,
                       cost_cache_read = excluded.cost_cache_read,
                       cost_cache_write = excluded.cost_cache_write,
                       open_weights = excluded.open_weights,
                       status = excluded.status,
                       api = excluded.api,
                       npm = excluded.npm,
                       updated_at = excluded.updated_at""",
                rows,
            )
        _set_sync_timestamp(provider)
        logger.info(
            "Synced %d model(s) for provider '%s' from models.dev.",
            len(rows),
            provider,
        )
        return {"status": "success", "models": len(rows)}
    except Exception as e:
        log_error(str(e), source="model_catalog.py:sync_catalog(insert)")
        return {"status": "error", "message": f"Database error: {e}"}
    finally:
        conn.close()


def get_models(provider: str) -> list[str]:
    """Return the list of model IDs for a provider from the catalog.

    Args:
        provider: Provider name (e.g. ``"groq"``).

    Returns:
        Sorted list of model ID strings. Empty if not found.
    """
    conn = _connect()
    if conn is None:
        return []
    try:
        rows = conn.execute(
            "SELECT model_id FROM model_catalog WHERE provider = ? ORDER BY model_id",
            (provider.strip().lower(),),
        ).fetchall()
        return [row["model_id"] for row in rows]
    except Exception as e:
        log_error(str(e), source="model_catalog.py:get_models")
        return []
    finally:
        conn.close()


def get_model(provider: str, model_id: str) -> dict[str, Any] | None:
    """Return full details for a specific model from the catalog.

    Args:
        provider: Provider name.
        model_id: Model ID (e.g. ``"openai/gpt-oss-120b"``).

    Returns:
        Dict with all model fields, or ``None`` if not found.
    """
    conn = _connect()
    if conn is None:
        return None
    try:
        row = conn.execute(
            "SELECT * FROM model_catalog WHERE provider = ? AND model_id = ?",
            (provider.strip().lower(), model_id),
        ).fetchone()
        if row is None:
            return None
        return dict(row)
    except Exception as e:
        log_error(str(e), source="model_catalog.py:get_model")
        return None
    finally:
        conn.close()


def get_context_window(provider: str, model_id: str) -> int | None:
    """Return the context window for a model.

    Args:
        provider: Provider name.
        model_id: Model ID.

    Returns:
        Context window in tokens, or ``None`` if unknown.
    """
    model = get_model(provider, model_id)
    if model is None:
        return None
    cw = model.get("context_window")
    return int(cw) if cw else None


def get_reasoning_options(provider: str, model_id: str) -> dict:
    """Return reasoning capabilities for a model.

    Translates the models.dev ``reasoning_options`` array into the format
    the frontend expects:

    - ``reasoning_supported``: bool | None
    - ``reasoning_options``: list of ``{"value": ..., "label": ...}``
    - ``reasoning_type``: ``"effort_levels"`` | ``"budget_tokens"`` |
      ``"toggle"`` | ``"boolean"``

    Args:
        provider: Provider name.
        model_id: Model ID.

    Returns:
        Dict with reasoning capability data.
    """
    result = {
        "reasoning_supported": None,
        "reasoning_options": [],
        "reasoning_type": None,
    }

    model = get_model(provider, model_id)
    if model is None:
        return result

    reasoning = model.get("reasoning")
    if not reasoning:
        result["reasoning_supported"] = False
        result["reasoning_options"] = [{"value": "default", "label": "Default"}]
        return result

    result["reasoning_supported"] = True
    raw_opts = model.get("reasoning_options")
    if not raw_opts:
        result["reasoning_options"] = [{"value": "default", "label": "Default"}]
        return result

    try:
        opts = json.loads(raw_opts) if isinstance(raw_opts, str) else raw_opts
    except (json.JSONDecodeError, TypeError):
        opts = []

    if not opts:
        result["reasoning_options"] = [{"value": "default", "label": "Default"}]
        return result

    effort_labels = {
        "max": "Máximo",
        "xhigh": "Muy alto",
        "high": "Alto",
        "medium": "Medio",
        "low": "Bajo",
        "minimal": "Mínimo",
        "none": "Ninguno",
    }

    for opt in opts:
        opt_type = opt.get("type")

        if opt_type == "effort":
            result["reasoning_type"] = "effort_levels"
            values = opt.get("values") or []
            result["reasoning_options"].append(
                {"value": "default", "label": "Default"}
            )
            for v in values:
                result["reasoning_options"].append({
                    "value": v,
                    "label": effort_labels.get(v, v),
                })

        elif opt_type == "budget_tokens":
            result["reasoning_type"] = "budget_tokens"
            min_tok = opt.get("min")
            max_tok = opt.get("max")
            result["reasoning_options"].append(
                {"value": "default", "label": "Default (dinámico)"}
            )
            if min_tok == 0 or min_tok is None:
                result["reasoning_options"].append(
                    {"value": "0", "label": "Desactivado"}
                )
            budget_values = [128, 1024, 2048, 4096, 8192, 16384, 32768]
            for b in budget_values:
                if max_tok and b > max_tok:
                    break
                if min_tok and b < min_tok:
                    continue
                label = f"{b // 1024}K tokens" if b >= 1024 else f"{b} tokens"
                result["reasoning_options"].append({"value": str(b), "label": label})

        elif opt_type == "toggle":
            if result["reasoning_type"] is None:
                result["reasoning_type"] = "boolean"
            result["reasoning_options"].append(
                {"value": "default", "label": "Default"}
            )
            result["reasoning_options"].append(
                {"value": "on", "label": "Activado"}
            )
            result["reasoning_options"].append(
                {"value": "off", "label": "Desactivado"}
            )

    if not result["reasoning_type"]:
        result["reasoning_type"] = "boolean"

    if not result["reasoning_options"]:
        result["reasoning_options"] = [{"value": "default", "label": "Default"}]

    return result


def list_configured_providers() -> list[str]:
    """Return provider IDs that have models in the catalog.

    Returns:
        Sorted list of provider ID strings.
    """
    conn = _connect()
    if conn is None:
        return []
    try:
        rows = conn.execute(
            "SELECT DISTINCT provider FROM model_catalog ORDER BY provider"
        ).fetchall()
        return [row["provider"] for row in rows]
    except Exception as e:
        log_error(str(e), source="model_catalog.py:list_configured_providers")
        return []
    finally:
        conn.close()
