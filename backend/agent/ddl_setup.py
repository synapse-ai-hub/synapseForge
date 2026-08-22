"""Database schema setup for the agent (no migrations).

Creates the ``sessions``, ``messages`` and ``config_kv`` tables using
``CREATE TABLE IF NOT EXISTS`` so the operation is idempotent and can be
called once at startup without per-session overhead.

NOTE: This module intentionally contains NO migration logic. When the
schema changes, the old database file is deleted and recreated from
scratch — the ``IF NOT EXISTS`` guard then simply creates the new tables.
"""

from __future__ import annotations

import sqlite3


def setup_database(conn: sqlite3.Connection) -> None:
    """Create all agent tables on the given connection.

    Idempotent: uses ``CREATE TABLE IF NOT EXISTS`` so calling it repeatedly
    (or after the tables already exist) adds no latency and recreates nothing.

    Args:
        conn: An open ``sqlite3.Connection`` (already configured with PRAGMAs).
    """
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT UNIQUE NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            metadata TEXT,
            title TEXT,
            parent_id TEXT,
            FOREIGN KEY (parent_id) REFERENCES sessions(session_id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT NOT NULL,
            role TEXT NOT NULL,
            content TEXT,
            reasoning TEXT,
            tool_calls TEXT,
            tool_results TEXT,
            status TEXT,
            message TEXT,
            prompt_tokens INTEGER,
            completion_tokens INTEGER,
            total_tokens INTEGER,
            total_time REAL,
            tool_call_id TEXT,
            tool_name TEXT,
            turn_number INTEGER,
            step INTEGER DEFAULT 0,
            created_at TEXT NOT NULL,
            FOREIGN KEY (session_id) REFERENCES sessions(session_id) ON DELETE CASCADE
        );

        CREATE INDEX IF NOT EXISTS idx_messages_session_id ON messages(session_id);
        CREATE INDEX IF NOT EXISTS idx_sessions_parent_id ON sessions(parent_id);

        CREATE TABLE IF NOT EXISTS config_kv (
            key TEXT PRIMARY KEY,
            value TEXT
        );

        CREATE TABLE IF NOT EXISTS providers (
            provider TEXT PRIMARY KEY,
            label TEXT NOT NULL,
            models TEXT,
            updated_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS provider_api_keys (
            provider TEXT PRIMARY KEY,
            api_key_encrypted TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS error_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT,
            parent_id TEXT,
            turn_number INTEGER,
            exception TEXT NOT NULL,
            source TEXT,
            created_at TEXT NOT NULL
        );

        CREATE INDEX IF NOT EXISTS idx_error_log_session_id ON error_log(session_id);
        CREATE INDEX IF NOT EXISTS idx_error_log_created_at ON error_log(created_at);

        CREATE TABLE IF NOT EXISTS context_files (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            filename TEXT NOT NULL,
            content TEXT NOT NULL,
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS attachments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT NOT NULL,
            turn_number INTEGER NOT NULL,
            file_name TEXT NOT NULL,
            size INTEGER,
            content BLOB,
            created_at TEXT NOT NULL,
            FOREIGN KEY (session_id) REFERENCES sessions(session_id) ON DELETE CASCADE
        );

        CREATE INDEX IF NOT EXISTS idx_attachments_session_turn
            ON attachments(session_id, turn_number);
        """
    )
