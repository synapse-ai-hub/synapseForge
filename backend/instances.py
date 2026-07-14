"""Singleton module that initializes and exports Agent and Tools instances.

Instances are created at module-import time (same pattern as ProspectingAgent),
so they are ready as soon as ``backend.instances`` is imported. The model is
resolved separately via the config endpoint (``/api/config/models``) at
application startup — never directly from a helper at import time.
"""

from __future__ import annotations

import logging
import os
import sys

from dotenv import load_dotenv

# ---------------------------------------------------------------------------
# Ensure the project root is in sys.path so absolute imports (backend.*)
# resolve correctly regardless of how the file is invoked.
# instances.py is at backend/ -> need 2 dirname() calls to reach root.
# ---------------------------------------------------------------------------
_current_dir = os.path.dirname(os.path.abspath(__file__))
_project_root = os.path.dirname(_current_dir)
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from backend.agent.session import SessionManager
from backend.agent.context import ContextManager
from backend.agent.agent import Agent
from backend.agent.tools import Tools

__all__ = [
    "agent",
    "tools",
    "session_manager",
    "context_manager",
]

_logger = logging.getLogger(__name__)

load_dotenv()

# ---------------------------------------------------------------------------
# Module-level singletons (created on import — no global, no async init).
# ---------------------------------------------------------------------------
agent = Agent()

# Create the canonical Tools singleton and inject it into the agent so that
# both ``agent.tools`` and ``instances.tools`` reference the same object.
tools = Tools()


session_manager = SessionManager()
context_manager = ContextManager()

_logger.info("Agent and Tools initialized successfully")
_logger.info("  Provider: %s", os.getenv("PROVIDER", "API").strip().upper())

