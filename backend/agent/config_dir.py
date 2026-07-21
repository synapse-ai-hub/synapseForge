"""Configuration directory management for synapseAgent.

Provides a single source of truth for the user config directory:
~/.config/synapseAgent/

Structure:
~/.config/synapseAgent/
├── skills/           # User skills (SKILL.md in subdirs)
├── tools/            # External tools (.py files)
├── agents/           # Agent definitions (.md files)
└── config.json       # Main config (MCP, UI prefs, etc.)
"""

from __future__ import annotations

import json
import logging
import os
import sys
from pathlib import Path
from typing import Any

_current_dir = os.path.dirname(os.path.abspath(__file__))
_project_root = os.path.dirname(os.path.dirname(_current_dir))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from backend.agent.utils.error_logger import log_error

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Config directory path
# ---------------------------------------------------------------------------

def get_config_dir() -> Path:
    """Return the synapseAgent config directory path.

    Creates the directory if it doesn't exist.

    Returns:
        Path to ~/.config/synapseAgent/ (consistent across Windows, Linux, macOS)
    """
    # Use ~/.config/synapseAgent on all platforms (like opencode)
    base = Path(os.getenv("XDG_CONFIG_HOME", Path.home() / ".config"))
    config_dir = base / "synapseAgent"
    config_dir.mkdir(parents=True, exist_ok=True)

    # Ensure subdirectories exist
    (config_dir / "skills").mkdir(exist_ok=True)
    (config_dir / "tools").mkdir(exist_ok=True)
    (config_dir / "agents").mkdir(exist_ok=True)

    return config_dir


def ensure_config_dir() -> Path:
    """Ensure config directory and subdirectories exist.

    Called at application startup.

    Returns:
        Path to the config directory.
    """
    return get_config_dir()


# ---------------------------------------------------------------------------
# Config file (config.json) helpers
# ---------------------------------------------------------------------------

_CONFIG_FILE = "config.json"


def _config_path() -> Path:
    return get_config_dir() / _CONFIG_FILE


def load_config() -> dict[str, Any]:
    """Load the main config.json file.

    Returns:
        Parsed config dict, or empty dict if file doesn't exist or is invalid.
    """
    path = _config_path()
    if not path.is_file():
        logger.info("No config.json found at %s, returning empty config", path)
        return {}

    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        logger.info("Loaded config from %s", path)
        return data
    except (json.JSONDecodeError, OSError) as e:
        log_error(str(e), source="config_dir.py:load_config")
        logger.warning("Failed to load config from %s: %s", path, e)
        return {}


def save_config(config: dict[str, Any]) -> bool:
    """Save the main config.json file.

    Args:
        config: Config dict to save.

    Returns:
        True on success, False on failure.
    """
    path = _config_path()
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=2, ensure_ascii=False)
        logger.info("Saved config to %s", path)
        return True
    except OSError as e:
        log_error(str(e), source="config_dir.py:save_config")
        logger.warning("Failed to save config to %s: %s", path, e)
        return False


def get_mcp_config() -> dict[str, Any]:
    """Get the MCP section from config.json.

    Returns:
        Dict with 'timeout' and 'servers' keys, or empty dict if not configured.
    """
    config = load_config()
    return config.get("mcp", {})


def set_mcp_config(mcp_config: dict[str, Any]) -> bool:
    """Update the MCP section in config.json.

    Args:
        mcp_config: Dict with 'timeout' and 'servers' keys.

    Returns:
        True on success.
    """
    config = load_config()
    config["mcp"] = mcp_config
    return save_config(config)


# ---------------------------------------------------------------------------
# Convenience paths for skills, tools, agents
# ---------------------------------------------------------------------------

def get_skills_dir() -> Path:
    """Return the skills directory path."""
    return get_config_dir() / "skills"


def get_tools_dir() -> Path:
    """Return the external tools directory path."""
    return get_config_dir() / "tools"


def get_agents_dir() -> Path:
    """Return the agents directory path."""
    return get_config_dir() / "agents"