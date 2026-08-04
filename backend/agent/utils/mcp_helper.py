"""MCP (Model Context Protocol) helper.

Loads MCP server configurations from ``mcp.json`` (direct array)
and provides functions to discover tools and execute tool calls over
the MCP protocol using the official ``mcp`` SDK (same approach as opencode).

Usage::

    from backend.utils.mcp_helper import get_mcp_tools, execute_mcp_tool

    # Get all MCP tools as function schemas (works for both providers)
    mcp_tools = get_mcp_tools()
    # mcp_tools -> [{"name": ..., "description": ..., "input_schema": ...}, ...]

    # Execute a tool
    result = await execute_mcp_tool("mssql", "execute_query", {"sql": "SELECT 1"})
"""

from __future__ import annotations

import asyncio
import logging
import os
import sys
from typing import Any

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

_current_dir = os.path.dirname(os.path.abspath(__file__))
_project_root = os.path.dirname(os.path.dirname(_current_dir))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from backend.agent.config_dir import load_mcp_servers, save_mcp_servers
from backend.agent.utils.error_logger import log_error

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Config loader
# ---------------------------------------------------------------------------

McpServerConfig = dict[str, Any]
"""Structure of a single MCP server entry from ``mcp.json`` (array).

Keys: ``label``, ``transport`` (``"stdio"`` or ``"http"``),
``command`` (string or list), ``args``, ``env``/``environment``,
``description``, ``server_url``, ``headers``,
``oauth``, ``disabled``, ``timeout``.
"""


def load_mcp_config() -> list[McpServerConfig]:
    """Load MCP server configurations from ``mcp.json`` (direct array).

    Returns:
        List of MCP server config dicts, or empty list if not configured.
    """
    servers = load_mcp_servers()
    if not servers:
        logger.info("No MCP servers found in mcp.json — skipping MCP config load.")
        return []

    logger.info("Loaded %d MCP server(s) from mcp.json", len(servers))
    return servers


# ---------------------------------------------------------------------------
# stdio transport helpers (official MCP SDK)
# ---------------------------------------------------------------------------


def _build_stdio_params(config: McpServerConfig) -> StdioServerParameters:
    """Build ``StdioServerParameters`` from an MCP server config.

    Args:
        config: MCP server config dict.

    Returns:
        ``StdioServerParameters`` ready for ``stdio_client``.
    """
    cmd_raw = config.get("command", [])
    if isinstance(cmd_raw, list):
        cmd = cmd_raw
    else:
        cmd = [cmd_raw] + config.get("args", [])
    env = {**os.environ, **config.get("environment", config.get("env", {}))}
    return StdioServerParameters(command=cmd[0], args=cmd[1:], env=env)


def _server_timeout(config: McpServerConfig, default: float = 10.0) -> float:
    """Return the per-server connection timeout in seconds.

    Args:
        config: MCP server config dict.
        default: Fallback timeout when the config has no ``timeout``.

    Returns:
        Timeout in seconds.
    """
    try:
        return float(config.get("timeout", default))
    except (TypeError, ValueError):
        return default


async def _discover_server_tools(config: McpServerConfig) -> list[Any]:
    """Discover tools from a single stdio MCP server using the official SDK.

    Args:
        config: MCP server config dict.

    Returns:
        List of ``mcp.types.Tool`` objects.

    Raises:
        asyncio.TimeoutError: If the server does not respond in time.
    """
    timeout = _server_timeout(config)
    params = _build_stdio_params(config)
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await asyncio.wait_for(session.initialize(), timeout=timeout)
            result = await asyncio.wait_for(session.list_tools(), timeout=timeout)
            return result.tools


async def _call_server_tool(
    config: McpServerConfig, name: str, arguments: dict[str, Any]
) -> Any:
    """Call a tool on a single stdio MCP server using the official SDK.

    Args:
        config: The MCP server config dict.
        name: Tool name.
        arguments: Tool arguments dict.

    Returns:
        The ``CallToolResult`` from the server.

    Raises:
        asyncio.TimeoutError: If the server does not respond in time.
    """
    timeout = _server_timeout(config)
    params = _build_stdio_params(config)
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await asyncio.wait_for(session.initialize(), timeout=timeout)
            return await asyncio.wait_for(
                session.call_tool(name, arguments), timeout=timeout
            )


# ---------------------------------------------------------------------------
# Tool-to-server mapping (populated by get_mcp_tools)
# ---------------------------------------------------------------------------

