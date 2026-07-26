"""MCP (Model Context Protocol) helper.

Loads MCP server configurations from ``config.json`` (mcp section)
and provides functions to discover tools and execute tool calls over
the MCP protocol (JSON-RPC over stdio).

Usage::

    from backend.utils.mcp_helper import get_mcp_tools, execute_mcp_tool

    # Get all MCP tools as function schemas (works for both providers)
    mcp_tools = get_mcp_tools()
    # mcp_tools -> [{"name": ..., "description": ..., "input_schema": ...}, ...]

    # Execute a tool
    result = await execute_mcp_tool("mssql", "execute_query", {"sql": "SELECT 1"})
"""

from __future__ import annotations

import json
import logging
import os
import subprocess
import sys
from typing import Any

_current_dir = os.path.dirname(os.path.abspath(__file__))
_project_root = os.path.dirname(os.path.dirname(_current_dir))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from backend.agent.config_dir import get_mcp_config
from backend.agent.utils.error_logger import log_error

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Config loader
# ---------------------------------------------------------------------------

McpServerConfig = dict[str, Any]
"""Structure of a single MCP server entry from ``config.json`` -> ``mcp.servers``.

Keys: ``label``, ``transport`` (``"stdio"`` or ``"http"``),
``command``, ``args``, ``env``, ``description``, ``server_url``, ``headers``,
``oauth``, ``disabled``, ``timeout``.
"""


def load_mcp_config() -> list[McpServerConfig]:
    """Load MCP server configurations from ``config.json`` (mcp section).

    Returns:
        List of MCP server config dicts, or empty list if not configured.
    """
    mcp_config = get_mcp_config()
    if not mcp_config:
        logger.info("No MCP config found in config.json — skipping MCP config load.")
        return []

    servers = mcp_config.get("servers", {})
    # Convert dict of servers to list, adding label to each
    server_list = []
    for label, config in servers.items():
        if config.get("disabled"):
            continue
        server_config = dict(config)
        server_config["label"] = label
        server_list.append(server_config)

    logger.info("Loaded %d MCP server(s) from config.json", len(server_list))
    return server_list


# ---------------------------------------------------------------------------
# JSON-RPC communication with stdio-based MCP servers
# ---------------------------------------------------------------------------

