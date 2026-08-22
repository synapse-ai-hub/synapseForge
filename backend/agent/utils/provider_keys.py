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

logger = logging.getLogger(__name__)

_VALID_PROVIDERS = frozenset({"GROQ", "GOOGLE", "OPENROUTER"})
"""Providers whose API keys can be managed through this module."""

_fernet_cache: Any = None
"""Cached ``Fernet`` instance so the secret is resolved once per process."""


def _db_path() -> str:
    """Return the agent SQLite database path.

    Reuses the canonical path defined in :mod:`backend.agent.session` so
    both modules always point at the same database file.

    Returns:
        Absolute path to ``agent.db``.
    """
    from backend.agent.session import _DB_PATH

    return _DB_PATH


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

    Follows the same per-operation connection pattern as
    :class:`backend.agent.session.SessionManager`.

    Returns:
        A new ``sqlite3.Connection``, or ``None`` on failure.
    """
    try:
        conn = sqlite3.connect(_db_path(), check_same_thread=False)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=5000")
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
        provider: One of ``GROQ``, ``GOOGLE``, ``OPENROUTER``.
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
        return fernet.decrypt(row["api_key_encrypted"].encode("ascii")).decode("utf-8")
    except Exception as e:
        log_error(str(e), source="provider_keys.py:get_key")
        return None


def delete_key(provider: str) -> dict:
    """Remove the stored API key for a provider.

    Args:
        provider: One of ``GROQ``, ``GOOGLE``, ``OPENROUTER``.

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

    Priority: key stored (encrypted) in the DB first, then the
    corresponding environment variable as fallback.

    Args:
        provider: Provider name (case-insensitive).

    Returns:
        The API key string, or ``None`` if none is available.
    """
    stored = get_key(provider)
    if stored:
        return stored
    env_names = {
        "GROQ": "GROQ_API_KEY",
        "GOOGLE": "GOOGLE_API_KEY",
        "OPENROUTER": "OPENROUTER_API_KEY",
    }
    env_name = env_names.get((provider or "").upper())
    if env_name:
        return os.getenv(env_name)
    return None