_mcp_tool_to_server: dict[str, str] = {}
"""Maps MCP tool name → server label for dispatch in ``_execute_tool``."""


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def _mcp_tool_to_function_schema(mcp_tool: Any) -> dict[str, Any]:
    """Convert an MCP tool definition to a function-call schema.

    Accepts both ``mcp.types.Tool`` objects (from the SDK) and plain dicts.

    Args:
        mcp_tool: MCP tool definition.

    Returns:
        Function schema ready for the tools registry.
    """
    if isinstance(mcp_tool, dict):
        name = mcp_tool.get("name", "")
        description = mcp_tool.get("description", "")
        input_schema = mcp_tool.get("inputSchema", {})
    else:
        name = getattr(mcp_tool, "name", "")
        description = getattr(mcp_tool, "description", "") or ""
        input_schema = getattr(mcp_tool, "inputSchema", {}) or {}
    return {
        "type": "function",
        "function": {
            "name": name,
            "description": description,
            "parameters": input_schema or {"type": "object", "properties": {}},
        },
    }


def _server_has_http_url(server: McpServerConfig) -> bool:
    """Check if server config has a valid HTTP/SSE URL."""
    url = server.get("server_url") or server.get("url")
    if not url:
        return False
    try:
        from urllib.parse import urlparse

        parsed = urlparse(url)
        return parsed.scheme in ("http", "https")
    except Exception:
        return False


def _mcp_tool_to_groq_entry(mcp_tool: Any, server: McpServerConfig) -> dict[str, Any]:
    """Convert an MCP tool definition to a Groq native MCP entry.

    Only works for HTTP/SSE-based MCP servers that Groq can reach.

    Args:
        mcp_tool: MCP tool definition (not used directly for Groq).
        server: MCP server config with HTTP URL.

    Returns:
        Groq MCP entry ``{"type": "mcp", "server_label", "server_url", ...}``.
    """
    url = server.get("server_url") or server.get("url")
    return {
        "type": "mcp",
        "server_label": server.get("label", "unknown"),
        "server_url": url,
        "headers": server.get("headers", {}),
        "require_approval": server.get("require_approval", "never"),
    }


def get_mcp_tools_groq() -> list[dict[str, Any]]:
    """Get MCP tool entries in Groq-compatible format.

    Only returns entries for HTTP/SSE-based MCP servers (``transport: "http"``),
    which Groq can orchestrate server-side.

    Returns:
        List of ``{"type": "mcp", "server_label", ...}`` entries.
    """
    servers = load_mcp_config()
    groq_entries: list[dict[str, Any]] = []
    for server in servers:
        if _server_has_http_url(server):
            groq_entries.append(_mcp_tool_to_groq_entry({}, server))
    return groq_entries


def get_mcp_tools_ollama() -> list[dict[str, Any]]:
    """Discover tools from all MCP servers and wrap as function schemas.

    Uses the official MCP SDK with a per-server timeout. A server that
    fails or times out is isolated — it is logged and skipped, and the
    rest of the startup continues normally.

    Returns:
        List of function schemas ready for ``tools_registry``.
    """
    global _mcp_tool_to_server
    servers = load_mcp_config()
    function_tools: list[dict[str, Any]] = []

    async def _discover_all() -> None:
        for server in servers:
            label = server.get("label", "unknown")
            try:
                tools = await _discover_server_tools(server)
                for tool in tools:
                    function_tools.append(_mcp_tool_to_function_schema(tool))
                    _mcp_tool_to_server[tool.name] = label
                logger.info("MCP '%s' — discovered %d tool(s)", label, len(tools))
            except Exception as exc:
                log_error(str(exc), source="mcp_helper.py:get_mcp_tools")
                logger.warning("MCP '%s' — failed to discover tools: %s", label, exc)

    try:
        asyncio.run(_discover_all())
    except Exception as exc:
        log_error(str(exc), source="mcp_helper.py:get_mcp_tools")

    return function_tools


def get_mcp_tools() -> list[dict[str, Any]]:
    """Get all MCP tools wrapped as function schemas (universal).

    Works for both providers by wrapping stdio MCP tools as
    ``"type": "function"`` schemas. This is the recommended approach
    for local MCP servers like MSSQL.

    Returns:
        List of function schemas ready for ``tools_registry``.
    """
    return get_mcp_tools_ollama()


def is_mcp_tool(tool_name: str) -> bool:
    """Check if *tool_name* belongs to an MCP server.

    Args:
        tool_name: Tool name to check.

    Returns:
        ``True`` if the tool is managed by an MCP server.
    """
    return tool_name in _mcp_tool_to_server