class McpConnection:
    """Manages a stdio connection to an MCP server process.

    Launches the subprocess once and keeps it alive for multiple
    JSON-RPC requests (``tools/list``, ``tools/call``, etc.).

    Args:
        config: MCP server configuration dict (from ``mcp.json``).
    """

    def __init__(self, config: McpServerConfig) -> None:
        self._config = config
        self._process: subprocess.Popen | None = None
        self._request_id = 0

    # ------------------------------------------------------------------
    # Context manager (auto start / stop)
    # ------------------------------------------------------------------

    async def __aenter__(self) -> "McpConnection":
        self.start()
        return self

    async def __aexit__(self, *args: Any) -> None:
        self.stop()

    # ------------------------------------------------------------------
    # Process lifecycle
    # ------------------------------------------------------------------

    def start(self) -> None:
        """Launch the MCP server subprocess."""
        if self._process is not None:
            return

        cmd = [self._config["command"]] + self._config.get("args", [])
        env = os.environ.copy()
        env.update(self._config.get("env", {}))

        logger.info("Starting MCP server: %s", " ".join(cmd))
        self._process = subprocess.Popen(
            cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=env,
            text=True,
            bufsize=1,  # line-buffered
        )

    def stop(self) -> None:
        """Terminate the MCP server subprocess."""
        if self._process is None:
            return
        logger.info("Stopping MCP server: %s", self._config.get("label", "unknown"))
        self._process.terminate()
        try:
            self._process.wait(timeout=5)
        except subprocess.TimeoutExpired as e:
            log_error(str(e), source="mcp_helper.py:McpConnection.stop")
            self._process.kill()
            self._process.wait()
        self._process = None

    # ------------------------------------------------------------------
    # JSON-RPC calls
    # ------------------------------------------------------------------

    def _next_id(self) -> int:
        self._request_id += 1
        return self._request_id

    def _send_request(self, method: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        """Send a JSON-RPC request and return the response.

        Args:
            method: JSON-RPC method name (e.g. ``"tools/list"``).
            params: Parameters dict.

        Returns:
            Response ``result`` dict, or raises on error.
        """
        if self._process is None or self._process.stdin is None or self._process.stdout is None:
            raise RuntimeError("MCP server not started")

        request = {
            "jsonrpc": "2.0",
            "id": self._next_id(),
            "method": method,
            "params": params or {},
        }
        request_line = json.dumps(request, ensure_ascii=False)
        logger.debug("MCP request: %s", request_line[:200])

        # Write request to stdin
        self._process.stdin.write(request_line + "\n")
        self._process.stdin.flush()

        # Read response from stdout (one line per response)
        response_line = self._process.stdout.readline()
        if not response_line:
            # Read stderr for clues
            stderr_output = ""
            if self._process.stderr:
                stderr_output = self._process.stderr.read()
            raise RuntimeError(
                f"MCP server closed stdout. "
                f"stderr: {stderr_output[:500] if stderr_output else '(empty)'}"
            )

        logger.debug("MCP response: %s", response_line[:200])
        response = json.loads(response_line)

        if "error" in response:
            err = response["error"]
            raise RuntimeError(f"MCP error {err.get('code', '?')}: {err.get('message', '?')}")

        return response.get("result", {})

    # ------------------------------------------------------------------
    # MCP protocol methods
    # ------------------------------------------------------------------

    def list_tools(self) -> list[dict[str, Any]]:
        """Call ``tools/list`` and return the list of tool definitions.

        Returns:
            List of tool dicts, each with ``name``, ``description``,
            and ``inputSchema``.
        """
        result = self._send_request("tools/list")
        return result.get("tools", [])

    def call_tool(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        """Call ``tools/call`` and return the result.

        Args:
            name: Tool name.
            arguments: Tool arguments dict.

        Returns:
            Tool result dict with ``content``, ``isError``, etc.
        """
        return self._send_request("tools/call", {"name": name, "arguments": arguments})


# ---------------------------------------------------------------------------
# Tool-to-server mapping (populated by get_mcp_tools)
# ---------------------------------------------------------------------------

_mcp_tool_to_server: dict[str, str] = {}
"""Maps MCP tool name → server label for dispatch in ``_execute_tool``."""


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def _mcp_tool_to_function_schema(mcp_tool: dict[str, Any]) -> dict[str, Any]:
    """Convert an MCP tool definition to a function-call schema.

    MCP tools come as ``{"name", "description", "inputSchema"}``.
    We convert to the OpenAI/Groq/Ollama function format:
    ``{"type": "function", "function": {"name", "description", "parameters"}}``.

    Args:
        mcp_tool: MCP tool definition.

    Returns:
        Function schema ready for the tools registry.
    """
    return {
        "type": "function",
        "function": {
            "name": mcp_tool["name"],
            "description": mcp_tool.get("description", ""),
            "parameters": mcp_tool.get("inputSchema", {"type": "object", "properties": {}}),
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


def _mcp_tool_to_groq_entry(mcp_tool: dict[str, Any], server: McpServerConfig) -> dict[str, Any]:
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

    Connects to each stdio-based MCP server, calls ``tools/list``,
    and wraps the results as ``"type": "function"`` schemas compatible
    with Ollama (and Groq for local tools).

    Returns:
        List of function schemas ready for ``tools_registry``.
    """
    global _mcp_tool_to_server
    servers = load_mcp_config()
    function_tools: list[dict[str, Any]] = []

    for server in servers:
        label = server.get("label", "unknown")
        try:
            conn = McpConnection(server)
            conn.start()
            try:
                mcp_tools = conn.list_tools()
                logger.info("MCP '%s' — discovered %d tool(s)", label, len(mcp_tools))
                for tool in mcp_tools:
                    function_tools.append(_mcp_tool_to_function_schema(tool))
                    _mcp_tool_to_server[tool["name"]] = label
            finally:
                conn.stop()
        except Exception as exc:
            log_error(str(exc), source="mcp_helper.py:get_mcp_tools")
            logger.warning("MCP '%s' — failed to discover tools: %s", label, exc)

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
        raise ValueError(f"MCP server '{label}' (for tool '{tool_name}') not found in config")

    conn = McpConnection(config)
    conn.start()
    try:
        result = conn.call_tool(tool_name, arguments)
        return result.get("content", [])
    finally:
        conn.stop()


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
        label: Server label from config.json.
        timeout: Connection timeout in seconds.

    Returns:
        Status dict with keys: label, status, tools_count, tools, error.
    """
    mcp_config = get_mcp_config()
    servers = mcp_config.get("servers", {})
    config = servers.get(label)
    if not config:
        return {
            "label": label,
            "status": McpServerStatus.FAILED,
            "error": f"Server '{label}' not found in config",
        }

    config_with_label = dict(config)
    config_with_label["label"] = label

    if config_with_label.get("disabled"):
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


async def _check_stdio_server_health(config: McpServerConfig, timeout: float) -> dict[str, Any]:
    """Check health of a stdio-based MCP server."""
    label = config.get("label", "unknown")
    conn = McpConnection(config)
    try:
        conn.start()
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
    finally:
        conn.stop()


async def _check_http_server_health(config: McpServerConfig, timeout: float) -> dict[str, Any]:
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
    mcp_config = get_mcp_config()
    servers = mcp_config.get("servers", {})
    results = []

    for label in servers.keys():
        result = await check_mcp_server_health(label, timeout)
        results.append(result)

    return results