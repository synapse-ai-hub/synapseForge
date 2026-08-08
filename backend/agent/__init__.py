"""Agent loop package for the <descripcion>Nombre del proyecto</descripcion>.

Contains the while(true) agent loop, SQLite session persistence,
context management, and compaction configuration.
"""

from __future__ import annotations

import logging
import os 
import sys

_current_dir = os.path.dirname(os.path.abspath(__file__))
_project_root = os.path.dirname(os.path.dirname(_current_dir))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

# Register custom SUBAGENT log level (must be imported early, before any usage)
try:
    from backend.agent.utils.subagent_logger import SUBAGENT_LEVEL as _SUBAGENT_LEVEL
except ImportError:
    pass

from backend.agent.utils.error_logger import log_error

logger = logging.getLogger(__name__)

# Lazy imports — submodules are created in separate tasks
try:
    from backend.agent.utils.config import CompactionConfig, SessionContext
except ImportError as e:
    log_error(str(e), source="agent/__init__.py(config)")
    CompactionConfig = None  # type: ignore
    SessionContext = None  # type: ignore
    logger.debug("backend.agent.config not yet available")

try:
    from backend.agent.session import SessionManager
except ImportError as e:
    log_error(str(e), source="agent/__init__.py(session)")
    SessionManager = None  # type: ignore
    logger.debug("backend.agent.session not yet available")

try:
    from backend.agent.context import ContextManager
except ImportError as e:
    log_error(str(e), source="agent/__init__.py(context)")
    ContextManager = None  # type: ignore
    logger.debug("backend.agent.context not yet available")

try:
    from backend.agent.loop import AgentLoop
except ImportError as e:
    log_error(str(e), source="agent/__init__.py(loop)")
    AgentLoop = None  # type: ignore
    logger.debug("backend.agent.loop not yet available")

__all__ = [
    "CompactionConfig",
    "SessionContext",
    "SessionManager",
    "ContextManager",
    "AgentLoop",
]
