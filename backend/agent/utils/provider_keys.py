"""Encrypted storage for provider API keys in the agent SQLite database.

Keys are stored encrypted (Fernet, reversible) in the ``provider_api_keys``
table so they can be recovered to authenticate API calls, but never leave
the backend in plain text. The encryption secret is resolved as:

1. ``APP_SECRET_KEY`` environment variable (any passphrase; hashed with
   SHA-256 to derive a valid Fernet key).
2. Auto-generated Fernet key persisted in ``<config_dir>/.secret_key``
   on first use.

If neither is available (e.g. the generated file was deleted), stored
keys can no longer be decrypted and are reported as not configured.

Imported by ``backend/routes/config.py`` and ``backend/agent/agent.py``.
"""

from __future__ import annotations

import base64
import hashlib
import logging
import os
import sqlite3
import sys
from datetime import datetime, timezone
from typing import Any

# ---------------------------------------------------------------------------
# Ensure the project root is in sys.path for absolute imports
# ---------------------------------------------------------------------------
_current_dir = os.path.dirname(os.path.abspath(__file__))
_project_root = os.path.dirname(os.path.dirname(_current_dir))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from backend.agent.utils.error_logger import log_error
from backend.utils.db import db_transaction, get_connection

logger = logging.getLogger(__name__)

_VALID_PROVIDERS = frozenset({"GROQ", "GOOGLE", "GEMINI"})
"""Providers whose API keys can be managed through this module."""

_fernet_cache: Any = None
"""Cached ``Fernet`` instance so the secret is resolved once per process."""


def _load_fernet() -> Any:
    """Return a ``Fernet`` instance, resolving the secret lazily.

    Resolution order:

    1. ``APP_SECRET_KEY`` env var → SHA-256 → URL-safe base64 Fernet key.
    2. Generated key persisted at ``<config_dir>/synapseForge/.secret_key``.

    Returns:
        A ``Fernet`` instance, or ``None`` if ``cryptography`` is missing.
    """
    global _fernet_cache
    if _fernet_cache is not None:
        return _fernet_cache
    try:
        from cryptography.fernet import Fernet
    except ImportError as e:
        log_error(str(e), source="provider_keys.py:_load_fernet(import)")
        logger.error("cryptography package is required for provider keys: %s", e)
        return None

    secret = os.getenv("APP_SECRET_KEY", "").strip()
    if secret:
        digest = hashlib.sha256(secret.encode("utf-8")).digest()
        _fernet_cache = Fernet(base64.urlsafe_b64encode(digest))
        return _fernet_cache

    # No APP_SECRET_KEY: use (or create) a locally persisted random key.
    try:
        from backend.agent.utils.config_dir import get_config_dir

        secret_file = get_config_dir() / ".secret_key"
        if secret_file.exists():
            raw = secret_file.read_text(encoding="utf-8").strip()
            if raw:
                _fernet_cache = Fernet(raw.encode("ascii"))
                return _fernet_cache
        key = Fernet.generate_key()
        secret_file.write_text(key.decode("ascii"), encoding="utf-8")
        _fernet_cache = Fernet(key)
        return _fernet_cache
    except Exception as e:
        log_error(str(e), source="provider_keys.py:_load_fernet(secret_file)")
        logger.error("Could not resolve provider-key secret: %s", e)
        return None


def _connect() -> sqlite3.Connection | None:
    """Open a short-lived connection to the agent DB and ensure the schema.

    Returns:
        A new ``sqlite3.Connection``, or ``None`` on failure.
    """
    try:
        conn = get_connection()
        from backend.agent.ddl_setup import setup_database

        setup_database(conn)
        return conn
    except Exception as e:
        log_error(str(e), source="provider_keys.py:_connect")
        logger.error("Could not open agent DB for provider keys: %s", e)
        return None


def save_key(provider: str, api_key: str) -> dict:
    """Encrypt and persist an API key for the given provider.

    Args:
        provider: One of ``GROQ``, ``GOOGLE``, ``GEMINI``.
        api_key: The plain-text API key (never stored in clear).

    Returns:
        Contract response ``{"status": "success"|"error", "message": ...}``.
    """
    provider_u = (provider or "").upper()
    if provider_u not in _VALID_PROVIDERS:
        return {"status": "error", "message": f"Provider inválido: '{provider}'."}
    if not api_key or not api_key.strip():
        return {"status": "error", "message": "La API key no puede estar vacía."}
    fernet = _load_fernet()
    if fernet is None:
        return {
            "status": "error",
            "message": "Cifrado no disponible (falta el paquete 'cryptography').",
        }
    try:
        encrypted = fernet.encrypt(api_key.strip().encode("utf-8")).decode("ascii")
        now = datetime.now(timezone.utc).isoformat()
        conn = _connect()
        if conn is None:
            return {"status": "error", "message": "No se pudo abrir la base de datos."}
        try:
            with conn:
                conn.execute(
                    """
                    INSERT INTO provider_api_keys (provider, api_key_encrypted, updated_at)
                    VALUES (?, ?, ?)
                    ON CONFLICT(provider) DO UPDATE SET
                        api_key_encrypted = excluded.api_key_encrypted,
                        updated_at = excluded.updated_at
                    """,
                    (provider_u, encrypted, now),
                )
        finally:
            conn.close()
        # Sync model catalog from models.dev for this provider.
        try:
            from backend.agent.utils.model_catalog import sync_catalog

            sync_catalog(provider_u.lower())
        except Exception as sync_err:
            # Sync failure is non-blocking: the key is already saved.
            log_error(str(sync_err), source="provider_keys.py:save_key:sync_catalog")
            logger.warning("Catalog sync failed for %s: %s", provider_u, sync_err)
        return {"status": "success", "message": f"API key de {provider_u} guardada."}
    except Exception as e:
        log_error(str(e), source="provider_keys.py:save_key")
        return {"status": "error", "message": f"Error guardando la API key: {e}"}