async def execute_mcp_tool(tool_name: str, arguments: dict[str, Any]) -> Any:
    """Execute a tool on the MCP server that owns it.

    Resolves the server label from the tool-to-server mapping
    (populated by ``get_mcp_tools_ollama``), connects, calls the
    tool, and returns the result.

    Args:
        tool_name: MCP tool name (e.g. ``"execute_query"``).
        arguments: Tool arguments dict.

    Returns:
        Tool result content (list of content items), or raises on error.

    Raises:
        ValueError: If the tool is not registered in any MCP server.
    """
    label = _mcp_tool_to_server.get(tool_name)
    if label is None:
        raise ValueError(f"Tool '{tool_name}' is not registered in any MCP server")

    servers = load_mcp_config()
    config = next((s for s in servers if s.get("label") == label), None)
    if config is None:
        raise ValueError(
            f"MCP server '{label}' (for tool '{tool_name}') not found in config"
        )

    result = await _call_server_tool(config, tool_name, arguments)
    return result.content


# ---------------------------------------------------------------------------
# Health check / Status API
# ---------------------------------------------------------------------------


class McpServerStatus:
    """MCP server status constants (matching opencode's Status type)."""

    CONNECTED = "connected"
    DISABLED = "disabled"
    FAILED = "failed"
    NEEDS_AUTH = "needs_auth"
    NEEDS_CLIENT_REGISTRATION = "needs_client_registration"


async def check_mcp_server_health(label: str, timeout: float = 10.0) -> dict[str, Any]:
    """Check health of a single MCP server by label.

    Args:
        label: Server label from mcp.json.
        timeout: Connection timeout in seconds.

    Returns:
        Status dict with keys: label, status, tools_count, tools, error.
    """
    servers = load_mcp_servers()
    config = next((s for s in servers if s.get("label") == label), None)
    if not config:
        return {
            "label": label,
            "status": McpServerStatus.FAILED,
            "error": f"Server '{label}' not found in mcp.json",
        }

    config_with_label = dict(config)
    config_with_label["label"] = label

    if config_with_label.get("disabled") or config_with_label.get("enabled") is False:
        return {
            "label": label,
            "status": McpServerStatus.DISABLED,
            "tools_count": 0,
        }

    # Check if HTTP/SSE server
    if _server_has_http_url(config_with_label):
        return await _check_http_server_health(config_with_label, timeout)

    # STDIO server
    return await _check_stdio_server_health(config_with_label, timeout)


async def _check_stdio_server_health(
    config: McpServerConfig, timeout: float
) -> dict[str, Any]:
    """Check health of a stdio-based MCP server using the official SDK."""
    label = config.get("label", "unknown")
    try:
        params = _build_stdio_params(config)
        async with stdio_client(params) as (read, write):
            async with ClientSession(read, write) as session:
                await asyncio.wait_for(session.initialize(), timeout=timeout)
        return {
            "label": label,
            "status": McpServerStatus.CONNECTED,
        }
    except Exception as exc:
        return {
            "label": label,
            "status": McpServerStatus.FAILED,
            "error": str(exc),
        }


async def _check_http_server_health(
    config: McpServerConfig, timeout: float
) -> dict[str, Any]:
    """Check health of an HTTP/SSE-based MCP server."""
    label = config.get("label", "unknown")
    url = config.get("server_url") or config.get("url")
    if not url:
        return {
            "label": label,
            "status": McpServerStatus.FAILED,
            "error": "No server_url configured",
        }

    try:
        import httpx

        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.get(url)
            if response.status_code < 500:
                return {
                    "label": label,
                    "status": McpServerStatus.CONNECTED,
                    "tools_count": 0,
                    "note": "HTTP endpoint reachable (full MCP handshake not performed)",
                }
            else:
                return {
                    "label": label,
                    "status": McpServerStatus.FAILED,
                    "error": f"HTTP {response.status_code}",
                }
    except Exception as exc:
        return {
            "label": label,
            "status": McpServerStatus.FAILED,
            "error": str(exc),
        }


async def check_all_mcp_servers_health(timeout: float = 10.0) -> list[dict[str, Any]]:
    """Check health of all configured MCP servers.

    Args:
        timeout: Connection timeout per server in seconds.

    Returns:
        List of status dicts for each server.
    """
    servers = load_mcp_servers()
    results = []

    for server in servers:
        label = server.get("label", "unknown")
        result = await check_mcp_server_health(label, timeout)
        results.append(result)

    return results