def get_key(provider: str) -> str | None:
    """Return the decrypted API key for a provider, or ``None``.

    Backend-only helper: the decrypted key must never be returned to the
    frontend.

    Args:
        provider: Provider name (case-insensitive).

    Returns:
        The plain-text API key, or ``None`` if not stored / undecryptable.
    """
    provider_u = (provider or "").upper()
    if provider_u not in _VALID_PROVIDERS:
        return None
    fernet = _load_fernet()
    if fernet is None:
        return None
    try:
        conn = _connect()
        if conn is None:
            return None
        try:
            row = conn.execute(
                "SELECT api_key_encrypted FROM provider_api_keys WHERE provider = ?",
                (provider_u,),
            ).fetchone()
        finally:
            conn.close()
        if row is None:
            return None
        key = fernet.decrypt(row["api_key_encrypted"].encode("ascii")).decode("utf-8")
        return key
    except Exception as e:
        log_error(str(e), source="provider_keys.py:get_key")
        return None


def delete_key(provider: str) -> dict:
    """Remove the stored API key for a provider.

    Args:
        provider: One of ``GROQ``, ``GOOGLE``, ``GEMINI``.

    Returns:
        Contract response ``{"status": "success"|"error", "message": ...}``.
    """
    provider_u = (provider or "").upper()
    if provider_u not in _VALID_PROVIDERS:
        return {"status": "error", "message": f"Provider inválido: '{provider}'."}
    try:
        conn = _connect()
        if conn is None:
            return {"status": "error", "message": "No se pudo abrir la base de datos."}
        try:
            with conn:
                cursor = conn.execute(
                    "DELETE FROM provider_api_keys WHERE provider = ?", (provider_u,)
                )
            deleted = cursor.rowcount > 0
            # Also delete the model catalog for this provider.
            if deleted:
                conn.execute(
                    "DELETE FROM model_catalog WHERE provider = ?",
                    (provider_u.lower(),),
                )
                conn.commit()
        finally:
            conn.close()
        message = (
            f"API key de {provider_u} eliminada."
            if deleted
            else f"No había API key guardada para {provider_u}."
        )
        return {"status": "success", "message": message}
    except Exception as e:
        log_error(str(e), source="provider_keys.py:delete_key")
        return {"status": "error", "message": f"Error eliminando la API key: {e}"}


def list_configured() -> list[dict[str, Any]]:
    """List which providers have an API key configured.

    Never includes the key material itself — only availability status.

    Returns:
        List of ``{"provider": str, "configured": bool}`` dicts, one entry
        per supported provider.
    """
    result: list[dict[str, Any]] = []
    for provider in sorted(_VALID_PROVIDERS):
        result.append({"provider": provider, "configured": get_key(provider) is not None})
    return result


def resolve_api_key(provider: str) -> str | None:
    """Resolve the effective API key for a provider.

    Keys are resolved **only** from the encrypted DB storage — environment
    variables are never consulted.

    Args:
        provider: Provider name (case-insensitive).

    Returns:
        The API key string, or ``None`` if none is stored.
    """
    return get_key(provider)


def validate_key(provider: str, api_key: str) -> dict:
    """Validate an API key against the provider's live API.

    The key is **not** persisted here — callers should only store it when
    this check succeeds.

    Args:
        provider: One of ``GROQ``, ``GOOGLE``, ``GEMINI``.
        api_key: The plain-text API key to verify.

    Returns:
        Contract response ``{"status": "success"|"error", "message": ...}``.
    """
    provider_u = (provider or "").upper()
    if provider_u not in _VALID_PROVIDERS:
        return {"status": "error", "message": f"Provider inválido: '{provider}'."}
    if not api_key or not api_key.strip():
        return {"status": "error", "message": "La API key no puede estar vacía."}
    key = api_key.strip()
    try:
        if provider_u == "GEMINI":
            # Validate by listing models via Google GenAI SDK (Gemini Embedding 2)
            try:
                from google import genai
                client = genai.Client(api_key=key)
                models = list(client.models.list())
                if not models:
                    return {
                        "status": "error",
                        "message": "API key de Gemini inválida o sin modelos disponibles.",
                    }
            except Exception as e:
                return {
                    "status": "error",
                    "message": f"API key de Gemini inválida: {e}",
                }
        elif provider_u == "GOOGLE":
            # Validate by listing models via Google GenAI API
            try:
                from google import genai
                client = genai.Client(api_key=key)
                models = list(client.models.list())
                if not models:
                    return {
                        "status": "error",
                        "message": "API key de Google inválida o sin modelos disponibles.",
                    }
            except Exception as e:
                return {
                    "status": "error",
                    "message": f"API key de Google inválida: {e}",
                }
        else:  # GROQ
            # Validate by listing models via Groq API
            import requests

            resp = requests.get(
                "https://api.groq.com/openai/v1/models",
                headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
                timeout=30,
            )
            if resp.status_code == 401:
                return {"status": "error", "message": "API key de Groq inválida."}
            resp.raise_for_status()
            data = resp.json()
            models = data.get("data", [])
            if not models:
                return {
                    "status": "error",
                    "message": "API key de Groq inválida o sin modelos disponibles.",
                }
        return {"status": "success", "message": f"API key de {provider_u} válida."}
    except Exception as e:
        log_error(str(e), source="provider_keys.py:validate_key")
        return {
            "status": "error",
            "message": f"No se pudo validar la API key de {provider_u}: {e}",
        }
